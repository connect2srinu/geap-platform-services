# <pattern> v<x.y.z>

> Release-track artifact. Produced by `pattern-publish`, reviewed at Gate E, published by a human at
> Gate F. `.github/workflows/release.yml` requires this file to exist and to state the
> live-verification status below.

| | |
|---|---|
| Pattern | `<pattern>` |
| Version | `<x.y.z>` |
| Status | `alpha` / `beta` / `certified` |
| Date | `<YYYY-MM-DD>` |
| Tag | `<pattern>/v<x.y.z>` |

## What changed

<!-- Summarise from CHANGELOG.md. State breaking changes first and plainly. -->

## Breaking changes

<!-- Each with the migration step. "None" is a valid answer; silence is not. -->

## Live managed-service verification

<!-- REQUIRED. The workflow greps for this heading. One of:
     - "Performed on <date> against <environment>: a value was written and read back in a later
       session."
     - "NOT PERFORMED. Unit and conformance tests ran against a fake provider client only. The first
       adopting domain is the first live user."
     Never imply the first when the second is true. -->

## Verification

| Check | Result | Evidence |
|---|---|---|
| Pattern manifest | | |
| Boundary checks | | |
| Unit tests | | |
| Conformance suite | | |
| Security scans | | |
| Terraform validate | | |

Report `passed` / `failed` / `skipped` / `unavailable` separately.

## Compatibility

| | |
|---|---|
| Upgrades supported from | |
| Provider SDK | |
| Terraform | |

## Known limitations

## Adoption

```
pattern: { name: <pattern>, version: <x.y.z> }
```

See [domain adoption](../onboarding/domain-adoption.md).
