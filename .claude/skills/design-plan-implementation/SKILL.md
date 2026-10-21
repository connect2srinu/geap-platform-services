---
name: design-plan-implementation
description: Stage 4 (Build) planning for the platform SDLC. Use after design.md and controls-check.md are approved and the user asks to "plan the implementation", "break this into tasks", "make a task plan", or when sdlc-status shows Gate C passed and Gate D open. Reads the approved intent, design and controls assessment, inspects the relevant code, and breaks the work into small verifiable tasks with dependencies, file ownership, tests and validation commands, mapped to acceptance criteria. Generates tasks.md and stops at Gate D. No material code changes before that approval.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(git log*)
  - Bash(python3 scripts/validate_design_artifacts.py*)
user-invocable: true
---

# design-plan-implementation — Stage 4: Build planning

## Purpose

Turn an approved design into a sequence of small tasks, each independently verifiable, so that
implementation is mechanical and progress is visible.

## When to use

After Gates B and C. Before any material code change.

## Required inputs

- Approved `intent.md`, `design.md`, `controls-check.md`

## Prerequisites

Verify Gates A, B and C yourself. If any artifact is not `approved`, stop and name it.

## Steps

### 1. Read all three approved artifacts

Acceptance criteria from the intent. Architecture, contracts and extension points from the design.
Gaps and verification approaches from the controls assessment — **controls work is task work**, not
an afterthought.

### 2. Inspect the code to be changed

Read the actual files. A plan written without reading the code produces tasks that do not fit.

### 3. Break the work down

Each task:

- **One coherent change.** If describing it needs "and", split it.
- **Independently verifiable** — a command proves it works.
- **Small enough to review** as one unit.
- Ships with its tests.

Prefer: contracts first → platform mechanism → extension points → infrastructure → documentation.
Contracts first means later tasks have something to build against.

### 4. Identify dependencies and file ownership

For each task, list its dependencies and the **files it owns**. File ownership matters here: several
developers or agents may work concurrently, and two tasks must never own the same file. See
`.claude/rules/sdlc-gates.md` and `docs/onboarding/developer-guide.md`.

### 5. Map tests and acceptance criteria

Every acceptance criterion maps to at least one task. Every task maps to at least one test. Fill the
traceability table — a criterion with no task is scope that will be forgotten.

For controls: every `Verified` status the assessment promises needs a task that produces the evidence.

### 6. Establish the sequence

Order tasks so each can be verified when complete. Note what can run in parallel.

### 7. Generate tasks.md

From `design/_template/tasks.md`. Every task gets every field. All statuses `pending`.
`status: draft`.

### 8. Validate and stop at Gate D

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

Present the plan. Stop. **No material code changes before approval.**

## During implementation

Once Gate D is approved, these rules govern the work (they are in `CLAUDE.md`, repeated here because
this skill hands off to them):

- One task at a time, to completion, following the approved design.
- Tests written or updated **with** the code, same commit.
- Run type checks, linters and tests; report results honestly.
- No unrelated refactoring. No undeclared dependencies.
- Preserve existing contracts unless the change is approved.
- Update task status in `tasks.md` as work progresses.
- Record deviations in the deviations table.
- **A material architecture change means stopping and returning to Stage 2.** Do not improvise around
  the design.

## Outputs

- `design/NNN-slug/tasks.md`, `status: draft`

## Validation rules

- Every task has objective, components, dependencies, tests, validation, files owned, status
- No two tasks own the same file
- Every acceptance criterion maps to a task
- Every promised control verification has a task
- Tasks are small — a task touching more than a handful of files is probably several

## Approval requirements

**Gate D.** A human sets `status: approved`.

## Failure and recovery

| Situation | Do this |
|---|---|
| An upstream artifact is not approved | Stop. Name the open gate. |
| The design is too vague to plan | Stop. Return to Stage 2 with the specific ambiguity. |
| A task would be large | Split it. |
| Two tasks need the same file | Sequence them, or merge them. |
| Controls gaps have no owner | Raise it before planning around them. |

## Does not

Start implementation. Approve its own plan. Expand scope beyond the approved design.
