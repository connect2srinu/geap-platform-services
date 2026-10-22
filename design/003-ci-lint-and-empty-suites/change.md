---
artifact: change
feature: 003-ci-lint-and-empty-suites
track: light
status: draft
---

# Change — Make local checks match CI, treat empty Python suites as skipped, and let gitleaks run

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
5. **The local venv was not on Python 3.12.** `make deps` ran `uv venv` without a version, and uv
   picked a managed CPython 3.9.23. **VERIFIED**: `.venv/pyvenv.cfg` pointed at
   `cpython-3.9.23`, while `standards/coding.md` and CI use 3.12. Local results weren't comparable
   to CI's. Added at the requester's instruction (2026-10-21).
6. **Secret scanning never scanned.** On PR #1 the gitleaks job fails with `403 Resource not
   accessible by integration` on `GET /repos/.../pulls/1/commits`. **VERIFIED** in
   `controls-check.md` C-08 (run 39695758417). gitleaks lists the PR's commits through the API,
   and the workflow grants only `contents: read`. No secret was found; the scan never ran. Added at
   the requester's instruction (2026-10-21).

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

- **`Makefile` `deps`:** `uv venv --python 3.12`. The `python3 -m venv` fallback refuses when
  `python3` is older than 3.12, and says how to fix it: install uv, or use `python3.12 -m venv`.
  An existing `.venv` older than 3.12 is refused with `make clean-venv deps`, rather than silently
  reused.
- **`security.yml` `secrets` job:** job-level `permissions: contents: read, pull-requests: read`.
  This is read-only, added to that one job only. The other jobs keep the workflow's
  `contents: read`.

**Not in scope** (reported, not fixed): `make terraform-validate` also ends in `|| true` on
`terraform fmt -check`, and so masks formatting failures.

**Overlap with 001:** task T-04 owns `python-ci.yml` and `Makefile`. This change merges first, and
001 rebases onto it.

## Controls delta

| Control | Effect | Status |
|---|---|---|
| C-08 | The gitleaks job can now actually scan, giving C-08 the evidence it lacked. The control is unchanged. The added permission is read-only and job-scoped | Unchanged posture; evidence restored |
| — | Everything else is CI hygiene. It changes no control in `standards/security.md` | Unchanged posture |

## Verification

All on **Python 3.12.3**, in a `.venv` deleted and recreated by the new `make deps`. Results from
the earlier 3.9.23 venv are superseded and are not counted.

| Check | Command | Result |
|---|---|---|
| An existing 3.9 venv is refused | `make deps` with the old `.venv` (3.9.23) | **passed** — `error: .venv uses Python 3.9.23; it must be 3.12 or newer`, exit 2 |
| Fallback refuses old `python3` | `make deps UV=` with `python3` → 3.9.23 | **passed** — refusal with both remedies, exit 2, no `.venv` created |
| Fallback works on 3.12 | `make deps UV=` with `python3` → 3.12.3 | **passed** — `Python 3.12.3`, ruff 0.8.4, pytest 8.3.4 |
| uv path pins 3.12 | `make clean-venv deps` | **passed** — `Using CPython 3.12.3 interpreter at: /usr/bin/python3.12` |
| `make lint` catches what CI catches | `ruff format --check` on the 9 files as at `69eee1b` | **failed as intended** — 9 files would be reformatted |
| Formatting | `make lint` | **passed** — `All checks passed!`, `10 files already formatted` |
| The reformat is formatting only | AST comparison `69eee1b` → `d4ada6a` | **passed** — 9 of 9 identical |
| Scripts still behave | `make validate-design validate-manifest check-boundary`; `run_conformance.py --list` | **passed** (25, 25, 4 checks); conformance **unavailable** (exit 3), as before |
| No tests collected → skipped | `make test` | **passed** — `No tests collected yet — skipped, not passed.`, exit 0 |
| A failing test fails `make test` | a temporary failing test, not committed | **passed** — `1 failed`, exit 2 |
| A passing test passes `make test` | a temporary passing test, not committed | **passed** — `1 passed`, exit 0 |
| CI type-check guard | the job's loop, locally | **passed** — skipped, exit 0 |
| CI test exit-5 handling | the job's step, locally, on an empty `tests/` | **passed** — skipped, exit 0 |
| gitleaks scans | `Security / Secret scanning` on this PR | **not yet run** — needs the push |
| CI jobs on GitHub | the PR's checks | **not yet run** — needs the push |
| Workflow lint | `actionlint` | **unavailable** — not installed. Both workflow files parse as YAML |

**Merge order with 002:** both change `scripts/validate_design_artifacts.py`. If 002 merges first,
rebase this branch and re-run `ruff format scripts`. The conflict is formatting only.

## Approval

**Gate A** — approved in session on 2026-10-21 by the requester (connect2srinu): "Approve 002 and
003, include the make test fix". Restate this in the PR description, as the light track requires.
`status` stays `draft` here: only a human sets `approved`.

**Additions** (items 5 and 6) — instructed by the requester on 2026-10-21, before the push.

Gate A inline (in the PR description) and Gate E (human review). Gate F for merge.
