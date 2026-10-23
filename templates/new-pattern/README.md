# <Pattern Name>

<One paragraph: the capability this pattern provides and the problem it solves.>

**Status:** `proposed` — the design has not been approved. Not ready for adoption.

## Ownership

| | |
|---|---|
| **Platform team owns** | This source, the contracts, the conformance suite, the platform-owned infrastructure |
| **Domain team owns** | Configuration, extension implementations, the container image, the deployment, operations |

The platform team does not build or operate a domain's image.

## Interfaces

See [`contracts/`](contracts/). The tool API is **identical across every domain** — a domain
configures policy behind it and does not change the surface.

## Configuration and extension points

See [`src/<pattern_name>/config.schema.json`](src/) and `src/<pattern_name>/extensions/`.
`src/` is a build root holding one package — see [`src/README.md`](src/README.md).

| Extension point | Required | Default | Failure mode |
|---|---|---|---|

Security-relevant extensions fail closed.

## Adoption

```bash
# From Claude Code in the platform repository
/domain-onboard
```

Or follow [docs/onboarding/domain-adoption.md](../../docs/onboarding/domain-adoption.md).

## Testing

| Suite | Who runs it |
|---|---|
| `tests/` | Platform team |
| `conformance/` | **The domain team, in its own CI** |

## Build

See [`examples/Dockerfile`](examples/Dockerfile). Domain-owned.

---

## A note on this template's `pattern.yaml`

The template manifest is deliberately **schema-shaped but not schema-valid**: `<pattern-name>` and the
other placeholders fail validation on purpose, so that a copied-but-unfilled manifest cannot pass CI.
`pattern-create` replaces every placeholder, and `scripts/validate_pattern_manifest.py` must pass
before the new pattern is considered created.
