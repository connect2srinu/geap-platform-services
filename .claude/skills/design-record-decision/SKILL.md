---
name: design-record-decision
description: Records an approved architecture decision as an ADR in docs/decisions/. Use when the user says "record this decision", "write an ADR", "document this choice", or when an approved design contains a significant decision — a contract change, managed-service selection, security-posture change, platform/domain boundary change, or anything expensive to reverse. Only writes ADRs for decisions a human has approved; never generates one speculatively or for routine implementation details.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
user-invocable: true
---

# design-record-decision — Architecture decision records

## Purpose

Capture *why* a significant decision was made, so that a future engineer can tell a deliberate choice
from an accident.

## When to use

A decision has been **approved** and it:

- changes a published contract or the tool API;
- selects or replaces a managed service;
- changes the security or isolation posture;
- changes the platform/domain boundary, or adds an extension point;
- is expensive to reverse.

## When not to use

- The decision is not yet approved → it stays a proposal in `design.md`.
- It is a routine implementation choice — a variable name, a file layout, a library already standard
  here. ADRs for everything make ADRs worthless.

## Required inputs

- The decision, and evidence that it was approved (who, when).
- The context: what forced the decision, what was considered.

## Steps

### 1. Confirm approval

Ask who approved it and when, if not already clear. **Do not write an ADR for a decision Claude
reached on its own.** An ADR records a human's decision.

### 2. Confirm it is ADR-worthy

Check against the list above. If it is not, say so and suggest recording it in `design.md` instead.

### 3. Allocate the number

Next sequential: `docs/decisions/ADR-NNNN-<kebab-title>.md`. Never reuse a number, including for
superseded ADRs.

### 4. Write it

```markdown
# ADR-NNNN: <Title>

- **Status:** Accepted
- **Date:** YYYY-MM-DD
- **Decision owners:** <the humans who decided>
- **Scope:** <what this governs>
- **Related:** design/NNN-slug/design.md

## Context

What forced this decision. The constraints, the evidence, what was and was not known. Label claims
`VERIFIED` / `PROPOSED` / `OPEN` / `ASSUMPTION`.

## Decision

What was decided, in the active voice and unambiguously. A reader must be able to tell whether a
future change contradicts it.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|

At least one real alternative. "None considered" means the decision was not made, it was defaulted
into.

## Consequences

What becomes easier, what becomes harder, what is now constrained. Include the costs — an ADR listing
only benefits is advocacy, not a record.

## Compatibility implications

Effects on published contracts, adopters, and supported upgrade paths. If none, say how that was
determined.

## Status history

| Date | Status | Note |
|---|---|---|
| YYYY-MM-DD | Accepted | Initial decision |
```

Statuses: `Proposed` · `Accepted` · `Superseded by ADR-NNNN` · `Deprecated`.

### 5. Link it

- Add `related_adrs: [ADR-NNNN]` to the design artifact's front matter.
- If it supersedes one, update that ADR's status and history — never delete or rewrite it. A
  superseded ADR is still the record of what was true then.
- Add it to `docs/decisions/README.md`.

## Outputs

- `docs/decisions/ADR-NNNN-<kebab-title>.md`
- Updated index and cross-references

## Validation rules

- Sequential number, never reused
- Decision owners are humans
- At least one alternative, with reasoning
- Consequences include costs
- Superseded ADRs updated, not deleted

## Approval requirements

The *decision* is approved before the ADR is written. The ADR itself is reviewed with the PR.

## Failure and recovery

| Situation | Do this |
|---|---|
| Decision not yet approved | Keep it in `design.md` as proposed. |
| Decision came from Claude, not a human | Present it as a recommendation; ask for a decision first. |
| Not significant enough | Say so. Suggest `design.md` instead. |
| It contradicts an existing ADR | Flag the conflict. Supersede explicitly, never silently. |

## Does not

Make decisions. Write ADRs for unapproved proposals. Delete or rewrite superseded ADRs.
