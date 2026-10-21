---
name: design-check-controls
description: Stage 3 (Controls) of the platform SDLC. Use after design.md is approved, when the user asks to "check controls", "run the security review", "do the controls assessment", or when sdlc-status shows Gate B passed and Gate C open. Also use with --recheck after implementation changes the design or security posture. Assesses the proposed design against the 19-control enterprise catalogue in standards/security.md and generates controls-check.md with requirement, applicability, implementation, verification, status and evidence per control. Never marks a control compliant without evidence. Stops at Gate C for security-reviewer approval.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(git diff*)
  - Bash(python3 scripts/validate_design_artifacts.py*)
  - Bash(python3 scripts/check_platform_domain_boundary.py*)
user-invocable: true
---

# design-check-controls — Stage 3: Controls

## Purpose

Establish, with evidence, which enterprise controls apply to a change and whether they are satisfied.

## When to use

- After Gate B, before implementation planning.
- **Again** (`--recheck`) whenever implementation changes the design or the security posture — adding
  a dependency, an endpoint, a permission, a data flow, or a log statement.

## Required inputs

- An approved `design/NNN-slug/design.md`
- `standards/security.md` — the catalogue is normative

## Prerequisites

Verify Gate B. If `design.md` is not `approved`, stop and say so.

## Steps

### 1. Read the design and the catalogue

All 19 controls, `C-01` to `C-19`. Do not work from memory of what controls usually exist.

### 2. Determine applicability per control

For each control, decide whether it applies **to this change** and say why. `Not applicable` needs a
stated reason — "not relevant" is not a reason.

Err toward applicable. A control wrongly marked not-applicable is invisible; one wrongly marked
applicable merely costs a paragraph.

### 3. Assess each applicable control

Fill all six fields. Be concrete — name files, resources, configuration keys, test names.

**Status is the field that matters, and the rules are strict:**

| Status | Allowed when |
|---|---|
| `Verified` | Evidence exists **that would fail if the control were removed** — a named test, scan output, or completed procedure. Nothing less. |
| `Implemented, not verified` | The code or configuration is there, but nothing proves it. **This is the correct status for most of a design-stage assessment.** |
| `Gap` | Not satisfied. An acceptable, honest outcome. |
| `Not applicable` | With a reason. |
| `Exception approved` | A named approver, date, expiry, and compensating control. |

**Never** mark a control `Verified` because the design says it will be done, because the code looks
right, or because it is obviously good practice. At design stage, almost nothing is `Verified` yet —
an assessment full of `Verified` before implementation exists is wrong, and CI will not catch it.

### 4. Pay particular attention to

- **`C-02` fail-closed** — trace every deny path, including extension errors.
- **`C-06` logging restrictions** — the most common real leak. Check every new log, trace attribute
  and error response for memory content, PII or secrets.
- **`C-11` least privilege** — no primitive roles; Memory Bank access to the Memory Manager service
  account only, never an agent.
- **`C-16` domain isolation** — isolation is by service account and IAM Conditions, not project
  boundary. Verify the design actually achieves it.
- **`C-17` / `C-19` retry and shared quota** — does retry amplify load against a rate-limited
  dependency? Is per-domain contention bounded?
- **Non-overridable controls** — confirm that no configuration key could switch one off. If one
  could, that is a design defect; report it as such.

### 5. Record gaps and exceptions honestly

Every `Gap` goes in the gaps table with risk, plan and owner. An exception needs an approver, date,
expiry and compensating control — never record one you were not explicitly given.

### 6. Generate controls-check.md

From `design/_template/controls-check.md`. Include the summary counts. `status: draft`.

### 7. Validate and stop at Gate C

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

Present the assessment, leading with gaps and with anything you could not verify. Stop.

## Recheck mode

With `--recheck`, scope to controls affected by the diff rather than reassessing all 19:

```bash
git diff --name-only <base>...HEAD
```

Map changed files to controls, reassess those, and note in the document which controls were rechecked
and which were carried forward unchanged.

## Outputs

- `design/NNN-slug/controls-check.md`, `status: draft`

## Validation rules

- Every applicable control has all six fields populated
- No `Verified` without evidence that would fail if the control were removed
- Every `Gap` appears in the gaps table
- Every exception names an approver, date and expiry
- Summary counts match the assessment body

## Approval requirements

**Gate C.** A security reviewer sets `status: approved`. CI fails an approved assessment containing a
`Gap` with no recorded exception.

## Failure and recovery

| Situation | Do this |
|---|---|
| `design.md` not approved | Stop. Report the open gate. |
| Cannot determine applicability | Mark applicable and note the uncertainty. Never default to not-applicable. |
| No evidence available yet | `Implemented, not verified`. Say so plainly. |
| Configuration could disable a mandatory control | Report as a **design defect**. Return to Stage 2. |
| Asked to mark a control compliant without evidence | Decline, and explain why the status rules exist. |

## Does not

Approve its own assessment. Mark controls compliant without evidence. Create exceptions it was not
given. Treat "will be implemented" as implemented.
