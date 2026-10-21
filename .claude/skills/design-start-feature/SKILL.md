---
name: design-start-feature
description: Stage 1 (Intent) of the platform SDLC. Use when starting any new feature, enhancement, defect fix, security remediation, contract change or dependency upgrade in this repository — when the user says "start a feature", "new pattern work", "I want to add", "we need to fix", or asks to begin work that has no design folder yet. Classifies the change onto the full or light track, gathers business objective, scope, non-goals and acceptance criteria, and generates intent.md. Stops at Gate A for human approval; creates the branch and draft PR only after that approval.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(git status*)
  - Bash(git branch*)
  - Bash(git log*)
  - Bash(git checkout -b*)
  - Bash(git push -u origin*)
  - Bash(gh pr create --draft*)
  - Bash(python3 scripts/validate_design_artifacts.py*)
user-invocable: true
---

# design-start-feature — Stage 1: Intent

## Purpose

Turn a request into an approved, scoped `intent.md` before any design or code exists.

## When to use

At the start of **every** change to this repository that is not a trivial typo. If there is no
`design/NNN-slug/` folder for the work, this skill creates it.

## When not to use

- The work already has a design folder → use `sdlc-status`, then the skill for the current stage.
- You are being asked to implement something → implementation needs Gates B and D first.

## Required inputs

- A description of what is wanted. If vague, ask — do not guess the objective.

## Prerequisites

- Clean working tree, or the user has acknowledged uncommitted work.

## Steps

### 1. Understand the request

Read what was asked. If the business objective is unclear, ask with `AskUserQuestion`. Do not invent
an objective — an invented requirement is indistinguishable from a real one later.

### 2. Inspect repository context

- `README.md` and the relevant `standards/` documents.
- Existing `design/` folders — is this related to, or superseded by, existing work?
- The patterns the change would touch, and their `contracts/`.
- `git log` for recent related work.

Note what you actually read; `intent.md` records it under **Method**.

### 3. Classify the change

Apply the track classifier in `.claude/rules/sdlc-gates.md`. The light track requires **every**
statement to be true. When in doubt, choose the full track — escalating later costs more than
starting thorough.

State the classification and your reasoning to the user before writing anything.

### 4. Identify impact

- Which patterns change?
- Which **contracts** change? The tool API is identical across domains — a change there affects every
  agent team and is always full track.
- Is this reusable platform work or domain-specific? If domain-specific, say why it belongs here.
- Which domains and agent teams are affected?

### 5. Allocate the design folder

Next free three-digit number. `design/NNN-slug/`, kebab-case slug. Check for collisions against both
`design/` and remote branches.

### 6. Generate the artifact

Copy `design/_template/intent.md` (full track) or `design/_template/change.md` (light track) and fill
every section. Front matter: `status: draft`.

Rules:

- Acceptance criteria are **numbered and testable**. "Works well" is not a criterion.
- Non-goals are specific. This section is what prevents scope creep in Stage 2.
- Open questions go in the table with who decides — do not resolve them by assumption.
- Label claims `VERIFIED` / `PROPOSED` / `OPEN` / `ASSUMPTION`.

### 7. Validate

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

### 8. Stop at Gate A

Present the intent and **stop**. Say explicitly that approval is needed before design work and before
any branch or PR is created.

Never set `status: approved` yourself. Never infer approval from silence.

### 9. After explicit approval only

When the user has approved — and only then:

```bash
git checkout -b design/NNN-slug
git push -u origin design/NNN-slug
gh pr create --draft --title "..." --body "..."
```

Ask before pushing. If there is no remote, or `gh` is not authenticated, say so and stop — do not
work around it.

## Outputs

- `design/NNN-slug/intent.md` (or `change.md`), `status: draft`
- After approval: a feature branch and a draft PR

## Validation rules

- Front matter validates against `schemas/design-artifacts.schema.json`
- `feature` matches the folder name
- Every acceptance criterion is testable
- No section left as template placeholder text

## Approval requirements

**Gate A.** A human sets `status: approved` with `approved_by` and `approved_date`. The branch and PR
come after, never before.

## Failure and recovery

| Situation | Do this |
|---|---|
| Objective unclear | Ask. Do not write a speculative intent. |
| Folder number collides | Take the next free number; check remote branches too. |
| Related design folder exists | Stop. Propose extending it instead of a duplicate. |
| No remote or `gh` unauthenticated | Report it. Create the folder locally; skip the branch step. |
| User asks to skip approval | Decline. Explain that Gate A is the branch gate. |

## Does not

Write application code. Produce a design. Create a branch or PR before approval. Approve anything.
