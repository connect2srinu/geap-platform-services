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
| [memory-manager](patterns/memory-manager/) | `proposed` — design not yet approved | — | Domain-owned governed memory tool API over a managed Memory Bank |

## Repository layout

```
.claude/          Claude Code operating rules and the 13 project skills
standards/        Normative engineering standards
schemas/          Machine-readable schemas (pattern manifest, design artifacts)
patterns/         The published patterns
templates/        Scaffolds for new patterns, domain consumers, builds, infra, CI
design/           Per-feature SDLC artifacts (intent, design, controls, tasks, closeout)
docs/             Architecture, decisions (ADRs), onboarding, operations, releases
scripts/          Validators — independently runnable, no Claude Code required
.github/          Workflows, CODEOWNERS, PR template
```

## Getting started

- **Developers:** [docs/onboarding/developer-guide.md](docs/onboarding/developer-guide.md)
- **The whole flow end to end:** [docs/onboarding/worked-example.md](docs/onboarding/worked-example.md)
- **Every command, in order:** [docs/onboarding/cli-runbook.md](docs/onboarding/cli-runbook.md)
- **Keystroke-by-keystroke, session by session:** [docs/onboarding/cli-session-script.md](docs/onboarding/cli-session-script.md)
- **Working with Claude Code here:** [CLAUDE.md](CLAUDE.md) and
  [docs/onboarding/skill-catalog.md](docs/onboarding/skill-catalog.md)
- **Adopting a pattern (domain teams):** [docs/onboarding/domain-adoption.md](docs/onboarding/domain-adoption.md)
- **Integrating an agent (agent teams):** [docs/onboarding/agent-team-guide.md](docs/onboarding/agent-team-guide.md)
- **Repository administrators:** [docs/operations/repository-administration.md](docs/operations/repository-administration.md)
  — six settings that must be configured by hand; they are the only real approval gates.

## Development lifecycle

Six stages with explicit human approval gates. No implementation begins before the design and task
plan are approved.

```
Intent ──A──► Design ──B──► Controls ──C──► Build (plan ──D──► implement) ──► Review ──E──► Close ──F──► merge
```

See [standards/architecture.md](standards/architecture.md) and
[.claude/rules/sdlc-gates.md](.claude/rules/sdlc-gates.md).

## Validation

```bash
make verify
```

Every check is runnable without Claude Code. See [Makefile](Makefile).
