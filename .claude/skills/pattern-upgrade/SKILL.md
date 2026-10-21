---
name: pattern-upgrade
description: Guides a domain team through upgrading from one published pattern version to another. Use when the user asks to "upgrade the pattern", "move to version X", "what changed between versions", or "plan a migration". Identifies contract changes, configuration compatibility, required migration steps, security changes, and the regression tests needed to prove the upgrade is safe. Produces a migration plan. Does not perform the upgrade or deploy anything.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(git tag -l*)
  - Bash(git diff*)
  - Bash(git log*)
  - Bash(python3 scripts/validate_pattern_manifest.py*)
user-invocable: true
---

# pattern-upgrade — Plan a pattern version upgrade

## Purpose

Tell a domain team exactly what changes, what breaks, and what to test — before they upgrade.

## Required inputs

- Pattern name, current pinned version, target version
- The domain's configuration and extension implementations, where available

## Steps

### 1. Establish the versions

```bash
git tag -l '<pattern>/v*' | sort -V
```

Confirm both exist. Check `spec.upgrade.from` in the target: if the current version is not listed,
**there is no supported migration path** — say so plainly rather than improvising one. The honest
answer may be "upgrade to an intermediate version first" or "this needs platform input".

### 2. Read the changelog

Every entry between the two versions, not just the target's. A two-minor-version jump accumulates
changes that no single entry describes.

### 3. Diff the contracts

```bash
git diff <pattern>/v<current>..<pattern>/v<target> -- patterns/<pattern>/contracts
```

Classify each change:

| Change | Impact |
|---|---|
| New optional field | Compatible |
| New endpoint | Compatible |
| Removed or renamed field | **Breaking — agent teams affected** |
| Changed status or error code | **Breaking** |
| Tightened validation | **Breaking** |
| Changed semantics | **Breaking**, and the most dangerous kind — it compiles and then misbehaves |

Remember that the tool API is shared across domains: a contract change affects **every agent team**
integrating with this domain, not just the domain itself.

### 4. Diff the configuration schema

```bash
git diff <pattern>/v<current>..<pattern>/v<target> -- patterns/<pattern>/config
```

New required keys, removed keys, changed defaults, tightened validation. **Flag any changed default
that affects a security control** — a silently changed default is the quietest way to lose a control.

Validate the domain's existing configuration against the target schema if it is available.

### 5. Diff the extension points

Added, removed, changed interfaces or failure modes. An extension the domain implements whose
interface changed needs code changes, not just a version bump.

### 6. Identify security changes

Changes to `nonOverridableControls`, `cloudPermissions`, required secrets, or the prohibited-log-field
list. New permissions may need IAM changes before the upgrade, not after.

### 7. Diff the infrastructure

Changes to platform-owned versus domain-owned Terraform. Platform-owned changes may need to land
**before** the domain upgrades — call out the ordering.

### 8. Determine the regression tests

- The pattern's conformance suite at the target version.
- Tests for each breaking change the domain is affected by.
- The domain's own tests for its extensions.
- A smoke test against a real deployment.

### 9. Produce the migration plan

```markdown
# Upgrade: <pattern> v<current> → v<target>

## Supported path
<yes / no — and what to do if no>

## Breaking changes affecting this domain
| Change | Impact | Action required |
|---|---|---|

## Configuration changes
| Key | Change | Action |
|---|---|---|

## Extension changes
| Extension | Change | Action |
|---|---|---|

## Security changes
<controls, permissions, secrets>

## Infrastructure ordering
<what the platform must do first, if anything>

## Migration steps
1. ...

## Regression tests
| Test | Proves |
|---|---|

## Rollback
<how to go back, and what cannot be rolled back>

## Risk assessment
<what could go wrong>
```

### 10. Stop

Present the plan. The upgrade itself is the domain's work and decision.

## Outputs

A migration plan. Nothing upgraded, nothing deployed.

## Validation rules

- Both versions verified to exist
- Unsupported paths stated plainly, never improvised
- Every breaking change classified by impact on this domain
- Security-relevant default changes called out
- Rollback addressed, including what cannot be rolled back

## Approval requirements

None to plan. The upgrade is the domain's decision and action.

## Failure and recovery

| Situation | Do this |
|---|---|
| A version does not exist | List available versions; stop. |
| No supported path | Say so. Propose an intermediate version or escalate to the platform team. |
| Changelog incomplete | Diff the code and say the changelog was insufficient. |
| Domain configuration unavailable | Produce a generic plan; state what could not be checked. |
| Asked to perform the upgrade | Produce the plan; the domain executes it. |

## Does not

Perform upgrades. Deploy. Modify a domain's project. Invent a migration path that was never supported.
