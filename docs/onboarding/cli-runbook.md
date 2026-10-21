# CLI runbook — running the full flow by hand

Every command to take `memory-manager` from an empty design folder to a second domain in production,
driven from `claude` in a terminal. The narrative version is the
[worked example](worked-example.md); this is the command sequence.

For the keystroke-level sequence with session boundaries marked, see the
[session script](cli-session-script.md). For the first real feature, the feature-specific overlay is
[implementing 001 — Memory Manager](../operations/implementing-001-memory-manager.md).

Conventions: `$` lines are shell. Lines beginning `/` are typed **inside** an interactive `claude`
session. `<angle brackets>` are placeholders.

---

# Phase 0 — once, before anything else

## 0.1 Validation dependencies

```bash
make deps
```

> On Debian, Ubuntu and WSL the system Python is **externally managed** (PEP 668) and refuses a
> bare `pip install`. `make deps` creates a project `.venv` and installs into it — do not pass
> `--break-system-packages`.

`make deps` installs the validators plus `ruff`, `mypy` and `pytest`, so `make verify` runs every
check instead of reporting `lint` and `test` as **unavailable** — which is not a pass.

## 0.2 First commit

The repository has no commits yet, so nothing below involving `git` or `gh` works until this is done.

```bash
git -C /home/sgadire1/projects/geap/geap-platform-services add -A
```

```bash
git -C /home/sgadire1/projects/geap/geap-platform-services commit -m "Establish platform foundation: SDLC, skills, standards, validators"
```

## 0.3 Remote

```bash
gh repo create geap-platform-services --private --source=. --remote=origin --push
```

Use `--internal` instead of `--private` if the account is in an organization and other teams need
read access.

## 0.4 CODEOWNERS teams

`.github/CODEOWNERS` ships with `@<org>/...` placeholders. **A CODEOWNERS file naming teams that do
not exist silently matches nobody**, and looks identical to a configured repository until the first
unreviewed merge.

Replace `<org>` and the four team names, then verify:

```bash
gh api repos/:owner/:repo/codeowners/errors
```

An empty `errors` array is what you want. On a personal account, teams do not exist at all — see 0.5.

## 0.5 Branch protection — the only gate with real teeth

Until this is configured, Gates A–F are honour-system: a PR can be merged with no review, no design
and no passing checks.

```bash
cat > /tmp/protection.json <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Validate SDLC design artifacts",
      "Manifest and boundary",
      "Lint and format",
      "Unit tests",
      "Dependency vulnerabilities",
      "Secret scanning",
      "Format and validate"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
gh api -X PUT repos/:owner/:repo/branches/main/protection --input /tmp/protection.json
```

GitHub cannot require a status check it has never seen, so run this **after** the first PR has run CI
once. Verify:

```bash
gh api repos/:owner/:repo/branches/main/protection --jq '.required_pull_request_reviews'
```

> **On a personal account**, `require_code_owner_reviews` and team-based ownership do not work, and
> you cannot approve your own PR. Either move the repository to an organization, or accept that
> Gate E is self-review and record that as a known limitation. Do not describe it as enforced.

Remaining manual settings — secret scanning, push protection, Dependabot, the `release` environment
with required reviewers, and `*/v*` tag protection — are in
[repository administration](../operations/repository-administration.md).

---

# Phase 1 — Platform team builds v0.1.0

## Stage 1 — Intent (Gate A)

```bash
cd /home/sgadire1/projects/geap/geap-platform-services && claude
```

```
/sdlc-status
/design-start-feature
```

Describe the increment when asked. For the thin first release: *`remember` with a fact the agent has
already extracted, one guardrail gate, the Memory Bank write, and `recall` to verify. No LLM
extraction.*

The skill writes `design/001-memory-manager/intent.md` with `status: draft` and **stops**.

Review it, then **edit the front matter by hand**:

```yaml
---
artifact: intent
feature: 001-memory-manager
track: full
status: approved
approved_by: <your name>
approved_date: 2026-10-22
---
```

> Edit this by hand rather than scripting it. A scripted approval is not an approval — it is the
> one step in the whole flow whose entire value is that a person read the document.

```bash
python3 scripts/validate_design_artifacts.py design/001-memory-manager
```

