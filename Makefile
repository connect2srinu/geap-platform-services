# GEAP Platform Services — validation entry points.
# Every target runs without Claude Code. Targets report unavailable tooling honestly
# rather than skipping silently.
#
# Dependencies install into a project virtual environment (.venv), because Debian and
# Ubuntu mark the system Python as externally managed (PEP 668) and refuse a bare
# `pip install`. Run `make deps` once.

VENV := .venv
# Resolved at startup: the project venv when it exists, otherwise the system Python
# (enough to run `make deps` and to print an honest message from everything else).
PYTHON := $(shell [ -x $(VENV)/bin/python ] && echo $(VENV)/bin/python || echo python3)
UV := $(shell command -v uv 2>/dev/null)
PYTHON_VERSION := 3.12

.PHONY: help deps verify validate-design validate-manifest check-boundary lint typecheck test terraform-validate clean-venv

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  Using python: $(PYTHON)"

# Python 3.12 is the standard (standards/coding.md) and what CI runs. A venv on another version
# gives local results that are not comparable to CI, so an older one is refused, not reused.
deps: ## Create .venv (Python 3.12) and install validation + dev dependencies
	@if [ -x $(VENV)/bin/python ] && ! $(VENV)/bin/python -c 'import sys; sys.exit(sys.version_info[:2] < (3, 12))'; then \
		echo "error: $(VENV) uses Python $$($(VENV)/bin/python -c 'import platform; print(platform.python_version())'); it must be $(PYTHON_VERSION) or newer, as CI is."; \
		echo "  Recreate it:  make clean-venv deps"; \
		exit 1; \
	fi
	@if [ ! -x $(VENV)/bin/python ]; then \
		if [ -n "$(UV)" ]; then \
			echo "Creating $(VENV) with uv, Python $(PYTHON_VERSION)"; \
			uv venv --python $(PYTHON_VERSION) $(VENV) || exit 1; \
		else \
			python3 -c 'import sys; sys.exit(sys.version_info[:2] < (3, 12))' || { \
				echo "error: python3 is $$(python3 -c 'import platform; print(platform.python_version())'); $(VENV) needs Python $(PYTHON_VERSION) or newer."; \
				echo "  Either install uv (https://docs.astral.sh/uv/) and re-run 'make deps' -- uv fetches $(PYTHON_VERSION) itself;"; \
				echo "  or install python$(PYTHON_VERSION) and run:  python$(PYTHON_VERSION) -m venv $(VENV) && make deps"; \
				exit 1; }; \
			echo "Creating $(VENV) with python3 -m venv"; \
			python3 -m venv $(VENV) || { \
				echo "error: python3 -m venv failed. On Debian/Ubuntu: sudo apt install python3-venv"; \
				exit 1; }; \
		fi; \
	fi
	@if [ -n "$(UV)" ]; then \
		uv pip install --python $(VENV)/bin/python -r scripts/requirements.txt; \
		uv pip install --python $(VENV)/bin/python ruff==0.8.4 mypy==1.14.0 pytest==8.3.4; \
		uv pip install --python $(VENV)/bin/python -e 'patterns/memory-manager[dev]'; \
	else \
		$(VENV)/bin/python -m pip install --quiet --upgrade pip; \
		$(VENV)/bin/python -m pip install -r scripts/requirements.txt; \
		$(VENV)/bin/python -m pip install ruff==0.8.4 mypy==1.14.0 pytest==8.3.4; \
		$(VENV)/bin/python -m pip install -e 'patterns/memory-manager[dev]'; \
	fi
	@echo
	@echo "Done. Every target now uses $(VENV)/bin/python."
	@echo "Activate it for ad-hoc commands with:  source $(VENV)/bin/activate"

verify: validate-design validate-manifest check-boundary lint typecheck test ## Run every available check

validate-design: ## Validate SDLC design artifacts
	@$(PYTHON) scripts/validate_design_artifacts.py

validate-manifest: ## Validate pattern manifests against the schema
	@$(PYTHON) scripts/validate_pattern_manifest.py

check-boundary: ## Check platform/domain boundary and layering rules
	@$(PYTHON) scripts/check_platform_domain_boundary.py

# Runs the same two checks as the Python CI lint job, so a local pass means a CI pass.
typecheck: ## Type-check pattern source (reports unavailable if mypy is absent)
	@if [ -x $(VENV)/bin/mypy ]; then mypy=$(VENV)/bin/mypy; \
	elif command -v mypy >/dev/null 2>&1; then mypy=mypy; \
	else echo "unavailable: mypy is not installed (run 'make deps') — NOT a pass"; exit 0; fi; \
	checked=0; \
	for pattern in patterns/*/; do \
	  find "$$pattern/src" -name '*.py' -print -quit 2>/dev/null | grep -q . || continue; \
	  mypy_abs=$$(cd $$(dirname $$mypy) 2>/dev/null && pwd)/$$(basename $$mypy); \
	  [ -x "$$mypy_abs" ] || mypy_abs=$$mypy; \
	  ( cd "$$pattern" && "$$mypy_abs" --strict src ) || exit 1; \
	  checked=$$((checked + 1)); \
	done; \
	if [ "$$checked" -eq 0 ]; then echo "No pattern source present yet — skipped, not passed."; fi

lint: ## Lint Python (reports unavailable if ruff is absent)
	@if [ -x $(VENV)/bin/ruff ]; then ruff=$(VENV)/bin/ruff; \
	elif command -v ruff >/dev/null 2>&1; then ruff=ruff; \
	else echo "unavailable: ruff is not installed (run 'make deps') — NOT a pass"; exit 0; fi; \
	$$ruff check patterns scripts templates && $$ruff format --check patterns scripts templates

# pytest exits 5 when it collects nothing: skipped, not passed. Any other failure must fail.
test: ## Run unit tests, plus the conformance suite against the reference implementation
	@if [ -x $(VENV)/bin/pytest ]; then pytest=$(VENV)/bin/pytest; \
	elif command -v pytest >/dev/null 2>&1; then pytest=pytest; \
	else echo "unavailable: pytest is not installed (run 'make deps') — NOT a pass"; exit 0; fi; \
	dirs=""; for d in patterns/*/tests patterns/*/conformance tests; do [ -d "$$d" ] && dirs="$$dirs $$d"; done; \
	if [ -z "$$dirs" ]; then echo "No test directories present yet — skipped, not passed."; exit 0; fi; \
	rc=0; $$pytest -q $$dirs || rc=$$?; \
	if [ $$rc -eq 5 ]; then echo "No tests collected yet — skipped, not passed."; exit 0; fi; \
	exit $$rc

terraform-validate: ## Validate Terraform (no backend, no apply)
	@if command -v terraform >/dev/null 2>&1; then \
		terraform fmt -check -recursive patterns templates || true; \
		for d in $$(find patterns templates -name '*.tf' -exec dirname {} \; | sort -u); do \
			echo "== $$d"; terraform -chdir=$$d init -backend=false -input=false >/dev/null && terraform -chdir=$$d validate; \
		done; \
	else \
		echo "unavailable: terraform is not installed — NOT a pass"; \
	fi

clean-venv: ## Remove the project virtual environment
	rm -rf $(VENV)
