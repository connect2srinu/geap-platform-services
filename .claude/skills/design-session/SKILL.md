---
name: design-session
description: Stage 2 (Design) of the platform SDLC. Use after intent.md is approved and the user asks to "design", "work out the architecture", "figure out how to build" a feature, or when sdlc-status shows Gate A passed and Gate B open. Inspects existing code and contracts, resolves design questions, proposes architecture, defines API and data contracts, declares configuration and extension points, evaluates alternatives, assesses backward compatibility, and generates design.md with diagrams and proposed ADRs. Stops at Gate B for human approval. Never writes implementation code.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(git log*)
  - Bash(git diff*)
  - Bash(python3 scripts/validate_design_artifacts.py*)
user-invocable: true
---

# design-session — Stage 2: Design

## Purpose

Produce a design good enough that implementation is mechanical and a reviewer can disagree with the
*approach* before any code is written.

## When to use

After Gate A. The design folder exists and `intent.md` is `status: approved`.

## When not to use

- `intent.md` is not approved → run `design-start-feature`, or get Gate A approval.
- The change is light track → `change.md` carries the approach; no separate design.

## Required inputs

- An approved `design/NNN-slug/intent.md`

## Prerequisites

Verify Gate A yourself. If `intent.md` is not `approved`, stop and say so.

## Steps

### 1. Read the approved intent

Scope, non-goals, acceptance criteria, open questions. The design answers the intent — it does not
expand it. New scope means returning to Stage 1.

### 2. Inspect the code and contracts

Actually read them:

- The pattern's `contracts/`, `src/`, `config/`, `extensions/`
- `pattern.yaml` — current version, compatibility, declared extension points
- Existing ADRs in `docs/decisions/`
- Prior art, where relevant

Record what you read under **Method**, with dates. Every `VERIFIED` claim traces back to it.

### 3. Read the applicable standards

`standards/architecture.md` always. Then `api-design.md` for contracts, `configuration.md` for
extension points, `security.md` for anything touching auth or data, `observability.md` for telemetry.

### 4. Resolve the design questions

Work through `intent.md`'s open questions. For each: resolve it with evidence, or carry it forward as
`OPEN` with who decides and what would resolve it. **Do not close a question by assuming an answer.**

Use `AskUserQuestion` when a decision is genuinely the user's — a trade-off with no technically
correct answer, or missing business context.

### 5. Propose the architecture

- Mermaid diagram, C4 container level, labelled `PROPOSED`.
- Follow the layering in `standards/architecture.md`.
- Show failure paths, not just the happy path.

### 6. Define contracts

Endpoints, shapes, status codes, error codes. Mark each change breaking or non-breaking, and say how
you determined it. Reference the OpenAPI spec rather than duplicating it.

Remember: the tool API is identical across every domain. A change here affects every agent team.

### 7. Define configuration and extension points

Prefer configuration over source modification. For each extension point: id, interface, required,
default, failure mode. **Security-relevant extensions fail closed.**

State explicitly which controls are non-overridable by domain configuration.

### 8. Evaluate alternatives

At least one real alternative, with why it was not chosen. "No alternative considered" means the
design has not been thought through. Include the option of doing nothing where that is plausible.

### 9. Address operations

Failure modes, retry and backoff, dead-lettering, idempotency, quota and throttling, degraded
operation, recovery, replay. For this platform specifically: quota is **shared across domains** in one
project — a design that ignores cross-domain contention is incomplete.

### 10. Address compatibility and migration

What breaks, who is affected, the migration path, and how you determined it.

### 11. Generate design.md

From `design/_template/design.md`. Fill every section. `status: draft`.

### 12. Propose ADRs

List decisions significant enough to record — contract changes, managed-service selection, security
posture, boundary changes, expensive-to-reverse choices. **Propose only.** `design-record-decision`
writes them after approval.

### 13. Validate and stop at Gate B

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

Present the design. State the open questions and assumptions prominently. Stop.

## Outputs

- `design/NNN-slug/design.md`, `status: draft`
- Diagrams in `docs/architecture/` where they are reusable
- A list of proposed ADRs

## Validation rules

- Front matter valid; `feature` matches the folder
- Method section names what was read
- At least one alternative evaluated
- Failure handling and compatibility sections are substantive, not placeholders
- Every intent acceptance criterion is addressed
- Claims carry evidence labels

## Approval requirements

**Gate B.** A human sets `status: approved`. Implementation planning does not start before that.

## Failure and recovery

| Situation | Do this |
|---|---|
| `intent.md` not approved | Stop. Report which gate is open. |
| Design needs scope not in the intent | Stop. Return to Stage 1 — do not expand scope here. |
| A question cannot be resolved | Carry it as `OPEN` with who decides. Never assume. |
| Requirements genuinely missing | Document the assumption explicitly. Do not invent a requirement. |
| The design implies a new pattern | Stop. Propose `pattern-create` instead. |

## Does not

Write implementation code. Create ADRs. Approve its own design. Expand scope beyond the intent.
