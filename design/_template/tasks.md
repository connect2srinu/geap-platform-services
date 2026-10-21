---
artifact: tasks
feature: NNN-slug
track: full
status: draft
---

# Implementation plan — <feature title>

> Stage 4. Requires approved `intent.md`, `design.md` and `controls-check.md`. Approval at
> **Gate D** is required before material code changes.

## Sequence

Order and dependencies, briefly. Note which tasks can run in parallel and which files each owns, so
that concurrent work does not collide.

## Tasks

### T-01 — <objective>

| | |
|---|---|
| **Objective** | One sentence |
| **Components** | Files and modules touched |
| **Expected changes** | What will be added, modified, removed |
| **Dependencies** | Other task IDs, or none |
| **Acceptance criteria** | Which `intent.md` criteria this advances |
| **Tests** | The tests written or updated with this task |
| **Validation** | The command that proves it works |
| **Files owned** | For parallel work — the files only this task may touch |
| **Status** | `pending` / `in-progress` / `complete` / `blocked` |

## Traceability

Every acceptance criterion maps to at least one task, and every task to at least one test.

| Acceptance criterion | Tasks | Tests |
|---|---|---|

## Deviations

Recorded during implementation. A material architecture change means returning to design review.

| Date | Task | Deviation | Approved by |
|---|---|---|---|

## Approval

Gate D. A human sets `status: approved`.
