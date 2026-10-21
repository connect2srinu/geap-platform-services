# Architecture standards

## The product shape

This repository publishes **versioned source patterns**. A pattern is adopted, owned, built and
deployed by a domain team. The platform team never builds a domain's container image and never
operates a domain's runtime.

Consequence for every design decision: ask *"can a domain do this without us?"* If the answer needs
the platform team in the loop at runtime, the design is wrong for this repository.

## Deployment context

A **single GCP project, owned by the platform team**, hosts every domain's memory banks and the
domain-deployed services. One memory bank per domain, created at onboarding. Isolation is by
**per-domain service account plus IAM Conditions on scope**, not by project boundary.

This is decided (see `docs/decisions/ADR-0001-published-pattern-model.md`) and has two consequences
every design must address:

1. **Quota is shared.** Memory Bank quota is per-project, per-region. Separate banks do not give
   separate quota. A design that ignores cross-domain quota contention is incomplete.
2. **Blast radius is shared.** One project is one failure domain and one misconfiguration domain.

## Layering

```
contracts/     the versioned interface — OpenAPI, schemas, error catalogue
   ↓
src/api/       transport: validation, authn, correlation, error mapping
   ↓
src/policy/    authorization and classification decisions (platform mechanism)
   ↓
src/worker/    asynchronous processing
   ↓
src/providers/ the managed-service boundary (Memory Bank client)

extensions/    declared extension points — domain code plugs in here
config/        configuration schema and safe examples
```

Dependencies point downward only. `providers/` knows nothing of `api/`. Nothing imports from
`extensions/` except the dispatcher. Enforced by `scripts/check_platform_domain_boundary.py`.

## Platform and domain separation

See `.claude/rules/platform-vs-domain.md`. The short form: platform owns the *mechanism and the
obligation*; domains own the *policy and the vocabulary*. Mandatory controls are non-overridable by
configuration — a domain may tighten, never loosen.

## Provider abstraction

Use an adapter at the managed-service boundary so the reference implementation is testable without
the provider. **Do not** abstract away provider capabilities that matter — quota semantics,
eventual consistency, revision history, scope-key limits. A leaky abstraction that preserves
important behaviour beats a clean one that hides it.

No multi-cloud abstraction layer. Google Cloud is the only target. The adapter seam is enough to keep
a future provider possible without building for one now.

## When an ADR is required

Write one for an **approved** decision that:

- changes a published contract or the tool API;
- selects or replaces a managed service;
- changes the security or isolation posture;
- changes the platform/domain boundary or adds an extension point;
- is expensive to reverse.

Do not write one for routine implementation choices. ADRs are
`docs/decisions/ADR-NNNN-<kebab-title>.md`, numbered sequentially, and carry `Status`, `Date`,
`Decision owners`, `Scope`. Use `design-record-decision`.

## Diagrams

- **C4 container level** is the default altitude. Component level only where a container is complex
  enough to need it.
- **Mermaid inside Markdown** is the committed, reviewable form — it diffs in a pull request.
- A `.drawio` source may accompany a diagram, but the Markdown version is normative. A diagram that
  exists only as an exported image is not an architecture artifact.
- Every diagram states its status: `CURRENT`, `TARGET` or `PROPOSED`.

## Evidence discipline

Documents making factual claims about the codebase state their method — what was read, which branch,
what date — and label claims `VERIFIED` / `PROPOSED` / `OPEN` / `ASSUMPTION`. See
`.claude/rules/evidence-and-claims.md`. The design-artifact validator checks the vocabulary.

Never label something `VERIFIED` because it is in the design. Verified means observed.
