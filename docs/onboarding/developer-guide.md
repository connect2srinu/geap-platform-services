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

## Feature ownership and parallel work

- **One design folder, one branch, one PR, one owner.** `design/NNN-slug` for all three.
- Allocate `NNN` by taking the next free integer; claim it by pushing the branch. If two people
  collide, the later branch renumbers.
- **High-contention files** — `standards/**`, `schemas/**`, `.claude/**`, `CLAUDE.md` — get their own
  small PR, merged first. Do not bundle a standards change into a feature.
- `tasks.md` declares the **files each task owns**. Two tasks never own the same file.

### Worktrees

For concurrent features, so the branch name matches the directory:

```bash
git worktree add ../geap-platform-services-002 design/002-some-feature
```

```bash
git worktree remove ../geap-platform-services-002
```

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
