# Memory Manager

A domain-owned tool API through which every agent memory read and write passes, backed by a managed
Memory Bank.

> **Status: `proposed`.** The design has not been approved. This directory holds the manifest,
> structure and declared contract surface — **there is no implementation**. Not adoptable.
>
> Design work: [`design/001-memory-manager/`](../../design/001-memory-manager/).

## Ownership

| Platform team owns | Domain team owns |
|---|---|
| This source, the contracts, the conformance suite | Configuration, extensions, prompts |
| The Memory Bank NFR Terraform — bank provisioning, IAM, audit sink, quota alerting | The container image and registry |
| The pattern contract and its versioning | The Cloud Run deployment and its Terraform |
| | Operations, on-call, upgrades |

The platform team never builds or operates a domain's image.

## Intended shape

Transcribed from the supplied `[Container] Domain Memory Manager` diagram, **PROPOSED** and pending
design approval:

| Component | Responsibility |
|---|---|
| **Tool endpoints** | `remember` (returns `202`), `recall`, `list`, `correct`, `forget`; per-caller rate limiting |
| **Domain policy & RBAC** | Caller roles, scope, privacy guardrails, categories — versioned domain configuration |
| **Memory worker** | Asynchronous processing of accepted writes; classification, entity resolution and curation via extension points |
| **Retry queue** | Resilience for over-limit and failed writes; bounded retry, backoff, dead-lettering |
| **Memory Bank client** | The managed-service boundary |

## Declared extension points

| ID | Required | Default | Failure mode |
|---|---|---|---|
| `pii-classifier` | yes | `deny-all` | **deny** |
| `policy-provider` | yes | `deny-all` | **deny** |
| `entity-resolver` | no | `noop` | skip |
| `fact-curator` | no | `last-write-wins` | skip |

The two required ones default to **deny-all**: an unconfigured deployment stores nothing rather than
storing everything. The diagram places entity resolution, PII stripping and fact curation inside the
worker; all three are domain behaviour and are therefore extension points, not platform code.

## Open design questions

Carried from `design/000-platform-foundation/intent.md`, to be resolved in Stage 2:

- Worker shape on Cloud Run: service with a pull subscription, or Jobs for batch replay.
- Memory bank boundary: **per domain** (decided, ADR-0003) versus **per agent** (as the diagram
  labels it) — needs the diagram author's confirmation.
- Idempotency mechanism: an in-fact idempotency key read back during the worker's existing pre-read,
  versus a dedicated dedupe store. Provider eventual consistency bounds the first option.
- Whether the agent's direct `recall` path to the bank is retained; it consumes the shared quota and
  is ungoverned by this service's rate limiter.
- Per-domain quota budgeting: static allocation or dynamic from observed headroom.

## Structure

```
contracts/       OpenAPI specification and error catalogue  (not yet written)
src/             reference implementation                   (not yet written)
config/          configuration schema and safe examples
extensions/      extension interfaces and platform defaults  (not yet written)
infrastructure/  platform-owned NFR and domain-owned runtime Terraform
tests/           platform unit tests                        (not yet written)
conformance/     consumer-runnable conformance suite        (not yet written)
examples/        reference Dockerfile and usage examples
```
