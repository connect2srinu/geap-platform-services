---
artifact: intent
feature: 001-memory-manager
track: full
status: approved
approved_by: Srinivasa reddy
approved_date: 2026-10-21
related_adrs: [ADR-0001, ADR-0003]
patterns_touched: [memory-manager]
---

# Intent — Memory Manager v0.1.0: a governed write path for agent memory

> Stage 1. Approval at **Gate A** is required before design work begins, and before any remote
> branch or pull request is created.

## Method

Rewritten on 2026-10-21 from the requester's v0.1.0 scope statement, which replaces the earlier draft
of this file (broader tool surface: `remember`/`recall`/`list`/`correct`/`forget`, async queue).
Read for context on `main` at `69eee1b`:

- `docs/decisions/ADR-0001-published-pattern-model.md`, `ADR-0003-shared-platform-gcp-project.md`
  (Accepted, 2026-10-20).
- `standards/security.md` — controls C-01, C-02, C-05, C-16, C-17.
- `patterns/memory-manager/pattern.yaml` and `config/example.domain.yaml` (status `proposed`).
- Prior art `../geap-memory`: `docs/vertex-memory-bank.md`, `docs/memory-bank-assumption-validation.md`,
  `apps/control-plane-api/app/control_plane_api/integrations/vertex_memory_store.py`.

## Business objective

Give agents one governed way to persist memory about the users they serve: only facts on approved,
non-sensitive topics are ever stored, ownership is decided by the platform rather than the caller,
and anything the memory provider later rewrites into prohibited content is caught and removed. Agent
teams get this without each reimplementing authorization, topic governance, sensitivity
classification or audit; domains control what is eligible through configuration.

## Requester and stakeholders

| Role | Who |
|---|---|
| Requester | Platform team — connect2srinu (project owner) |
| Platform lead | connect2srinu |
| Affected domains | First consuming domain on onboarding; the pattern is domain-neutral |
| Affected agent teams | Agents that write or recall user memory through this pattern |

## Reusable or domain-specific

| | |
|---|---|
| Classification | `reusable-pattern` |
| Patterns touched | `memory-manager` (first version, `0.1.0`) |
| Contracts touched | New: the tool API `v1` — write and recall operations only |

Reusable. The *obligations* — authenticate, authorize, resolve ownership server-side, validate,
classify, verify after write, audit — are platform. *Which* topics exist, their sensitivity and their
eligibility are domain configuration, supplied through a `topic-provider` extension point whose
default reads versioned YAML.

**Full track** — a new contract, a new extension point (`topic-provider`) and a new managed-service
call (`GenerateMemories`) each independently rule out the light track.

## Scope

1. **Authenticated write of already-structured facts.** An agent submits facts; it does not submit
   raw user messages.
2. **Identity-derived authorization.** The agent's permissions come from its authenticated identity,
   never from the request.
3. **Server-side ownership.** The user and the owning memory scope are resolved server-side. Any
   user, scope or role value in the request body has no effect on where a fact is written.
4. **Topic eligibility.** The agent's approved topic configuration is loaded; only topics that are
   approved for that agent, enabled, and classified non-sensitive are eligible. Sensitive,
   restricted and unknown topics are excluded.
5. **Per-fact validation** before any write: topic, field, value type, sensitivity and ownership.
   A fact is rejected if it is an unsupported inference, or if its value carries prohibited
   information even though it is labelled with an allowed topic.
6. **Provider write.** Approved facts are written with `GenerateMemories` using
   `direct_memories_source` — no provider-side extraction.
7. **No-op on nothing eligible.** A request in which no fact qualifies returns a no-op result, not an
   error, and makes no provider write.
8. **Post-write verification.** Because consolidation can rewrite a fact after validation, each write
   is followed by reading back the consolidated memories in the scope, re-running the sensitivity
   classifier, and deleting and auditing any memory that now carries prohibited content. This
   deletion is internal; it is not the `forget` tool operation.
