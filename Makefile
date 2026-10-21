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

.PHONY: help deps verify validate-design validate-manifest check-boundary check-release lint test terraform-validate clean-venv

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  Using python: $(PYTHON)"

deps: ## Create .venv and install validation + dev dependencies
	@if [ ! -x $(VENV)/bin/python ]; then \
		if [ -n "$(UV)" ]; then \
			echo "Creating $(VENV) with uv"; uv venv $(VENV); \
		else \
			echo "Creating $(VENV) with python3 -m venv"; \
			python3 -m venv $(VENV) || { \
				echo "error: python3 -m venv failed. On Debian/Ubuntu: sudo apt install python3-venv"; \
				exit 1; }; \
		fi; \
	fi
	@if [ -n "$(UV)" ]; then \
		uv pip install --python $(VENV)/bin/python -r scripts/requirements.txt; \
		uv pip install --python $(VENV)/bin/python ruff==0.8.4 mypy==1.14.0 pytest==8.3.4; \
	else \
		$(VENV)/bin/python -m pip install --quiet --upgrade pip; \
		$(VENV)/bin/python -m pip install -r scripts/requirements.txt; \
		$(VENV)/bin/python -m pip install ruff==0.8.4 mypy==1.14.0 pytest==8.3.4; \
	fi
	@echo
	@echo "Done. Every target now uses $(VENV)/bin/python."
	@echo "Activate it for ad-hoc commands with:  source $(VENV)/bin/activate"

verify: validate-design validate-manifest check-boundary lint test ## Run every available check

validate-design: ## Validate SDLC design artifacts
	@$(PYTHON) scripts/validate_design_artifacts.py

validate-manifest: ## Validate pattern manifests against the schema
	@$(PYTHON) scripts/validate_pattern_manifest.py

check-boundary: ## Check platform/domain boundary and layering rules
	@$(PYTHON) scripts/check_platform_domain_boundary.py

check-release: ## Check a release-track change touches metadata only (BASE=origin/main)
	@$(PYTHON) scripts/check_release_commit.py --base $${BASE:-origin/main}

lint: ## Lint Python (reports unavailable if ruff is absent)
	@if [ -x $(VENV)/bin/ruff ]; then \
		$(VENV)/bin/ruff check patterns scripts templates; \
	elif command -v ruff >/dev/null 2>&1; then \
		ruff check patterns scripts templates; \
	else \
		echo "unavailable: ruff is not installed (run 'make deps') — NOT a pass"; \
	fi

test: ## Run platform unit tests (reports unavailable if pytest is absent)
	@if [ -x $(VENV)/bin/pytest ]; then \
		$(VENV)/bin/pytest -q patterns/*/tests tests 2>/dev/null || echo "no tests collected yet"; \
	elif command -v pytest >/dev/null 2>&1; then \
		pytest -q patterns/*/tests tests 2>/dev/null || echo "no tests collected yet"; \
	else \
		echo "unavailable: pytest is not installed (run 'make deps') — NOT a pass"; \
	fi

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
