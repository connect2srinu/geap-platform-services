---
artifact: controls-check
feature: 001-memory-manager
track: full
status: approved
approved_by: Srinivasa reddy
approved_date: 2026-10-21
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

**Not done:** no call to a live Memory Bank. See the precondition below.

## Precondition not met — live verification

The approved design's section "Live verification required before Gate C" lists L1–L10, and the
intent requires L1 before Gate C. **VERIFIED**: no record of any live run exists in the design
folder or the repository. C-05, C-09, C-16 and C-17 rest on L1, L4, L5, L7 and L10. The security
reviewer decides whether Gate C can be approved with these outstanding, or must wait for them. This
assessment does not assume their outcome.

## Summary

| Status | Count |
|---|---|
| Verified | 0 |
| Implemented, not verified | 9 |
| Gap | 9 |
| Not applicable | 1 |
| Exception approved | 0 |

Total 19. Gaps: C-05, C-06, C-09, C-10, C-11, C-13, C-16, C-17, C-19.

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
| **Implementation** | Design: `src/api` verifies the agent ID token (audience = service URL) and maps it to exactly one entry in the new `callers[]` configuration. Otherwise `401 UNAUTHENTICATED` or `403 CALLER_NOT_REGISTERED`. `X-End-User-Token` is verified against `endUserIdentity` (issuer, JWKS, audiences, expiry). JWKS is cached with a bounded TTL and there is no fallback to unsigned tokens (`401 END_USER_TOKEN_INVALID`). The design has no development header shortcut. The fake provider is permitted only with `environment: local`. `/healthz` is unauthenticated and reveals nothing. Requirements from this assessment: `endUserIdentity` is required in the schema; `environment: local` is refused on Cloud Run. |
| **Verification** | Unit/conformance tests: no token → 401; wrong audience → 401; valid token, unregistered principal → 403; token mapping to two callers rejected at configuration load; end-user token expired / wrong issuer / wrong audience / bad signature / `alg: none` → 401; JWKS unreachable after cache expiry → 401; `environment: local` with `K_SERVICE` set → startup refusal; configuration without `endUserIdentity` → schema rejection. |
| **Status** | Implemented, not verified |
| **Evidence** | Design only (`design.md` "Request headers", "Failure handling"). No code, no tests. |

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
| **Implementation** | Before write: per-fact topic eligibility + field schema + `basis` rule + `pii-classifier` (default `deny-all`, failure `deny`). After write: every created or updated memory is read back and re-classified by the same instance, then rolled back if the prior revision is clean, otherwise deleted (D3). At recall: re-classified and withheld on failure. |
| **Verification** | Test: default classifier → nothing written. Test: classifier raises → fact rejected. AC6 test (prohibited value on an eligible topic). AC11 test with a fake provider that rewrites on consolidation. Test: recall withholds a prohibited memory. Live: L1, L4, L6. |
| **Status** | Gap |
| **Evidence** | Two gaps in the design, neither covered by an approved exception: **(a)** *Rolled-back content persists in revision history.* Rollback (D3) restores a prior revision, but the prohibited revision presumably stays listable through the revisions API. That means prohibited content stays persisted in the bank. The design does not say whether revisions can be purged, and L4 does not test for it. **(b)** *A window of persistence.* Prohibited content exists in the bank between consolidation and remediation. When verification is incomplete (D5), it stays there until the next recall of that scope. Recall-time withholding stops it being *returned*, but not *persisted*. The reviewer must decide whether (b) is acceptable, which is Q5 at Gate C. |

### C-06 — Logging restrictions

