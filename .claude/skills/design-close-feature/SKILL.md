---
name: design-close-feature
description: Stage 6 (Close) of the platform SDLC. Use when a PR has been reviewed and approved and the user asks to "close out the feature", "write the closeout", "wrap this up", or when sdlc-status shows Gate E passed. Summarizes delivered functionality, identifies changes from the approved design, confirms test results, updates architecture and release documentation and configuration examples, records lessons learned, reviews whether standards or skills should improve, and generates closeout.md. Verifies readiness for merge but never merges.
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
  - Bash(python3 scripts/*)
  - Bash(gh pr view*)
  - Bash(gh pr checks*)
user-invocable: true
---

# design-close-feature — Stage 6: Close

## Purpose

Leave the feature in a state where someone who was not involved can understand what was delivered,
what changed from plan, and what is still outstanding.

## When to use

After Gate E (human review approval), before merge.

## Steps

### 1. Summarise what was delivered

Plainly, in terms of the acceptance criteria. What now exists and works.

### 2. Identify changes from the approved design

Compare `design.md` with what was built. Every deviation gets: what changed, why, who approved it,
and the ADR if one was written. **If nothing deviated, say so explicitly** — an empty section reads
like it was skipped.

### 3. Confirm the tests

Re-run them. Do not copy results from Stage 5 — code may have changed during review.

```bash
make verify
```

Report `passed` / `failed` / `skipped` / `unavailable` with commands and output. If live
managed-service verification was not performed, **state that** rather than leaving it implied.

### 4. Update architecture documentation

If the architecture changed: update `docs/architecture/`, with the diagram's status label moved from
`PROPOSED` to `CURRENT`. A `PROPOSED` diagram describing shipped code is stale on arrival.

### 5. Update release documentation

- `patterns/<name>/CHANGELOG.md` — what changed, breaking or not, migration steps, security-relevant
  changes called out.
- Version in `pattern.yaml` bumped per `standards/release-management.md`.
- `docs/releases/` if this is part of a release.

### 6. Update configuration examples

If configuration changed, the examples must still validate — and still use neutral placeholders, no
real identifiers.

### 7. Record lessons learned

Honestly. Specifically: did a standard prove wrong or missing? Did a skill misfire? Was the design
wrong somewhere? These are the most valuable lines in the document because they are the only input to
improving the process.

### 8. Review standards and skills

If the work exposed a gap in `standards/` or a skill, propose the improvement — as a **separate
follow-up**, not bundled into this feature.

### 9. Generate closeout.md

From `design/_template/closeout.md`. `status: draft` until reviewed with the PR.

### 10. Verify merge readiness

- [ ] Tasks complete or explicitly deferred
- [ ] Controls assessment current
- [ ] Checks run with evidence
- [ ] Documentation, changelog, examples current
- [ ] Gate E approval present
- [ ] No unapproved breaking change

Report readiness. **Stop.**

## Merge

**Never merge.** Gate F is explicit human authorization. Say the feature is ready and let the user
decide. If asked to merge, confirm first, then let the user run it — `gh pr merge` is denied in
`.claude/settings.json` by design.

The closeout should be the last documentation change on the branch before squash merge, except for
corrections a reviewer asks for.

## Outputs

- `design/NNN-slug/closeout.md`
- Updated architecture docs, changelog, configuration examples
- A merge-readiness report

## Validation rules

- Deviations section is explicit, including "none"
- Test results are re-run, not copied
- Unavailable checks reported as unavailable
- Changelog updated for any pattern change
- Lessons learned is substantive

## Approval requirements

Gate E precedes this. **Gate F (merge) requires explicit authorization** and is never performed here.

## Failure and recovery

| Situation | Do this |
|---|---|
| Gate E not yet approved | Stop. Closeout comes after review approval. |
| Tests now fail | Report it. The feature is not ready. |
| Deviations were never approved | Flag them. They need approval or reversion before merge. |
| Documentation out of date | Update it as part of closeout. |
| Asked to merge | Decline to do it directly; confirm readiness and hand the command to the user. |

## Does not

Merge. Publish. Approve. Copy forward stale test results.
