# Platform logic vs. domain logic

The test: **would this code be wrong for a domain other than the one that asked for it?** If yes, it
is domain logic and does not belong in `patterns/*/src/`.

## Platform (reusable) — belongs in `src/`

- Tool endpoint structure, request and response shapes, the error catalogue.
- The *obligation* to authorize before acting, and the order in which checks run.
- The *obligation* to classify and redact before persisting.
- Queue mechanics, retry, backoff, dead-lettering, idempotency.
- The Memory Bank client and its failure handling.
- Observability plumbing, audit emission, correlation-ID propagation.
- Configuration loading, schema validation, extension-point dispatch.

## Domain (not reusable) — belongs in configuration or an extension

- Which roles exist and which agents hold them.
- Which attributes are sensitive or restricted; the category vocabulary.
- How an entity reference resolves to an internal identifier.
- How two conflicting facts are merged.
- Prompt text and extraction instructions.
- Retention periods, consent semantics, household or org structures.

## Three traps, taken from the proposed architecture

The supplied diagram places three domain behaviours inside platform components. Each is an
**extension point with a default**, never platform code:

| Diagram text | Reality | Pattern treatment |
|---|---|---|
| worker "resolves entity refs to internal IDs" | Domain identity resolution | `entity-resolver` extension, default no-op |
| worker "strips PII" | The *obligation* is platform; the *classifier* is domain | `pii-classifier` extension, default **deny-all** (fail closed) |
| worker "curates the same fact from two sources" | Domain merge policy | `fact-curator` extension, default last-write-wins |

## Non-overridable controls

Some controls exist to protect the enterprise and **cannot be disabled by domain configuration**. A
domain may make them stricter, never weaker. They are listed in `standards/security.md` and declared
in each `pattern.yaml` under `spec.security.nonOverridableControls`.

If configuration could switch a control off, the design is wrong — not the configuration.

## Never in reusable code

Real enterprise identifiers: company names, partner product names, project IDs, service account
emails, bank IDs, internal hostnames. Use neutral placeholders (`example-domain`, `acme-*`,
`ENTITY_ID`, `<project-id>`). Real names belong in design narrative, not in code, manifests,
templates, or examples.
