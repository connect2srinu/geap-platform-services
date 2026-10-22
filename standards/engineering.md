# Engineering standards

## Stack

Python 3.12 · FastAPI · Pydantic v2 · `ruff` (lint + format) · `mypy --strict` on `src/` · `pytest` ·
`uv` with `uv.lock` committed.

Repository validation scripts use the standard library plus PyYAML and jsonschema only, so `make verify`
runs without a project environment.

## Layering

```
contracts/    the versioned interface — OpenAPI, error catalogue
src/api/      transport: validation, authn, correlation, error mapping
src/policy/   authorization and classification decisions
src/providers/ the managed-service boundary
extensions/   declared extension points — domain code plugs in here
config/       configuration schema and safe examples
```

Dependencies point downward only. Nothing imports from `extensions/` except the dispatcher.

## Platform vs domain

The test: **would this code be wrong for a domain other than the one that asked for it?** If yes, it
belongs in configuration or an extension point, not in `src/`.

**Platform owns the mechanism and the obligation.** Endpoint structure, the order checks run in, the
obligation to classify before persisting, queue and retry mechanics, the provider client,
observability plumbing, extension dispatch.

**Domains own the policy and the vocabulary.** Which roles exist, which attributes are sensitive, the
category list, how an entity reference resolves, prompt text, retention periods.

Every extension point has a default, and **security-relevant defaults fail closed** — a PII
classifier defaults to deny-all, never allow-all.

Never put real enterprise identifiers in code, manifests, templates or examples. Use neutral
placeholders.

## API

- OpenAPI in `contracts/` is the source of truth, written before the implementation.
- **The tool API is identical across every domain.** A domain configures policy behind it; it does not
  change the surface. That is what makes an agent portable.
- Path-based major version: `/v1/...`. Removing or renaming a field, changing a status or error code,
  or changing semantics is breaking.
- Every mutating operation takes an `Idempotency-Key`. Same key + same payload → one effect; same key
  + different payload → `422`.
- Every error returns a stable code from the pattern's catalogue, a message with no payload content,
  and the correlation ID. Never a provider's raw error text.

## Configuration

A new domain must be supportable **without changing `src/`**. Configuration is validated against a
JSON Schema at startup and the service **refuses to start** on invalid configuration — never
degrade to a default when security configuration is wrong.

Precedence: schema defaults → file → environment → secret references.

## Tests

| Suite | Who runs it |
|---|---|
| `patterns/*/tests/` | Us, in CI |
| `patterns/*/conformance/` | **The domain team, in their CI** — black-box against their own build |

Required, regardless of coverage percentage: every deny path, every error code, every extension point
with its default and a substitute, and each of the eight security rules.

**A mock proves your code calls the mock.** It does not prove the integration works. Say exactly that,
and keep live verification a separate, labelled step.

## Code

Explain *why* in comments, not *what*. Full type annotations on public functions. Pydantic models at
module boundaries, not `dict[str, Any]`. Never swallow an exception. Pin dependencies and commit the
lockfile.

## Observability

Structured JSON to stdout. Every record carries: timestamp, severity, correlation ID, caller, domain,
operation, decision, reason code. **Log the attribute name, never the value** — see S-4.
