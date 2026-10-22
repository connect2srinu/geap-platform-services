---
artifact: change
feature: 004-iso-date-enforcement
track: light
status: draft
---

# Change — Enforce `format: date`, and say plainly that a light-track `change.md` records no approval

> **Light track.** Use only when *every* statement below is true. If any becomes false during the
> work, stop and escalate to the full track — this is one-way and automatic.
>
> - [x] No change to any API contract, tool API, or `pattern.yaml`
> - [x] No change to a security control or the security posture
> - [x] No new managed service, dependency, or extension point
> - [x] No architectural change

## What and why

### 1. `format: date` was never checked

`schemas/design-artifacts.schema.json` declares `approved_date` as `format: date`.
`scripts/validate_design_artifacts.py` called `jsonschema.validate(fm, schema)` without a format
checker. jsonschema treats `format` as an annotation unless a checker is passed, so
`approved_date: 10/21/2026` in `design/001-memory-manager/intent.md` passed validation.

**VERIFIED** on Python 3.12.3 with jsonschema 4.25.1 (the version pinned in
`scripts/requirements.txt`):

| Value | Default `validate` | With `FormatChecker()` |
|---|---|---|
| `2026-10-21` | accepted | accepted |
| `10/21/2026` | accepted | **rejected** |
| `2026-13-45` | accepted | **rejected** |

### 2. What `status` means on a light-track `change.md` was ambiguous

On the light track, Gate A is recorded in the PR description and Gate E as a GitHub review
(`.claude/rules/sdlc-gates.md`). But `change.md` carries the same `status` field as the full-track
artifacts, where `approved` *is* the gate record. **VERIFIED**: every merged light-track
`change.md` on `main` (002, 003, 005, 007) says `status: draft`, so a reader can't tell whether
that means "never approved" or "status is not used here". Nothing stopped someone setting
`approved` and creating a second approval record that could disagree with the PR.

There were two ways to resolve it:

- **(a) Require `status: approved` on `change.md` before merge.** That would duplicate the PR
  description's Gate A record, and the light-track rule in `.claude/rules/sdlc-gates.md` would
  have to change. That file is high-contention and needs its own PR. It would also turn `main`
  red at once: the four merged `change.md` files are `draft`, and only a human may set them
  `approved`.
- **(b) The field doesn't apply to the light track.** This matches the existing rule, needs no
  edits to the four merged folders, and leaves one record per gate.

**PROPOSED, and implemented here: (b).** `change.md`'s `status` stays `draft`, or becomes
`superseded`; `in-review` is also accepted. The validator **rejects** `status: approved`,
`approved_by` and `approved_date` in `change.md`. `design/_template/change.md` says so under
"Approval". The schema is unchanged, because `schemas/**` is high-contention, and this check is
per-track, which the validator handles.

| | |
|---|---|
| Classification | `defect` (1) and documentation + validator rule (2) |
| Patterns touched | none |

## Approach

- `jsonschema.validate(fm, schema, format_checker=jsonschema.FormatChecker())`. jsonschema checks
  `date` with the standard library, so this adds no dependency. The front-matter parser already
  turns unquoted ISO dates into strings (`_common.py`), so a valid unquoted `2026-10-21` still
  passes.
- In `validate_folder`, for `change.md`: an error if `status` is `approved`, or if
  `approved_by` or `approved_date` is present.
- Template: a paragraph under "Approval" in `design/_template/change.md`.
- Tests: `tests/test_validate_front_matter_dates.py` and
  `tests/test_validate_light_track_status.py`. Both run the real `validate_folder` against a
  temporary design tree.
- **No existing folder breaks.** **VERIFIED** by running this validator on `main` and on copies of
  the `design/001-memory-manager` and `design/006-control-c20-cmek-at-rest` branches; see
  Verification. 001's `approved_date` was corrected to `2026-10-21` in `7b078a0`.

## Controls delta

| Control | Effect | Status |
|---|---|---|
| — | Enforces an existing schema declaration and an existing SDLC rule on design artifacts. No control in `standards/security.md` changes | Unchanged posture |

## Verification

Python 3.12.3, jsonschema 4.25.1, ruff 0.8.4. Branch from `main` at `107f2a6`.

| Check | Command | Result |
|---|---|---|
| All unit tests | `pytest -q tests` | **passed** — `25 passed` (13 existing, 5 date, 7 light-track status) |
| Date tests fail without fix 1 | `format_checker=` argument removed temporarily | **failed as intended** — `3 failed, 9 passed`: `10/21/2026`, `2026-13-45`, `21 October 2026`. Fix restored; file byte-identical to backup |
| Status tests fail without fix 2 | the `change.md` rule disabled temporarily | **failed as intended** — `3 failed, 9 passed`: approved with approver and date, `approved_by` alone, `approved_date` alone. Fix restored; file byte-identical to backup |
| Lint | `ruff check patterns scripts templates tests` | **passed** — `All checks passed!` |
| Format | `ruff format --check patterns scripts templates tests` | **passed** — `13 files already formatted` |
| Validator on this branch, including this folder | `python3 scripts/validate_design_artifacts.py` | **passed** — `62 checks, 0 warning(s)` |
| Validator on the 001 branch (copy at `4b5b08e`) | same, against the copy | **failed, as expected before this change** — `38/47`, 9 errors, all of them the 9 known Gap errors from 002. Neither new rule adds an error |
| Validator on the 006 branch (copy at `3ad9abe`) | same, against the copy | **passed** — `25 checks` |

## Approval

**Gate A** — two parts, both from the requester (connect2srinu) on 2026-10-21:

1. Fix 1: approved in session ("004 — ISO date enforcement", approved before 003 merged).
2. Fix 2 added to scope by instruction: "resolve the light-track change.md status ambiguity —
   either require approved or state the field doesn't apply to light track, your recommendation".

Restate both in the PR description. Per fix 2, this file's `status` is not a gate record and stays
`draft`.

Gate A inline (in the PR description) and Gate E (human review). Gate F for merge.