| | |
|---|---|
| **Requirement** | Memory content, PII, secrets and full auth headers never reach logs, traces or error responses. |
| **Applicability** | Applies. New logs, spans, audit events, error bodies, and a new secret-like header (`X-End-User-Token`). |
| **Implementation** | Design: logs carry topic name, decision, reason code and counts. Never a value, the fact string, the subject or either token. Span attributes follow the prohibited-field list. Errors are `{code, message, correlation_id}` with no payload content. Responses never echo a value. `end_user_token` is added to `prohibitedLogFields`. Sentinel test across logs, spans, audit and error bodies (AC15). Requirement from this assessment: FastAPI's default `RequestValidationError` response includes the offending `input` value, so it must be replaced by the `400 REQUEST_INVALID` handler, and the sentinel suite must include a schema-invalid request carrying a sentinel. The same applies to provider exception text (`provider_error_body`). |
| **Verification** | AC15 sentinel test, failing if redaction is removed; it includes schema-invalid requests, classifier errors and provider errors. A test that `logLevel: DEBUG` emits no sentinel. |
| **Status** | Gap |
| **Evidence** | Internal contradiction in the approved design: "Observability → Logs" says never log "the subject". But "Audit events" carries the **scope identifier** with every event, and under the default `subject-passthrough` resolver the scope identifier **is** the token subject: the end user's identifier at the identity provider. The audit sink is Cloud Logging. Whether an end-user identifier may appear in the audit sink — raw, pseudonymised (for example HMAC with a key from Secret Manager), or not at all — is a reviewer decision. It is not recorded anywhere. |

### C-07 — Audit completeness

| | |
|---|---|
| **Requirement** | Every memory write, deletion, denial and policy decision emits an audit event with a correlation ID to the platform audit sink. |
| **Applicability** | Applies. |
| **Implementation** | Design "Audit events" table: `memory_write` (per touched memory; `written`/`unknown`), `policy_denial` (request-level and per rejected fact), `memory_rollback`, `memory_deletion`, `verification_incomplete`, `remediation_failed`, `recall_withheld`, `configuration_change`. The sink is platform-owned Terraform in `infrastructure/terraform/memory-bank-nfr` (**VERIFIED**: empty today). The manifest's `requiredAuditEvents` is extended. **Not specified by the design, carried here as an implementation requirement:** what happens when audit emission itself fails. To fail closed, a write whose `memory_write` event cannot be emitted must not be reported as `written`. If emission goes to stdout and the sink routes it by log name, the emitting path and its failure semantics must be stated in the implementation plan. |
| **Verification** | One test per event type, with correlation ID and reason code present and the sentinel absent (AC16). Terraform review: the sink filter matches the dedicated log name, and the domain's SA cannot modify the sink. |
| **Status** | Implemented, not verified |
| **Evidence** | Design only. |

### C-08 — Secret handling

| | |
|---|---|
| **Requirement** | Secrets are referenced by name and resolved from Secret Manager at runtime. Never in source, images, Terraform variables, logs or committed `.env`. |
| **Applicability** | Applies. The design removes the manifest's `MEMORY_BANK_CREDENTIALS` secret in favour of Workload Identity. The end-user token is a credential handled in transit. |
| **Implementation** | Design: Workload Identity for the provider; `spec.secrets` emptied; `roles/secretmanager.secretAccessor` removed. The JWKS is public and needs no secret. The end-user token is never logged (C-06). If C-06 chooses HMAC pseudonymisation, that key becomes a Secret Manager secret and the secret access role returns, scoped to that one secret. |
| **Verification** | CI secret scanning (gitleaks) on every PR; a repository test forbidding credential-shaped literals; manifest review that `spec.secrets` holds no provider credential. |
| **Status** | Implemented, not verified |
| **Evidence** | **VERIFIED** failure: PR #1's `Secret scanning` job (run 39695758417) failed with `403 Resource not accessible by integration` on `GET /repos/.../pulls/1/commits`. gitleaks did not scan, so this produced **no evidence**. It is a workflow permissions defect in `.github/workflows/security.yml`, which grants only `contents: read`. It is unrelated to this feature and reported, not fixed (CLAUDE.md rule 11). |

### C-09 — Classification and retention declared and enforced

