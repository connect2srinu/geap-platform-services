---
artifact: design
feature: NNN-slug
status: draft
---

# <title> — design

Requires an approved `intent.md`. **No implementation code before this is approved.**

## Provider assumptions verified

What was checked against the installed SDK or a live service, and what came back. Read the SDK, not
the documentation.

| Assumption | Result |
|---|---|

## Approach

The design. A Mermaid diagram if it helps.

## Contract

| Operation | Method | Path | Breaking? |
|---|---|---|---|

Error codes, status codes, idempotency.

## Configuration and extension points

What a domain sets, and what it plugs in. Every extension point has a default;
security-relevant defaults fail closed.

| Extension point | Required | Default | On failure |
|---|---|---|---|

## Security

Which of the eight rules in `standards/security.md` this touches, and the test covering each.
One line per rule.

| Rule | How it's met | Test |
|---|---|---|

## Risks

What could bite. Anything that cannot meet a security rule goes here with what compensates for it and
an expiry date.

| Risk | Impact | What we do about it |
|---|---|---|

## Alternatives

At least one, with why it wasn't chosen. "None considered" means it wasn't designed, it was defaulted
into.

## Tasks

A checklist. Not a project plan.

- [ ]

## Approval

A human sets `status: approved`.