9. **Recall** for the same server-resolved scope, so that a write can be proven.
10. **Topic configuration as versioned YAML** behind a `topic-provider` extension point.
11. Audit events, structured logs, traces and metrics for the above; a consumer-runnable conformance
    suite.

### Reference topic configuration

Classification drives eligibility. This is the shape of the **example** configuration shipped with
the pattern — it lives in `config/`, never in `src/`:

| Topic | Classification | Extraction | Eligible in v0.1.0 |
|---|---|---|---|
| `preferred_brands` | non-sensitive | allowed | yes |
| `preferred_cuisines` | non-sensitive | allowed | yes |
| `medical_conditions` | sensitive | blocked | no |
| `prescription_details` | restricted | blocked | no |

The `extraction` flag is declared now so the shape is stable for v0.2.0; nothing in v0.1.0 acts on
it.

## Non-goals

- **Gemini extraction from raw user messages** — v0.2.0.
- **A configuration database.** Topics are versioned YAML behind the `topic-provider` extension point.
- **`correct`, `forget` and `list` tool operations.**
- **MCP** — remains `planned`.
- **Provider-side extraction** in any form. Only `direct_memories_source` is used.
- The platform operating any domain's runtime (ADR-0001).
- Any business-domain rule in `src/` — topic names and their classification are configuration.

## Acceptance criteria

1. An unauthenticated request receives `401`; nothing is written (C-01).
2. An authenticated agent whose identity carries no write permission receives `403`; nothing is
   written (C-02).
3. A request whose body names a different user, scope or role writes only to the server-resolved
   scope; the body value has no effect, asserted by a test that reads both scopes.
4. A fact on a topic that is sensitive, restricted, unknown, disabled, or not approved for the
   calling agent is excluded and not written. One test per case, using the reference configuration.
5. A fact with an unknown field or a value of the wrong type for its topic is rejected and not
   written.
6. A fact labelled with an eligible topic whose value the classifier marks prohibited — for example a
   medical condition submitted as `preferred_brands` — is rejected and not written.
7. A fact identified as an unsupported inference is rejected and not written. *Testable once Q3
   defines "unsupported inference".*
8. If the classifier or the `topic-provider` errors or is unconfigured, the affected facts are denied,
   never written (fail closed).
9. Approved facts reach the provider only through `GenerateMemories` with `direct_memories_source`.
   A unit test against a fake client asserts the call shape and that no extraction source is
   ever sent; a separately labelled live test confirms it against Memory Bank.
10. A request with no eligible facts returns a no-op result with a success status, and the provider
    receives no write call.
11. When consolidation rewrites a stored memory into prohibited content, post-write verification
    deletes that memory and emits an audit event; asserted with a fake provider that rewrites on
    consolidation.
12. When post-write verification cannot complete, the write is never reported as verified, and the
    outcome follows the policy chosen in Q7.
13. A fact written by an agent is returned by `recall` for the same scope within bound *N*; *N* is
    set in `design.md` and validated live against the provider (reads are eventually consistent).
14. An agent cannot write to or recall from another domain's memory (C-16, per-domain bank).
15. No log, trace attribute or error response contains a fact value, PII or secret, asserted by a
    test that fails if the redaction is removed. Logs carry topic *names*, decisions and reason codes.
16. Every write, every rejection and every post-write deletion emits an audit event with a
    correlation ID and a reason code, and no value.
17. A new domain with its own topic set is supported by YAML configuration alone, with no change to
    `src/`.
18. The conformance suite runs against a built image and passes.

## Constraints and dependencies

- **Per-domain memory bank** in one platform-owned project (ADR-0003, **VERIFIED** — Accepted
  2026-10-20). Isolation is per-domain service account plus IAM Conditions on bank scope.
- **Shared quota** across all domains in the project (ADR-0003). Every write now also costs a
  read-back for verification, so a write consumes more read quota than in the prior art.
- **Eventually consistent reads** (**VERIFIED** in prior art, `docs/vertex-memory-bank.md`). This
  bounds both recall-after-write (AC13) and post-write verification (Q5, Q7).