| | |
|---|---|
| **Requirement** | Data classification and retention are declared in configuration, and retention is enforced. |
| **Applicability** | Applies. The design adds per-topic `classification` and `retentionDays`. |
| **Implementation** | Per-topic `retentionDays`, bounded by a platform maximum in the schema. Enforcement uses a per-memory provider TTL set on write. |
| **Verification** | Schema test: `retentionDays` above the maximum rejected. Fake-client test: the TTL is sent on every write. Live: L7, and expiry observed. |
| **Status** | Gap |
| **Evidence** | Enforcement depends on L7 (provider TTL on direct memories), which is **ASSUMPTION** and unverified. The bound values are **OPEN** pending Legal (Q11). The design states that C-09 becomes a declared Gap if no TTL is available. Also unspecified: whether consolidation updating a memory resets, keeps or drops its TTL. |

### C-10 — Minimal network exposure

| | |
|---|---|
| **Requirement** | Internal ingress by default; public ingress requires an approved exception. |
| **Applicability** | Applies. The design adds an HTTP service on Cloud Run. |
| **Implementation** | **Not specified in the approved design.** The container view shows agents on "Cloud Run / Agent Runtime" calling the service, but no ingress setting is stated. |
| **Verification** | Checkov on `infrastructure/terraform/domain-runtime`; a Terraform test asserting `ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"` (or internal + load balancer) on the service. |
| **Status** | Gap |
| **Evidence** | The design is silent. It also matters whether an agent on Agent Runtime can reach an internal-only Cloud Run service (for example through Private Service Connect or VPC egress). If not, public ingress needs an exception. Open question for the platform architect and security reviewer. |

### C-11 — Least-privilege IAM

| | |
|---|---|
| **Requirement** | One service account per component, least privilege, no primitive roles. Memory Bank access is granted to the Memory Manager service account only — never to an agent — constrained by IAM Conditions on scope where supported. |
| **Applicability** | Applies. The design changes `spec.cloudPermissions` and the Memory Bank binding. |
| **Implementation** | Design: one component, `api`, with `roles/logging.logWriter`, `roles/cloudtrace.agent` and `roles/monitoring.metricWriter`; the Pub/Sub and Secret Manager roles and the `worker` component are removed. The Memory Bank role is granted by platform Terraform (`memory-bank-nfr`) to the domain's Memory Manager SA only. |
| **Verification** | Checkov; a repository test asserting no `roles/owner`, `roles/editor` or `roles/viewer` in any module or manifest; Terraform review that no agent principal appears in a bank binding. |
| **Status** | Gap |
| **Evidence** | The Memory Bank role is **OPEN** (O3), and the design defers it to this gate. This assessment does not invent one. Predefined roles such as `roles/aiplatform.user` grant far more than memory operations (**ASSUMPTION** — confirm against current IAM docs). The likely least-privilege answer is a custom role holding only the memory permissions the design uses: generate, get, list revisions, rollback, delete, retrieve. Needs an owner and a decision. **VERIFIED** today: `pattern.yaml` still lists Pub/Sub, `secretAccessor` and a `worker` component; the design removes them. |

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
| **Implementation** | Design: `spec.compatibility.memoryBankSdk` pinned to the range verified live. |
| **Verification** | pip-audit (or equivalent) over the pattern's lockfile on every PR. |
| **Status** | Gap |
| **Evidence** | **VERIFIED**: the `Dependency vulnerabilities` job in `.github/workflows/security.yml` audits only `scripts/requirements.txt`, so pattern dependencies would not be scanned. Extending that job to cover `patterns/*/uv.lock` is in scope for this feature, because this feature introduces the dependencies. It must be a task in `tasks.md`. |

### C-15 — Infrastructure as code, policy-scanned

