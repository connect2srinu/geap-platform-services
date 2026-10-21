---
name: pattern-validate
description: Validates that a pattern satisfies the enterprise pattern contract. Use when the user asks to "validate the pattern", "check pattern compliance", "is this pattern complete", before preparing a release, or when reviewing a PR that changes a pattern. Checks manifest schema conformance, structural completeness, configuration schema validity, contract specifications, extension-point declarations and failure modes, security requirements, test and conformance suite presence, documentation, and deployment expectations. Read-only — reports findings and never modifies the pattern.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash(python3 scripts/validate_pattern_manifest.py*)
  - Bash(python3 scripts/check_platform_domain_boundary.py*)
  - Bash(python3 scripts/run_conformance.py --list*)
  - Bash(make validate-manifest)
  - Bash(make check-boundary)
  - Bash(terraform fmt -check*)
  - Bash(terraform validate*)
user-invocable: true
---

# pattern-validate — Check a pattern against the contract

## Purpose

Determine whether a pattern actually satisfies `standards/pattern-contract.md` — with evidence, not
inspection by eye.

## When to use

Before a release, when reviewing a pattern change, or whenever completeness is in question.

**Read-only.** Reports; never fixes. Fixing is a separate, tracked change.

## Steps

### 1. Run the automated validators

```bash
python3 scripts/validate_pattern_manifest.py patterns/<name>
python3 scripts/check_platform_domain_boundary.py
```

Capture real output. These cover the manifest schema, referenced paths, required structure, extension
failure modes, changelog consistency, primitive roles and real identifiers.

### 2. Check the 16 contract requirements

Walk `standards/pattern-contract.md` item by item. For each: satisfied, partial or missing, with the
artifact that proves it.

### 3. Validate the contracts

- OpenAPI specification parses and is complete.
- Every operation has request, response and error definitions.
- Error codes come from a defined catalogue.
- Idempotency is specified on mutating operations.
- `202` semantics documented where used.
- Versioning follows `standards/api-design.md`.

### 4. Validate the configuration schema

- Parses as JSON Schema 2020-12.
- Every key documented.
- `required` set for anything without a safe default.
- **No default weakens a security control.**
- Examples validate against the schema.
- Examples use neutral placeholders only.

### 5. Check extension points

- Declared in the manifest and present in `extensions/`.
- Each has a default.
- Security-relevant ones have `failureMode: deny` **and** a default that actually fails closed —
  check the code, not just the declaration.

### 6. Check security requirements

- `nonOverridableControls` declared and non-empty.
- No configuration key could disable one.
- Secrets by name only; no values anywhere.
- No primitive IAM roles.
- `nonRoot: true`.

### 7. Check tests

- `tests/` and `conformance/` both exist and are **separate**.
- Conformance is runnable by a consumer:
  ```bash
  python3 scripts/run_conformance.py --pattern <name> --list
  ```
- An **empty conformance suite is `unavailable`, not a pass.** Report it as such — this is the single
  most likely place for a pattern to look complete while being hollow.

### 8. Check infrastructure

- `platformOwned` and `domainOwned` both present and genuinely separate.
- Terraform validates:
  ```bash
  terraform fmt -check -recursive patterns/<name>/infrastructure
  terraform -chdir=<dir> init -backend=false && terraform -chdir=<dir> validate
  ```
- No `apply`. Ever.

### 9. Check documentation

README, build instructions, deployment documentation, runbook, upgrade guidance, changelog current.

### 10. Report

```
Pattern:    <name> v<version>  (status: <status>)

Automated
  manifest schema      passed / failed
  boundary checks      passed / failed
  terraform validate   passed / failed / unavailable

Contract requirements
  satisfied   N of 16
  partial     <list>
  missing     <list>

Findings
  [blocker]  ...
  [major]    ...
  [minor]    ...

Certification readiness: <assessment, with what is missing>
```

Separate blockers from nits. A pattern with 15 of 16 requirements and no conformance suite is not
"nearly done" — the missing one is the one that matters.

## Outputs

A validation report. No files changed.

## Validation rules

- Every check reported with its real status
- Empty conformance reported as `unavailable`, never passed
- Declared security behaviour verified in code, not just in the manifest

## Approval requirements

None — read-only. But a pattern cannot be published or certified until this passes.

## Failure and recovery

| Situation | Do this |
|---|---|
| Pattern not found | List available patterns. |
| Manifest invalid | Report the exact schema violation; stop further checks that depend on it. |
| Terraform unavailable | Report `unavailable`. |
| Conformance suite empty | Report as a **blocker** for anything beyond `proposed`. |
| Asked to fix findings | Decline here; propose `design-start-feature` for the fix. |

## Does not

Modify the pattern. Mark anything certified. Publish. Report unavailable checks as passed.
