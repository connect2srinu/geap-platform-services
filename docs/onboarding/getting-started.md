# Getting started — first-time setup

From a new laptop to a passing `make verify` and the service answering on `localhost`. Written for
macOS; the Linux differences are noted where they matter.

> **How this was checked.** The clone, `make deps`, `make verify` and the local run in step 6 were run
> on Linux on 2026-10-23: `351 passed`, every validator `PASSED`. The macOS install commands are the
> standard Homebrew ones and **have not yet been run on a Mac**. If a step differs there, fix this
> page in the same PR.

## 1. Install the tools

| Tool | Needed for | macOS |
|---|---|---|
| Xcode Command Line Tools | `git`, `make`, `curl` | `xcode-select --install` |
| [Homebrew](https://brew.sh) | installing the rest | see brew.sh |
| `uv` | Python 3.12 and the project environment | `brew install uv` |
| GitHub CLI | clone, PRs, CI status | `brew install gh` |
| Claude Code | the `/feature-start` workflow | [install guide](https://docs.claude.com/en/docs/claude-code/setup) |
| Terraform *(optional)* | `make terraform-validate` | `brew tap hashicorp/tap && brew install hashicorp/tap/terraform` |
| Google Cloud CLI *(optional)* | live checks against a real Memory Bank | `brew install --cask google-cloud-sdk` |

**Why `uv`.** The project needs Python 3.12 or newer, which is what CI runs. macOS ships an older
`python3` with the Command Line Tools, and `make deps` refuses it rather than build an environment
whose results differ from CI's. `uv` downloads 3.12 by itself. Without `uv`, run
`brew install python@3.12` and then `python3.12 -m venv .venv` before `make deps`.

Secret scanning (gitleaks), the dependency audit (pip-audit) and the IaC scan (Checkov) run only in
CI. You don't need them locally; the PR runs them.

## 2. Sign in to GitHub and clone

```bash
gh auth login
```

```bash
gh repo clone <owner>/geap-platform-services && cd geap-platform-services
```

The rest of this page runs from the repository root.

## 3. Create the environment

```bash
make deps
```

It creates `.venv` with Python 3.12 and installs the validators, the linters and the
`memory-manager` pattern in editable mode. It ends with:

```
Done. Every target now uses .venv/bin/python.
```

Never `pip install` into the system Python, and never use `--break-system-packages`.

## 4. Run every check

```bash
make verify
```

A healthy run ends like this:

```
PASSED  39 checks, 0 warning(s)      ← design documents
PASSED  32 checks, 0 warning(s)      ← pattern manifest
PASSED  4 checks, 0 warning(s)       ← platform/domain boundary
All checks passed!                   ← ruff
Success: no issues found in 27 source files   ← mypy
351 passed                           ← unit + conformance tests
```

The counts grow as the repository does. What matters is **no `FAILED` and no `unavailable`**.
`unavailable` means a tool was missing and that check **did not run**. It is not a pass.

`make help` lists every target. Two are separate: `make terraform-validate` (needs Terraform) and
`make rehearsal`, which adopts the pattern as a domain would, end to end. It is slow, and CI runs it
on every PR.

## 5. Open it in Claude Code

```bash
claude
```

The project's rules load from [CLAUDE.md](../../CLAUDE.md). `.claude/settings.json` allows the
read-only checks and blocks merging, `terraform apply`, image pushes and force-pushes. Three skills
are available: `/feature-start`, `/feature-review` and `/pattern-release`. How they fit together is
in [demo.md](demo.md).

## 6. Run the service locally (5 minutes)

This proves the setup end to end. It uses the in-memory fake Memory Bank, so it needs no cloud
access.

**a. A working directory outside the repository**, with demo extensions. The platform defaults
deny everything, so without extensions the service stores nothing. That is the fail-closed design
working, not a bug.

```bash
mkdir -p $HOME/mm-local/localdemo && touch $HOME/mm-local/localdemo/__init__.py
```

```bash
cat > $HOME/mm-local/localdemo/extensions.py <<'EOF'
"""Demo extensions for a local run. NOT a real classifier."""
import re

from memory_manager.extensions import ClassificationResult, PolicyDecision

BLOCKED = re.compile(r"\d+\s?mg|diagnos|prescri|atorvastatin", re.IGNORECASE)


class DemoClassifier:
    def classify(self, fact, caller):
        if BLOCKED.search(fact.text):
            return ClassificationResult(allowed=False, reason="DEMO_MEDICAL_TERM")
        return ClassificationResult(allowed=True)


class DemoPolicy:
    def decide(self, caller, operation, topic):
        return PolicyDecision(allowed=True)
EOF
```

**b. Configuration**, copied from the pattern's example, with the extensions pointed at the demo:

```bash
sed -e 's#extensions.pii.DomainClassifier#localdemo.extensions.DemoClassifier#' \
    -e 's#extensions.policy.DomainPolicyProvider#localdemo.extensions.DemoPolicy#' \
    patterns/memory-manager/config/example.domain.yaml > $HOME/mm-local/domain.yaml
```

**c. Start it.** `ENVIRONMENT=local` selects the fake bank and the header-based caller identity.
Both are refused in any other environment. `SUBJECT_HMAC_KEY` can be any string locally; deployed,
it comes from Secret Manager.

```bash
ENVIRONMENT=local CONFIG_PATH=$HOME/mm-local/domain.yaml SUBJECT_HMAC_KEY=local-only \
  PYTHONPATH=$HOME/mm-local .venv/bin/uvicorn memory_manager.asgi:create --factory --port 8080
```

**d. Call it** from a second terminal. `X-Agent-ID` names the calling agent (registered in the
config). `Authorization` carries the end user's token; locally the verifier takes the bearer value
as the end user, so any string works. Keep it in a variable — a real token does not belong in your
shell history:

```bash
export END_USER_TOKEN=end-user-1
```

```bash
curl -s localhost:8080/readyz
```

```bash
curl -s -X POST localhost:8080/v1/memories -H 'Content-Type: application/json' \
  -H 'X-Agent-ID: writer-agent' -H "Authorization: Bearer $END_USER_TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -d '{"facts":[{"topic":"preferred_brands","field":"brand","value":"Horizon","fact":"The user prefers the organic brand Horizon.","basis":"stated"}]}'
```

```
{"outcome":"written","stored":1,"results":[{"index":0,"topic":"preferred_brands","reasonCode":"ACCEPTED","memoryId":"fake-1"}]}
```

```bash
curl -s "localhost:8080/v1/memories?topic=preferred_brands" \
  -H 'X-Agent-ID: writer-agent' -H "Authorization: Bearer $END_USER_TOKEN"
```

You get the fact back. [demo.md, Act 3](demo.md#4-run-it-locally) has the full set of
client tests: blocked topics, prohibited content, and the log check — and conformance after it.

Stop the server with `Ctrl-C`. Delete `$HOME/mm-local` when you are done.

## 7. Google Cloud (only for live checks)

Unit tests, conformance and the local run need no cloud access. You need it only to run a spike
against a real Memory Bank.

```bash
gcloud auth login && gcloud auth application-default login
```

```bash
gcloud config set project <project-id>
```

The provider SDK is an optional extra, not installed by `make deps`:

```bash
uv pip install --python .venv/bin/python -e 'patterns/memory-manager[provider]'
```

Never commit a project ID, account or bank ID. Spikes print `<project>` in their place.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make deps`: `python3 is 3.9 …; .venv needs Python 3.12 or newer` | Install `uv` (`brew install uv`) and re-run `make deps` |
| `make deps`: `.venv uses Python 3.x; it must be 3.12 or newer` | `make clean-venv deps` |
| `xcrun: error: invalid active developer path` | `xcode-select --install` |
| `make verify` prints `unavailable: … is not installed` | `make deps` did not finish. Re-run it and read the first error |
| `uvicorn`: `address already in use` | Another process has port 8080: `lsof -i :8080`, or use `--port 8081` |
| The service exits with `ConfigurationError …` | The message names the field. Fix `$HOME/mm-local/domain.yaml` |
| An allowed fact returns `stored: 0` with `TOPIC_NOT_APPROVED` | The platform's deny-all defaults are in use: the demo extensions are not configured. Check the two `extensions:` lines in the config |
| The service exits with `could not be imported` | `PYTHONPATH` does not point at the directory that contains `localdemo/` |
| `gh` commands fail with 401 | `gh auth status`, then `gh auth login` |
| CI fails but `make verify` passed | Run `make terraform-validate`. The secret and IaC scans run only in CI, so read the job log |
