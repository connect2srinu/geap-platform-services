# Worked example — from nothing to a domain in production

One pass through the whole flow with a deliberately small first feature, so the process is visible
rather than buried in the work. Four acts:

1. **Platform team** designs, builds and publishes `memory-manager` **v0.1.0**
2. **Customer domain** adopts it, deploys it, and tests it
3. **An agent team** integrates with Customer's deployment
4. **v0.2.0** adds LLM extraction; Customer upgrades, Inventory starts fresh

Commands shown as `/name` are Claude Code skills. Everything else is a shell command a human runs.
For the exact command sequence to run this yourself, see the [CLI runbook](cli-runbook.md).

> **The first increment is deliberately thin:** `remember` with a fact the agent already extracted,
> one guardrail gate, a Memory Bank write, and `recall` to prove it. LLM extraction waits for v0.2.0.
> A first release that is small is a first release that actually ships.

---

# Act 1 — Platform team: design, build, publish

## Stage 1 — Intent (Gate A)

```
/design-start-feature
```

Classifies the change (full track: new contract, new managed service, security-relevant), reads the
standards and the existing pattern, and writes:

| File | State |
|---|---|
| `design/001-memory-manager/intent.md` | `status: draft` |

**The skill stops.** A human reviews scope, non-goals and acceptance criteria, then edits the front
matter:

```yaml
status: approved
approved_by: <a human>
approved_date: 2026-10-22
```

**Only after that approval** does the branch and draft PR get created:

```bash
git checkout -b design/001-memory-manager && git push -u origin design/001-memory-manager
```

Gate A is also the branch gate — no remote branch before approval.

## Stage 2 — Design (Gate B)

```
/design-session
```

Refuses to run if `intent.md` is not approved. Produces `design.md` with the architecture, the
`remember`/`recall` contract, where the guardrail gate sits, the extension-point table, failure
handling, and **ADR-0004 proposed, not written**.

→ **Gate B.** A human approves. Still no implementation code.

## Stage 3 — Controls (Gate C)

```
/design-check-controls
```

Assesses all 19 controls. At design stage most come back **`Implemented, not verified`** — that is the
correct answer, not a failure. `C-14` (provenance) is `Verified` because `release.yml` exists.

→ **Gate C.** A security reviewer approves. CI fails an approved assessment with an unexplained `Gap`.

## Stage 4a — Plan (Gate D)

```
/design-plan-implementation
```

Writes `tasks.md`. For this increment, roughly:

| Task | Objective | Owns |
|---|---|---|
| T-01 | OpenAPI spec + error catalogue | `contracts/` |
| T-02 | Configuration schema + example | `config/` |
| T-03 | `pii-classifier` interface + deny-all default | `extensions/pii_classifier.py` |
| T-04 | `policy-provider` interface + deny-all default | `extensions/policy_provider.py` |
| T-05 | Memory Bank provider adapter + fake client | `src/providers/` |
| T-06 | The guardrail gate | `src/policy/` |
| T-07 | `remember` and `recall` endpoints | `src/api/` |
| T-08 | Conformance suite | `conformance/` |

No two tasks own the same file, so they can be split across people or agents.

→ **Gate D.** A human approves. **Now** implementation may begin.

## Stage 4b — Implement

One task at a time, tests in the same commit:

```bash
make verify
```

Along the way:

- `/design-record-decision` writes **ADR-0004** once the decision is approved.
- `/design-check-controls --recheck` — implementation changed the security posture, so controls are
  reassessed. Several move from `Implemented, not verified` to `Verified` as their tests land.
- `tasks.md` statuses update as work progresses; deviations go in the deviations table.

If something forces a material architecture change, **stop and return to Stage 2.** Do not improvise.

## Stage 5 — Review (Gate E)

```
/design-open-pr
```

Diffs the implementation against `design.md`, verifies task completion, runs the checks, and reports
each as `passed` / `failed` / `skipped` / `unavailable`. Marks the PR ready **only** when conditions
hold; otherwise it leaves a draft and a blocker list.

→ **Gate E.** A human reviews. CODEOWNERS routes `contracts/` to the architects and
`controls-check.md` to security.

## Stage 6 — Close (Gate F)

```
/design-close-feature
```

