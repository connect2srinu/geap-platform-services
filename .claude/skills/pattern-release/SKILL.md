---
name: pattern-release
description: Prepare a pattern version for release. Use when the user asks to "cut a release", "publish the pattern", or "tag a version". Validates readiness, checks the version bump against the actual contract diff, and produces the checklist and the exact commands. PREPARATION ONLY — never tags, never publishes.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash(git log*)
  - Bash(git tag -l*)
  - Bash(git diff*)
  - Bash(make verify)
  - Bash(python3 scripts/validate_pattern_manifest.py*)
  - Bash(sha256sum*)
user-invocable: true
---

# pattern-release

**This skill never publishes.** No `git tag`, no `gh release create`. A published version is a
contract with every adopting domain and cannot be withdrawn once consumed.

## 1. Validate

```bash
python3 scripts/validate_pattern_manifest.py patterns/<name>
make verify
```

Any failure stops the release. Report it; do not produce a "ready" checklist anyway.

## 2. Check the version against the real diff

```bash
git diff <name>/v<previous>..HEAD -- patterns/<name>/contracts patterns/<name>/config
```

Removed or renamed field, changed status or error code, tightened validation, changed semantics →
**major**. New optional config or capability → **minor**. Fix with no contract change → **patch**.

If the intended version doesn't match what changed, **say so and stop**. A patch release containing a
breaking change is the most damaging thing this skill can prevent.

## 3. Check the rest

- `CHANGELOG.md` has an entry stating what changed, whether it is breaking, and the migration steps.
- Conformance suite has been **run** against a real build — report the result, or `unavailable`.
- Live managed-service verification: performed, or **state plainly that it was not**.
- `metadata.status` is not `proposed`.

## 4. Produce the checklist and the commands

```
## Release readiness — <name> v<version>
| Check | Result | Evidence |

### Blockers
### To publish, a human runs:
    git tag <name>/v<version> && git push origin <name>/v<version>
    gh workflow run release.yml -f pattern=<name> -f version=<version> -f dry_run=true
```

Then stop. State clearly that nothing has been published.
