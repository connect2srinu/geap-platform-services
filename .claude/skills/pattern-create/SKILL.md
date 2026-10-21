---
name: pattern-create
description: Creates a new reusable platform pattern. Use when the user asks to "create a pattern", "start a new pattern", "add a platform capability", or when a design concludes that new reusable work needs its own pattern rather than extending an existing one. Generates the pattern directory, pattern.yaml manifest, contract skeleton, configuration schema, extension-point interfaces, platform-owned and domain-owned infrastructure directories, unit and conformance test structure, documentation and its design folder. Does not write implementation code — that needs an approved design.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(python3 scripts/validate_pattern_manifest.py*)
  - Bash(python3 scripts/check_platform_domain_boundary.py*)
user-invocable: true
---

# pattern-create — Scaffold a new platform pattern

## Purpose

Create the structure a new reusable pattern needs, so that Stage 1 can begin against a real skeleton
rather than a blank directory.

## When to use

A new reusable capability is wanted and it does not fit an existing pattern.

## When not to use

- It extends an existing pattern → `design-start-feature` against that pattern.
- It is domain-specific → it does not belong in `patterns/` at all.
- The capability is not yet agreed → start with `design-start-feature`.

## Required inputs

- Pattern name (kebab-case), one-line description, maintaining team
- What interfaces it exposes, and what a domain would configure or extend

Ask for anything missing. Do not invent a scope.

## Steps

### 1. Confirm it should be a pattern

Check `patterns/` for overlap. Ask: would a second domain genuinely use this? A pattern with one
plausible consumer is a domain service, not a platform pattern. Say so if that is the case.

### 2. Validate the name

`^[a-z][a-z0-9-]{2,40}$`, unique, describing the capability rather than its implementation.

### 3. Create the structure

```
patterns/<name>/
├── README.md
├── pattern.yaml
├── CHANGELOG.md
├── contracts/openapi.yaml
├── src/{api,policy,worker,providers}/
├── config/{config.schema.json,example.domain.yaml}
├── extensions/
├── infrastructure/terraform/{platform-owned,domain-runtime}/
├── tests/
├── conformance/
└── examples/
```

Copy `templates/new-pattern/` where it fits.

### 4. Generate pattern.yaml

Every field in `schemas/pattern.schema.json`. Rules:

- `metadata.status: proposed` — **always**. Nothing is certified at creation.
- `metadata.version: 0.1.0`
- `spec.build.ownedBy: domain` — the platform never builds a domain's image.
- `spec.runtime.container.nonRoot: true`
- Security-relevant extension points get `failureMode: deny`.
- `spec.infrastructure.platformOwned` and `domainOwned` both present — the split is what makes
  enforcement real (`standards/pattern-contract.md`).
- No primitive IAM roles.
- Secrets listed by **name and purpose only**.
- Neutral placeholders throughout. No real enterprise identifiers.

### 5. Extension-point interfaces

For each declared extension point, write the interface (a Python `Protocol`) and a default
implementation in `extensions/`. **Security-relevant defaults fail closed** — a classifier defaults to
deny-all, not allow-all.

The interface and default are platform code. Actual domain implementations live in the domain's
project.

### 6. Documentation skeleton

`README.md`: what it is, who owns what, how a domain adopts it, where the contracts are. State plainly
that domains build and deploy their own image.

`CHANGELOG.md`: Keep a Changelog header, `Unreleased` section.

### 7. Create the design folder

Next free number: `design/NNN-<name>/`, with `intent.md` from the template, `status: draft`. The
pattern's design has not been approved and the skeleton does not imply otherwise.

### 8. Validate

```bash
python3 scripts/validate_pattern_manifest.py patterns/<name>
python3 scripts/check_platform_domain_boundary.py
```

Both must pass before you report success.

### 9. Report

State what was created, that status is `proposed`, and that the next step is Stage 1 — not
implementation.

## Outputs

- `patterns/<name>/` with a valid manifest and complete structure
- `design/NNN-<name>/intent.md` in draft

## Validation rules

- Manifest validates against the schema
- Every referenced path exists
- Status is `proposed`
- Security-relevant extension points fail closed
- No primitive roles, no real identifiers, no secret values
- Boundary check passes

## Approval requirements

Creating the skeleton needs no gate. **Implementing it does** — Gates A through D.

## Failure and recovery

| Situation | Do this |
|---|---|
| Name collides | Stop; propose an alternative. |
| Overlaps an existing pattern | Stop; propose extending that one. |
| Only one plausible consumer | Say it is probably a domain service, not a pattern. |
| Interfaces not yet known | Declare them `planned` in the manifest rather than inventing a spec. |
| Manifest validation fails | Fix it before reporting success. |

## Does not

Write implementation code. Mark a pattern beyond `proposed`. Publish. Skip the design stages.
