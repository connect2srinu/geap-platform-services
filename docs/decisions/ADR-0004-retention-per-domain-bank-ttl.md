# ADR-0004: Memory retention is one period per domain, enforced by the bank's TTL

- **Status:** Accepted
- **Date:** 2026-10-22
- **Decision owners:** Srinivasa reddy (requester; project owner and platform lead)
- **Scope:** How long memories written by the `memory-manager` pattern are kept in v0.1.0, and the
  configuration contract that declares it
- **Related:** `design/001-memory-manager/design.md` ("Retention", "Live verification"),
  `design/001-memory-manager/controls-check.md` (C-09), ADR-0003

## Context

The design approved at Gate B on 2026-10-21 promised **per-topic** retention: each topic declares
`retentionDays`, enforced by a per-memory provider expiry set on write. That rested on an
**ASSUMPTION** that `GenerateMemories` accepts a TTL for direct memories.

**VERIFIED** on 2026-10-22 by introspecting `google-cloud-aiplatform` 2.3.0 (module `agentplatform`,
the version the prior art pins). This is not a live run.

- `GenerateMemoriesConfig` has no `ttl` field, and `Memories` has no update method. A per-memory TTL
  can be set only through `create`, which the design does not use for writes (D6).
- TTL for generated memories is configured **per bank**:
  `managed_semantic_memory_config.ttl_config.granular_ttl_config` holds `generate_created_ttl` and
  `generate_updated_ttl`.

ADR-0003 gives each domain one bank. So one retention period per domain is all the provider
supports, and the approved design contradicted the provider. The requester returned the design to
Stage 2 on 2026-10-22.

What was **not** known when deciding:

- Whether the bank-level TTL actually expires generated memories, and what a consolidation update
  does to it. That is live check L7, Tier 1, not yet run: **ASSUMPTION**.
- The retention bounds. They are **OPEN** with Legal (design Q11; tasks.md DEC-8).

Control C-09 requires that retention be declared in configuration and enforced.

## Decision

1. In v0.1.0, retention is **one period per domain**. The domain declares a single domain-level
   value in its configuration. Its name is **PROPOSED** as `retentionDays`. It is bounded by a
   platform maximum held in the schema, not in domain configuration; the value is **OPEN** (DEC-8).
2. **Topics carry no retention.** The per-topic `retentionDays` in the approved design's
   "Configuration changes" is removed.
3. **The bank enforces retention.** Platform-owned Terraform (tasks.md T-39) sets the domain bank's
   `generate_created_ttl` and `generate_updated_ttl` from the domain's declared value. A memory's
   retention therefore runs from its **last write**, whether that was a creation or a consolidation
   update. L7 (b) confirms this.
4. **The write path sends no TTL.**
5. **Per-topic retention is deferred to v0.2.0**, where application-side expiry becomes possible once
   the worker exists.
6. **ADR-0003 stands**: one bank per domain.
7. **This decision rests on L7.** If the bank-level TTL does not hold, there is nothing to enforce
   retention with. The decision is then **reopened**, not quietly replaced by a C-09 exception.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|
| **One bank per retention class** | Per-topic retention in v0.1.0, enforced by the provider | Supersedes ADR-0003. Recall fans out across banks, multiplying quota cost (C-19). C-16 needs a binding per bank. Consolidation cannot merge across banks | An architecture change, for a need not yet established: the Legal bounds are still OPEN |
| **Application-side expiry** | Any granularity, per topic or finer | Needs a scheduler or worker. D1 removed the worker, so this means a new component and managed service, which is a return to Stage 1 | Not possible in v0.1.0. It is the v0.2.0 path (Decision 5) |
| **Keep per-topic `retentionDays`; disclose and take a C-09 exception** | No change to the configuration contract | Ships a key whose value is not enforced, in the first released contract. Correcting it after release is a breaking change | A misleading contract is worse than a narrower, honest one |
| **Per-memory TTL through `create`** | A per-memory TTL exists on that path | `create` never consolidates. It is the Q4 fallback, used only if L1 or L5 fail | The write path is `GenerateMemories` (D6). If the design falls back to `create`, this ADR is revisited with it |

## Consequences

**Easier**

- Retention is enforced by the provider, with no expiry code in the pattern.
- The configuration contract promises only what the provider can enforce.

**Harder, and the costs**

- **One period for everything a domain stores.** A domain with mixed data must choose one value.
  Choosing the longest keeps short-lived data past its policy, so in practice it chooses the
  shortest its strictest topic needs, and longer-lived topics are deleted early.
- **Retention runs from the last write.** A memory that consolidation keeps updating may never
  expire. Whether "retention from last write" satisfies Legal's definition is **OPEN**, alongside the
  bounds.
- **Retention becomes a provisioning input.** Changing it is a platform Terraform change, not a domain
  configuration deploy. The declared value and the bank's TTL can drift apart. Whether the service
  checks at startup that they match is **OPEN**: it would add a bank read permission to the DEC-6
  custom role.
- **Revisions are copies too.** Retention must cover memory revisions as well
  (`ttl_config.memory_revision_default_ttl`). That is decided together with the open
  `disable_memory_revisions`-versus-rollback question in the same Stage 2 pass.

**Constrained**

- No code path may set a TTL per topic or per memory in v0.1.0.
- A per-topic retention key may not return to the schema before the v0.2.0 expiry mechanism exists.

## Compatibility implications

- **No adopter is affected.** **VERIFIED** 2026-10-22: no tag exists locally or on `origin`;
  `patterns/memory-manager/pattern.yaml` has `metadata.status: proposed`; and
  `config/config.schema.json` carries no retention key today.
- The change is to the **approved design's** configuration contract (design.md "Configuration
  changes"), which is amended to match.
- The tool API is unchanged.
- The platform Terraform interface (T-39) gains a retention input per domain bank.
- **v0.2.0:** per-topic retention can return **additively**, as an optional per-topic value
  constrained to be no longer than the domain value. The domain value stays the ceiling, so no v0.1.0
  configuration becomes invalid.

## Status history

| Date | Status | Note |
|---|---|---|
| 2026-10-22 | Accepted | Decided by the requester in the Stage 2 pass opened for the retention defect. Rests on live check L7 |