Now, and only now, the branch and draft PR:

```bash
git checkout -b design/001-memory-manager
```

```bash
git add -A && git commit -m "001: intent for Memory Manager v0.1.0" && git push -u origin design/001-memory-manager
```

```bash
gh pr create --draft --title "001: Memory Manager — remember, guardrail, recall" --body "Design folder: design/001-memory-manager/. Gate A approved; design in progress."
```

## Stage 2 — Design (Gate B)

```
/design-session
```

Refuses to run unless `intent.md` is approved. Produces `design.md` with the architecture, the
contract, the guardrail placement, failure handling, and **proposed** ADRs.

Approve by hand (`status: approved`, `approved_by`, `approved_date`), then:

```bash
python3 scripts/validate_design_artifacts.py design/001-memory-manager
```

```bash
git add -A && git commit -m "001: design approved" && git push
```

## Stage 3 — Controls (Gate C)

```
/design-check-controls
```

Most controls will read `Implemented, not verified` at this stage. That is correct, not a failure.

A **security reviewer** — ideally not the author — approves. Then commit and push as above.

## Stage 4a — Plan (Gate D)

```
/design-plan-implementation
```

Approve `tasks.md` by hand. **No implementation code before this point.**

## Stage 4b — Implement

Work one task at a time. Per task:

```
implement T-01 from design/001-memory-manager/tasks.md
```

```bash
make verify
```

```bash
git add -A && git commit -m "001: T-01 OpenAPI contract and error catalogue" && git push
```

When an architectural decision is approved along the way:

```
/design-record-decision
```

Once implementation has changed the security posture:

```
/design-check-controls --recheck
```

## Stage 5 — Review (Gate E)

```
/design-open-pr
```

It runs the checks, reports each as passed / failed / skipped / unavailable, and marks the PR ready
only if the conditions hold.

An independent review in a fresh context finds more than the session that wrote the code:

```bash
claude -p "/code-review high"
```

```bash
gh pr checks --watch
```

Then a **human** approves in GitHub. Claude never approves.

## Stage 6 — Close (Gate F)

```
/design-close-feature
```

Then, after reading the closeout:

```bash
gh pr merge --squash --delete-branch
```

---

# Phase 2 — Release v0.1.0

```bash
git checkout main && git pull
```

```
/pattern-validate
```

```bash
git checkout -b release/memory-manager-v0.1.0
```

Edit, by hand, only these:

| File | Change |
|---|---|
| `patterns/memory-manager/pattern.yaml` | `version: 0.1.0`; `status: proposed` → `alpha` |
| `patterns/memory-manager/CHANGELOG.md` | `[Unreleased]` → `## [0.1.0] — 2026-xx-xx` |
| `docs/releases/memory-manager-v0.1.0.md` | Copy `_template.md`; **state the live-verification status** |
| `README.md` | The patterns table |

```bash
python3 scripts/check_release_commit.py --base origin/main
```

This fails if the release touches `src/` or `contracts/`. Then:

```bash
git add -A && git commit -m "release: memory-manager v0.1.0" && git push -u origin release/memory-manager-v0.1.0
```

```bash
gh pr create --title "release: memory-manager v0.1.0" --body "Release track. Metadata and notes only."
```

```
/pattern-publish
```

It produces the readiness checklist and publishes nothing. After Gate E and merge:

```bash
git checkout main && git pull
```

```bash
git tag memory-manager/v0.1.0 && git push origin memory-manager/v0.1.0
```

**Dry run first** — it validates, builds the tarball and attests provenance without creating a
Release:

```bash
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=true
```

```bash
gh run watch
```

Only when that is green:

```bash
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=false
```

```bash
gh release view memory-manager/v0.1.0
```

---

# Phase 3 — Customer domain adopts

## 3.1 Generate the project

From the platform repository:

```
/domain-onboard
```

Answer: pattern `memory-manager`, version `0.1.0`, domain `customer`, the target project and region.
It writes a **separate project directory** — not a fork.

```bash
cd ../customer-memory-manager && git init -b main && git add -A && git commit -m "Adopt memory-manager v0.1.0"
```

```bash
gh repo create customer-memory-manager --private --source=. --remote=origin --push
```

## 3.2 Vendor, configure, extend

