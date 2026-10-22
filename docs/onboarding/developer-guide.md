# Developer guide

## First hour

1. Read [`CLAUDE.md`](../../CLAUDE.md) — the operating rules.
2. Skim [`standards/architecture.md`](../../standards/architecture.md) — what this repository is and
   is not.
3. Read [`standards/pattern-contract.md`](../../standards/pattern-contract.md), especially *The
   limits of enforcement*. It is the most important section in the repository and the easiest to get
   wrong.
4. Skim the [skill catalog](skill-catalog.md).
5. Read the [worked example](worked-example.md) — one pass through the whole flow, from an empty
   design folder to a second domain in production. It is the fastest way to see how the gates,
   the release track and domain adoption fit together.
6. Keep the [CLI runbook](cli-runbook.md) open the first time you run the flow — it is every
   command in order, including the one-time setup this repository still needs.

## Setup

```bash
make deps
```

> On Debian, Ubuntu and WSL the system Python is **externally managed** (PEP 668) and refuses a
> bare `pip install`. `make deps` creates a project `.venv` and installs into it — do not pass
> `--break-system-packages`.

```bash
make verify
```

`make verify` reports `unavailable` rather than silently skipping when a tool is absent. That is
deliberate — an unavailable check is not a pass.

`make deps` installs `ruff`, `mypy` and `pytest` into the same `.venv`, so `make lint` and
`make test` run rather than reporting `unavailable`. For ad-hoc commands:

```bash
source .venv/bin/activate
```

## The mental model

This repository **publishes patterns**. It is not a service. Three stakeholders:

- **Platform team** (you) — publishes patterns, contracts, conformance suites, and the platform-owned
  infrastructure that is the one hard control.
- **Domain owners** — adopt, own and customize the code; build their own image; deploy and operate.
- **Agent teams** — call a domain's deployed service through the tool API.

Two contracts, both versioned: platform→domain (the pattern contract) and domain→agent team (the tool
API). **The tool API is identical across every domain** — that is what makes agents portable, and it is
why `patterns/*/contracts/` has the strictest review ownership here.

## Daily workflow

```bash
/sdlc-status
```

Then the skill for the current stage. Do not improvise a process — the skills exist so that the
process is the same for everyone.

**Never write implementation code before Gates B and D.** This is the rule most likely to be broken
under time pressure and most expensive when it is.

## Feature ownership and branching

**Default: one feature, one branch, one PR.** `design/NNN-slug` names the design folder, the branch
and the PR. Every task in that feature's `tasks.md` lands on that one branch — a 40-task feature is
still one branch and one PR, not forty.

- Allocate `NNN` by taking the next free integer; claim it by pushing the branch. If two people
  collide, the later branch renumbers.
- `tasks.md` declares the **files each task owns**. Two tasks never own the same file. That is for
  ordering and for parallel agents, not a reason to split branches.
- Work in the main checkout with plain `git checkout`. No worktrees by default.

### Defects you find mid-feature

Fix them **in your branch**. Report them in the feature's artifacts and move on.

Split a fix into its own branch and PR **only** when one of these is true:

| Condition | Why |
|---|---|
| It is **unrelated to your feature** — process docs, another pattern, unconnected tooling | `CLAUDE.md` rule 11. An unrelated change in a feature PR is invisible to the people who should review it, and it rides on that feature's gates instead of its own. |
| It touches `standards/**`, `schemas/**`, `.claude/**`, `CLAUDE.md`, `docs/onboarding/**` or `.github/workflows/**` | High-contention shared files. A feature branch holding them blocks everyone else. |
| It is **blocking CI for every open PR** | Everyone stays red until it lands. |
| Another team needs it before your feature is done | Your feature would hold their fix hostage. |

Otherwise, in-branch. The cost of splitting is real: more branches, more merges, more rebases after
each one, and each split PR must be brought up to date again when the previous one merges.

The cost of *not* splitting is also real — a bigger PR, mixed concerns, weaker review. Accept that
when nothing else is in flight; split when something is.

### Worktrees — the exception, not the habit

Only when you are genuinely building **two features at once** and need both checked out:

```bash
git worktree add ../geap-platform-services-002 design/002-some-feature
```

```bash
git worktree remove ../geap-platform-services-002
```

Three things that bite, all of them learned the hard way:

- **A worktree holding `main` blocks every other worktree from switching to it.** Keep `main` checked
  out in at most one place. `gh pr merge --delete-branch` fails part-way through when it cannot.
- **`.venv` is per-directory and gitignored**, so a new worktree has no environment. Either run
  `make deps` in it or run commands from the main checkout — and say which when reporting results.
- **Remove a worktree as soon as its PR merges.** They accumulate fast and stale ones cause the
  failure above.

### Squash merge and branch deletion

Merges are squashed, which **discards branch ancestry**. Consequences:

- `git branch -d` refuses with "not fully merged" even when the PR is merged. Confirm the PR state,
  then use `-D`.
- Anything relying on `git branch --merged` will not see it either.

Delete merged branches by **PR state**, never by git ancestry.

### Multiple AI agents

- Bounded task from `tasks.md`, with its declared file ownership.
- Never two agents editing one file.
- An agent needing a file outside its task **stops and reports** rather than widening its scope.
- Only two specializations are justified today: an **independent reviewer** context for Stage 5 (a
  reviewer that did not write the code finds more), and a **read-only explorer** for codebase
  questions. Resist adding more without evidence that they help.

## Conflict resolution

| Conflict | Resolution |
|---|---|
| Two features need the same pattern file | Sequence them. The second rebases. |
| Two features change the same contract | Stop. This needs a design decision, not a merge. |
| A standards change conflicts with in-flight work | Standards merge first; features rebase. |
| Design folder number collision | Later branch renumbers. |
| A PR is "behind" and will not merge | Branch protection uses `strict: true`, so every merge invalidates every other open PR. Bring each up to date with `git merge origin/main` before merging it. This is why stacked PRs are expensive, and why one feature branch is the default. |

## Before you push

```bash
make verify
```

Report results honestly, including what was unavailable. See
[`.claude/rules/evidence-and-claims.md`](../../.claude/rules/evidence-and-claims.md).

## Things that will trip you up

| Trap | Reality |
|---|---|
| "I'll just add the domain's rule here, it's small" | It belongs in configuration or an extension point. There is a test for this. |
| "The tests should pass" | Run them. Paste the output. |
| "The conformance suite is empty, so it passes" | Empty is **unavailable**. It is the single most likely way a pattern looks complete while being hollow. |
| "CODEOWNERS requires review" | It assigns reviewers. Requiring review is a setting an administrator configures. |
| "Separate memory banks give separate quota" | They do not. Quota is per project, per region, shared across every domain. |
| "A mock test proves the integration works" | It proves your code calls the mock correctly. Nothing more. |
| "I'll split this fix into its own PR to keep it clean" | Each split PR must be brought up to date again after every other merge. Split only for the reasons above. |
| "`git branch -d` says not merged, so it isn't" | Squash merge discards ancestry. Check the PR state. |
| "`gh pr merge` failed, so the merge didn't happen" | Check first. It may have merged and failed only on `--delete-branch`. |
| "`gh pr checks` exited 1, so a required check failed" | It exits 1 if *any* check fails, required or not. Compare against the required list. |
