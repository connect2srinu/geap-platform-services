# The platform pattern contract

What every reusable pattern in this repository must provide, and — just as importantly — what the
platform can and cannot enforce once a domain adopts it.

## Required of every pattern

| # | Requirement | Artifact |
|---|---|---|
| 1 | Unique name, description, maintainer | `pattern.yaml` |
| 2 | Semantic version | `pattern.yaml`, git tag |
| 3 | Runtime requirements | `pattern.yaml` |
| 4 | Versioned interfaces with a machine-readable specification | `contracts/` |
| 5 | Configuration schema + safe examples | `config/` |
| 6 | Declared extension points with defaults | `extensions/`, `pattern.yaml` |
| 7 | Required secrets — names and purposes, never values | `pattern.yaml` |
| 8 | Required cloud permissions, least privilege | `pattern.yaml` |
| 9 | Infrastructure dependencies, split platform-owned vs domain-owned | `infrastructure/` |
| 10 | Security requirements and non-overridable controls | `pattern.yaml`, `controls-check.md` |
| 11 | Observability requirements | `pattern.yaml` |
| 12 | Reference build instructions producing a domain-owned image | `examples/Dockerfile`, docs |
| 13 | Deployment documentation and a runbook | `docs/` |
| 14 | Unit tests **and** a consumer-runnable conformance suite | `tests/`, `conformance/` |
| 15 | Compatibility information | `pattern.yaml` |
| 16 | Upgrade and migration guidance | `CHANGELOG.md`, upgrade guide |

Validated by `scripts/validate_pattern_manifest.py` against `schemas/pattern.schema.json`.

## Status lifecycle

`proposed` → `alpha` → `beta` → `certified` → `deprecated`

Certification is a governance act requiring: an approved design and controls assessment, a passing
conformance suite, a live managed-service verification, a runbook, and at least one adopting domain.
**Nothing is certified by default.** A pattern whose design is not yet approved stays `proposed`.

## What a domain may customize

Configuration · extension implementations · prompts · privacy vocabulary · Terraform variables ·
scaling · its own CI · its own image and registry.

## What a domain must preserve

The tool API contract and error catalogue · non-overridable controls · the audit event schema and the
platform audit sink · required metrics and the prohibited-log-field list · the idempotency contract ·
platform-owned Memory Bank IAM and provisioning · `pattern.yaml` compatibility pins.

## Detecting unsupported change

| Mechanism | Detects | Runs where |
|---|---|---|
| Conformance suite | Contract and control behaviour, black-box | **The domain's CI** |
| `check_platform_domain_boundary.py` | Domain code importing platform internals; redefined controls | **The domain's CI** |
| Manifest digest check | An altered `pattern.yaml` | **The domain's CI** |
| Platform-owned Terraform | IAM posture, audit sink, quota alerting | **Platform**, independent of the application |

## The limits of enforcement — read this before claiming a control

Domain teams **own and customize the code**. That is the model, not a weakness to be engineered away.
It follows that:

- The first three mechanisms above run in **the domain's own CI**, which the platform does not control
  and cannot observe. A domain that forks the source can disable all three.
- **Only the fourth survives a fork**, and only because the Memory Bank is provisioned, IAM-bound,
  audit-sunk and quota-alerted by platform-owned Terraform in the platform-owned GCP project. That
  single seam is the whole hard-enforcement story.
- Precisely: the platform controls **what a domain's service account may do to a memory bank**. It does
  **not** control what the domain's code does before it gets there.

So: a claim that a control is "enforced for all consumers" is true only for controls expressed in
platform-owned infrastructure. Every other control is *verified for the reference implementation* and
*contractually required* of adopters. State it that way. Overstating this is the most likely way this
repository misleads someone.

## Honest consequences

- A domain can log memory content from its own code. The platform cannot prevent it; it can detect it
  only if the domain runs the conformance suite.
- A domain can weaken its own RBAC configuration within the bounds the schema allows.
- A domain cannot grant an agent direct Memory Bank access, because that IAM binding is platform-owned.
- A domain cannot suppress the platform audit sink, because it is configured outside the application.