| | |
|---|---|
| **Requirement** | Infrastructure is reviewed as code and policy-scanned. No manual console changes to platform-owned resources. |
| **Applicability** | Applies. The design requires reference Terraform in `memory-bank-nfr` (platform) and `domain-runtime` (domain). This repository validates it and never applies it (CLAUDE.md rule 17). |
| **Implementation** | Both modules are reference Terraform, validated with `terraform init -backend=false` + `validate` and scanned by Checkov in CI. |
| **Verification** | `Terraform / Format and validate` and `Security / Infrastructure policy scan` passing on the PR that adds the modules. |
| **Status** | Implemented, not verified |
| **Evidence** | No module exists yet. **VERIFIED**: on PR #1, `Infrastructure policy scan` is currently **failing** on pre-existing `templates/terraform-gcp/main.tf` (CKV_GCP_83, CSEK on `google_pubsub_topic.writes` / `.dead_letter`). That code is outside this feature and is reported, not fixed. While it fails, the scan cannot serve as evidence for the new modules. |

### C-16 — Domain isolation

| | |
|---|---|
| **Requirement** | In a shared project, isolation is by per-domain service account and IAM Conditions on scope. One domain cannot read or write another's memory. |
| **Applicability** | Applies. ADR-0003: one platform project, one bank per domain. |
| **Implementation** | The bank resource name comes from deployment configuration, an output of platform Terraform. No request field selects it (AC14). One SA per domain, bound to that domain's bank only, with an IAM Condition on the bank resource. |
| **Verification** | Test: no request field can change the bank. Live: domain A's SA is denied on domain B's bank (L10), with the output recorded. |
| **Status** | Gap |
| **Evidence** | Isolation rests on L10 (whether an IAM Condition can restrict an SA to one bank), which is **unverified**. If L10 is false, the design says isolation rests on SA separation alone and the security reviewer decides. That decision has not been made. A unit test cannot prove this control (`evidence-and-claims.md` "Managed services"). |

### C-17 — Bounded retry, backoff, dead-lettering, idempotency

| | |
|---|---|
| **Requirement** | Bounded retry, exponential backoff, dead-lettering and idempotency. Retry must not amplify load against a rate-limited dependency. |
| **Applicability** | Applies, except the dead-lettering clause: v0.1.0 has no queue (D1), so there is nothing to dead-letter. That clause is not applicable for this reason and returns with v0.2.0's queue. |
| **Implementation** | Write: at most 2 retries, exponential backoff with full jitter, honouring provider `Retry-After`, 10 s deadline. Read-back: 3 attempts, 5 s deadline. Each retry consumes a domain budget token, so retries cannot exceed the budget. The provider's 429 is mapped to `503 PROVIDER_UNAVAILABLE` + `Retry-After`. Idempotency: a required `Idempotency-Key` and a per-instance LRU (10 min) that replays responses or returns 422 on payload mismatch. |
| **Verification** | Test: injected provider 429 → bounded attempts, then 503, with no further calls (fake records the count). Test: each retry consumes a budget token. Test: same key on the same instance → identical response, one provider call. Test: same key, different payload → 422. Live: L5. |
| **Status** | Gap |
| **Evidence** | Idempotency across instances is **not guaranteed** (design O1). A duplicate on a different instance relies on provider consolidation deduplicating it (L5, unverified), and a reused key with a different payload is not detected. The design offered two options: an exception with expiry v0.2.0, or a shared store, which means returning to Stage 1. **The Gate B approval commit (`32174bb`) changed only front matter and records no decision on O1.** No exception has been given to this assessment, so none is recorded. |

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
| **Implementation** | A per-domain token bucket (`domainProviderRequestsPerMinute`, schema-bounded). Every provider request takes a token. `503 DOMAIN_BUDGET_EXHAUSTED` when the bucket is empty. `quota_consumed{domain}` provides attribution. |
| **Verification** | Test: a domain over budget gets 503 locally and the fake provider sees no further calls. Terraform review: `max_instances` is set and the per-instance budget is the domain budget ÷ `max_instances`. |
| **Status** | Gap |
| **Evidence** | The governor is **per instance** (design O2). The effective ceiling is budget × live instances, bounded only if `max_instances` is set and the division is done correctly. A domain could raise `max_instances` in its own Terraform (domain-owned) and so exceed its share of the shared quota. Whether that bound is acceptable depends on the same decision as O1, which is not recorded. Quota *alerting* is platform-owned and survives a fork; the *budget* does not. |

