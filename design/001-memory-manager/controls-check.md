---
artifact: controls-check
feature: 001-memory-manager
track: full
status: draft
---

# Controls assessment — Memory Manager v0.1.0: a governed write path for agent memory

> Stage 3. Generated from the catalogue in `standards/security.md`. Approval at **Gate C**.
>
> A control is **never** `Verified` without evidence that would fail if the control were removed.
> `Gap` is an acceptable outcome; an undisclosed gap is not.

Statuses: `Verified` · `Implemented, not verified` · `Gap` · `Not applicable` · `Exception approved`

## Method

Produced on 2026-10-21 on branch `design/001-memory-manager` at `32174bb`. Read in full:
`standards/security.md` (C-01…C-19), `design/001-memory-manager/design.md` (approved 2026-10-21),
`design/001-memory-manager/intent.md`, `patterns/memory-manager/pattern.yaml`,
`patterns/memory-manager/config/config.schema.json`, both Terraform READMEs under
`patterns/memory-manager/infrastructure/terraform/`, `patterns/memory-manager/examples/Dockerfile`,
`.github/workflows/security.yml`. The failed jobs of PR #1's CI run were read with
`gh run view --job <id> --log-failed`.

**What "Implemented" means here.** **VERIFIED**: `src/`, `extensions/`, `contracts/`, `tests/` and
`conformance/` hold only README placeholders, and both Terraform directories are empty. No code
exists. In this document `Implemented, not verified` means *specified in the approved design*,
which is what the skill prescribes at design stage. Nothing is `Verified`.

**Not done:** no call to a live Memory Bank. See the live verification status below.

## Recheck — 2026-10-22 (draft, for the Gate C re-confirmation)

**Base:** `54bfa9f`, the commit that recorded this assessment as approved (Srinivasa reddy,
2026-10-21). It is compared with branch `design/001-memory-manager` at `50c6465`, plus the uncommitted
`design.md` and `tasks.md` amendments and `spike/` of 2026-10-22. **Read:** `git diff --name-only
54bfa9f...HEAD`, tasks.md DEC-1 to DEC-11, design.md "Live verification", `.github/workflows/security.yml`,
PR #1's checks at `50c6465` (job logs fetched with `gh api …/actions/jobs/<id>/logs`), and the
`agentplatform` surface of `google-cloud-aiplatform` 2.3.0, by introspection only.

**This recheck returns the assessment to `draft`.** The approval of 2026-10-21 is preserved in git
at `54bfa9f`. Only the security reviewer sets `approved` again.

| Change since `54bfa9f` | Controls |
|---|---|
| The requester accepted the recommendations for the nine Gaps (2026-10-21): DEC-1, DEC-3, DEC-4, DEC-5 and DEC-6 decided in tasks.md | C-05, C-06, C-08, C-10, C-11, C-16, C-17, C-19 |
| DEC-2 (audit failure semantics) and DEC-7 (local trust anchor) decided | C-07, C-01 |
| L4 and L7 extended, L12 added, and live verification split into Tier 1 and Tier 2 | C-05, C-09, C-10, C-16, C-17 |
| SDK introspection: no per-request TTL on `GenerateMemories` | C-09 |
| Change 003 merged: secret-scanning permissions fixed, so gitleaks now runs | C-08 |
| Change 005 merged: the pre-existing Checkov failure is gone | C-15 |
| T-05 planned: the dependency scan covers the pattern lockfile | C-13 |

**Rechecked:** C-01, C-05, C-06, C-07, C-08, C-09, C-10, C-11, C-13, C-15, C-16, C-17, C-19.
**Carried forward unchanged:** C-02, C-03, C-04, C-12, C-18, and C-14 (not applicable). C-18 gains
`audit_emission_failures` (DEC-2) and a `remediations` alert (T-39); its status is unaffected.

**A control this recheck moves from `Gap` to `Implemented, not verified`** is closed by a decision
recorded in `tasks.md`, which is still a draft (Gate D held). If Gate D is not approved as written,
that control returns to `Gap`.

## Live verification status (rechecked 2026-10-22)

The design's live checks are now split into two tiers (design.md "Live verification", amended
2026-10-22 at the requester's instruction). **Tier 1** (L1–L9, L11) runs before this
re-confirmation, using `spike/probe_memory_bank.py` (tasks.md T-24). **Tier 2** (L10, L12) needs
deployed pattern infrastructure and runs before release (T-45). **VERIFIED**: no live run exists yet;
the probe is written and has not been run. Exceptions that depend on Tier 1 are marked **pending**
below. The security reviewer approves them after the T-24 record exists, or decides explicitly to
approve them before it.

## Summary

