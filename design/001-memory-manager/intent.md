---
artifact: intent
feature: 001-memory-manager
track: full
status: draft
related_adrs: [ADR-0001, ADR-0003]
patterns_touched: [memory-manager]
---

# Intent — Domain Memory Manager (Pattern 001)

> **Stage 1, `status: draft`.** Awaiting **Gate A**. Created as part of the foundation so that
> Pattern 001 has a home; the content below is a starting point derived from the supplied diagram and
> the foundation assessment, **not** an approved intent.

## Method

Derived on 2026-10-20 from: the supplied `[Container] Domain Memory Manager` diagram (screenshot,
transcribed in `design/000-platform-foundation/intent.md` §1.3); the prior-art repository
`geap-memory` (read on 2026-10-20, in particular `docs/vertex-memory-bank.md` and
`docs/memory-bank-assumption-validation.md`); and ADR-0001 and ADR-0003.

## Business objective

Give agent teams one governed way to store and retrieve customer memory, owned and operated by the
domain that owns the data and its rules, without each agent team reimplementing authorization,
privacy classification, rate-limit handling or audit.

## Requester and stakeholders

| Role | Who |
|---|---|
| Requester | Platform team (project owner) |
| Platform lead | `OPEN` |
| Affected domains | Customer first; Inventory on onboarding |
| Affected agent teams | Agents integrating with the Customer domain |

## Reusable or domain-specific

| | |
|---|---|
| Classification | `reusable-pattern` |
| Patterns touched | `memory-manager` |
| Contracts touched | New: the tool API (`v1`) |

Reusable. The three behaviours the diagram places inside the worker — entity resolution, PII
stripping, fact curation — are **domain** behaviour and are declared as extension points, not
platform code.

## Scope

1. Tool endpoints: `remember`, `recall`, `list`, `correct`, `forget`, with per-caller rate limiting.
2. Domain policy and RBAC driven by versioned configuration.
3. Asynchronous write processing, with classification, entity resolution and curation at declared
   extension points.
4. A retry queue for over-limit and failed writes, with bounded retry, backoff and dead-lettering.
5. A Memory Bank integration boundary.
6. Observability: structured logs, traces, the required metrics, and audit events.
7. Reference deployment Terraform, split platform-owned and domain-owned.
8. A consumer-runnable conformance suite.

## Non-goals

- The platform operating any domain's runtime (ADR-0001).
- Any business-domain rule in `src/` — households, consent semantics, category vocabularies.
- An MCP interface in v1 — declared `planned`.
- Managed provider-side memory extraction. The prior art turned it off deliberately
  (**VERIFIED**, MB-05: *"provider extraction stores ungoverned memories"*); this pattern stores only
  governed writes.
- An admin console.
- Multi-cloud support.

## Acceptance criteria

1. An authenticated caller with a write role can `remember` a value and receive `202`; the value is
   retrievable by `recall` in a later session.
2. `202` is returned only when the write is **durably enqueued**; an enqueue failure returns `503`.
3. A duplicate `remember` with the same `Idempotency-Key` produces exactly one stored effect.
4. A read-only role attempting a write receives `403`; no value is stored.
5. A caller from one domain cannot read or write another domain's memory.
6. With no `pii-classifier` configured, the default denies and nothing is stored.
7. An extension that raises becomes a denial plus an `extension_errors` metric, never a bypass.
8. Provider throttling results in the write being parked and retried with backoff — not a hot loop,
   and not an error to the caller.
9. A write exhausting its attempts lands in the dead-letter queue and is inspectable and replayable.
10. No log, trace attribute or error response contains memory content, PII or secrets, asserted by a
    test that fails if the redaction is removed.
11. Every memory write, deletion and policy denial emits an audit event with a correlation ID.
12. A domain can be supported by configuration alone, with no change to `src/`.
13. The conformance suite runs against a built image and passes.
14. `max_writes_per_minute` is enforced per domain, and `quota_consumed` is attributable per domain.

## Constraints and dependencies

- **Shared quota** (ADR-0003): per project, per region, across every domain. Separate banks do not
  separate quota. Writes consume read quota (**VERIFIED**).
- **No field-level profile update** in Memory Bank; the prior art stores append-only typed JSON facts
  with a write counter (**VERIFIED**).
- **Eventually consistent reads** (**VERIFIED**) — bounds any read-back-based idempotency check.
- Deployment is Cloud Run in the platform-owned project.
- Platform-owned Terraform must provision the bank, its IAM binding, the audit sink and quota
  alerting before a domain can deploy.

## Open questions

| ID | Question | Blocks | Who decides |
|---|---|---|---|
| Q1 | Is the memory bank boundary **per domain** (ADR-0003) or **per agent** (as the diagram labels it)? | NFR Terraform, isolation model | Diagram author + platform lead |
| Q2 | Is the agent's direct `recall` path to the bank retained? It consumes shared quota and is ungoverned by this service's limiter. | Quota strategy, `C-16` | Platform lead |
| Q3 | Worker shape: Cloud Run service with a pull subscription, or Jobs for batch replay? | Deployment Terraform | Design |
| Q4 | Idempotency mechanism: key stored in-fact and checked during the worker's existing pre-read, or a dedicated dedupe store? Eventual consistency bounds the first. | Contract, `C-17` | Design, with provider validation |
| Q5 | Per-domain quota budgets: static configuration or dynamic from observed project headroom? | Config schema | Platform lead |
| Q6 | Is `correct` a distinct operation or `remember` with a prior-version reference? | Contract | Design |
| Q7 | Retention bounds — the prior art's values are placeholders pending Legal (**VERIFIED**). | Config schema | Legal + platform lead |
| Q8 | Which caller identity model: Google-signed ID token, matching the prior art? | `C-01` | Platform lead |

## Assumptions

- **ASSUMPTION** — "Memory Bank" is Vertex AI / Gemini Enterprise Agent Platform Memory Bank on the
  `agentplatform` 2.x surface, as the prior art uses (**VERIFIED** as its choice, exercised live).
- **ASSUMPTION** — the transcribed diagram accurately reflects intent. It is labelled *Proposed* and
  its author has not confirmed the transcription (Q1 is one consequence).

## Approval

**Gate A.** Not approved. A human sets `status: approved` with `approved_by` and `approved_date`
after reviewing scope, non-goals and acceptance criteria — and after resolving, or explicitly
deferring, Q1.