## Non-applicable controls

| Control | Reason |
|---|---|
| C-14 | This feature produces no release artifact. Provenance and checksums attach to a published version, which is assessed on the release track by `pattern-publish` against `.github/workflows/release.yml`. This feature does not change that workflow. |

Partial non-applicability, recorded in the controls above: C-17's dead-lettering clause and C-18's
queue-depth and dead-letter-depth metrics, because v0.1.0 has no queue (D1).

## Gaps

| Control | Gap | Risk | Plan | Owner |
|---|---|---|---|---|
| C-05 | (a) Rolled-back prohibited revision stays in revision history; (b) prohibited content persists between consolidation and remediation, indefinitely when verification is incomplete | Restricted content (for example health data) persisted in the bank despite classification | Add to L4: can a revision be purged, and does delete remove all revisions? If revisions can't be purged, prefer delete over rollback for prohibited content. Reviewer decides on (b) (Q5) | Security reviewer + platform architect |
| C-06 | Audit events carry the scope identifier, which by default is the end user's token subject | End-user identifier in Cloud Logging | Decide: raw, pseudonymised (HMAC, key in Secret Manager), or omitted; amend design if changed | Security reviewer |
| C-09 | Retention enforcement depends on unverified provider TTL (L7); bounds OPEN (Q11); TTL behaviour on consolidation unknown | Data kept beyond policy | Run L7; obtain Legal bounds; if no TTL, a scheduled deletion path means returning to design | Platform lead + Legal |
| C-10 | Ingress not specified; reachability from Agent Runtime to an internal-only service unknown | Public exposure of the memory API | Specify ingress in the design / `domain-runtime` Terraform; confirm reachability; exception if public ingress is unavoidable | Platform architect + security reviewer |
| C-11 | Memory Bank IAM role undecided (O3) | Over-broad role on the SA | Select the narrowest role (likely custom) from the memory permissions the design uses; record it in `memory-bank-nfr` | Platform architect + security reviewer |
| C-13 | CI dependency scan covers only `scripts/requirements.txt` | Vulnerable pattern dependency ships unscanned | Task in `tasks.md`: extend the scan to the pattern lockfile in the same PR that adds it | Platform lead |
| C-16 | IAM Condition per bank unverified (L10) | One domain's SA reaching another's bank | Run L10 live and record the output; if false, reviewer decides whether SA separation alone suffices | Security reviewer |
| C-17 | No cross-instance idempotency (O1); reliance on consolidation dedup (L5) unverified | Duplicate writes; undetected key reuse | Run L5; then either an exception with expiry at v0.2.0 or a shared store (return to Stage 1) | Platform architect |
| C-19 | Per-instance budget; domain-owned `max_instances` can exceed share | One domain exhausting shared quota | Same decision as O1; consider a platform-owned max-instance constraint or a platform-side quota alert with a paging threshold | Platform architect |

## Approved exceptions

| Control | Exception | Compensating control | Approver | Date | Expires |
|---|---|---|---|---|---|

None. No exception was given to this assessment.

## Approval

Gate C. A security reviewer sets `status: approved`. CI fails an approved assessment that contains a
`Gap` with no recorded exception.

Decisions this gate needs, beyond the gaps table: **O6** (the `policy-provider` default relaxed to
`passthrough`), **D3** (rollback-else-delete, in light of C-05 (a)), **Q5** (the persistence
window), and whether Gate C can proceed before live verification L1–L10.