- **Departure from prior art.** The prior art never calls `GenerateMemories`; it writes with a direct
  `create` so that no provider consolidation runs (**VERIFIED**, `vertex_memory_store.py:195`;
  MB-05 in `memory-bank-assumption-validation.md`). This intent deliberately accepts consolidation
  and compensates with post-write verification. See Q4.
- **Manifest changes required**, to be made in design, not here: add a `topic-provider` extension
  point; reconsider `entity-resolver` `failureMode: skip`, which would be wrong if ownership
  resolution runs through it; reconcile queue metrics and Pub/Sub roles with Q8; set the interface
  scope to write and recall.
- Deployment is Cloud Run in the platform-owned project. Platform-owned Terraform provisions the bank,
  its IAM binding, the audit sink and quota alerting before a domain deploys.

## Resolved during intent

| ID | Question | Resolution |
|---|---|---|
| R1 | Is the memory bank per domain or per agent? | **Per domain**, by accepted ADR-0003. The diagram's "one per agent" label diverges; the diagram author is asked to confirm, but the decision stands unless ADR-0003 is superseded. |
| R2 | Caller identity model? | **Google-signed ID token** mapped to exactly one registered caller — already mandated by `standards/security.md` C-01. |

## Open questions

| ID | Question | Blocks | Who decides |
|---|---|---|---|
| Q2 | Where does the server-side user identity come from — an ID-token claim, a session lookup, or the `entity-resolver` extension? If an extension, its failure must deny, not skip. | AC3, contract, manifest | Platform architect |
| Q3 | What is an "unsupported inference", and what detects it — the classifier extension, a rule in topic configuration, or both? | AC7 | Platform lead + first domain |
| Q4 | Is provider consolidation wanted for its own sake (deduplication, merging), justifying `GenerateMemories` over the prior art's direct `create`? Record as an ADR in design. | Scope 6, AC9 | Platform architect |
| Q5 | Between consolidation and post-write deletion, prohibited content exists in the bank and could be recalled. Is that window acceptable, or must `recall` also re-classify before returning? | AC11, AC13, C-05 | Security reviewer |
| Q6 | Consolidation can merge a new fact into an existing memory. Deleting the merged memory may remove previously valid content. Delete, quarantine, or restore? | AC11 | Platform architect + security reviewer |
| Q7 | When verification cannot complete — read-back fails, or the consolidated result is not yet visible — retry, quarantine, or alert? | AC12 | Platform architect |
| Q8 | Are rate limiting, async processing, retry with backoff, idempotency and dead-lettering in v0.1.0? The earlier draft scoped them; this scope neither includes nor excludes them. C-17 and the shared quota apply either way. | Contract, manifest, Terraform | Platform lead |
| Q9 | Read-after-write bound *N* for AC13. Deferred to design by the requester. | AC13 | Design, validated live |
| Q10 | Should `recall` return only topics the calling agent is approved for, or everything in the scope? | Recall contract | Platform lead |
| Q11 | Retention bounds — the prior art's values are placeholders pending Legal (**VERIFIED**). | Config schema | Legal + platform lead |

## Assumptions

- **ASSUMPTION** — `GenerateMemories` with `direct_memories_source` stores the supplied facts without
  extraction but still runs consolidation. This is the premise of post-write verification; it is not
  yet verified live and must be before Gate C.
- **ASSUMPTION** — "Memory Bank" is Vertex AI / Gemini Enterprise Agent Platform Memory Bank on the
  `agentplatform` 2.x surface, as the prior art uses (**VERIFIED** as its choice).
- **ASSUMPTION** — the sensitivity classifier used before the write and the one used after it are the
  same `pii-classifier` extension, so the two decisions cannot disagree by construction.

## Approval

**Gate A.** Not approved. A human sets `status: approved` with `approved_by` and `approved_date`
after reviewing scope, non-goals and acceptance criteria. Q3 may be deferred to design, but AC7 is
not testable until it is answered.
