---
name: sdlc-status
description: Reports which design folder applies, which SDLC stage the work is in, which approval gates are open, and what the next action is. Use at the start of any session in this repository, when the user asks "where are we", "what's the status", "which stage is this", "what's next", or whenever it is unclear whether a gate has been passed. Read-only — inspects the filesystem and git state and changes nothing.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash(git status*)
  - Bash(git branch*)
  - Bash(git log*)
  - Bash(gh pr view*)
  - Bash(gh pr checks*)
  - Bash(python3 scripts/validate_design_artifacts.py*)
user-invocable: true
---

# sdlc-status — Where are we?

## Purpose

`CLAUDE.md` requires determining the current SDLC stage before changing anything. This skill does it
from evidence instead of guesswork.

## When to use

- At the start of a session in this repository.
- Before any change, to confirm which gates are open.
- Whenever gate state is unclear.

**Read-only.** It never modifies anything.

## Steps

### 1. Determine the active feature

```bash
git branch --show-current
```

A branch named `design/NNN-slug` identifies the design folder directly. Otherwise, look for recently
modified folders under `design/` and ask the user which applies rather than assuming.

### 2. Read the artifact front matter

For the folder, read the front matter of each artifact and record `artifact`, `track` and `status`.

### 3. Determine stage and gates

| Artifacts present and approved | Stage | Next gate |
|---|---|---|
| none | Pre-Stage 1 | Run `design-start-feature` |
| `intent.md` draft | Stage 1 | **Gate A** — awaiting human approval |
| `intent.md` approved | Stage 2 | Run `design-session` |
| `design.md` draft | Stage 2 | **Gate B** — awaiting approval |
| `design.md` approved | Stage 3 | Run `design-check-controls` |
| `controls-check.md` draft | Stage 3 | **Gate C** — awaiting security approval |
| `controls-check.md` approved | Stage 4 | Run `design-plan-implementation` |
| `tasks.md` draft | Stage 4 | **Gate D** — awaiting approval |
| `tasks.md` approved, tasks pending | Stage 4 | Implement the next pending task |
| all tasks complete | Stage 5 | Run `design-open-pr` |
| PR approved | Stage 6 | Run `design-close-feature` |
| `closeout.md` present | Stage 6 | **Gate F** — merge, with explicit authorization |

For the light track: `change.md` → Gate A inline → implement → Gate E → Gate F.

### 4. Check the pull request

```bash
gh pr view --json number,isDraft,reviewDecision,statusCheckRollup
```

Report draft state, review decision and check status. If `gh` is unavailable or there is no PR, say
so — do not infer.

### 5. Validate the artifacts

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

### 6. Report

```
Feature:      NNN-slug  (branch: design/NNN-slug)
Track:        full | light
Stage:        N — <name>
Artifacts:    intent.md approved (by X, date) · design.md draft · ...
Open gate:    Gate B — design awaiting human approval
PR:           #N, draft, checks passing | no PR | gh unavailable
Tasks:        3 of 7 complete
Next action:  <the single next thing>
Blocked by:   <what needs a human, if anything>
```

Lead with the open gate. That is the answer to "what's next" nine times out of ten.

## Outputs

A status report in the conversation. No files changed.

## Validation rules

- Gate state read from front matter, never inferred from file existence alone
- Unavailable tooling reported as unavailable
- Ambiguous feature identity → ask, do not guess

## Approval requirements

None. Read-only.

## Failure and recovery

| Situation | Do this |
|---|---|
| Branch name does not match any folder | List candidates and ask. |
| No design folder at all | Report pre-Stage 1; suggest `design-start-feature`. |
| Front matter malformed | Report it as a defect; do not guess the status. |
| Several folders modified recently | Ask which applies. |
| `gh` unavailable | Report local state; mark PR state unavailable. |

## Does not

Modify anything. Infer approval. Advance a stage.
