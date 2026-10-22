---
artifact: change
feature: 008-branching-guidance
track: light
status: draft
---

# Change — single feature branch becomes the documented default

> **Light track.** All four conditions hold:
>
> - [x] No change to any API contract, tool API, or `pattern.yaml`
> - [x] No change to a security control or the security posture
> - [x] No new managed service, dependency, or extension point
> - [x] No architectural change

## What and why

`docs/onboarding/developer-guide.md` recommended git worktrees for parallel work and did not say when
to split a fix into its own branch. **VERIFIED** — following it produced six worktrees and five stacked
pull requests for four foundation defects discovered while 001 was in flight, which cost two
force-pushes, a stale-worktree merge failure that left `gh pr merge --delete-branch` half-complete,
and a bring-up-to-date pass on every remaining PR after each merge. All observed in this repository
between 2026-10-21 and 2026-10-22.

`.claude/rules/sdlc-gates.md` already says *"One folder, one branch, one PR, one owner."* The guide
did not reflect it. This change makes the guide agree with the rule.

| | |
|---|---|
| Classification | `documentation` |
| Patterns touched | none |

## Approach

- **Default stated plainly:** one feature, one branch, one PR — every task in a feature's `tasks.md`
  lands on that one branch.
- Clarified that `tasks.md`'s file-ownership column is for ordering and for parallel agents, **not**
  a reason to split branches. That ambiguity caused part of the sprawl.
- **Splitting now requires a stated reason**, as a table: unrelated to the feature (`CLAUDE.md`
  rule 11), high-contention shared files, blocking CI for every open PR, or another team needs it
  first. Both costs are named, not just the cost of splitting.
- **Worktrees demoted to a documented exception**, with the three failure modes **VERIFIED** in this
  repository: a worktree holding `main` blocks every other worktree and breaks
  `gh pr merge --delete-branch` part-way; `.venv` is per-directory and gitignored so a fresh worktree
  has no environment; stale worktrees cause the first failure.
- **New section on squash merge** discarding branch ancestry: `git branch -d` refuses on a merged
  branch, and `git branch --merged` does not see it. Delete by PR state.
- **New conflict-table row** for `strict: true` — every merge invalidates every other open PR, which
  is the mechanical reason stacked PRs are expensive.
- Four entries added to "things that will trip you up", including `gh pr merge` failing *after* a
  successful merge, and `gh pr checks` exiting 1 for non-required failures.

Added `docs/onboarding/**` to the high-contention list, which is why this change is itself a separate
branch rather than a commit on 001.

## Controls delta

None. No control, no security posture, no contract. Documentation only.

| Control | Effect | Status |
|---|---|---|
| — | none | unchanged |

## Verification

| Check | Command | Result |
|---|---|---|
| Design artifacts | `python3 scripts/validate_design_artifacts.py design/008-branching-guidance` | see below |
| Markdown links | repository link sweep | passed — 76 relative links, 0 broken |
| Guide agrees with the rule | read against `.claude/rules/sdlc-gates.md` | passed — both now say one folder, one branch, one PR |

Not run: `make verify` in full, because `design/001-memory-manager` reports its nine known
controls-check gaps and that is unrelated to this change.

## Approval

Light-track Gate A is recorded in the pull request description. Gate E is a human review; Gate F is
merge.
