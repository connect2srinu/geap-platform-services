# ADR-0003: Single platform-owned GCP project with per-domain memory banks

- **Status:** Accepted
- **Date:** 2026-10-20
- **Decision owners:** Project owner (platform team)
- **Scope:** Cloud topology, isolation model and quota management for memory patterns
- **Related:** ADR-0001, `standards/architecture.md`

## Context

ADR-0001 moves implementation and deployment ownership to domain teams, which weakens enforcement.
Where the memory banks live determines whether the platform retains **any** hard technical control.

The supplied diagram assigns bank provisioning, the "IAM: only Memory Manager" binding, the central
audit sink and quota alerting to the platform ("Memory Bank NFRs — platform capability"), while
"teams deploy independently" suggested domain-owned projects. That tension needed resolving.

The project owner decided on 2026-10-20: **a single GCP project, owned by the platform team**, hosts
every domain's memory banks and the domain-deployed services. The Customer domain creates its own bank
in it; Inventory creates a separate bank in the same project at onboarding.

The prior art records (**VERIFIED**, `geap-memory/docs/memory-bank-assumption-validation.md`):

- **MB-07** — *"Memory Bank-specific roles and IAM Conditions over scope values can back up the
  database grants as defense in depth. They are not configured yet."*
- **MB-20** — whether one bank suits every organization was an **OPEN QUESTION**.
- Quota: *"Memory Bank enforces per-project, per-region request quotas… Exceeding them returns
  `429 RESOURCE_EXHAUSTED`"*, and *"each write first retrieves the scope's facts to compute the next
  counter, so writes also consume read quota."*

## Decision

One platform-owned GCP project. One memory bank per domain, created at onboarding. Isolation is by
**per-domain service account plus IAM Conditions on bank scope**, not by project boundary. The memory
bank, its IAM binding, the central audit sink and quota alerting are **platform-owned Terraform**; the
domain's Terraform consumes their outputs and must not create them.

IAM Conditions move from "available and unused" in the prior art to a **required control** (`C-16`).

**Residual question, deliberately recorded rather than resolved:** the diagram labels the bank
`[External Data Store — one per agent]` and says "an agent may write one or more banks", whereas this
decision is one bank **per domain**. Per-domain is adopted because it matches who owns the policy and
keeps bank count linear in domains rather than agents. The diagram's author should confirm; if
per-agent is required, this ADR needs superseding, not amending.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|
| One project per domain | Quota and blast radius isolated per domain; clean least privilege | **The platform retains no hard control whatsoever** — the whole pattern contract becomes advisory (ADR-0001) | Rejected: it removes the only enforcement seam |
| One shared bank, scope isolation only | Fewest resources | Isolation rests entirely on application-layer scope keys; no IAM defense in depth; no per-domain attribution | Rejected as insufficient isolation |
| One platform project, bank per domain | Platform retains IAM, audit and quota control; IAM Conditions give defense in depth; per-domain attribution possible | **Shared quota** and **shared blast radius** | **Chosen** |

## Consequences

**Easier:** the enforcement story becomes real. Project IAM, the bank IAM binding, org policy, the
audit sink and quota alerting are platform-held and survive a domain forking the application code.
`C-16` domain isolation becomes verifiable with IAM Conditions rather than application logic alone.

**Harder — and this is the material cost:**

1. **Quota is shared across every domain.** It is enforced per project, per region. **Separate banks
   do not give separate quota.** Compounding: writes consume read quota; and the diagram's agent →
   bank direct `recall` path consumes the same pool while being ungoverned by the Memory Manager's
   rate limiter. One domain can exhaust the pool and cause an outage for another, with no project
   boundary to contain it and two different teams owning the two deployments.

   Mitigation, and a platform-pattern responsibility rather than a domain concern: per-domain quota
   budgets (`max_writes_per_minute`) enforced by a token-bucket governor in the worker, plus
   `quota_consumed` labelled per domain so a contention incident can be triaged. The prior art records
   this telemetry as absent (MB-15, **NOT VALIDATED**), so it is new work, now required by `C-18` and
   `C-19`.

2. **Shared blast radius.** One project is one failure domain and one misconfiguration domain.

3. **Domain deploy access into a platform-owned project** is in tension with least privilege. Each
   domain's deployer service account must be scoped to its own resource name prefix; this is called
   out for Pattern 001's controls assessment.

4. Cloud Run per-project resource quotas and naming collisions become real once several domains deploy
   into one project — hence the `<domain>-<pattern>` prefix convention.

## Compatibility implications

Establishes the deployment context every pattern is designed against. A pattern assuming a dedicated
project per domain would contradict this ADR. Moving a domain to its own project later would be a
breaking change to the isolation and quota model and would require superseding this ADR.

## Status history

| Date | Status | Note |
|---|---|---|
| 2026-10-20 | Accepted | Per-agent vs per-domain bank boundary flagged for confirmation |
