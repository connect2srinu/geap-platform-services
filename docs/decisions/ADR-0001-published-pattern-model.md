# ADR-0001: Published pattern model, not a central control plane

- **Status:** Accepted
- **Date:** 2026-10-20
- **Decision owners:** Project owner (platform team)
- **Scope:** The delivery model for every platform capability in this repository
- **Related:** `design/000-platform-foundation/intent.md`

## Context

An existing proof of concept (`geap-memory`, a sibling repository — **VERIFIED** by reading it on
2026-10-20) implements a **centrally operated control plane**: the platform team hosts a FastAPI
control-plane API, an admin console and PostgreSQL; agents hold no memory logic and call one central
service. Its README states the boundary as *"Agents never call Memory Bank directly and never make
authorization decisions."*

The new mandate, and the supplied `[Container] Domain Memory Manager` architecture diagram, describe
the opposite shape. The diagram's own note: *"Domain-driven. Agent teams build agents. The Customer
domain owns and hosts Memory Manager… The platform gives reference code and Memory Bank NFRs, never
the rules."*

These are different products, not different releases of one product. Proceeding without an explicit
decision risked building a second memory product that competes with the first.

The project owner confirmed on 2026-10-20: this is a brand-new project with three stakeholders —
platform team, agent teams and domain owners. The platform publishes reusable patterns and templates
**including implementation code** (Memory API, Evaluation API). Individual teams adopt, **own and
customize the code**, and deploy independently on Cloud Run.

## Decision

This repository **publishes versioned source patterns and reference implementations**. Domain teams
adopt a release, own and customize the code, build their own container image, and deploy and operate
it themselves. The platform team never builds a domain's image and never operates a domain's runtime.

`geap-memory` is **prior art and reference only**. It is not the product and is not evolved here.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|
| Evolve the existing control plane | ~7,700 lines of tested authorization, household, consent and resolution logic already exist; enforcement is strong because the platform runs the service | Platform team becomes a runtime bottleneck and an operator for every domain; contradicts the mandate and the diagram; much of that logic is Customer-domain business rule that cannot be reused | Rejected by the stated ownership model |
| Publish patterns **and** operate a central service | Domains could choose | Two products, two contracts, double the maintenance, ambiguous ownership | Rejected as unaffordable |
| Publish patterns only | Domain autonomy; platform scales with patterns rather than with domains | **Weaker enforcement** — see Consequences | **Chosen** |

## Consequences

**Easier:** domains move independently; the platform team scales with the number of patterns rather
than with the number of domains or request volume; no central runtime to operate or page for.

**Harder — and this is the real cost:** enforcement weakens substantially. Policy is enforced by code
the domain builds, in a project the domain can edit. Of the four mechanisms for detecting unsupported
change, three (the conformance suite, the boundary checks, the manifest digest check) run in **the
domain's own CI**, which the platform does not control and cannot observe. A domain that forks the
source can disable all three.

Only **platform-owned Terraform** survives a fork — the memory bank, its IAM binding, the audit sink
and quota alerting. That single seam is the whole hard-enforcement story, which is why
`spec.infrastructure.platformOwned` is a required manifest field and why it has the strictest review
ownership in the repository. See ADR-0003.

Precisely: the platform controls **what a domain's service account may do to a memory bank**. It does
**not** control what the domain's code does before it gets there. Any claim beyond that is overstated,
and `standards/pattern-contract.md` says so in those terms.

**Also harder:** much of `geap-memory`'s tested logic is not reusable, because it encodes
Customer-domain business rules (households, health consent, grocery sensitivity categories) that
reusable platform code must not contain. What carries over is the *shape* — fail-closed decision
order, the scope-key contract, the provider adapter seam, the audit spine — not the code.

## Compatibility implications

No published contracts exist yet, so nothing breaks. This ADR establishes the model that every
subsequent pattern and contract is designed against. A future decision to operate a capability
centrally would contradict this ADR and must supersede it explicitly.

## Status history

| Date | Status | Note |
|---|---|---|
| 2026-10-20 | Accepted | Confirmed by the project owner; supersedes no prior ADR in this repository |