Writes `closeout.md`, re-runs the checks (it does not copy Stage 5's results), updates the changelog
and architecture docs, and reports merge readiness.

→ **Gate F.** A human merges, squashed. **No skill merges.**

## Release v0.1.0

```
/pattern-validate
```

Then a **release-track** PR — metadata and notes only:

| File | Change |
|---|---|
| `patterns/memory-manager/pattern.yaml` | `version: 0.1.0`; `status: proposed` → `alpha` |
| `patterns/memory-manager/CHANGELOG.md` | `[Unreleased]` → `[0.1.0] — 2026-xx-xx` |
| `docs/releases/memory-manager-v0.1.0.md` | From `_template.md`, **including the live-verification statement** |
| `README.md` | The patterns table |

`scripts/check_release_commit.py` fails this PR if it touches `src/` or `contracts/`. The release
track skips Gates A–D; it keeps **E and F**.

```
/pattern-publish
```

Produces the readiness checklist and the exact commands — it publishes nothing. A human then runs:

```bash
git tag memory-manager/v0.1.0 && git push origin memory-manager/v0.1.0
```

Dispatch `release.yml` with **`dry_run: true`** first — it validates, builds the tarball, writes
`SHA256SUMS` and attests provenance, without creating a Release. Then dispatch with
`dry_run: false`; the `release` environment's required reviewers are the second human gate.

**Published:** tarball, `pattern.yaml`, `SHA256SUMS`, provenance, conformance suite.

---

# Act 2 — Customer domain: adopt, deploy, test

## 1. Generate the project

```
/domain-onboard
```

Produces `customer-memory-manager` — **their own repository, not a fork of ours**. A fork would carry
every pattern, all the standards and the whole SDLC machinery, and would turn each upgrade into a
monorepo merge.

```
customer-memory-manager/
├── pattern.lock.yaml        name + version 0.1.0 + manifest digest
├── vendor/pattern/          memory-manager v0.1.0, untouched
├── config/domain-config.yaml
├── extensions/              their implementations
├── Dockerfile               theirs
├── .github/workflows/       theirs
├── infrastructure/terraform/ theirs
└── docs/{runbook,agent-api,role-request,upgrade}.md
```

## 2. Configure and extend

`domain-config.yaml`: roles (`writer-agent`, `reader-agent`), sensitive and restricted attributes, the
category vocabulary.

`extensions/pii_classifier.py`: **required**, and it ships fail-closed. Until they implement it, the
service stores nothing. That is deliberate — an unconfigured deployment that stores everything is the
failure mode worth preventing.

## 3. The ordering that catches everyone

The memory bank IAM binding is **platform-owned**, and it binds *their* service accounts — which do
not exist until they apply Terraform. So:

```bash
terraform -chdir=infrastructure/terraform apply        # creates the service accounts
terraform -chdir=infrastructure/terraform output api_service_account
terraform -chdir=infrastructure/terraform output worker_service_account
```

They send those two emails to the platform team, **and agree a `max_writes_per_minute` allocation** —
the project's Memory Bank quota is shared across every domain, so their share is negotiated, not
chosen. The platform team then applies the NFR module: the bank, the IAM binding with scope
conditions, the audit sink, quota alerting.

**Until that binding exists, `/readyz` fails and conformance cannot pass.** This is not a bug; it is
the enforcement seam doing its job. Plan for two Terraform passes.

## 4. Build, scan, deploy

Their pipeline: lint → tests → **conformance** → build → scan → push → deploy → smoke test. The
conformance job fails the build if it collects zero tests, so an empty suite cannot masquerade as a
pass.

```bash
pytest -q vendor/pattern/conformance/
```

```bash
python3 scripts/verify_pattern_lock.py
```

The second one fails if the vendored pattern has been edited locally.

## 5. Validate

Functional smoke test · a read-only role cannot write · another domain's scope is unreachable · audit
events arrive at the sink · `quota_consumed` is labelled per domain · **no memory content or PII in
logs**.

---

# Act 3 — An agent team integrates

They talk to **Customer**, not to the platform team.

1. Read Customer's `docs/agent-api.md`.
2. Request a role via `docs/role-request.md`, stating purpose, categories and **expected volume** —
   volume may force a quota renegotiation before the role is granted.
3. Customer adds the binding to `domain-config.yaml` and deploys.
4. The agent calls:

```
POST /v1/memories     Idempotency-Key: <stable per logical write>     → 202
GET  /v1/memories                                                     → the value
```

`202` means **durably enqueued**, not applied — a read immediately after may not show it. `503` means
the write was not accepted; retry. Keep the correlation ID from every response.

The same agent works against Inventory's deployment later, because the tool API is identical across
domains. That is the whole reason `contracts/` is locked down.

---

# Act 4 — v0.2.0, and a second domain

## Platform: add extraction

Full track again — it is a contract change. `extraction_mode: none | server`,
`model_provider: gemini | litellm`, the input guardrail gate, and the platform-controlled endpoint
allowlist. New ADR for the model-provider decision. Release as **v0.2.0** (minor: additive, with
`none` remaining the default).

`spec.upgrade.from: ["0.1.0"]`, with migration guidance.

## Customer: upgrade

```
/pattern-upgrade
```

Produces the migration plan — contract diffs, configuration changes, security changes, regression
tests, rollback, and **the ordering**: if platform-owned infrastructure changed, the platform applies
first. Then re-vendor, update the lock, run the new conformance suite, deploy, smoke test.

## Inventory: start fresh

```
/domain-onboard
```

At v0.2.0. **No migration** — they have nothing to migrate from. Their own repository, their own
image, their own extensions, a second bank in the same platform project, and their own quota
allocation carved out of the same shared pool.

This asymmetry is the point: Inventory's onboarding is easy; Customer's upgrade is the hard case, and
it is what `spec.upgrade.from` and the migration guidance exist for.

---

# What stops, and who unblocks it

| Gate | Waits on | Mechanism |
|---|---|---|
| A, B, C, D | A human editing front matter | Honour system, checked by CI for *form* only |
| E | A human reviewing the PR | **GitHub required reviews + CODEOWNERS** |
| F | A human merging, tagging, dispatching | Denied to skills in `.claude/settings.json` |
| Release publish | `release` environment reviewers | GitHub environment |

**Gates A–D are the weakest link and it is worth being honest about it.** CI can verify that
`design.md` exists, is well-formed, and is not marked approved by an AI. It cannot verify that a human
read it. Only Gate E has real teeth, and only once an administrator has configured branch protection —
see [repository administration](../operations/repository-administration.md).

# What the platform cannot see

Once Customer has the code, the conformance suite, the boundary checks and the lock verification all
run in **their** CI. If they remove those jobs, nothing outside their team notices. The platform-owned
bank IAM, audit sink and quota alerting survive regardless, because they live outside the application.

So: the platform controls **what a domain's service account may do to a bank**. It does not control
what the domain's code does before it gets there. See
[the pattern contract](../../standards/pattern-contract.md).
