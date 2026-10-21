---
name: design-open-pr
description: Stage 5 (Review) of the platform SDLC. Use when implementation is complete and the user asks to "open the PR", "mark it ready for review", "prepare the pull request", or when sdlc-status shows tasks complete and Gate E open. Reviews the implementation against the approved design, verifies task completion, runs the available automated checks, reviews test coverage and security requirements, checks backward compatibility and pattern conformance, and prepares the PR summary. Marks the PR ready for review only when conditions are met. Never approves or merges; never reports unexecuted tests as passing.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(git status*)
  - Bash(git diff*)
  - Bash(git log*)
  - Bash(make verify)
  - Bash(make validate-design)
  - Bash(make validate-manifest)
  - Bash(make lint)
  - Bash(make test)
  - Bash(python3 scripts/*)
  - Bash(gh pr view*)
  - Bash(gh pr diff*)
  - Bash(gh pr checks*)
  - Bash(gh pr edit*)
  - Bash(gh pr ready*)
user-invocable: true
---

# design-open-pr — Stage 5: Review

## Purpose

Establish, with evidence, whether the implementation matches what was approved — before a human
spends time reviewing it.

## When to use

Implementation tasks are complete and the change is ready for human review.

## Required inputs

- The design folder with approved artifacts
- A branch with the implementation and an open draft PR

## Steps

### 1. Compare the implementation with the design

Read `design.md`, then read the diff:

```bash
git diff $(git merge-base HEAD origin/main)...HEAD
```

For each change, ask: is this in the approved design? Anything outside it is either an undocumented
deviation or scope creep. **Report both; do not quietly accept either.**

### 2. Verify task completion

Every task in `tasks.md` is `complete` or explicitly deferred with a reason. A task marked complete
whose code is not in the diff is a reporting error — say so.

### 3. Run the automated checks

```bash
make verify
```

Run them. Capture the actual output. Then, separately:

```bash
python3 scripts/validate_design_artifacts.py
python3 scripts/validate_pattern_manifest.py
python3 scripts/check_platform_domain_boundary.py
make lint
make test
```

**Record each as `passed`, `failed`, `skipped` or `unavailable`, with its command and output.**
Unavailable is not passed. Never write "tests pass" without output showing it.

### 4. Review test coverage

Not a percentage — these specifically:

- Every authorization deny path tested?
- Every new error code produced by a test?
- Every extension point tested with its default and a substitute?
- Every retry and dead-letter path, including duplicate delivery?
- Does any test fail if the control it covers is removed?

### 5. Verify security requirements

- `controls-check.md` current? If implementation changed the posture, run
  `design-check-controls --recheck` before continuing.
- Any new log, trace attribute or error response carrying memory content, PII or secrets?
- Any new permission, and is it least privilege?
- Any new dependency, and was it scanned?

### 6. Check backward compatibility

Contract diffs against the previous version. Any breaking change must be either covered by an
approved ADR and a major version bump, or reverted.

### 7. For reusable patterns, additionally verify

- **Pattern contract:** `pattern.yaml` validates; version bumped appropriately.
- **Domain configuration:** example configurations still validate against the schema.
- **Extension mechanisms:** defaults still present; security-relevant ones still fail closed.
- **Container build:** the reference Dockerfile still builds — run it, or report `unavailable`.
- **Reference deployment:** `terraform validate` passes.
- **Version compatibility:** `CHANGELOG.md` and compatibility matrix updated.

### 8. Identify unresolved risks

Known limitations, deferred work, anything a reviewer should look at closely. Volunteering these is
the most useful thing this skill does.

### 9. Prepare the PR summary

```markdown
## What and why
<summary; link the design folder>

## Design conformance
<matches approved design, or the deviations with their approvals>

## Tasks
<N of M complete; deferred ones with reasons>

## Verification
| Check | Command | Result |
|---|---|---|
| ... | ... | passed / failed / skipped / unavailable |

## Security
<controls status; recheck outcome if run>

## Compatibility
<breaking changes and version impact, or how "none" was determined>

## Risks and follow-ups
<unresolved items>

## Reviewer notes
<where to look closely>
```

### 10. Ready, or not

Mark ready **only** when: all tasks complete or deferred with reasons, checks run with evidence of
passing, controls current, no unapproved breaking change, documentation updated.

```bash
gh pr ready
```

If conditions are not met, leave it a draft and report exactly what is missing. A draft PR with an
honest blocker list is more useful than a ready one that wastes a reviewer's time.

## Independent review

Where possible, run the code review in a **separate context** from the one that wrote the code — a
reviewer that did not write the code finds more. Use `/code-review` or a fresh session.

**Automated review does not replace human approval.** Gate E is a human.

## Outputs

- A PR description with verification evidence
- A review report in the conversation
- The PR marked ready, or a blocker list

## Validation rules

- Every check reported with its real status
- No unexecuted test reported as passing
- Every deviation from the design reported
- Breaking changes identified with version impact

## Approval requirements

**Gate E** is a human review approval through GitHub. This skill prepares; it never approves.

## Failure and recovery

| Situation | Do this |
|---|---|
| Checks fail | Report the failure with output. Do not mark ready. |
| A tool is unavailable | Report `unavailable`. Never imply a pass. |
| Implementation deviates from the design | Report it. Material deviation → back to Stage 2. |
| Tasks incomplete | Leave as draft; list what remains. |
| Asked to mark ready anyway | Say what is unmet; proceed only on explicit instruction, and record it in the PR. |

## Does not

Approve the PR. Merge. Report unexecuted tests as passing. Hide deviations.
