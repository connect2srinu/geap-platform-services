# Architecture decision records

Significant, **approved** decisions. Not every implementation choice — ADRs for everything make ADRs
worthless.

Significant decisions now live in the feature's `design.md`. Keep an ADR only for a decision that
outlives one feature — a cloud topology, a delivery model, a stack choice.

| ADR | Title | Status | Date |
|---|---|---|---|
| [0001](ADR-0001-published-pattern-model.md) | Published pattern model, not a central control plane | Accepted | 2026-10-20 |
| [0002](ADR-0002-reference-implementation-stack.md) | Python 3.12 + FastAPI for reference implementations | Accepted | 2026-10-20 |
| [0003](ADR-0003-shared-platform-gcp-project.md) | Single platform-owned GCP project with per-domain memory banks | Accepted | 2026-10-20 |

## When to write one

A decision that changes a published contract, selects or replaces a managed service, changes the
security or isolation posture, changes the platform/domain boundary or adds an extension point, or is
expensive to reverse.

## Conventions

- `ADR-NNNN-<kebab-title>.md`, sequential, **never reused** — including for superseded ADRs.
- Status: `Proposed` · `Accepted` · `Superseded by ADR-NNNN` · `Deprecated`.
- A superseded ADR is **updated, never deleted or rewritten**. It remains the record of what was true
  then.
- At least one real alternative, with why it was not chosen.
- Consequences include the costs. An ADR listing only benefits is advocacy, not a record.