| Status | Count |
|---|---|
| Verified | 0 |
| Implemented, not verified | 14 |
| Gap | 4 |
| Not applicable | 1 |
| Exception approved | 0 |

Total 19. Gaps: C-05, C-09, C-17, C-19. Moved out of `Gap` by this recheck: C-06, C-10, C-11, C-13,
C-16. At the approval of 2026-10-21: 9 implemented-not-verified, 9 Gaps.

## Non-overridable controls — can configuration switch one off?

C-01, C-02, C-05, C-06, C-07, C-08, C-11 and C-16 are declared in
`pattern.yaml` `spec.security.nonOverridableControls` (**VERIFIED**). **No design defect found**: the
approved design defines no configuration key that skips a token check, makes a `sensitive` or
`restricted` topic eligible, skips verification or recall-time classification, suppresses audit,
logs a value or selects a bank. Three schema properties are needed to keep that true, and are
carried as implementation requirements under C-01 and C-02:

1. `endUserIdentity` must be **required** in `config.schema.json`. If it is optional, leaving it out
   becomes a way to skip the second token check.
2. `extensions` currently allows **any** key (`additionalProperties: {type: string}`). It must be
   restricted to the declared extension-point IDs, so configuration cannot inject a module at an
   undeclared dispatch point.
3. `environment: local`, which permits the fake provider (AC18), must be **refused** when the process
   runs on Cloud Run (for example, when `K_SERVICE` is set). The configured value alone must not be
   trusted (`standards/configuration.md` "Environments").

## Assessment

### C-01 — Authentication

| | |
|---|---|
| **Requirement** | Every caller is authenticated. Deployed environments require a Google-signed ID token mapped to exactly one registered caller. Development header shortcuts are refused outside local environments, not merely defaulted off. |
| **Applicability** | Applies. The design adds two authenticated operations (`/v1/remember`, `/v1/recall`) and a second, end-user token (D2). |
| **Implementation** | Design: `src/api` verifies the agent ID token (audience = service URL) and maps it to exactly one entry in the new `callers[]` configuration. Otherwise `401 UNAUTHENTICATED` or `403 CALLER_NOT_REGISTERED`. `X-End-User-Token` is verified against `endUserIdentity` (issuer, JWKS, audiences, expiry). JWKS is cached with a bounded TTL and there is no fallback to unsigned tokens (`401 END_USER_TOKEN_INVALID`). The design has no development header shortcut. The fake provider is permitted only with `environment: local`. `/healthz` is unauthenticated and reveals nothing. Requirements from this assessment: `endUserIdentity` is required in the schema; `environment: local` is refused on Cloud Run. **Recheck:** DEC-7 (decided 2026-10-21) adds a local-only trust anchor for agent tokens (a configurable issuer and JWKS), so that the conformance suite can authenticate against a locally built image. It is guarded exactly like the fake provider: allowed only with `environment: local`, and refused when `K_SERVICE` is set. |
| **Verification** | Unit/conformance tests: no token → 401; wrong audience → 401; valid token, unregistered principal → 403; token mapping to two callers rejected at configuration load; end-user token expired / wrong issuer / wrong audience / bad signature / `alg: none` → 401; JWKS unreachable after cache expiry → 401; `environment: local` with `K_SERVICE` set → startup refusal; configuration without `endUserIdentity` → schema rejection. DEC-7 condition: `conformance/test_local_trust_refused.py` (T-37) asserts, in the deployed profile, that a token signed by the local issuer gets `401`, and that the built image refuses to start with `environment: local` and `K_SERVICE` set. |
| **Status** | Implemented, not verified |
| **Evidence** | Design, plus tasks.md DEC-7. No code, no tests. |

### C-02 — Authorization fails closed

| | |
|---|---|
| **Requirement** | Unknown caller, unknown attribute, unmapped scope, or a classifier error → deny. |
| **Applicability** | Applies. The design defines every authorization decision in the service. It also **relaxes the `policy-provider` default from `deny-all` to `passthrough`** (O6), which the design flags for this review. |
| **Implementation** | Deny paths traced through the design: unknown caller → 403; role lacks `read`/`write` → 403; `policy-provider` raises → 403; `entity-resolver` raises or returns nothing → `403 SCOPE_UNRESOLVED` (changed from `skip`); `topic-provider` raises or is unconfigured → `503 POLICY_UNAVAILABLE`, nothing written; unknown topic / field / wrong type / disallowed `basis` → fact rejected; `pii-classifier` raises → fact rejected `CLASSIFIER_ERROR`; read-back classifier raises or the fact prefix does not parse → memory remediated; recall-time classifier raises → memory withheld. `sensitive`/`restricted` topics are never eligible, and no key changes that. **On O6:** the platform RBAC decision already denies by default, and the design states that `policy-provider` can only further deny. It can do so only if the dispatcher treats any refinement result other than "deny" as "keep the platform decision", never as "allow". The `passthrough` default does not weaken a control *if and only if* that holds. Requirement from this assessment: restrict `extensions` keys to declared IDs. |
| **Verification** | One test per deny path above, each failing if its check is removed. A test that `policy-provider` returning "allow" after a platform deny still yields 403. A test that a raising `policy-provider` yields 403 even when platform RBAC permits. A schema test that an undeclared `extensions` key is rejected. |
| **Status** | Implemented, not verified |
| **Evidence** | Design only (`design.md` "Extension points", "Failure handling"). **Security reviewer decision requested on O6.** |

