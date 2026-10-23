---
artifact: intent
feature: 000-platform-foundation
track: full
status: approved
approved_by: connect2srinu (project owner)
approved_date: 2026-10-20
related_adrs: [ADR-0001, ADR-0002, ADR-0003]
patterns_touched: [memory-manager]
---

# GEAP Platform Services — Foundation Assessment and Proposal

**Status:** Draft for review — Phase 1 (Discovery) and Phase 2 (Proposal). No repository files created or modified.
**Date:** 2026-10-20
**Target repository:** `<workspace>/geap-platform-services`
**Confirmed constraints from requester:** CI/CD via GitHub Actions; infrastructure via Terraform on Google Cloud.

Evidence labels used throughout, adopted from the prior repository's own convention:

| Label | Meaning |
|---|---|
| **VERIFIED** | Observed directly in this session (file read, command run). |
| **PROPOSED** | This document's recommendation. Not a decision. |
| **OPEN** | Requires a human decision before it can be built. |
| **ASSUMPTION** | Taken as true to make progress; recorded rather than hidden. |

---

# PHASE 1 — DISCOVERY AND ASSESSMENT

## 1.1 Current project state

**VERIFIED — the target directory is empty.**

```
<workspace>/geap-platform-services/   # 0 files, 0 subdirectories
```

- Not a git repository (`git rev-parse` → `fatal: not a git repository`).
- No remote, no `.github/`, no `.claude/`, no `CLAUDE.md`, no language toolchain files.
- Everything in the deliverables list is net-new.

**VERIFIED — toolchain available on this machine:**

| Tool | Version | Notes |
|---|---|---|
| git | 2.43.0 | Interactive rebase/add unavailable in this harness |
| gh | 2.45.0 | Authenticated as the maintainer's personal account; scopes `gist`, `read:org`, `repo`, `workflow` |
| terraform | 1.9.8 | `tofu` not installed |
| docker | 29.0.0 | |
| gcloud | 589.0.0 | the maintainer's personal account and sandbox project, region `us-central1` |
| python3 | 3.12.3 | |
| node / npm / pnpm | 22.16.0 | |
| uv | present | `poetry` absent |
| make, jq | present | |
| Claude Code | 2.1.284 | |

**VERIFIED — not installed:** `yq`, `pre-commit`, `ruff`, `mypy`, `pytest`, `tofu`, `poetry`.
Consequence: Python quality tooling must be project-local (`uv`-managed), and any validation script we
write must either be pure-Python/stdlib or declare its dependency explicitly. CI must install its own
toolchain and not assume a developer machine. Phase 4 validation of Python linting will be reported as
**unavailable** unless we provision a local `uv` environment first.

**VERIFIED — the `gh` token has `repo` and `workflow` scope but the account is a personal account,
not an enterprise org.** Branch protection, CODEOWNERS enforcement and required
reviews behave differently on personal repositories than on an organization with rulesets. This matters
for §2.7 and is an **OPEN** item (D8).

## 1.2 Existing conventions discovered

There is no code in the target repository, but there are three sibling projects under
the same workspace directory. One of them is directly load-bearing.

| Project | What it is | Relevance |
|---|---|---|
| `geap-memory` | **VERIFIED** — a built-out governed preference-memory control plane: FastAPI control-plane API (70 admin + 15 runtime routes), React 19 admin console, two ADK reference agents, PostgreSQL (26 tables, Alembic 0001–0009), Vertex Memory Bank adapter, Terraform, CI | **The primary architecture input.** Far more informative than a greenfield start. |
| `geap-plarform-poc-agent` | **VERIFIED** — a single ADK agent scaffolded by `agents-cli` (manifest, Dockerfile, `pyproject.toml`, `.claude/settings.json` with a 2-entry allowlist) | Shows the house shape of a *consumer* agent project. |
| `cloudrun-eval` | **VERIFIED** — two ADK agents with `deployment/` folders and eval artifacts | Shows the Cloud Run deployment habit. |

### Conventions worth inheriting (VERIFIED in `geap-memory`)

1. **Python 3.12 + FastAPI + Pydantic**, `ruff` for lint, `pytest` for tests, `uv.lock` for pinning,
   Alembic for migrations, per-app `pyproject.toml` with a `[dev]` extra.
2. **Terraform layout:** `infrastructure/terraform/modules/<module>/` + `environments/dev/` with
   `versions.tf`, `backend.tf.example`, `terraform.tfvars.example`, `.terraform.lock.hcl` committed.
   Google provider **7.45.0**, random 3.9.0. Resources in use: `google_cloud_run_v2_service`,
   `google_sql_database_instance`, `google_artifact_registry_repository`, `google_compute_network` /
   `subnetwork`, `google_service_networking_connection`, `google_project_service`, IAP service agent
   wiring, plus a `monitoring.tf`.
3. **Cloud Run posture:** `ingress = INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER`, dedicated per-service
   service accounts, `vpc_access` with `egress = PRIVATE_RANGES_ONLY`, Cloud SQL mounted as a volume,
   `cpu_idle = true`, min 1 / max 10 instances. This is a good secure default and should be the
   starting point for the reference deployment, not re-derived.
