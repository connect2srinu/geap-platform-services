---
name: pattern-publish
description: Prepares a versioned platform pattern release. Use when the user asks to "publish the pattern", "cut a release", "prepare a release", or "tag a version". Validates release readiness, semantic version correctness, changelog completeness, compatibility notes, conformance results and provenance configuration, then produces the release checklist and artifacts. PREPARATION ONLY — it never creates a tag, never creates a GitHub release, and never publishes. Publication requires explicit human approval and a human-run command.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(git status*)
  - Bash(git log*)
  - Bash(git tag -l*)
  - Bash(git diff*)
  - Bash(python3 scripts/validate_pattern_manifest.py*)
  - Bash(python3 scripts/check_platform_domain_boundary.py*)
  - Bash(python3 scripts/run_conformance.py*)
  - Bash(make verify)
  - Bash(sha256sum*)
user-invocable: true
---

# pattern-publish — Prepare a pattern release

## Purpose

Establish, with evidence, that a pattern version is fit to publish — and hand the publication itself
to a human.

## Hard boundary

**This skill never publishes.** It does not run `git tag`, `git push --tags`, `gh release create`, or
any registry command. Those are denied in `.claude/settings.json`. It produces a checklist and the
artifacts; a human reviews and executes.

This is not excessive caution. A published version is a contract with every adopting domain, and it
cannot be unpublished once consumed.

## Required inputs

- Pattern name and the intended version

## Steps

### 1. Validate the pattern

```bash
python3 scripts/validate_pattern_manifest.py patterns/<name>
python3 scripts/check_platform_domain_boundary.py
make verify
```

Any failure stops the release. Report it; do not continue to the checklist.

### 2. Check version correctness

Compare contracts and configuration against the last released tag:

```bash
git tag -l '<name>/v*' | sort -V | tail -5
git diff <name>/v<previous>..HEAD -- patterns/<name>/contracts patterns/<name>/config
```

Apply `standards/release-management.md`:

| Change | Required bump |
|---|---|
| Removed/renamed field, tightened validation, changed status or error code, changed semantics, removed extension point | **major** |
| New optional configuration, new extension point, additive contract change | **minor** |
| Fix with no contract or configuration change | **patch** |

If the intended version does not match the observed changes, **say so and stop.** A patch release
containing a breaking change is the most damaging thing this skill can prevent.

### 3. Check the changelog

`CHANGELOG.md` has an entry for this version stating: what changed, whether it is breaking, migration
steps, and security-relevant changes called out explicitly. Vague entries ("various fixes") are a
blocker — the changelog is how adopters decide whether to upgrade.

### 4. Check compatibility

`spec.compatibility` is current and tested. `spec.upgrade.from` lists every supported source version,
and each has migration guidance. A version with no guidance has **no supported path** — say that
rather than implying one exists.

### 5. Check conformance results

```bash
python3 scripts/run_conformance.py --pattern <name> --list
```

Report whether the suite has been **run** against a real build, and its result. An unrun suite is
`unavailable`. A pattern cannot leave `proposed` without a populated, passing suite.

### 6. Check live verification

Has a live managed-service verification been performed for this version? If not, **state that
explicitly** in the release notes. A mock-tested release is not an end-to-end verified release, and
the prior art is clear that this distinction matters.

### 7. Check provenance configuration

`.github/workflows/release.yml` is configured for `actions/attest-build-provenance` with Actions OIDC, and the
release will carry `SHA256SUMS`. Verify the configuration; do not run it.

### 8. Check status progression

`proposed` → `alpha` → `beta` → `certified`. Certification additionally requires: approved design and
controls, passing conformance, live verification, a runbook, and at least one adopting domain.
**Do not advance status** without those; say which are missing.

### 9. Produce the release checklist

```markdown
## Release readiness — <name> v<version>

| Check | Result | Evidence |
|---|---|---|
| Manifest valid | passed/failed | <output> |
| Boundary checks | passed/failed | <output> |
| Unit tests | passed/failed/unavailable | <output> |
| Conformance suite | passed/failed/unavailable | <output> |
| Live verification | performed/not performed | <detail> |
| Version bump correct | yes/no | <observed changes> |
| Changelog complete | yes/no | |
| Upgrade guidance | complete/gaps | |
| Provenance configured | yes/no | |
| Design & controls approved | yes/no | |

Status: <current> → <proposed>

### Blockers
<must be fixed before release>

### To publish, a human runs:
    git tag <name>/v<version>
    git push origin <name>/v<version>
    # then dispatch .github/workflows/release.yml (dry_run=true first; the 'release'
    # environment's required reviewers are the second gate)
```

### 10. Stop

Present the checklist. State clearly that nothing has been published and that publication needs
explicit approval.

## Outputs

- A release readiness report with evidence
- The exact commands for a human to run
- No tag, no release, no published artifact

## Validation rules

- Every check reported with its real status
- Version bump verified against actual contract diffs
- Unrun conformance reported as `unavailable`
- Absence of live verification stated explicitly

## Approval requirements

**Gate F.** Explicit human authorization. `.github/workflows/release.yml` is manually dispatched and gated by a
GitHub Environment with required reviewers — a setting a repository administrator configures by hand
(`docs/operations/repository-administration.md`).

## Failure and recovery

| Situation | Do this |
|---|---|
| Any validation fails | Stop. Report. Do not produce a "ready" checklist. |
| Version bump wrong | Stop. State the correct bump and why. |
| Conformance never run | Report `unavailable` and treat as a blocker above `proposed`. |
| Changelog incomplete | Blocker. |
| Asked to publish directly | Decline. Provide the commands for the user to run. |

## Does not

Create tags. Create releases. Publish artifacts. Advance status without the required evidence.
