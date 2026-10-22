---
artifact: change
feature: 003-ci-lint-and-empty-suites
track: light
status: draft
---

# Change — Make local lint match CI, and treat empty Python suites as skipped

> **Light track.** Use only when *every* statement below is true. If any becomes false during the
> work, stop and escalate to the full track — this is one-way and automatic.
>
> - [x] No change to any API contract, tool API, or `pattern.yaml`
> - [x] No change to a security control or the security posture
> - [x] No new managed service, dependency, or extension point
> - [x] No architectural change

## What and why

These are foundation defects from `69eee1b`. All are **VERIFIED** on PR #1's CI and locally on
2026-10-21:

1. **CI and `make lint` disagree.** CI runs `ruff format --check`, but `make lint` does not, so
   `make lint` passes locally (`All checks passed!`) while CI fails on 9 unformatted files under
   `scripts/` and `templates/`.
2. **Type check fails when there's no Python.** It fails with exit 2 (`There are no .py[i] files in
   directory 'patterns/memory-manager/src'`). The job's empty-directory guard tests that the
   directory exists, not that it contains any Python.
3. **Unit tests fail when no tests are collected.** pytest exits with code 5 (`no tests ran`).
4. **`make test` hides real failures.** Found while scoping item 3: `make test` ends in
   `|| echo "no tests collected yet"`, so a failing test exits 0. It also discards stderr. Included
   at the requester's instruction (2026-10-21).

| | |
|---|---|
| Classification | `defect` |
| Patterns touched | none |

## Approach

- **`Makefile` `lint`:** add `ruff format --check patterns scripts templates`, matching CI.
- **Formatting:** run `ruff format` on the 9 files. This is a mechanical, whitespace-level diff
  only, with no logic change, committed separately so the review can skip it.
- **`python-ci.yml` `types`:** keep only the `patterns/*/src` directories that contain at least one
  `.py` file. If none do, print `skipped, not passed` and exit 0.
- **`python-ci.yml` `test`:** treat pytest exit 5 as `skipped, not passed`. Any other non-zero exit
  still fails.
- **`Makefile` `test`:** pass only the test directories that exist, apply the same exit-5 handling,
  and stop discarding stderr. Real failures propagate (item 4).

**Not in scope** (reported, not fixed): `make terraform-validate` also ends in `|| true` on
`terraform fmt -check`, and so masks formatting failures.

**Overlap with 001:** task T-04 owns `python-ci.yml` and `Makefile`. This change merges first, and
001 rebases onto it.

## Controls delta

| Control | Effect | Status |
|---|---|---|
| — | CI hygiene only. It changes no control in `standards/security.md` | Unchanged posture |

## Verification

| Check | Command | Result |
|---|---|---|
| `make lint` catches what CI catches | `make lint`, before reformatting | **failed as intended** — `9 files would be reformatted`, exit 2 |
| Formatting | `make lint`, after `ruff format` | **passed** — `All checks passed!`, `10 files already formatted` |
| The reformat is formatting only | AST comparison against `HEAD` for each of the 9 files | **passed** — all 9 `AST identical` |
| Scripts still behave | `validate_design_artifacts.py`, `validate_pattern_manifest.py`, `check_platform_domain_boundary.py`, `run_conformance.py --list` | **passed** (17, 25 and 4 checks); conformance reports **unavailable** (exit 3), as it did before |
| No tests collected → skipped | `make test` with no tests | **passed** — `No tests collected yet — skipped, not passed.`, exit 0 |
| A failing test fails `make test` | a temporary failing test, not committed | **passed** — `1 failed`, exit 2 |
| A passing test passes `make test` | a temporary passing test, not committed | **passed** — `1 passed`, exit 0 |
| CI type-check guard | the job's loop, run locally on this tree | **passed** — `No pattern source present yet — skipped, not passed.` |
| CI jobs on GitHub | the PR's checks | **not yet run** — needs the push |
| Workflow lint | `actionlint` | **unavailable** — not installed. The YAML parses |

**Merge order with 002:** both change `scripts/validate_design_artifacts.py`. If 002 merges first,
rebase this branch and re-run `ruff format scripts`. The conflict is formatting only.

## Approval

**Gate A** — approved in session on 2026-10-21 by the requester (connect2srinu): "Approve 002 and
003, include the make test fix". Restate this in the PR description, as the light track requires.
`status` stays `draft` here: only a human sets `approved`.

Gate A inline (in the PR description) and Gate E (human review). Gate F for merge.