4. **Documentation discipline — the single best asset in the prior repo.** `docs/` uses explicit
   status labels (`CURRENT` / `TARGET` / `PROPOSED`) and an assumption register with
   `VALIDATED` / `PARTIAL` / `NOT VALIDATED` / `CONFLICT` / `BY DESIGN` / `OPEN QUESTION`. The
   reference-architecture document states its method ("derived by reading the code on branch X on
   date Y; every CURRENT statement is verifiable"). **PROPOSED: make this mandatory in
   `standards/architecture.md` and enforce the label vocabulary in the design-artifact validator.**
5. **Executable conformance precedent:** `scripts/validate_deployment_security.py` and a repo-level
   `tests/` directory holding *boundary* tests (e.g. a test that forbids provider-SDK imports in the
   reference agent). This is exactly the mechanism §2.8 needs for pattern conformance, and it already
   has a working precedent here.
6. **ADR naming:** `docs/adr/ADR-0001-<kebab-title>.md` with `Status`, `Date`, `Decision owners`,
   `Scope` header fields.

### Conventions worth *not* inheriting

- **A single monolithic CI job.** `platform-ci.yml` is one `validate` job running Python install, a
  security script, ruff, three pytest invocations, Alembic migration, a Postgres integration test,
  npm ci/build/test/audit, and four Terraform steps **in sequence**. One slow step blocks every
  signal. **PROPOSED: split into parallel jobs** so a required-check list can be meaningful and fast.
- **No dependency scanning, secret scanning, container scanning, or SBOM** in that workflow
  (`npm audit` only). The new SDLC lists all four as required.
- **A `packages/contracts/` directory that is a 6-line placeholder README.** Section 15 of the brief
  explicitly forbids placeholder assets. Either contracts are real artifacts validated by CI, or the
  directory does not exist.
- **No `CLAUDE.md`, no `.claude/`, no skills.** The AI-native SDLC is entirely net-new; there is no
  prior art in these repos to be consistent with.

## 1.3 Architecture input: the diagram

**VERIFIED — the diagram was inspected.** It was supplied as a screenshot of `E2E.drawio` rendered in
a Confluence/Atlassian page, not as a file in the repository. It is legible. I transcribe its
assertions below because the image is not a durable repository artifact and the brief requires the
limitation to be recorded.

> **Limitation recorded:** the authoritative `.drawio` source is not in the target repository. The
> transcription below is my reading of a screenshot and must be confirmed by the diagram's author
> before it is treated as a requirements baseline. Related `.drawio` files exist in
> `geap-memory/docs/` (`GEAP_Memory_Flows.drawio`, `geap-target-architecture.drawio`,
> `google-cloud-services-architecture.drawio`) but none was verified to be this diagram.

**Title:** `[Container] Domain Memory Manager` — "Every memory read and write goes through one
domain-owned tool. Scope: Customer domain · **Proposed**."

**Stated organising principle (from the diagram's own note):** *"Domain-driven. Agent teams build
agents. The Customer domain owns and hosts Memory Manager: RBAC, rate limits, privacy guardrails,
entity resolution, fact curation. The platform gives reference code and Memory Bank NFRs, never the
rules."*

| Element | Diagram text | Ownership |
|---|---|---|
| KSA agent | Flags turns that may hold a memory; recalls before answering | Agent team |
| Other agent | Same tools; role granted by the domain | Agent team |
| External agent | e.g. Cooklist — read-only role, granted by the domain | External |
| **Tool endpoints** | Component — OpenAPI (MCP later). `remember` returns **202**; `recall`, `list`, `correct`, `forget`; rate limit per caller | Customer domain |
| **Domain policy & RBAC** | Component — versioned config. Caller roles, privacy guardrails (sensitive and restricted lists), categories | Customer domain |
| **Memory worker** | Component — async. Extracts facts, strips PII, resolves entity refs to Kroger IDs, curates the same fact from two sources | Customer domain |
| **Retry queue** | Component — Data Store, Pub/Sub, internal. "Resilience only: over-limit or failed writes. Dead letter after N tries" | Customer domain |
| KSA Memory Bank | External Data Store — one per agent. Memories isolated by customer scope | Google (managed) |
| Other Memory Bank | External Data Store — per agent or entity. An agent may write one or more banks | Google (managed) |
| **Memory Manager reference code** | Container — GitHub. "Endpoints, worker, retry queue, bank client. **Domain fills policy, RBAC, prompts**" | Agent Platform team |
| **Memory Bank NFRs** | Container — platform capability (12-factor). "Per-agent bank provisioning (IaC) · IAM: only Memory Manager · audit logs to central sink · failure events · quota monitoring" — *"Wraps every Memory Bank: provisions, IAM, audit, alerts [Terraform, IAM, Cloud Logging]"* | Agent Platform team |

Flows shown: agent → tool endpoints (OpenAPI tool call); endpoints → policy/RBAC ("checks role, scope
and rate limit"); endpoints → worker ("hands over accepted writes"); endpoints → retry queue ("over
the rate limit, parks the write"); queue ⇄ worker ("replays with backoff" / "write failed: parks it");
worker → policy ("applies privacy rules"); worker → Memory Bank ("writes approved facts", *direct,
memory source*); agent → Memory Bank ("recall (sync), retrieve", dashed/optional).

### What the diagram tells us that the prior POC does not

**This is the most consequential finding of Phase 1.** The diagram is not a redraw of `geap-memory`.
It inverts the ownership model and it closes three specific gaps the POC's own assumption register
flags as unresolved:

| POC gap (VERIFIED, from `docs/memory-bank-assumption-validation.md`) | What the diagram adds |
|---|---|
| **MB-13** "Event ingestion is durably decoupled from the agent request" → *BY DESIGN / PARTIAL: written synchronously in the request; there is no outbox or retry layer* | `remember` → **202** + async worker + Pub/Sub retry queue with dead-lettering |
| **MB-15** "Provider quotas and costs are observable" → *NOT VALIDATED; provider 429 surfaces as HTTP 500* | Per-caller rate limiting at the endpoint, "over the rate limit → park the write", quota monitoring as a platform NFR |
| **MB-16** "Terraform deploys the complete managed memory resource" → *CONFLICT: Terraform deploys the app stack and takes an existing Agent Engine identifier* | "Per-agent bank provisioning (IaC)" as an explicit platform-owned NFR container |
| **MB-20** "One Memory Bank is right for every organization" → *OPEN QUESTION* | "one per agent" / "per agent or entity" — a tentative answer, still needs ratifying |

**ASSUMPTION (needs confirmation):** the diagram supersedes the `geap-memory` control-plane topology
for this pattern, rather than sitting alongside it. See decision **D1**.

## 1.4 The ownership-model inversion — read this before approving anything

`geap-memory` is a **centrally operated control plane**. The platform team hosts
`control-plane-api`, the admin console and PostgreSQL; agents hold no memory logic and call one
central service; the README's security boundary says *"Agents never call Memory Bank directly and
never make authorization decisions."*

The brief and the diagram require the **opposite shape**: the platform team *publishes a versioned
source pattern and reference implementation*; the **Customer domain owns, configures, builds, hosts
and operates** its own Memory Manager; the platform never operates the runtime.

These are different products, not different releases of one product. Specific consequences:

1. **Enforcement weakens, and the brief already anticipates this (§18).** In the central model,
   policy is enforced by a service the platform runs. In the published-pattern model, policy is
   enforced by code the *domain* builds, in a project the *domain* can edit. The platform's only
   real levers become: (a) the pattern conformance suite the domain is required to run in its own CI,
   (b) platform-owned Terraform for the Memory Bank NFR wrapper (IAM allowing only the Memory Manager
   service account, audit sink, alerts) which sits *outside* the domain's application code, and
   (c) supply-chain provenance on the published bundle. **A domain that forks the source can defeat
   (a) and (c) but not (b).** This must be stated plainly in `standards/pattern-contract.md`, not
   glossed.
2. **~7,700 lines of tested authorization, household, consent and resolution logic in `geap-memory`
   cannot be lifted wholesale** — much of it is Customer-domain business rule (households, health
   consent, grocery sensitivity categories), which §2 of the brief forbids in reusable platform code.
   What is reusable is the *shape*: the fail-closed decision order, the scope-key contract, the
   `MemoryStore` protocol seam, the audit spine.
3. **The diagram itself contains a domain rule inside a platform component.** "Memory worker …
   resolves entity refs to **Kroger IDs**" is Customer-domain identity resolution. In reusable
   pattern code this must be an **extension point with a no-op default**, not platform logic. Same
   for "strips PII" (the *classifier* is domain config; the *obligation to strip before persisting*
   is a platform control) and "curates the same fact from two sources" (domain merge policy).
4. **No real enterprise identifiers in reusable code or examples.** The diagram is sourced from an
   internal Atlassian page and names a real retailer and a real partner product. Pattern code,
   `pattern.yaml`, templates and examples will use neutral placeholders (`example-domain`,
   `acme-*`, `ENTITY_ID`); the diagram's names stay in the design narrative only.

## 1.4a Three stakeholders, two contracts — added 2026-10-20

The owner's clarification names **three** stakeholders, and the distinction between the second and
third is load-bearing in a way my first draft under-weighted:

| Stakeholder | Owns | Consumes |
|---|---|---|
| **Platform team** | Reusable patterns and templates, *including implementation code* (Memory API, Evaluation API), the pattern contract, conformance suites, reference infrastructure | — |
| **Domain owners** (e.g. Customer) | The adopted code, the memory *rules* (RBAC, policy, privacy categories, prompts), their build, their Cloud Run deployment, their operations | The platform's published pattern |
| **Agent teams** (e.g. KSA) | Their agents | **A domain's deployed Memory Manager** — via its tool API, with a role the domain grants |

### Consequence: there are two consumer-facing contracts, not one

1. **Platform → Domain — the *pattern contract*.** `pattern.yaml`, config schema, extension points,
   conformance suite, reference Terraform. Covered in §2.8.
2. **Domain → Agent team — the *tool API contract*.** `remember` / `recall` / `list` / `correct` /
   `forget`, the error catalogue, rate-limit semantics, the idempotency key, the RBAC role model.
   **This is the contract agent teams write code against.**

My first draft listed the OpenAPI contract under "must preserve" (§2.9) but understated *why*. The
reason is now explicit: contract #2 must be **identical across every domain**, or an agent team that
talks to the Customer domain cannot talk to the Inventory domain without a rewrite, and no agent is
portable. So the tool API surface is a **non-overridable platform artifact**: a domain configures
policy, roles, categories and prompts behind it, and must not fork the surface itself. Conformance
treats tool-API drift as a hard failure, and `patterns/*/contracts/**` gets the strictest CODEOWNERS
rule in the repository.

### Consequence: the agent-team tier currently has no artifact

`domain-onboard` scaffolds a domain project. Nothing yet tells an **agent team** how to discover a
domain's deployed Memory Manager, request a role, and call the tools. Prior art exists —
`geap-memory/docs/new-agent-onboarding.md` (VERIFIED, 111 lines).

**PROPOSED, deliberately small:** no new skill. Instead, `domain-onboard` additionally emits, into the
domain's own project, (a) agent-facing API documentation generated from the pattern's OpenAPI spec and
(b) a role-grant request template. Plus one platform-owned
`docs/onboarding/agent-team-guide.md` describing the generic integration shape. The domain publishes
its endpoint and grants roles; the platform never brokers that relationship.

### Consequence: the pattern factory is multi-pattern from day one

"Evaluation and Memory APIs" means `patterns/` holds **at least two** patterns, so the pattern
contract must not be memory-shaped. §2.8's manifest is already generic; Evaluation becomes the first
real test of that, and there is prior art for it in the `cloudrun-eval` sibling project and
`geap-memory/memory-test-results/` (both VERIFIED present). This strengthens **D12** (monorepo with
pattern-scoped tags) but does not by itself close it.

## 1.4b Single platform-owned project — consequences — added 2026-10-20

**Decided:** one GCP project, owned by the platform team, holds every domain's memory banks and
agents. One bank per domain, created as each domain onboards. Domain teams own and deploy their own
implementations *into that project*.

### What this buys

The enforcement story in §2.9 stops being aspirational. Isolation moves from *project boundaries* to
**per-domain service accounts plus IAM Conditions on bank scope** — which the prior art already
identified as available and unused (VERIFIED, MB-07: *"Memory Bank-specific roles and IAM Conditions
over scope values can back up the database grants as defense in depth. They are not configured yet"*).
The platform holds, and a domain cannot edit away: project IAM, the bank-level IAM binding, org
policy, the central audit sink, and quota alerting. Pattern 001's controls assessment should make
IAM Conditions a **required** control rather than the "still a gap" it is in the POC.

### What this costs — the risk that matters

**Memory Bank quota is enforced per-project, per-region** (VERIFIED, `docs/vertex-memory-bank.md`:
*"Memory Bank enforces per-project, per-region request quotas (read requests per minute are the usual
limit). Exceeding them returns `429 RESOURCE_EXHAUSTED`"*). One project therefore means **one shared
quota pool across every domain**. Separate banks do *not* give separate quota.

Three compounding factors:

1. **Writes consume read quota too.** VERIFIED: *"Each write first retrieves the scope's facts to
   compute the next counter, so writes also consume read quota."* Write-heavy load degrades reads.
2. **Agents also read directly.** The diagram shows an agent → Memory Bank `recall (sync)` path that
   bypasses the Memory Manager. Those reads consume the same pool and are **not** governed by the
   Memory Manager's rate limiter.
3. **Noisy neighbour is now a cross-domain, cross-team incident.** Customer's traffic can exhaust the
   pool and make Inventory's agents fail, with no project boundary to contain it and two different
   teams owning the two deployments.

**This is the direct cause of the rate-limit question being asked, and it makes per-domain quota
budgeting a platform-pattern responsibility, not a domain concern.** See §2.13.

### Second-order items for Pattern 001 design

- Cloud Run per-project resource quotas and naming collisions once *N* domains deploy services there.
- Domain teams need deploy permission into the platform's project — scope it to their own service
  prefix, or the "independent deployment" promise and least privilege pull against each other.
- Blast radius: one project is one failure and one misconfiguration domain.
- Shared quota needs per-domain attribution for cost and for incident triage (MB-15 is
  **NOT VALIDATED** in the prior art: *"production telemetry for provider operations, quota, and
  per-organization cost does not exist"*).

## 1.5 Missing foundation components

Everything below is absent and in scope for Phase 3:

- Git repository, remote, branch model, `.gitignore`.
- `CLAUDE.md`, `AGENTS.md`, `.claude/settings.json`, `.claude/rules/`, 12 project skills.
- `standards/` (9 documents).
- `patterns/memory-manager/` skeleton + `pattern.yaml` + manifest JSON Schema + validator.
- `templates/` (new pattern, domain consumer, container build, Terraform GCP, GitHub Actions).
- `design/` convention + `design/_template/` + `design/000-platform-foundation/`.
- `docs/` (architecture, decisions, onboarding, operations, releases) + skill catalog.
- `.github/workflows/` (split), `CODEOWNERS`, PR template, issue templates.
- `scripts/` design-artifact validator, manifest validator, conformance runner.
- Release/versioning mechanism for pattern publication.

## 1.6 Risks and assumptions

| # | Risk / assumption | Severity | Handling |
|---|---|---|---|
| ~~R1~~ | ~~Ownership-model inversion vs. `geap-memory` is unratified.~~ | — | **RETIRED 2026-10-20.** Ratified by the project owner; see D1. `geap-memory` is prior art, not a competing product. |
| R2 | **Enforcement claims cannot be fully honoured for consumers who own the code.** | ~~High~~ → **Medium** | **Substantially mitigated by the D14 resolution (single platform-owned project).** Teams still own and customize the code, so conformance and boundary checks remain advisory. But project-level IAM, the Memory Bank IAM binding, org policy, the audit sink and quota alerting are now **platform-held and survive any fork of the application code**. The honest residual: the platform controls *what a domain's service account may do to a bank*, not *what the domain's code does before it gets there*. |
| R3 | **The diagram is a screenshot, labelled "Proposed", author unconfirmed.** Transcription may be wrong. | Medium | §1.3 transcription reviewed by the author in Stage 1 (Intent) of Pattern 001. |
| R4 | **Personal GitHub account, not an org.** Required reviews, CODEOWNERS and rulesets may be unavailable or weak. | Medium | Decision **D8**. CI validations are designed to work without them; approval gates degrade to documented manual steps. |
| R5 | **Memory Bank is a managed service with per-project, per-region quotas and eventual-consistency reads** (VERIFIED in `docs/vertex-memory-bank.md`: 429 → `RESOURCE_EXHAUSTED`; "each write first retrieves the scope's facts to compute the next counter, so writes also consume read quota"). | Medium | Pattern must treat quota as a first-class failure mode; conformance tests must cover 429 and replay. |
| R6 | **No field-level structured-profile update in Memory Bank** (VERIFIED) — the POC stores each value as an append-only typed JSON fact with a write counter. | Medium | Carry forward as a stated provider constraint in `design.md`; do not design an update-in-place API. |
| R7 | **Idempotency is an open defect in the prior art** (MB-12, status **CONFLICT**: "no idempotency keys, distributed locking, retry state, or reconciliation"). The new design adds at-least-once delivery via Pub/Sub, which makes this *worse* unless solved. | **High** | Decision **D7**: idempotency key is part of the `remember` contract from v1, not a later enhancement. |
| R8 | Python tooling (`ruff`/`pytest`/`mypy`) absent on this machine. | Low | `uv`-managed project venv; CI installs its own. Phase 4 reports honestly. |
| R9 | No Google Cloud project is designated for this repo's reference infrastructure (the configured project is a personal sandbox). | Low | No infrastructure will be applied. Terraform is validated with `-backend=false` only. Decision **D9**. |
| R10 | **ASSUMPTION:** reference implementation language is Python 3.12 + FastAPI, matching the POC and ADK. Not yet decided. | Medium | Decision **D2**. |
| R11 | **Shared Memory Bank quota across all domains** *(new, 2026-10-20)*. One platform project = one per-region quota pool; separate banks do not separate quota. Writes consume read quota; agents' direct `recall` bypasses the Memory Manager's limiter entirely. One domain can starve another. | **High** | Per-domain quota budgets as platform-owned config, enforced by a rate governor in the worker and monitored by the NFR module. See §2.13. Quota-increase request and per-domain attribution are Pattern 001 design items. |
| R12 | **Domain deploy access into the platform project** *(new, 2026-10-20)* conflicts with least privilege: "deploy independently" needs write access to a project the platform owns. | Medium | Scope each domain's deployer SA to its own resource name prefix; Pattern 001 controls assessment must cover it explicitly. |
| A1 | **ASSUMPTION:** "Memory Bank" means Vertex AI / Gemini Enterprise Agent Platform Memory Bank, `agentplatform` 2.x SDK surface (VERIFIED as the POC's choice, exercised live). | — | Stated in `pattern.yaml` runtime requirements. |
| A2 | **ASSUMPTION:** this repository is the single home for all platform patterns (monorepo), not one repo per pattern. | — | Decision **D12**. |

---

# PHASE 2 — SDLC AND REPOSITORY PROPOSAL

## 2.1 Repository layout (PROPOSED)

Based on the brief's reference structure, with seven justified changes marked **[Δ]**.

```
geap-platform-services/
├── CLAUDE.md                        # operating rules for Claude (concise, pointers only)
├── AGENTS.md                        # [Δ1] thin pointer to CLAUDE.md — no duplicate rules
├── README.md
├── .gitignore
│
├── .claude/
│   ├── settings.json                # permissions allowlist, hooks
│   ├── rules/                       # progressive-disclosure rule files loaded on demand
│   │   ├── sdlc-gates.md
│   │   ├── platform-vs-domain.md
│   │   ├── security-baseline.md
│   │   └── evidence-and-claims.md
│   └── skills/                      # 12 skills, one folder each, each with SKILL.md
│       ├── design-start-feature/    ├── pattern-create/
│       ├── design-session/          ├── pattern-validate/
│       ├── design-check-controls/   ├── pattern-publish/
│       ├── design-plan-implementation/ ├── domain-onboard/
│       ├── design-record-decision/  └── pattern-upgrade/
│       ├── design-open-pr/
│       └── design-close-feature/
│
├── standards/                       # the detailed engineering standards
│   ├── architecture.md              # incl. the CURRENT/TARGET/PROPOSED + evidence-label vocabulary
│   ├── coding.md
│   ├── security.md
│   ├── testing.md
│   ├── observability.md
│   ├── api-design.md
│   ├── configuration.md
│   ├── pattern-contract.md          # the normative pattern contract + enforcement limits
│   └── release-management.md
│
├── schemas/                         # [Δ2] canonical machine-readable schemas, validated by CI
│   ├── pattern.schema.json          # JSON Schema for every patterns/*/pattern.yaml
│   └── design-artifacts.schema.json # front-matter schema for intent/design/controls/tasks/closeout
│
├── patterns/
│   └── memory-manager/
│       ├── README.md
│       ├── pattern.yaml             # the manifest (§2.8)
│       ├── CHANGELOG.md
│       ├── contracts/               # OpenAPI spec, JSON Schemas, error catalogue
│       ├── src/                     # reference implementation
│       ├── config/                  # configuration schema + safe example configs
│       ├── extensions/              # [Δ3] declared extension points + no-op default impls
│       ├── infrastructure/
│       │   └── terraform/
│       │       ├── memory-bank-nfr/ # [Δ4] PLATFORM-owned: bank provisioning, IAM, audit sink, alerts
│       │       └── domain-runtime/  # DOMAIN-owned reference: Cloud Run, Pub/Sub, SA, secrets
│       ├── tests/                   # platform's own unit/integration tests
│       ├── conformance/             # [Δ5] consumer-runnable conformance suite
│       └── examples/
│
├── templates/
│   ├── new-pattern/
│   ├── domain-consumer/
│   ├── container-build/
│   ├── terraform-gcp/               # [Δ6] renamed from google-cloud-deployment (Terraform confirmed)
│   └── cicd-github-actions/         # [Δ6] split out so the pipeline template versions separately
│
├── design/
│   ├── _template/                   # [Δ7] version-controlled artifact skeletons
│   │   ├── intent.md  design.md  controls-check.md  tasks.md  closeout.md
│   ├── 000-platform-foundation/
│   └── 001-memory-manager/
│
├── docs/
│   ├── architecture/                # Mermaid-in-Markdown + .drawio sources
│   ├── decisions/                   # ADR-NNNN-<kebab-title>.md
│   ├── onboarding/                  # developer guide + SKILL CATALOG
│   ├── operations/
│   └── releases/
│
├── scripts/                         # independently runnable, no Claude Code required
│   ├── validate_design_artifacts.py
│   ├── validate_pattern_manifest.py
│   ├── run_conformance.py
│   └── check_platform_domain_boundary.py
│
└── .github/
    ├── workflows/                   # split jobs (§2.7)
    ├── CODEOWNERS
    ├── PULL_REQUEST_TEMPLATE.md
    └── ISSUE_TEMPLATE/
```

**Justification for the changes:**

- **[Δ1] `AGENTS.md` as a pointer.** Two files of rules drift. One is normative; the other says so.
- **[Δ2] `schemas/`.** `pattern-validate` and CI both need *one* canonical schema file. Burying it in
  the skill folder makes the skill the source of truth for a contract that outlives it.
- **[Δ3] `extensions/`.** §1.4 point 3: the diagram puts domain rules (entity resolution, PII
  classification, fact curation) inside platform components. Making the extension points a first-class
  directory with no-op defaults is what prevents domain logic leaking into `src/`. It also makes
  `check_platform_domain_boundary.py` writable as a real test.
- **[Δ4] Split Terraform by owner.** The diagram draws two distinct boxes: domain-hosted runtime vs.
  platform-owned "Memory Bank NFRs" wrapper. Per §1.4 point 1 this split *is* the enforcement story —
  the one control a forking domain cannot bypass. Co-mingling them in one module destroys it.
- **[Δ5] `conformance/` separate from `tests/`.** Domain teams run conformance against their own
  build; they must never be asked to run the platform's unit tests. Without this split, "pattern
  conformance tests" in §16 of the brief has no concrete artifact.
- **[Δ6] Template renames/splits.** Terraform is now confirmed, so name it. The CI/CD template is
  consumed and upgraded on a different cadence than the app scaffold.
- **[Δ7] `design/_template/`.** Skills that generate artifacts from prose embedded in `SKILL.md`
  drift from the validator. A version-controlled skeleton is reviewable in a PR and diffable.

**Not adopted:** a pattern registry (brief §17 advises against it without justification), a
`packages/contracts/` placeholder (brief §15 forbids placeholders), multi-cloud adapter directories
(premature; the cloud seam lives behind a provider interface in `src/`, nothing more).

## 2.2 The six-stage SDLC and the approval model

```
 Stage 1 INTENT ──GATE A──► Stage 2 DESIGN ──GATE B──► Stage 3 CONTROLS ──GATE C──►
 Stage 4 BUILD (plan ──GATE D──► implement) ──► Stage 5 REVIEW ──GATE E──► Stage 6 CLOSE ──GATE F──► merge
```

| Gate | What is approved | Who | Enforced by |
|---|---|---|---|
| **A** | `intent.md` — scope, non-goals, acceptance criteria, reusable-vs-domain classification | Feature requester + platform lead | Human. *Then* the branch and draft PR are created — never before. |
| **B** | `design.md` + diagrams + proposed ADRs | Platform architect | Human; CI verifies the artifact exists and is well-formed |
| **C** | `controls-check.md` — every applicable control has evidence or an approved exception | Security reviewer (CODEOWNERS on `standards/security.md` + `controls-check.md`) | Human; CI fails on `Status: Gap` without a linked approved exception |
| **D** | `tasks.md` — the implementation plan | Platform lead | Human; no material code change before this |
| **E** | The pull request itself | ≥1 human reviewer per CODEOWNERS; security reviewer if controls changed | **GitHub required reviews** — the only hard gate |
| **F** | Merge, and separately: publish / deploy | Repository admin; publishing requires explicit approval per brief §12 | Human. Skills never merge, publish or deploy. |

**Two tracks.** A classifier in `.claude/rules/sdlc-gates.md` decides, and `design-start-feature`
applies it:

| | **Full track** | **Light track** |
|---|---|---|
| **Triggers** | New pattern · breaking or additive API contract change · new managed service · security-posture change · major architecture change · new extension point | Defect fix with no contract change · dependency upgrade (non-breaking) · documentation · test-only change · example/config fix |
| **Artifacts** | `intent.md`, `design.md`, `controls-check.md`, `tasks.md`, ADR(s), `closeout.md` | **one `change.md`** (intent + approach + verification) and a **controls delta** section inside it |
| **Gates** | A, B, C, D, E, F | A (inline in the PR description), E, F |
| **ADR** | When a significant decision is approved | No |

Escalation is one-way and automatic: if a light-track change turns out to alter a contract, a
control, or the architecture, the skill **stops**, says so, and re-enters the full track. The reverse
(downgrading) requires human approval.

**Security remediation** is full-track on controls and design but may run with a compressed timeline;
it never skips Gate C.

## 2.3 Skill catalog (PROPOSED)

All twelve required skills, each in `.claude/skills/<name>/SKILL.md` with YAML front matter
(`name`, `description` with trigger phrases, `allowed-tools`, `user-invocable: true`), a
`reference.md` for detail loaded on demand, and `templates/` where it emits artifacts.
Exact front-matter key support will be **verified against the installed Claude Code 2.1.284 in
Phase 4**, not asserted now.

| Skill | Stage | Reads | Writes | Gate it respects |
|---|---|---|---|---|
| `design-start-feature` | 1 | repo context, `standards/`, existing `design/` | `design/NNN-slug/intent.md` | **Stops at A.** Branch + draft PR **only after** explicit approval |
| `design-session` | 2 | `intent.md`, code, standards | `design.md`, diagrams, proposed ADRs | **Stops at B.** No implementation |
| `design-check-controls` | 3 | `design.md`, `standards/security.md` | `controls-check.md` | **Stops at C.** Never self-marks a control compliant |
| `design-plan-implementation` | 4 | all approved artifacts | `tasks.md` | **Stops at D** |
| `design-record-decision` | 4 | the decision context | `docs/decisions/ADR-NNNN-*.md` | Only for *approved* decisions |
| `design-open-pr` | 5 | diff, `tasks.md`, `design.md` | PR body, review report | Marks ready-for-review only when conditions hold; **never approves** |
| `design-close-feature` | 6 | everything | `closeout.md`, doc/release updates | **Never merges** |
| `pattern-create` | — | `templates/new-pattern/` | new `patterns/<name>/` + `design/NNN-*/` | — |
| `pattern-validate` | — | `pattern.yaml`, `schemas/pattern.schema.json` | validation report | Read-only |
| `pattern-publish` | — | release readiness | tag/release draft, provenance | **Requires explicit approval; never publishes unprompted** |
| `domain-onboard` | — | published pattern + version | domain consumer scaffold | — |
| `pattern-upgrade` | — | two versions, CHANGELOG, contracts | migration plan | — |

**Two additional skills PROPOSED (small, and each earns its place):**

- **`sdlc-status`** — answers "which design folder, which stage, which gates are open?" from the
  filesystem and git state. `CLAUDE.md` rule 3 requires Claude to determine the current SDLC stage on
  every task; without this, every session re-derives it by hand and sometimes guesses. Read-only.
- **`controls-recheck`** — re-runs only the controls affected by a diff (brief §8: *"re-run applicable
  checks when implementation changes affect the design or security posture"*). Could be a flag on
  `design-check-controls` instead; **OPEN (D11)** — I lean toward a flag, to keep the catalog at 13.

**Deliberately not created:** a "code generator" skill, a "deploy" skill, a "merge" skill.

**Hooks (PROPOSED, advisory only).** Two, both small, both in `.claude/settings.json`:

1. `PreToolUse` on `Write|Edit` matching `patterns/**/src/**` → a script that checks for an approved
   `design.md` in the active design folder and **warns** (exit 0 with a message) when absent.
2. `PreToolUse` on `Bash` matching `git push --force|gh pr merge|terraform apply|gh release create`
   → **blocks** (non-zero exit) and tells the user to run it themselves.

**Stated plainly, per brief §15:** hooks and prompt instructions are *not* enforcement. They are
ergonomics for the person at the keyboard. Enforcement is CI + branch protection + CODEOWNERS (§2.7),
and the second hook above protects against accident, not intent.

## 2.4 `CLAUDE.md` structure (PROPOSED)

Target: **under 120 lines.** It carries the 15 required rules as short imperatives and nothing else;
every detail lives behind a pointer so it loads only when relevant.

```markdown
# GEAP Platform Services — operating rules for Claude Code

What this repository is  (4 lines: publishes reusable patterns; does not operate domain runtimes)

## Before you change anything
1. Read the standards that apply → standards/  (table: topic → file)
2. Find the design folder → design/NNN-slug/ ; if none applies, use design-start-feature
3. Determine the stage and open gates → run sdlc-status
4. Never bypass a gate. Never implement before Gate B+D. @.claude/rules/sdlc-gates.md

## While you work
5. Follow the approved design and tasks.md; report deviations
6. Platform code holds no domain business rules → @.claude/rules/platform-vs-domain.md
7. Security and privacy are non-negotiable → @.claude/rules/security-baseline.md
8. Tests and docs change with the code
9. Record approved architecture decisions → design-record-decision
10. Do not touch unrelated components

## Before you report
11. Run the available checks (make verify)
12. Never claim a test, scan or deployment passed without output → @.claude/rules/evidence-and-claims.md
13. Distinguish passed / failed / skipped / unavailable
14. Confirm before anything destructive, published, deployed or merged

## Prefer the project skills
15. Skill table → docs/onboarding/skill-catalog.md
```

`@path` references load on demand; the four `.claude/rules/` files hold the detail. The nine
`standards/` documents are the normative long form and are referenced, never inlined.

## 2.5 Engineering standards (PROPOSED scope of each)

| File | Carries |
|---|---|
| `architecture.md` | Layering; platform/domain boundary; the evidence-label vocabulary (§1.2.4) as a **requirement**; diagram conventions (C4 container level, Mermaid in Markdown, `.drawio` source committed); when an ADR is required |
| `coding.md` | Python 3.12, `ruff`, type hints + `mypy` scope, module structure, error handling, no business rules in platform packages, dependency policy (pinned, lockfile committed, no undeclared deps) |
| `security.md` | The **control catalogue** that `controls-check.md` is generated from — 18 controls from brief §8, each with requirement / applicability test / verification method; which controls are **non-overridable by domain configuration** |
| `testing.md` | Test pyramid; tests-alongside-code; what must be a conformance test vs. a unit test; coverage expectations; the rule that a live managed-service flow is not proven by a mock |
| `observability.md` | Structured log schema, correlation-ID propagation, required metrics (tool invocations, queue depth, retry count, DLQ depth, provider 429s, latency percentiles), trace spans, **the PII/memory-content logging prohibition and how it is tested** |
| `api-design.md` | OpenAPI first; versioning (`/v1`); error catalogue; idempotency-key contract; pagination; rate-limit headers; async 202 + status semantics; backward-compatibility rules |
| `configuration.md` | Config-over-code; schema-validated configuration; precedence (defaults → file → env → secret); what a domain may set; extension-point declaration format |
| `pattern-contract.md` | The normative pattern contract (§2.8) **and the honest limits of enforcement** (§1.4 point 1) |
| `release-management.md` | SemVer for patterns; tag scheme; changelog; compatibility matrix; deprecation policy; provenance; the publish approval gate |

## 2.6 Pattern publishing model (PROPOSED)

No registry. Git and GitHub Releases only.

- **Version:** SemVer, per pattern. Breaking contract change → major. New optional config or
  extension point → minor. Fix with no contract change → patch.
- **Tag:** `memory-manager/v0.1.0` (pattern-scoped, so a monorepo can release patterns independently).
- **Release artifact:** a GitHub Release with (a) a tarball of `patterns/memory-manager/` at that tag,
  (b) `pattern.yaml`, (c) `SHA256SUMS`, (d) the compatibility matrix, (e) the conformance suite.
- **Provenance:** GitHub Actions OIDC attestation (`actions/attest-build-provenance`) on the tarball.
- **Consumption:** a domain pins `pattern: memory-manager, version: 0.1.0` in its own
  `domain-config.yaml`; `pattern-upgrade` diffs the two tags' contracts and changelog.
- **Gate:** `pattern-publish` prepares and validates; a human runs the release. **OPEN (D13)** —
  whether consumers vendor the tarball or depend on a published Python package. Vendoring is simpler
  and matches "build your own image"; a package gives cleaner upgrades. I lean vendored-source for
  v0, revisited at the second consuming domain.

## 2.7 GitHub and CI/CD enforcement strategy (PROPOSED)

**Branching:** trunk-based on `main`. Feature branches `design/NNN-slug` (matching the design folder —
one name, no mapping to remember), `fix/NNN-slug`, `chore/NNN-slug`. Draft PR opened at Gate A,
squash merge at Gate F.

**Workflows (split, parallel):**

| Workflow | Runs | Independently runnable as |
|---|---|---|
| `design-artifacts.yml` | validate design folder structure, front matter, required sections, controls status, light/full track consistency | `python scripts/validate_design_artifacts.py` |
| `pattern-contract.yml` | `pattern.yaml` ⇄ `schemas/pattern.schema.json`; OpenAPI lint; platform/domain boundary test | `python scripts/validate_pattern_manifest.py` + `pytest` |
| `python-ci.yml` | `ruff`, `mypy`, `pytest` unit + integration | `make verify` |
| `conformance.yml` | the pattern conformance suite against a built reference image | `python scripts/run_conformance.py` |
| `security.yml` | dependency scan, secret scan, container scan, SBOM | per-tool CLI |
| `terraform.yml` | `fmt -check -recursive`, `init -backend=false`, `validate`, `tflint`, `checkov`/`tfsec` | `terraform` CLI |
| `container.yml` | build the reference image, scan it, do **not** push | `docker build` |

Every script is pure-Python/stdlib or declares deps; **nothing requires Claude Code.**

### What CI can and cannot enforce — stated per brief §16

| Requirement | Automatable? | Mechanism |
|---|---|---|
| Design artifacts exist, well-formed, consistent with the track | **Yes** | `design-artifacts.yml` |
| No control marked `Gap` without a linked approved exception | **Yes** | `design-artifacts.yml` |
| `pattern.yaml` valid; contracts lint; boundary respected | **Yes** | `pattern-contract.yml` |
| Tests/lint/types pass; scans clean | **Yes** | `python-ci.yml`, `security.yml` |
| Terraform valid and policy-clean | **Yes** | `terraform.yml` |
| Consumer can build its own image from the pattern | **Yes** | `container.yml` + `conformance.yml` |
| **A human actually reviewed and approved the design** | **No** | GitHub **required reviews** + **CODEOWNERS** |
| **Approval came from the right person** | **No** | CODEOWNERS + branch protection |
| **The design is architecturally sound** | **No** | Human judgment |
| **A deployed consumer still honours the contract** | **No** | The domain's own CI running the conformance suite — platform cannot observe it |

### Manual repository-administrator configuration (cannot be committed to the repo)

1. Branch protection / ruleset on `main`: require PR, require ≥1 approval, dismiss stale approvals,
   require CODEOWNERS review, require the named status checks, no force-push, no deletion.
2. Required status checks list (must name the split jobs once they have run at least once).
3. Enable secret scanning + push protection, and Dependabot alerts/updates.
4. Environments + required reviewers for any release/publish workflow.
5. Restrict who may create `*/v*` tags.
6. Actions permissions: read-only default `GITHUB_TOKEN`, allow OIDC for attestation.

**These six items are the real approval gates.** `CODEOWNERS` and `PULL_REQUEST_TEMPLATE.md` in the
repo are prompts, not controls — the brief's §16 warning is correct and will be repeated verbatim in
`docs/onboarding/`.

## 2.8 Platform pattern contract and `pattern.yaml` (PROPOSED)

One manifest per pattern, validated by `schemas/pattern.schema.json` (JSON Schema draft 2020-12) and
`scripts/validate_pattern_manifest.py`. Illustrative shape — field set per brief §17:

```yaml
apiVersion: platform.geap/v1
kind: Pattern
metadata:
  name: memory-manager
  version: 0.1.0                      # SemVer
  description: Domain-owned governed memory tool API over a managed Memory Bank
  maintainer: { team: agent-platform, contact: <placeholder> }
  status: proposed                    # proposed | alpha | beta | certified | deprecated
spec:
  runtime: { language: python, version: "3.12", container: { base: <placeholder>, port: 8080 } }
  interfaces:
    - { kind: openapi, spec: contracts/openapi.yaml, version: v1 }
    # - { kind: mcp, ... }            # deferred — see D6
  configuration: { schema: config/config.schema.json, examples: [config/example.domain.yaml] }
  extensionPoints:
    - { id: entity-resolver,     interface: extensions/entity_resolver.py,     required: false, default: noop }
    - { id: pii-classifier,      interface: extensions/pii_classifier.py,      required: true,  default: deny-all }
    - { id: fact-curator,        interface: extensions/fact_curator.py,        required: false, default: last-write-wins }
    - { id: policy-provider,     interface: extensions/policy_provider.py,     required: true,  default: none }
  secrets:        [...]               # names and purpose only, never values
  cloudPermissions: { google: [...] } # least-privilege role list per component
  infrastructure:
    platformOwned: infrastructure/terraform/memory-bank-nfr      # [Δ4]
    domainOwned:   infrastructure/terraform/domain-runtime
  security:      { nonOverridableControls: [...], dataClassification: [...] }
  observability: { requiredMetrics: [...], requiredAuditEvents: [...], prohibitedLogFields: [...] }
  build:         { instructions: docs/build.md, dockerfile: examples/Dockerfile }
  tests:         { unit: tests/, conformance: conformance/ }
  compatibility: { memoryBankSdk: "<range>", terraform: ">=1.9", google: "~>7.45" }
  upgrade:       { from: [], guide: docs/upgrade.md }
```

`status: proposed` is deliberate: certification is a governance act, and nothing is certified on day one.

## 2.9 Domain adoption workflow (PROPOSED)

The ten steps from brief §18, with the owner of each made explicit:

| # | Step | Owner | Artifact |
|---|---|---|---|
| 1–2 | Discover the pattern, pick a version | Domain | `docs/onboarding/` + GitHub Releases |
| 3 | Generate the consumer project | Domain, via `domain-onboard` | from `templates/domain-consumer/` |
| 4 | Apply domain configuration | Domain | `domain-config.yaml` validated against the pattern's config schema |
| 5 | Implement allowed extensions | Domain | `extensions/` implementations only |
| 6 | **Run pattern conformance tests** | Domain, in the domain's CI | `conformance/` |
| 7 | Build the container image | **Domain** | its own Dockerfile + registry |
| 8 | Scan and publish the image | **Domain** | its Artifact Registry |
| 9 | Deploy to the domain's GCP project | **Domain**, Terraform | `terraform-gcp` template |
| 10–11 | Validate and operate | **Domain** | runbook from `templates/domain-consumer/` |

**May customise:** `domain-config.yaml`; extension-point implementations; prompts; the privacy
category/sensitivity lists; Terraform variables; its own CI; scaling and resource settings.

**Must preserve:** the OpenAPI contract and error catalogue; the non-overridable security controls;
the audit-event schema and the platform audit sink; required metrics and the prohibited-log-field
list; the Memory Bank NFR Terraform (platform-owned); the idempotency contract; `pattern.yaml`
compatibility pins.

**Detection of unsupported changes (PROPOSED):**
(a) the conformance suite asserts contract and control behaviour as black-box tests against the
domain's own build; (b) `scripts/check_platform_domain_boundary.py` fails if domain code imports
platform internals or redefines a non-overridable control; (c) a manifest-digest check detects an
altered `pattern.yaml`; (d) the platform-owned Terraform asserts the IAM posture independently of the
application.

**Limits, stated plainly (brief §18):** a domain that copies or forks the pattern source can disable
(a), (b) and (c) — they run in the domain's own CI, which the platform does not control and cannot
observe. Only (d) survives a fork, and only because the Memory Bank IAM binding and audit sink are
provisioned by platform-owned Terraform in a project the domain does not solely control. Any claim
beyond that is aspiration.

## 2.10 Multi-developer and multi-agent collaboration (PROPOSED)

- **Design folder = branch = PR**, one owner. Numbers are allocated by taking the next free integer
  and are claimed by pushing the branch; collisions are resolved by renumbering the later branch.
- **Parallel-work boundaries:** one pattern per feature where possible. Shared files
  (`standards/**`, `schemas/**`, `.claude/skills/**`, `CLAUDE.md`) are **high-contention** — changes
  to them get their own small PR, merged first.
- **Worktrees** for concurrent features (`git worktree`), so each agent/developer has an isolated
  checkout and the `design/NNN-slug` branch name matches its directory.
- **Multi-agent rules:** bounded task from `tasks.md`; explicit file ownership declared in the task;
  never two agents editing one file; an agent that needs a file outside its task stops and reports.
- **Agent specialisation — minimal, per brief §19.** Only two are justified today: an
  **independent reviewer** context for Stage 5 (a reviewer that did not write the code finds more),
  and a **read-only explorer** for codebase questions. No specialist "security agent" or "test agent"
  until there is evidence they beat the skills plus CI.
- **Review ownership** via CODEOWNERS: `standards/security.md` + `**/controls-check.md` → security
  reviewer; `patterns/*/contracts/**` → architect; `.claude/**` + `standards/**` → platform lead.

## 2.11 ECC (Everything Claude Code) evaluation

**VERIFIED:** nothing from ECC is installed. The only Claude plugin enabled globally is
`frontend-design@claude-plugins-official`; `~/.claude/skills/` holds the Google ADK skill suite and
`gstack` — both unrelated to this SDLC.

**I have not inspected the ECC repository in this session**, so I will not characterise its contents
or quality. What I can say:

- **Recommendation: do not install ECC, in whole or in part, now.** Build the 12–13 project skills
  first. Our SDLC must not depend on a third-party extension (brief §20).
- **Four ideas worth borrowing conceptually**, each already in the plan without any dependency:
  planning-before-implementation (Stages 1–4), tests-alongside-code (`standards/testing.md`),
  an independent review context (§2.10), and session continuity (the `design/NNN-*/` folder *is* the
  durable context — a new session reconstructs state from the filesystem via `sdlc-status`).
- **If a specific ECC component is later proposed**, it goes through the seven steps in brief §20
  (verify source, check 2.1.284 compatibility, review permissions, assess maintenance risk, check SDLC
  conflicts, state trade-offs, request approval) and is recorded as an ADR. No silent installs.

## 2.12 Unresolved decisions — needed before or during Phase 3

| ID | Decision | Blocks | My recommendation |
|---|---|---|---|
| ~~**D1**~~ | ~~Does the published-pattern model supersede the `geap-memory` central control plane?~~ | — | **RESOLVED 2026-10-20 by the project owner.** This is a brand-new project with three stakeholders (platform team, agent teams, domain owners). The platform publishes reusable patterns and templates *including implementation code* (Memory API, Evaluation API); individual teams adopt, **own and customize the code**, and deploy independently on **Cloud Run**. The `geap-memory` control plane is **prior art and reference only**, not the product. → record as **ADR-0001**. |
| **D2** | Reference-implementation language and framework | Phase 3 (templates) | **Python 3.12 + FastAPI + Pydantic v2** — matches the POC, the ADK ecosystem and the team's demonstrated skills |
| **D3** | ~~Cloud Run vs. GKE~~ → **narrowed:** how the *worker* runs on Cloud Run | Phase 5 (design) | **Cloud Run is decided** (owner, 2026-10-20). Remaining question is only the worker shape: Cloud Run **service** with a Pub/Sub push subscription, versus Cloud Run **Jobs** for batch replay. Decide in Pattern 001 `design.md`; not a foundation blocker |
| **D4** | Is `remember` async-202 from v1, or sync with async as an option? | Phase 5 | Async-202 per the diagram — it closes MB-13. But it changes the agent-facing contract materially; needs the diagram author's confirmation |
| **D5** | Memory Bank topology (MB-20, **OPEN** in prior art) | Phase 5 + NFR Terraform | **Mostly RESOLVED 2026-10-20: one bank per domain, all banks in one platform-owned project.** ⚠️ **This contradicts the diagram**, which labels the bank `[External Data Store — one per agent]` and says "an agent may write one or more banks". Per-domain and per-agent are different isolation and quota-attribution models. **Residual question for the diagram author:** is the bank boundary the *domain* (owner's statement) or the *agent* (diagram)? I recommend **per domain** — it matches who owns the policy and keeps bank count linear in domains rather than in agents |
| **D6** | MCP interface now or later | Phase 3 (`pattern.yaml`) | Later. OpenAPI v1 first; MCP declared as a planned interface, not stubbed |
| **D7** | Idempotency contract for `remember` (MB-12 is **CONFLICT** in prior art; Pub/Sub makes it worse) | Phase 3 + 5 | **Client-supplied idempotency key, required, v1.** Not a later enhancement |
| **D8** | GitHub home: personal account vs. an organisation; private or internal | Phase 3 (CI/CODEOWNERS) | An org, if available — required reviews and rulesets are the only hard approval gate we have |
| **D9** | Does this repo own any live GCP infrastructure, and which project / Terraform state backend? | Phase 3 (Terraform) | **No live infrastructure for the platform repo.** Terraform is reference + validated only; state backend documented in `backend.tf.example`, never configured here |
| **D10** | Caller identity model for the Memory Manager API | Phase 5 | Google-signed ID token / Workload Identity, matching the POC. Needs confirming against the domain's actual front door |
| **D11** | `controls-recheck` as a 13th skill, or a flag on `design-check-controls` | Phase 3 | A flag. Keeps the catalog small |
| **D12** | Monorepo for all patterns vs. one repo per pattern | Phase 3 (layout) | Monorepo now; pattern-scoped tags keep releases independent |
| **D13** | Consumers vendor the pattern tarball vs. depend on a published package | Phase 3 (templates) | Vendored source for v0 — it matches "build your own image"; revisit at the second consuming domain |
| ~~**D14**~~ | ~~Who provisions the Memory Bank and owns its IAM binding?~~ | — | **RESOLVED 2026-10-20 by the project owner.** **A single GCP project, owned by the platform team**, hosts every domain's memory banks *and* agents. The Customer domain creates its own bank in it; Inventory creates a separate bank in the same project when onboarded. Domain teams own and deploy their implementations, but **into the platform's project**. → This makes the §2.9(d) enforcement seam **real**: project-level IAM, org policy, the audit sink and quota alerting are all platform-held. See the consequences in §1.4b. |
| **D15** | Is the **Evaluation API** in scope as Pattern 002 during this foundation work, or later? *(new, 2026-10-20)* | Phase 3 scope | Later. Scaffold `patterns/` to hold many, prove the contract with Memory Manager (Pattern 001) only, then onboard Evaluation as the first real test that the contract is not memory-shaped |
| **D16** | **Rate-limit buffering: PostgreSQL + scheduled job vs. Pub/Sub** *(asked 2026-10-20)* | Pattern 001 `design.md` + ADR | **Pub/Sub, with a *pull* subscription and a token-bucket rate governor in the worker** — not push, and not a scheduled job. Full reasoning, the three qualifications that matter more than the choice, and the narrow remaining place for a database in the dead-letter tier: **§2.13** |
| **D17** | **Per-domain quota budgeting** *(new, 2026-10-20)* — how the shared project quota (R11) is divided, attributed and alerted on | Pattern 001 + NFR module | Platform-owned config (`maxWritesPerMinute` per domain) enforced by the worker's governor; per-domain attribution metrics in the NFR module. Closes MB-15, which is **NOT VALIDATED** in the prior art |

---

## 2.13 Rate-limit handling: PostgreSQL + scheduled job vs. Pub/Sub — RECOMMENDATION

**Asked by the project owner, 2026-10-20.** This is a Stage 2 design decision and belongs in Pattern
001's `design.md` with an ADR. The recommendation below is input to that, not a substitute for it.

### Framing the problem correctly

A rate limit is not a failure to retry — it is a **rate to respect**. The two options are usually
compared on durability, but durability is the part both get right. The question that decides it is:
*which one lets you control the aggregate request rate against a shared, quota-limited dependency?*

Three constraints make this concrete:

1. **Quota is shared across all domains** (R11) and enforced per-project, per-region.
2. **A retry is not free.** A write that 429s has already consumed quota, and writes consume read
   quota as well (VERIFIED). Naive redelivery against an exhausted quota **burns the very resource it
   is waiting for** — a retry storm that extends its own outage.
3. **Delivery is at-least-once once a queue is involved**, and idempotency is already a known defect
   (MB-12, **CONFLICT**). Adding a queue makes duplicates routine rather than rare.

### Assessment

| | **PostgreSQL + scheduled job** | **Pub/Sub** |
|---|---|---|
| Durability | Good | Good |
| Aggregate rate control | **Excellent** — drain at exactly the rate you choose | **Only with a *pull* subscription + a limiter.** Push subscriptions redeliver on Pub/Sub's schedule, not yours — this is the trap |
| Fairness across domains | Easy (`ORDER BY`, per-domain budget in SQL) | Needs per-domain subscriptions + per-domain limiter |
| Operator visibility ("what is parked?") | **Excellent** — it is a queryable table | Poor — a dead-letter topic is not inspectable; you must drain it to look |
| Selective replay | Easy | Awkward |
| Idempotency | Easy — unique constraint on the key | Needs a separate dedupe store |
| Backoff, DLQ, scaling | Hand-rolled | **Built in** |
| Latency floor | Tick interval — minutes | Sub-second |
| **New infrastructure for the domain** | **A Cloud SQL instance** — provision, migrate, back up, pool, pay for, HA | A topic and subscription |

The decisive asymmetry is the last row. **The Memory Manager is otherwise stateless.** The diagram
makes policy and RBAC *versioned config*, and the Memory Bank holds the memories. The POC had
PostgreSQL because it was a control plane with 26 tables; this pattern inherits none of that.
Introducing a relational database *solely as a retry buffer* adds a stateful, operated, HA-needing,
per-domain dependency to a pattern whose whole footprint would otherwise be "a container and a queue".
Every onboarding domain pays that cost forever.

### Recommendation

**Pub/Sub as the transport — with three qualifications that matter more than the choice itself.**

1. **Pull subscription with a token-bucket rate governor in the worker, not a push subscription.**
   This is the crux. Push gives durability but surrenders rate control to Pub/Sub, which is precisely
   what you cannot afford against a shared quota. A pull subscription with flow control lets the
   worker consume at a rate *it* sets. The bucket is sized to the domain's allocated share of the
   project quota and is **platform-owned configuration** (`maxWritesPerMinute` per domain) — which is
   exactly the "standardized approach for managing rate limits" you asked the pattern to define.
   Combined with Pub/Sub's own `minimumBackoff`/`maximumBackoff` and a dead-letter topic after *N*
   attempts, this satisfies brief §4.D without hand-rolling the hard parts.

2. **`202` must mean "durably enqueued", never "accepted and hopefully published".** The API has no
   database, so there is no transactional outbox. The honest contract: publish to Pub/Sub *before*
   returning; if the publish fails, return **503**, not 202. This avoids the outbox entirely and is
   why the stateless design holds together. It must be stated in the OpenAPI contract and asserted in
   the conformance suite.

3. **Idempotency is required in v1, not deferred** (D7). Possible approach worth validating: the
   worker already reads the scope's facts before every write to compute the counter, so store the
   client's idempotency key *inside the fact* and let that pre-existing read serve as the dedupe
   check — **no additional datastore at all**. Honest caveat: Memory Bank reads are eventually
   consistent (VERIFIED), so this catches retry-induced duplicates seconds-to-minutes apart but
   **not** genuinely concurrent ones. If concurrent duplicate writes must be impossible, a real lock
   or a dedupe store is required and the stateless claim weakens. **This needs provider validation
   before it is relied upon.**

### Where PostgreSQL still earns a place — narrowly

Not as the queue. As the **dead-letter tier**: messages that exhaust *N* attempts should land
somewhere an operator can query, triage and selectively replay. A Pub/Sub dead-letter topic is poor at
that. Writing exhausted messages to BigQuery or GCS (with a small replay tool) gives inspection and
replay without a transactional database in the hot path. A table is a fine choice too *if* the domain
already runs a database for other reasons — which is why this belongs in the pattern as a **pluggable
dead-letter sink**, defaulting to the simplest option, rather than a mandate.

### What I would not do

- **Push subscriptions** — see (1).
- **Scheduled-job-only.** It adds a latency floor measured in ticks and is poorly matched to spiky
  agent traffic: slow ticks lag writes by minutes, fast ticks poll an empty table.
- **Retry at the API edge.** Over-limit writes must be parked, not held — the diagram is right that
  the endpoint's job is to park and return.
- **Treat Pub/Sub as sufficient on its own.** The brief's warning is correct: it gives durability,
  backoff and dead-lettering, but **not** aggregate rate control, **not** idempotency, **not**
  cross-domain fairness, and **not** operator visibility. Those four are the pattern's job.

### Open sub-questions for Pattern 001 design

- Per-domain quota budget: static config, or dynamically allocated from observed project headroom?
- The agent's direct `recall` path consumes the same quota and is ungoverned (R11.2) — is it kept?
- Is read-path rate limiting needed, or is write-path parking sufficient?
- `recall` behaviour when a write is still parked: does the caller see stale data, and is that stated
  in the contract?

# What happens on approval

**Phase 3** scaffolds the foundation in the order: git init + `.gitignore` → `CLAUDE.md` +
`.claude/rules/` → `standards/` → `schemas/` + validator scripts → `design/_template/` +
`design/000-platform-foundation/` → the 12 skills → `templates/` → `.github/` → `docs/` + skill
catalog → `patterns/memory-manager/` **skeleton and manifest only, no implementation**.

**Phase 4** validates and reports passed / failed / skipped / unavailable separately — including an
honest statement that `ruff`/`pytest`/`actionlint` may be **unavailable** until a project environment
is provisioned.

**Phase 5** runs the real SDLC on Pattern 001 using the skills just built, producing `intent.md`,
`design.md`, `controls-check.md` and `tasks.md` for the Domain Memory Manager — and stopping there.

**Nothing in Phase 3 creates a remote branch, opens a PR, publishes a release, or applies
infrastructure.**
