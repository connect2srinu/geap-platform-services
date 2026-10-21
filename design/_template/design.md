---
artifact: design
feature: NNN-slug
track: full
status: draft
---

# Design — <feature title>

> Stage 2. Requires an approved `intent.md`. Approval at **Gate B** is required before the
> implementation plan.

## Method

What was read to produce this design — files, branches, documents — and when. Every `VERIFIED`
claim must be traceable to something named here.

## Summary

The proposed approach in one paragraph.

## Architecture

Mermaid diagram at C4 container level, labelled `CURRENT`, `TARGET` or `PROPOSED`.

```mermaid
flowchart TB
```

## Interfaces and contracts

New or changed endpoints, request and response shapes, error codes, status codes. Reference the
OpenAPI specification; do not duplicate it here.

| Operation | Method | Path | Breaking? |
|---|---|---|---|

## Data contracts

Stored shapes, scope keys, identifiers, retention.

## Configuration and extension points

What a domain configures, and what it extends. Prefer configuration over source modification.

| Extension point | Interface | Required | Default | Failure mode |
|---|---|---|---|---|

## Platform vs. domain

What is platform mechanism and what is domain policy, explicitly. List the controls that are
**non-overridable** by domain configuration.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|

## Failure handling and operations

Failure modes, retry and backoff, dead-lettering, idempotency, quota and throttling behaviour,
degraded operation, recovery, replay. State what happens when the managed service is unavailable.

## Backward compatibility and migration

What breaks, who is affected, what the migration path is. If nothing breaks, say how that was
determined.

## Observability

Metrics, logs, traces and audit events this change adds or alters. Confirm no prohibited field is
emitted.

## Assumptions and open questions

| ID | Item | Label | Resolution needed |
|---|---|---|---|

## Proposed ADRs

Decisions significant enough to record, once approved.

| ID | Decision |
|---|---|

## Approval

Gate B. A human sets `status: approved`.
