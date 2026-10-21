# Testing standards

## Tests ship with code

In the same commit. A task is not complete when the code works; it is complete when the code works
and a test proves it, and the test fails if the behaviour is removed.

## The three suites

| Suite | Location | Who runs it | Purpose |
|---|---|---|---|
| **Unit / integration** | `patterns/*/tests/` | Platform team, platform CI | Correctness of the reference implementation |
| **Conformance** | `patterns/*/conformance/` | **Domain teams, in their own CI** | Black-box: does *this build* still honour the contract and the mandatory controls? |
| **Repository boundary** | `tests/` (repo root) | Platform CI | Structural invariants — layering, no domain logic in `src/`, no primitive IAM roles, prohibited log fields |

**Keep conformance separate from unit tests.** A domain team runs conformance against its own built
image. It must never be asked to run the platform's unit tests, which depend on platform internals.

## What must be a conformance test

Anything a domain could break by customizing:

- Every tool API endpoint: request shape, response shape, status codes, error codes.
- `202` semantics — accepted means durably enqueued.
- Idempotency: a duplicate request with the same key produces one effect.
- Fail-closed authorization on every deny path.
- The default PII classifier denies.
- Mandatory controls are present and cannot be configured off.
- Required audit events are emitted.
- Prohibited fields never appear in logs.

## Managed services

A mock proves your code calls the mock correctly. **It does not prove the integration works.** Say so
explicitly.

- Unit tests run against a fake provider client — always available, always in CI.
- A **contract test** runs against a real provider, opt-in via an environment flag, excluded from the
  default run.
- A release is not end-to-end validated until a live smoke test writes and reads back a value.
  Document the result; do not infer it.

Specifically, never claim these from a mock: quota and 429 behaviour, eventual-consistency windows,
IAM Conditions, provider error taxonomy, revision semantics.

## Coverage

No single number is a goal. Required instead:

- Every authorization deny path is tested.
- Every error-catalogue code is produced by at least one test.
- Every extension point is tested with its default and with a substitute.
- Every retry and dead-letter path is tested, including duplicate delivery.

A change that reduces coverage of a security control is rejected regardless of the percentage.

## Reporting

Report `passed` / `failed` / `skipped` / `unavailable` separately, with the command and its output.
See `.claude/rules/evidence-and-claims.md`. Never report a skipped or unavailable suite as passing.