### C-03 — RBAC from versioned, schema-validated configuration

| | |
|---|---|
| **Requirement** | RBAC is driven by versioned domain configuration, validated against a schema. Roles grant the narrowest capability that works; read-only can never write. |
| **Applicability** | Applies. The design adds `callers[]` and `rbac.roles[].topics[]`, and narrows `permissions` to `read`/`write`. |
| **Implementation** | `config.schema.json` changes per the design ("Configuration changes"). The `topics.version` string is emitted in `configuration_change` at startup. `rbac` has no version field of its own. It is versioned with the configuration file it deploys in (**ASSUMPTION** — the reviewer should confirm this is enough). |
| **Verification** | Test: role with only `read` calling `remember` → 403. Test: role not approved for a topic → fact `TOPIC_NOT_APPROVED`. Schema tests: unknown permission value rejected; role referencing an undefined topic rejected. |
| **Status** | Implemented, not verified |
| **Evidence** | Design only. **VERIFIED** today: the current schema still allows `correct`/`forget`/`list` and has no `callers` key; the design changes this. |

### C-04 — Cross-caller and cross-domain access is explicit

| | |
|---|---|
| **Requirement** | Cross-caller and cross-domain access is explicit and recorded. Default is no access. |
| **Applicability** | Applies. Several agents in one domain share an end user's scope, and the scope is derived per request. |
| **Implementation** | The scope comes only from the verified end-user token through `entity-resolver`. Any `user_id`/`scope`/`role`/`domain`/`bank` body field → `400 REQUEST_INVALID` (`additionalProperties: false`). Cross-agent sharing *within* a user's scope is explicit: per-role topic approval (`rbac.roles[].topics[]`), and recall returns approved topics only (D4). Cross-domain: the bank comes from deployment configuration, one per domain (see C-16). Denials are recorded as `policy_denial`. |
| **Verification** | AC3 test: body names user B and the token is user A; assert user B's scope is untouched and only A's is written. Test: agent role X cannot recall a topic approved only for role Y → `403 TOPIC_NOT_APPROVED`. |
| **Status** | Implemented, not verified |
| **Evidence** | Design only (`design.md` "Request headers", "`recall`"). |

### C-05 — Classification and redaction before persistence

| | |
|---|---|
| **Requirement** | Data is classified before persistence; sensitive and restricted values are redacted or refused per domain policy. The classifier is a domain extension; the obligation is platform and defaults to deny-all. |
| **Applicability** | Applies. This is the core of the feature. Provider consolidation (D6) can also create content the service never classified. |
| **Implementation** | Before write: per-fact topic eligibility + field schema + `basis` rule + `pii-classifier` (default `deny-all`, failure `deny`). After write: every created or updated memory is read back and re-classified by the same instance, then rolled back if the prior revision is clean, otherwise deleted (D3). At recall: re-classified and withheld on failure. **Recheck:** (a) DEC-3 (decided): delete is the default remediation. Rollback (T-27) is built only if L4 shows that a rollback leaves no listable or retrievable prohibited revision. If delete leaves one too, re-enter design. The SDK exposes `disable_memory_revisions` and `revision_ttl` on `GenerateMemoriesConfig` (**VERIFIED** by introspecting 2.3.0, not live); the probe observes the first under L4, and neither is adopted. (b) is accepted as an exception (below). Its compensating controls: read-back and re-classification of every touched memory (T-25), recall-time re-classification and withholding (T-33), `written_unverified`, and a per-domain `remediations` alert (T-39). |
| **Verification** | Test: default classifier → nothing written. Test: classifier raises → fact rejected. AC6 test (prohibited value on an eligible topic). AC11 test with a fake provider that rewrites on consolidation. Test: recall withholds a prohibited memory. Live: L1, L4, L6. Tier 1 live: L1, L2, L3, L4 (extended) and L6, with `spike/probe_memory_bank.py` (T-24). |
| **Status** | Gap |
| **Evidence** | (a) is closed in the plan by DEC-3; the outcome depends on L4, which has not run. (b) stays a Gap until its exception is approved. That row is **pending Tier 1 (L1–L3)**, because its compensating controls rely on the read-back that L2 and L3 test. **VERIFIED**: no `live-verification.md` exists. |

