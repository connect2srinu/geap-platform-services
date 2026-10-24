# GEAP Platform Services

Reusable engineering patterns for enterprise AI platform services, published by the Agent Platform
team and adopted by business domains.

## What this repository is

This repository **publishes versioned source patterns and reference implementations**. It is not a
deployed service and the platform team does not operate domain runtimes.

A pattern is a complete, adoptable unit: contracts, reference implementation, configuration schema,
declared extension points, reference infrastructure, a conformance suite, and upgrade guidance.
Domain teams take a versioned release, configure it, implement permitted extensions, build their own
container image, and deploy and operate it themselves.

## Three stakeholders

| Stakeholder | Owns | Consumes |
|---|---|---|
| **Platform team** | Patterns, contracts, conformance suites, reference infrastructure, the Memory Bank NFR wrapper | — |
| **Domain owners** (Customer, Inventory, …) | The adopted code, the business rules (RBAC, policy, privacy categories, prompts), their build, their deployment, their operations | A published pattern |
| **Agent teams** (KSA, …) | Their agents | A domain's deployed service, via its tool API and a domain-granted role |

Two contracts follow from this, and both are versioned:

1. **Platform → Domain** — the *pattern contract* (`pattern.yaml`, config schema, extension points).
2. **Domain → Agent team** — the *tool API contract* (OpenAPI). This one is **identical across every
   domain**, so that an agent written against one domain works against another.

## Patterns

| Pattern | Status | Version | Description |
|---|---|---|---|
| [memory-manager](patterns/memory-manager/) | `alpha` — adoptable by a pilot domain; the contract may still change | `0.1.0`, not yet tagged | Domain-owned governed memory tool API over a managed Memory Bank |

## Repository layout

```
.claude/skills/   three skills: feature-start, feature-review, pattern-release
standards/        engineering.md and security.md
schemas/          pattern manifest + design artifact front matter
patterns/         the published patterns
templates/        scaffolds for consumers, builds, infra, CI
design/           per-feature intent.md and design.md
docs/             decisions (ADRs) and onboarding
scripts/          validators — plain Python, no Claude Code needed
.github/          workflows, CODEOWNERS, PR template
```

## Getting started

- **First-time setup (macOS or Linux):** [docs/onboarding/getting-started.md](docs/onboarding/getting-started.md)
- **The whole lifecycle — build, gates, release, test as a client:** [docs/onboarding/demo.md](docs/onboarding/demo.md)
- **Developers:** [docs/onboarding/developer-guide.md](docs/onboarding/developer-guide.md)
- **Adopting a pattern:** [docs/onboarding/domain-adoption.md](docs/onboarding/domain-adoption.md)
- **Working here with Claude Code:** [CLAUDE.md](CLAUDE.md)

## Development lifecycle

Two documents, two gates:

```
intent.md  → approved  →  design.md  → approved  →  implement → PR → approved → merge
```

See [CLAUDE.md](CLAUDE.md) and [docs/onboarding/demo.md](docs/onboarding/demo.md).

## Validation

```bash
make verify
```

Every check is runnable without Claude Code. See [Makefile](Makefile).