```bash
python3 scripts/vendor_pattern.py
```

```bash
python3 scripts/verify_pattern_lock.py
```

Then fill in `config/domain-config.yaml` and implement `extensions/pii_classifier.py`. Until the
classifier is implemented it denies everything and the service stores nothing — by design.

## 3.3 Two-pass infrastructure

The bank IAM binding is platform-owned but binds *your* service accounts, which do not exist yet.

**Pass 1 — the domain:**

```bash
terraform -chdir=infrastructure/terraform init
```

```bash
terraform -chdir=infrastructure/terraform apply
```

```bash
terraform -chdir=infrastructure/terraform output api_service_account
terraform -chdir=infrastructure/terraform output worker_service_account
```

Send both emails to the platform team and agree `max_writes_per_minute` — the project's Memory Bank
quota is shared across every domain, so your share is negotiated, not chosen.

**Pass 2 — the platform team** applies the NFR module: the bank, the scoped IAM binding, the audit
sink, quota alerting.

Until that lands, `/readyz` fails and conformance cannot pass. Expect it.

## 3.4 Build, scan, deploy, verify

```bash
docker build -t <region>-docker.pkg.dev/<project>/<repo>/memory-manager:$(git rev-parse --short HEAD) .
```

```bash
docker scout cves <region>-docker.pkg.dev/<project>/<repo>/memory-manager:$(git rev-parse --short HEAD)
```

```bash
pytest -q vendor/pattern/conformance/
```

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" "<service-url>/readyz"
```

A write and a read back:

```bash
curl -s -X POST "<service-url>/v1/memories" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"fact":{"attribute":"example_preference","value":"example"},"extraction_mode":"none"}'
```

Expect **`202`**. Then:

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" "<service-url>/v1/memories?attribute=example_preference"
```

Confirm no memory content reached the logs:

```bash
gcloud logging read 'resource.type="cloud_run_revision"' --limit 50 --format='value(textPayload)' | grep -i "example" || echo "clean — no payload in logs"
```

---

# Phase 4 — An agent team integrates

The agent team talks to **Customer**, not to the platform team.

1. Read Customer's `docs/agent-api.md`.
2. Submit `docs/role-request.md` — purpose, categories, and **expected volume** (volume may force a
   quota renegotiation before the role is granted).
3. Customer adds the binding and deploys.
4. Call `POST /v1/memories` with an `Idempotency-Key`; expect `202`. `503` means not accepted — retry.
   Keep the correlation ID from every response.

---

# Phase 5 — v0.2.0 and a second domain

**Platform:** Phase 1 again for the extraction modes (full track — it is a contract change), then
Phase 2 with `version: 0.2.0` and `spec.upgrade.from: ["0.1.0"]`.

**Customer upgrades:**

```
/pattern-upgrade
```

Read the migration plan, re-vendor, update `pattern.lock.yaml`, run the new conformance suite, deploy,
smoke test.

**Inventory starts fresh:** Phase 3 at v0.2.0. No migration — nothing to migrate from.

---

# Quick reference

| Need | Command |
|---|---|
| Where am I? | `/sdlc-status` |
| Validate design artifacts | `python3 scripts/validate_design_artifacts.py` |
| Validate a manifest | `python3 scripts/validate_pattern_manifest.py` |
| Check a release commit | `python3 scripts/check_release_commit.py --base origin/main` |
| Everything available | `make verify` |
| Independent review | `claude -p "/code-review high"` |
| Resume the last session | `claude -c` |

## Things that will bite

| Symptom | Cause |
|---|---|
| A skill refuses to run | An upstream gate is not approved. Run `/sdlc-status`. |
| `make verify` says `unavailable` | `ruff`/`pytest` not installed. Unavailable is **not** a pass. |
| Release PR fails CI | It touches `src/` or `contracts/`. That is a feature, not a release. |
| `release.yml` refuses | Status still `proposed`, empty conformance suite, or no release notes. |
| `/readyz` fails after deploy | The platform-owned bank IAM binding does not exist yet (3.3). |
| Conformance collects 0 tests | Reported as unavailable and fails the build. It is not a pass. |
| CODEOWNERS matches nobody | `@<org>/` placeholders, or a personal account with no teams. |