### C-06 — Logging restrictions

| | |
|---|---|
| **Requirement** | Memory content, PII, secrets and full auth headers never reach logs, traces or error responses. |
| **Applicability** | Applies. New logs, spans, audit events, error bodies, and a new secret-like header (`X-End-User-Token`). |
| **Implementation** | Design: logs carry topic name, decision, reason code and counts. Never a value, the fact string, the subject or either token. Span attributes follow the prohibited-field list. Errors are `{code, message, correlation_id}` with no payload content. Responses never echo a value. `end_user_token` is added to `prohibitedLogFields`. Sentinel test across logs, spans, audit and error bodies (AC15). Requirement from this assessment: FastAPI's default `RequestValidationError` response includes the offending `input` value, so it must be replaced by the `400 REQUEST_INVALID` handler, and the sentinel suite must include a schema-invalid request carrying a sentinel. The same applies to provider exception text (`provider_error_body`). **Recheck:** DEC-1 (decided 2026-10-21): the audit scope identifier is HMAC-SHA256 of the subject, keyed from one Secret Manager secret exposed as a Cloud Run Secret Manager reference. The raw subject never reaches an audit event, and a deployed instance without the key refuses to start (T-09, T-12). |
| **Verification** | AC15 sentinel test, failing if redaction is removed; it includes schema-invalid requests, classifier errors and provider errors. A test that `logLevel: DEBUG` emits no sentinel. T-12: a sentinel subject never appears in any event, and the same subject yields the same pseudonym under one key. T-09: deployed without the key → refusal. |
| **Status** | Implemented, not verified |
| **Evidence** | Design, plus tasks.md DEC-1. Takes effect with Gate D. If Gate D is not approved as written, this returns to Gap. No code, no tests. |

### C-07 — Audit completeness

| | |
|---|---|
| **Requirement** | Every memory write, deletion, denial and policy decision emits an audit event with a correlation ID to the platform audit sink. |
| **Applicability** | Applies. |
| **Implementation** | Design "Audit events" table: `memory_write` (per touched memory; `written`/`unknown`), `policy_denial` (request-level and per rejected fact), `memory_rollback`, `memory_deletion`, `verification_incomplete`, `remediation_failed`, `recall_withheld`, `configuration_change`. The sink is platform-owned Terraform in `infrastructure/terraform/memory-bank-nfr` (**VERIFIED**: empty today). The manifest's `requiredAuditEvents` is extended. **Not specified by the design, carried here as an implementation requirement:** what happens when audit emission itself fails. To fail closed, a write whose `memory_write` event cannot be emitted must not be reported as `written`. If emission goes to stdout and the sink routes it by log name, the emitting path and its failure semantics must be stated in the implementation plan. **Recheck:** the implementation plan now states the failure semantics (DEC-2, decided 2026-10-21). Events are written synchronously to a dedicated log name through the Cloud Logging API. If a `memory_write` event fails, the outcome is downgraded to `written_unverified`, a CRITICAL fallback line with no values goes to stdout, and `audit_emission_failures` is counted. The scope identifier is pseudonymised (DEC-1). |
| **Verification** | One test per event type, with correlation ID and reason code present and the sentinel absent (AC16). Terraform review: the sink filter matches the dedicated log name, and the domain's SA cannot modify the sink. T-12: emission failure follows DEC-2. |
| **Status** | Implemented, not verified |
| **Evidence** | Design, plus tasks.md DEC-2. No code. |

### C-08 — Secret handling

| | |
|---|---|
| **Requirement** | Secrets are referenced by name and resolved from Secret Manager at runtime. Never in source, images, Terraform variables, logs or committed `.env`. |
| **Applicability** | Applies. The design removes the manifest's `MEMORY_BANK_CREDENTIALS` secret in favour of Workload Identity. The end-user token is a credential handled in transit. |
| **Implementation** | Design: Workload Identity for the provider; `spec.secrets` emptied; `roles/secretmanager.secretAccessor` removed. The JWKS is public and needs no secret. The end-user token is never logged (C-06). If C-06 chooses HMAC pseudonymisation, that key becomes a Secret Manager secret and the secret access role returns, scoped to that one secret. **Recheck:** DEC-1 chooses HMAC, so the key is one Secret Manager secret. It reaches the container as a Cloud Run Secret Manager reference, never as a Terraform variable or an image layer. `roles/secretmanager.secretAccessor` is bound on that secret only (T-40), and the secret is declared under `spec.secrets` (T-41). |
| **Verification** | CI secret scanning (gitleaks) on every PR; a repository test forbidding credential-shaped literals; manifest review that `spec.secrets` holds no provider credential. T-40 Terraform check: the binding is on the secret resource, not the project. |
| **Status** | Implemented, not verified |
| **Evidence** | **VERIFIED**: change 003 (merged as `c577d52`) fixed the workflow permissions defect. On PR #1 at `50c6465`, `Secret scanning` passed: gitleaks reported `10 commits scanned` and `No leaks detected` (job 119642927095). That shows the branch holds no secret today. Correct handling of the HMAC key needs T-40 and T-41. |

