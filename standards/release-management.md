# Release management

## Versioning

Semantic versioning, **per pattern**. A pattern's version is independent of the repository and of
other patterns.

| Change | Bump |
|---|---|
| Breaking contract change; removed or renamed configuration; removed extension point | **major** |
| New optional configuration; new extension point; additive contract change; new capability | **minor** |
| Fix with no contract or configuration change | **patch** |

Pre-1.0 (`0.x`): minor may break. A pattern reaching `certified` moves to `1.0.0`.

## Tags and releases

Pattern-scoped tags, so patterns in one repository release independently:

```
memory-manager/v0.1.0
evaluation-api/v0.2.1
```

A GitHub Release per tag carries:

1. a tarball of `patterns/<name>/` at that tag;
2. `pattern.yaml`;
3. `SHA256SUMS`;
4. the compatibility matrix;
5. the conformance suite;
6. provenance attestation (`actions/attest-build-provenance`, via Actions OIDC).

## Consumption

Domains **vendor the released source** — it matches "build your own image" and needs no package
registry. The consumer project records the pinned version:

```yaml
pattern: { name: memory-manager, version: 0.1.0 }
```

Revisit at the second adopting domain; a published package may win once upgrade friction is observed.

## Changelog

`patterns/<name>/CHANGELOG.md`, Keep a Changelog format. Every release states: what changed, whether
it is breaking, required migration steps, and security-relevant changes called out explicitly.

## Compatibility

Each release declares its tested compatibility — provider SDK range, Terraform version, provider
versions, supported upgrade sources. A version not listed under `upgrade.from` has no supported
migration path, and saying so is better than implying one.

## Deprecation

Announce in `CHANGELOG.md` with a removal date; keep at least one minor release of overlap; provide
the migration path before removal, not with it.

## The publish gate

`pattern-publish` **prepares and validates** a release: readiness checks, version consistency,
changelog completeness, conformance results, provenance configuration. It does not publish.

A human creates the tag and the release, after explicit approval. **No skill, hook or workflow
publishes a release on its own.** `.github/workflows/release.yml` is manually dispatched and gated by a GitHub
Environment with required reviewers — one of the six settings a repository administrator must
configure by hand (`docs/operations/repository-administration.md`).

## Release readiness

- [ ] Design and controls assessment approved
- [ ] Conformance suite passes — with output
- [ ] Live managed-service verification performed, or its absence stated
- [ ] `pattern.yaml` validates; version bumped correctly
- [ ] `CHANGELOG.md` complete; breaking changes flagged
- [ ] Upgrade guidance present for every supported source version
- [ ] Security scans clean or exceptions approved
- [ ] Documentation and runbook current
- [ ] Reference build produces a working image
