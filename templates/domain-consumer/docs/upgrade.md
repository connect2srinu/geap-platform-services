# Upgrading the pattern version

## Current version

See [`pattern.lock.yaml`](../pattern.lock.yaml). CI verifies on every run that the vendored source
still matches the lock — a mismatch means the vendored pattern was edited locally, which silently
breaks the contract.

## Plan the upgrade first

Compare the two released versions' contracts, configuration schema, extension interfaces, security
rules and infrastructure, and write down the migration steps before changing anything:

```bash
git diff <pattern>/v<current>..<pattern>/v<target> -- patterns/<pattern>/contracts \
    patterns/<pattern>/src/memory_manager/config.schema.json patterns/<pattern>/infrastructure
```

Run it in a clone of the platform repository. **Do not upgrade by bumping the lock file.**

## Check the path is supported

A target version lists its supported sources in `spec.upgrade.from`. If your current version is not
listed there is **no supported path** — you may need an intermediate version, or platform input.

## Procedure

1. Read the plan and the pattern `CHANGELOG.md` for **every** version between yours and the target,
   not just the target's entry.
2. Re-vendor at the new version and update `pattern.lock.yaml`, including the manifest digest.
3. Apply configuration changes; validate against the new schema.
4. Update extension implementations whose interfaces changed.
5. If platform-owned infrastructure changed, **confirm the platform team has applied it first** —
   ordering matters.
6. Run the new conformance suite:
   ```bash
   pytest -q vendor/pattern/conformance/
   ```
7. Run your own tests and your extension tests.
8. Deploy to a non-production environment and smoke test.
9. Deploy to production. Keep the previous revision available for rollback.

## Rollback

Roll traffic back to the previous Cloud Run revision. Note what **cannot** be rolled back: data
already written under new semantics, and any platform-owned infrastructure change. The migration plan
states these explicitly.