### C-09 — Classification and retention declared and enforced

| | |
|---|---|
| **Requirement** | Data classification and retention are declared in configuration, and retention is enforced. |
| **Applicability** | Applies. The design adds per-topic `classification` and, since ADR-0004 (2026-10-22), one domain-level `retentionDays`. |
| **Implementation** | **Since ADR-0004 (2026-10-22):** one domain-level `retentionDays`, bounded by a platform maximum in the schema (T-07). It is enforced by the domain bank's `generate_created_ttl` and `generate_updated_ttl`, set by platform Terraform (T-39). No TTL is sent on write. Per-topic retention is deferred to v0.2.0. *Superseded text: per-topic `retentionDays`, enforced by a per-memory provider TTL set on write.* **Recheck:** L7 is extended: the TTL must survive consolidation, and expiry is observed. **VERIFIED by introspecting SDK 2.3.0, not live:** `GenerateMemoriesConfig` has no per-request `ttl`, and `Memories` has no update method. TTL for generated memories is bank-level (`ttl_config.granular_ttl_config.generate_created_ttl` / `generate_updated_ttl`). So the approved design's per-topic `retentionDays`, set on write, cannot be carried by `GenerateMemories` with this SDK. One bank per domain means one retention period per domain. |
| **Verification** | Schema test: `retentionDays` above the maximum rejected (T-07). Tier 1 live: L7 (T-24), against a bank with generate TTLs, with expiry observed. |
| **Status** | Gap |
| **Evidence** | Two open items. (1) **Pending Tier 1 (L7):** whether the bank-level TTL applies, survives consolidation and expires memories. If L7 fails, the contingent exception below applies. (2) **A design defect, returned to Stage 2 (requester, 2026-10-22), and decided the same day (ADR-0004):** one retention period per domain, declared once in domain configuration and enforced by the bank's TTL, set by platform Terraform (T-39). Per-topic retention is deferred to v0.2.0. **ADR-0004 rests on L7:** if L7 fails, it is reopened, not replaced by an exception. Still OPEN: the bounds (DEC-8), and whether "retention from last write" meets Legal's definition. The bounds are still OPEN with Legal (DEC-8). |

### C-10 — Minimal network exposure

| | |
|---|---|
| **Requirement** | Internal ingress by default; public ingress requires an approved exception. |
| **Applicability** | Applies. The design adds an HTTP service on Cloud Run. |
| **Implementation** | DEC-5 (decided 2026-10-21): `INGRESS_TRAFFIC_INTERNAL_ONLY` on the Cloud Run service (T-40). No `allUsers` or `allAuthenticatedUsers` invoker: `run.invoker` is held only by the registered agent service accounts. |
| **Verification** | T-40 Terraform checks: ingress is internal-only and no public principal holds the invoker role. Checkov. Tier 2 live: L12 (T-45), before release. |
| **Status** | Implemented, not verified |
| **Evidence** | Plan only (tasks.md DEC-5, T-40). Reachability from Agent Runtime is unverified (L12, Tier 2). If L12 fails, public ingress takes the DEC-5 exception, with compensating controls: IAM-only invocation by registered agent service accounts, in-app token verification (C-01) and the per-caller rate limit (T-31). That exception would be recorded before release, not at this gate. |

### C-11 — Least-privilege IAM

| | |
|---|---|
| **Requirement** | One service account per component, least privilege, no primitive roles. Memory Bank access is granted to the Memory Manager service account only — never to an agent — constrained by IAM Conditions on scope where supported. |
| **Applicability** | Applies. The design changes `spec.cloudPermissions` and the Memory Bank binding. |
| **Implementation** | Design: one component, `api`, with `roles/logging.logWriter`, `roles/cloudtrace.agent` and `roles/monitoring.metricWriter`; the Pub/Sub and Secret Manager roles and the `worker` component are removed. The Memory Bank role is granted by platform Terraform (`memory-bank-nfr`) to the domain's Memory Manager SA only. **Recheck:** DEC-6 (decided): a custom role holding only generate, get, retrieve and delete, plus list-revisions and rollback only if T-27 is built. HMAC adds `secretAccessor`, on one secret only (C-08). |
| **Verification** | Checkov; a repository test asserting no `roles/owner`, `roles/editor` or `roles/viewer` in any module or manifest; Terraform review that no agent principal appears in a bank binding. T-39: a check that the custom role holds no permission outside the DEC-6 list. T-45 runs under that role. |
| **Status** | Implemented, not verified |
| **Evidence** | Plan only. **VERIFIED** today: `pattern.yaml` still lists Pub/Sub, `secretAccessor` and a `worker` component; T-41 removes them. The exact permission names come from the IAM permission reference, in T-39. |

