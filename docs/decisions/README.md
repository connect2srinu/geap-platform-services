# Architecture decision records

Significant, **approved** decisions. Not every implementation choice — ADRs for everything make ADRs
worthless.

Written with [`design-record-decision`](../../.claude/skills/design-record-decision/SKILL.md).

| ADR | Title | Status | Date |
|---|---|---|---|
| [0001](ADR-0001-published-pattern-model.md) | Published pattern model, not a central control plane | Accepted | 2026-10-20 |
| [0002](ADR-0002-reference-implementation-stack.md) | Python 3.12 + FastAPI for reference implementations | Accepted | 2026-10-20 |
| [0003](ADR-0003-shared-platform-gcp-project.md) | Single platform-owned GCP project with per-domain memory banks | Accepted | 2026-10-20 |
| [0004](ADR-0004-retention-per-domain-bank-ttl.md) | Memory retention is one period per domain, enforced by the bank's TTL | Accepted | 2026-10-22 |

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
