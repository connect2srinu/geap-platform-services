---
artifact: change
feature: NNN-slug
track: light
status: draft
---

# Change — <title>

> **Light track.** Use only when *every* statement below is true. If any becomes false during the
> work, stop and escalate to the full track — this is one-way and automatic.
>
> - [ ] No change to any API contract, tool API, or `pattern.yaml`
> - [ ] No change to a security control or the security posture
> - [ ] No new managed service, dependency, or extension point
> - [ ] No architectural change

## What and why

The problem and the fix, in a few sentences.

| | |
|---|---|
| Classification | `defect` / `dependency` / `documentation` / `test` / `config-example` |
| Patterns touched | |

## Approach

How it is being fixed. Note anything a reviewer should look at closely.

## Controls delta

Which controls this touches, if any, and why the posture is unchanged. If it changes, escalate.

| Control | Effect | Status |
|---|---|---|

## Verification

| Check | Command | Result |
|---|---|---|

Report `passed` / `failed` / `skipped` / `unavailable` separately.

## Approval

Gate A inline (in the PR description) and Gate E (human review). Gate F for merge.
