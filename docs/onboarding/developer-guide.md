# Developer guide

## Setup

First time on a machine: [getting-started.md](getting-started.md), from installing the tools to the
service answering on `localhost`. After that:

```bash
make deps
```

```bash
make verify
```

`make deps` creates a project `.venv` on Python 3.12. Never `pip install` into the system Python,
and never use `--break-system-packages`.

`make verify` reports `unavailable` rather than silently skipping when a tool is missing. **Unavailable
is not a pass** — treat it as a blind spot.

## The process

For the whole lifecycle — build, release, test as a client, adopt — with every gate, see
[demo.md](demo.md). It is also a script you can run in front of people.

Two documents, two gates. [CLAUDE.md](../../CLAUDE.md) has the rules; this is the mechanics.

```bash
claude
```

```
/feature-start
```

It writes `design/NNN-slug/intent.md` and stops. You read it and set the front matter yourself:

```yaml
status: approved
approved_by: <your name>
approved_date: 2026-10-22
```

Edit it by hand. That step's whole value is that a person read the document — a scripted approval is
not an approval.

Then it writes `design.md` and stops again. Approve the same way. **Then** implementation starts.

```bash
git checkout -b design/NNN-slug && git push -u origin design/NNN-slug
gh pr create --draft --title "NNN: <title>" --body "Design: design/NNN-slug/"
```

When the work is done:

```
/feature-review
```

Then a human approves the PR and merges.

## Branching

**One feature, one branch, one PR.** Every task lands on `design/NNN-slug`. Fix incidental defects in
the same branch — don't open a second PR for a typo.

Split a fix out only when it touches `standards/`, `schemas/`, `.claude/`, `CLAUDE.md` or
`.github/workflows/`, or when it is blocking CI for every open PR.

No worktrees unless you are genuinely building two features at once.

## Things that bite

| Trap | Reality |
|---|---|
| "The validator passed, so the gate is approved" | It checks form, not approval. A well-formed draft passes. Read the status line it prints. |
| "The tests should pass" | Run them. Paste the output. |
| "`make verify` said unavailable, that's fine" | It means the check did not run. Not a pass. |
| "I'll add the domain's rule here, it's small" | It belongs in configuration or an extension point. There is a test for this. |
| "A mock test proves the integration works" | It proves your code calls the mock. Verify against the real service separately. |
| "`git branch -d` says not merged" | Squash merge discards ancestry. Check the PR state, then `-D`. |
| "`gh pr checks` exited 1" | It exits 1 if *any* check fails, required or not. |
| "A PR won't merge, it's behind" | Branch protection is `strict` — bring it up to date with `git merge origin/main` first. |

## Repository settings an admin must configure by hand

These are not in the repository and do not travel with a clone:

1. Branch protection on `main`: require a PR, require the status checks, no force-push, no deletion,
   include administrators.
2. Secret scanning, push protection, Dependabot.
3. A `release` environment with required reviewers.
4. Tag protection on `*/v*`.
5. Real teams in `.github/CODEOWNERS` — `gh api repos/:owner/:repo/codeowners/errors` must return
   an empty list.

**On a single-maintainer repository, GitHub will not let you approve your own PR.** Set
`required_approving_review_count: 0` and be honest that review is unenforced, rather than configuring
a gate that blocks every merge.
