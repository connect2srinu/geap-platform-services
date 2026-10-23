---
name: feature-start
description: Start a feature. Use when the user wants to build, add, change or fix something that has no design folder yet — "let's add X", "I want to build Y", "we need to fix Z". Writes intent.md (what and why), stops for approval, then writes design.md (how), and stops again. Never writes implementation code.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(git status*)
  - Bash(git log*)
  - Bash(git checkout -b*)
  - Bash(make verify)
  - Bash(python3 scripts/validate_design_artifacts.py*)
user-invocable: true
---

# feature-start

Two documents, two stops. Nothing else.

## Step 1 — intent.md

Find the next free `NNN`, create `design/NNN-slug/intent.md` from `design/_template/intent.md`, and
fill it in. **Half a page.** Scope, non-goals, and how we will know it works.

Ask if the objective is unclear. Never invent one.

Then **stop** and ask for approval. Do not continue to the design.

## Step 2 — design.md, after the intent is approved

Check `intent.md` says `status: approved`. If it doesn't, stop and say so.

Before designing, **verify the provider assumptions the design will rest on.** Read the installed SDK
rather than the documentation, and where it matters write a throwaway script in
`design/NNN-slug/spike/` and ask the user to run it. This has caught three contract-level defects that
would otherwise have surfaced mid-implementation.

Then write `design/NNN-slug/design.md` — **two to three pages**:

- **Approach** — the design, with a Mermaid diagram if it helps
- **Contract** — endpoints, shapes, error codes; what breaks
- **Configuration and extension points** — what a domain sets, what it plugs in
- **Security** — which of the eight rules in `standards/security.md` this touches, and the test that
  covers each. One line per rule.
- **Risks** — what could bite, including anything that can't meet a security rule, with what
  compensates and an expiry
- **Tasks** — a checklist. Not a project plan.

Then **stop** and ask for approval.

## After approval

Create the branch and a draft PR, then implement — one task at a time, tests in the same commit.

```bash
git checkout -b design/NNN-slug
```

## Never

Write implementation code before `design.md` is approved. Set `status: approved` yourself. Create more
than these two documents.