### C-12 — Container hardening

| | |
|---|---|
| **Requirement** | Non-root user, pinned base image, no build secrets in any layer. |
| **Applicability** | Applies. The pattern ships a reference Dockerfile used by AC18's conformance run. The image is domain-built (ADR-0001), so the control is contractually required of adopters. |
| **Implementation** | **VERIFIED** by reading `patterns/memory-manager/examples/Dockerfile`: `USER 10001:10001`, multi-stage, base `python:3.12-slim@sha256:<BASE_IMAGE_DIGEST>` (placeholder digest), no `ARG`/`ENV` secrets. |
| **Verification** | `.github/workflows/container.yml` (Dockerfile lint and container scan) run against the built image. A test that the running container's UID is not 0. |
| **Status** | Implemented, not verified |
| **Evidence** | The Dockerfile exists, but no image has been built. The digest is a placeholder, and the container workflow did not run on PR #1 (it is not among the PR's checks). |

### C-13 — Dependencies pinned and scanned

| | |
|---|---|
| **Requirement** | Dependencies are pinned, lockfiles committed, and scanned for known vulnerabilities on every PR. |
| **Applicability** | Applies. The implementation adds the pattern's first runtime dependencies (FastAPI per ADR-0002, the `agentplatform` 2.x SDK, a JWT/JWKS library) and a `uv.lock`, which the Dockerfile already expects. |
| **Implementation** | T-05 extends the `Dependency vulnerabilities` job to audit `patterns/*/uv.lock`, in the same PR that adds the lockfile (T-02). The SDK is pinned provisionally at `google-cloud-aiplatform[agent_engines]==2.3.0` (DEC-11). |
| **Verification** | pip-audit (or equivalent) over the pattern's lockfile on every PR. |
| **Status** | Implemented, not verified |
| **Evidence** | **VERIFIED** 2026-10-22: `.github/workflows/security.yml` still audits only `scripts/requirements.txt` (`inputs: scripts/requirements.txt`). The pattern has no lockfile yet, so nothing goes unscanned today. T-05 must land with T-02. |

### C-15 — Infrastructure as code, policy-scanned

| | |
|---|---|
| **Requirement** | Infrastructure is reviewed as code and policy-scanned. No manual console changes to platform-owned resources. |
| **Applicability** | Applies. The design requires reference Terraform in `memory-bank-nfr` (platform) and `domain-runtime` (domain). This repository validates it and never applies it (CLAUDE.md rule 17). |
| **Implementation** | Both modules are reference Terraform, validated with `terraform init -backend=false` + `validate` and scanned by Checkov in CI. |
| **Verification** | `Terraform / Format and validate` and `Security / Infrastructure policy scan` passing on the PR that adds the modules. |
| **Status** | Implemented, not verified |
| **Evidence** | No module exists yet. **VERIFIED**: change 005 (merged as `107f2a6`) removed the pre-existing Checkov failure (CKV_GCP_83 in `templates/terraform-gcp/main.tf`). On PR #1 at `50c6465`, `Infrastructure policy scan` passed with `Passed checks: 1, Failed checks: 0, Skipped checks: 0` (job 119642927062). The scan can now serve as evidence for the new modules when T-39 and T-40 add them. |

### C-16 — Domain isolation

| | |
|---|---|
| **Requirement** | In a shared project, isolation is by per-domain service account and IAM Conditions on scope. One domain cannot read or write another's memory. |
| **Applicability** | Applies. ADR-0003: one platform project, one bank per domain. |
| **Implementation** | The bank resource name comes from deployment configuration, an output of platform Terraform. No request field selects it (AC14). One SA per domain, bound to that domain's bank only, with an IAM Condition on the bank resource. **Recheck:** decided 2026-10-21, with no exception. If L10 fails, use a resource-level IAM policy on the bank if the provider has one; otherwise re-enter design. |
| **Verification** | Test: no request field can change the bank. Tier 2 live: L10 (T-45), before release, with the output recorded. |
| **Status** | Implemented, not verified |
| **Evidence** | Plan only. L10 is Tier 2 and cannot run until T-39 is applied for two domains. A unit test cannot prove this control (`evidence-and-claims.md` "Managed services"); `Verified` requires the T-45 record. |

