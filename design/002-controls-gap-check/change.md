---
artifact: change
feature: 002-controls-gap-check
track: light
status: draft
---

# Change — Make the controls-check gap rule actually fire

> **Light track.** Use only when *every* statement below is true. If any becomes false during the
> work, stop and escalate to the full track — this is one-way and automatic.
>
> - [x] No change to any API contract, tool API, or `pattern.yaml`
> - [x] No change to a security control or the security posture
> - [x] No new managed service, dependency, or extension point
> - [x] No architectural change

## What and why

`scripts/validate_design_artifacts.py:155` is meant to fail an approved `controls-check.md` that has
a `Gap` without a recorded exception. It only checks whether the literal `Exception approved`
appears anywhere in the file. The template's status legend and summary table always contain that
string, so the rule can never fire. **VERIFIED**: `design/001-memory-manager/controls-check.md` is
approved with 9 Gaps and 0 exceptions, and the validator reports `PASSED`.

A second defect sits in the same block. The unknown-status check looks for `**Status:**`, but the
template writes `| **Status** | <value> |`, so an unrecognised status is never reported either.

| | |
|---|---|
| Classification | `defect` |
| Patterns touched | none |

## Approach

The rewritten rule reads each control's status from the `| **Status** |` row of its own `### C-NN`
section, never from the legend or the summary. Then it reads the `## Approved exceptions` table. A
row counts only if its first cell is a control ID and its approver, date and expiry cells are
filled.

- Any control whose status is unrecognised, or that has no Status row, is an error.
- In an approved assessment, any control whose status is `Gap` or `Exception approved` and has no
  matching exception row is an error, **naming the control**.

The rewrite uses only the standard library, so no new dependency is added. Tests: a repository-root
`tests/test_validate_controls_check.py` with fixtures for the following cases (13 tests in all):

- the template legend alone;
- a Gap with no exception;
- a Gap with an incomplete exception row;
- a complete exception;
- an unknown status;
- a draft with Gaps, which passes.

**Expected consequence, deliberately:** once this merges, `Design artifacts` fails on branch
`design/001-memory-manager` until its Gate C is re-confirmed or amended. That is the defect being
fixed, not a regression.

## Controls delta

| Control | Effect | Status |
|---|---|---|
| — | Restores enforcement of a documented SDLC rule (`design/_template/controls-check.md` "Approval"). It changes no control in `standards/security.md` | Unchanged posture |

## Verification

| Check | Command | Result |
|---|---|---|
| Unit tests | `pytest -q tests/test_validate_controls_check.py` | **passed** — `13 passed` |
| Tests fail without the fix | the old string-presence rule restored temporarily | **failed as intended** — `7 failed, 6 passed`; fix restored |
| Lint on changed files | `ruff check scripts/validate_design_artifacts.py tests` | **passed** — `All checks passed!` |
| Validator on `main`'s design folders | `python3 scripts/validate_design_artifacts.py` | **passed** — `17 checks` |
| Validator on 001's committed artifacts (copy at `e1b0f68`) | same, against the copy | **failed as intended** — 9 errors: C-05, C-06, C-09, C-10, C-11, C-13, C-16, C-17, C-19 |
| `ruff format --check` on the script | — | **skipped** — the script was never formatted (that is change 003). New lines follow the file's existing style |

## Approval

**Gate A** — approved in session on 2026-10-21 by the requester (connect2srinu): "Approve 002 and
003". Restate this in the PR description, as the light track requires. `status` stays `draft`
here: only a human sets `approved`.

Gate A inline (in the PR description) and Gate E (human review). Gate F for merge.