### C-17 — Bounded retry, backoff, dead-lettering, idempotency

| | |
|---|---|
| **Requirement** | Bounded retry, exponential backoff, dead-lettering and idempotency. Retry must not amplify load against a rate-limited dependency. |
| **Applicability** | Applies, except the dead-lettering clause: v0.1.0 has no queue (D1), so there is nothing to dead-letter. That clause is not applicable for this reason and returns with v0.2.0's queue. |
| **Implementation** | Write: at most 2 retries, exponential backoff with full jitter, honouring provider `Retry-After`, 10 s deadline. Read-back: 3 attempts, 5 s deadline. Each retry consumes a domain budget token, so retries cannot exceed the budget. The provider's 429 is mapped to `503 PROVIDER_UNAVAILABLE` + `Retry-After`. Idempotency: a required `Idempotency-Key` and a per-instance LRU (10 min) that replays responses or returns 422 on payload mismatch. **Recheck:** DEC-4 (decided): the cross-instance limit takes the exception below, recorded only after L5 passes. An added compensating control: Cloud Run session affinity (T-40). |
| **Verification** | Test: injected provider 429 → bounded attempts, then 503, with no further calls (fake records the count). Test: each retry consumes a budget token. Test: same key on the same instance → identical response, one provider call. Test: same key, different payload → 422. Tier 1 live: L5 (T-24). |
| **Status** | Gap |
| **Evidence** | The exception row below is **pending Tier 1 (L5)**. If L5 fails, there is no exception and the design re-enters Stage 2 (DEC-4). |

### C-18 — Required telemetry

| | |
|---|---|
| **Requirement** | Tool invocations, queue depth, retry count, dead-letter depth, provider 429s, latency percentiles, per-domain quota attribution. |
| **Applicability** | Applies. The queue-depth and dead-letter-depth metrics are not applicable, because there is no queue in v0.1.0 (D1). The design removes them from the manifest. |
| **Implementation** | Retained: `tool_invocations`, `tool_latency`, `retry_attempts`, `provider_requests`, `provider_throttled`, `quota_consumed`, `policy_denials`, `extension_errors`. Added: `facts_evaluated`, `verification_outcomes`, `remediations`, `recall_withheld`, `quota_budget_exhausted{domain}`. Labels come from closed enumerations, and topic is not a label. Quota alerting is platform Terraform. |
| **Verification** | A test asserting every manifest `requiredMetrics` entry is emitted by the AC suite. A dashboard reference in `docs/operations.md` / the runbook. |
| **Status** | Implemented, not verified |
| **Evidence** | Design only. |

### C-19 — Shared-quota contention bounded per domain

| | |
|---|---|
| **Requirement** | Shared-quota contention between domains is bounded by per-domain budgets, and cost is attributable per domain. |
| **Applicability** | Applies. ADR-0003's shared quota is the design's main stated operational risk. Every write now also costs read-back and possibly remediation calls. |
| **Implementation** | A per-domain token bucket (`domainProviderRequestsPerMinute`, schema-bounded). Every provider request takes a token. `503 DOMAIN_BUDGET_EXHAUSTED` when the bucket is empty. `quota_consumed{domain}` provides attribution. **Recheck:** one Terraform variable sets both `max_instances` and the container's `MAX_INSTANCES`. The per-instance bucket is the domain budget ÷ `MAX_INSTANCES`. A deployed instance without `MAX_INSTANCES`, or with a budget below it, refuses to start (T-09, T-22, T-40). A platform-owned per-domain quota alert (T-39). |
| **Verification** | Tests: over budget → `503` locally and no further provider calls (T-22); the bucket is budget ÷ `MAX_INSTANCES` (T-22); refusal without `MAX_INSTANCES` (T-09). Terraform check: one variable feeds both values (T-40). |
| **Status** | Gap |
| **Evidence** | The per-instance limit remains: a domain that forks its Terraform can still raise both values together. DEC-4 accepts this through the exception below. That row does **not** depend on Tier 1 and is ready for the security reviewer. |

## Non-applicable controls

| Control | Reason |
|---|---|
| C-14 | This feature produces no release artifact. Provenance and checksums attach to a published version, which is assessed on the release track by `pattern-publish` against `.github/workflows/release.yml`. This feature does not change that workflow. |

Partial non-applicability, recorded in the controls above: C-17's dead-lettering clause and C-18's
queue-depth and dead-letter-depth metrics, because v0.1.0 has no queue (D1).

## Gaps

| Control | Gap | Risk | Plan | Owner |
|---|---|---|---|---|
| C-05 | (b) Prohibited content persists between consolidation and remediation, and until the next recall when verification is incomplete. (a) is closed in the plan by DEC-3; its outcome comes from L4 | Restricted content persisted in the bank despite classification | Exception (row below), **pending Tier 1 L1–L3**. Run T-24 | Security reviewer |
| C-09 | Retention granularity decided (ADR-0004: one period per domain, bank TTL), but its enforcement is unverified (L7). Bounds OPEN (Q11) | Data kept beyond policy | Run L7 (T-24). If it fails, reopen ADR-0004. Obtain the Legal bounds | Requester + Legal + security reviewer |
| C-17 | No cross-instance idempotency or key-reuse detection | Duplicate writes; undetected key reuse | Exception (row below), **pending Tier 1 L5** | Platform architect + security reviewer |
| C-19 | Per-instance budget; a forked deployment can raise `max_instances` and `MAX_INSTANCES` together | One domain exhausting shared quota | Exception (row below); not Tier-1-dependent | Platform architect + security reviewer |

Closed by the plan since 2026-10-21, and now `Implemented, not verified`: C-06 (DEC-1), C-10 (DEC-5;
Tier 2 L12 before release), C-11 (DEC-6), C-13 (T-05), C-16 (no exception; Tier 2 L10 before release).

## Approved exceptions

| Control | Exception | Compensating control | Approver | Date | Expires |
|---|---|---|---|---|---|
| C-05 | (b) Prohibited content can persist in the bank between provider consolidation and remediation, and until the next recall when verification is incomplete. **Pending Tier 1: L1, L2, L3** | Read-back and re-classification of every touched memory (T-25); recall-time re-classification and withholding (T-33); `written_unverified`; per-domain `remediations` alert (T-39) |  |  |  |
| C-09 | **Contingent, and probably to be deleted:** ADR-0004 says an L7 failure reopens the retention decision rather than taking an exception. Kept only until the requester confirms. **Pending Tier 1: L7** | Retention disclosure in the adopting domain's runbook, and a manual purge procedure (T-43) |  |  |  |
| C-17 | No cross-instance idempotency or key-reuse detection in v0.1.0. **Pending Tier 1: L5** (if L5 fails, there is no exception: Stage 2) | Required `Idempotency-Key` and per-instance replay (T-30); bounded, budgeted retry (T-22); provider-side dedup (L5); Cloud Run session affinity (T-40) |  |  |  |
| C-19 | The per-domain budget is enforced per instance; a forked deployment can raise `max_instances` and `MAX_INSTANCES` together. Not Tier-1-dependent. **Drafted 2026-10-22 for the approver's confirmation** | Platform-owned per-domain quota alert and `quota_consumed{domain}` (T-39); one variable for `max_instances` and `MAX_INSTANCES`, with refusal to start without it (T-09, T-40) | Srinivasa reddy | 2026-10-22 | 2027-04-22 |

**Draft rows. None is approved.** The requester accepted these exceptions in principle on
2026-10-21.

- **C-05, C-09, C-17:** Approver, Date and Expires stay **deliberately empty until Tier 1 runs**
  (requester, 2026-10-22). The design-artifact validator rejects an approved assessment while any of
  the three is empty for a `Gap`. Delete the C-09 row if L7 passes and Stage 2 makes it unnecessary.
  Delete the C-17 row, and return to Stage 2, if L5 fails.
- **C-19** is filled at the requester's instruction, for confirmation. Approver and date are as
  instructed. **The expiry `2027-04-22` is PROPOSED, not given:** no v0.2.0 date or maximum exception
  length exists in the repository, so it is six months from the date. Change it if v0.2.0 has a
  target. The row takes effect only when the assessment is approved.

## Approval

Gate C. A security reviewer sets `status: approved`. CI fails an approved assessment that contains a
`Gap` with no recorded exception.

**Re-confirmation (2026-10-22 recheck) needs:**

1. **T-24's Tier 1 record.** The reviewer will not approve on a promise of evidence (2026-10-22).
2. Approver, date and calendar expiry on each exception row that applies, after Tier 1, with rows
   that do not apply deleted. C-19's row is drafted for confirmation now.
3. **The Stage 2 pass** on retention granularity (C-09), on `disable_memory_revisions` vs rollback
   (C-05 (a)), and on **O6**. design.md is re-approved at the end of it (design.md "Approval").
4. Decided 2026-10-22: the tier split itself needs no Gate B re-approval.

D3 and Q5 are now decided (DEC-3; the C-05 (b) exception). Live verification is no longer a single
precondition: Tier 1 precedes this gate, and Tier 2 precedes release (T-45).
