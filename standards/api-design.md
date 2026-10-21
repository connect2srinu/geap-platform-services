# API design standards

## Contract first

The OpenAPI specification in `patterns/*/contracts/` is the source of truth. It is written and
reviewed before the implementation, and CI fails when implementation and specification disagree.

## The tool API is identical across domains

This is the rule that makes agents portable. A domain configures policy, roles, categories and prompts
*behind* the contract; it does not change the contract. An agent written against one domain's
deployment must work against another's.

Consequence: `patterns/*/contracts/**` carries the strictest review ownership in the repository, and
conformance treats any drift as a hard failure.

## Versioning

- Path-based major version: `/v1/...`.
- Additive, optional changes are minor and backward compatible.
- Removing or renaming a field, tightening validation, changing a status code or an error code, or
  changing an operation's semantics is **breaking** → new major version.
- Two major versions may run side by side during a migration. Announce deprecation with a date in
  `CHANGELOG.md`, never silently.

## Asynchronous writes

Where an operation is accepted for later processing:

- Return **`202 Accepted`**, and `202` means **durably enqueued** — not "received and hopefully
  published". If the enqueue fails, return `503`. The pattern has no transactional outbox, so this is
  the contract that keeps the design honest.
- The response carries an operation identifier the caller can use to query status.
- Document what a subsequent read returns while a write is still pending. Callers must not have to
  guess whether they are seeing stale data.

## Idempotency — required, not optional

Every mutating operation accepts an **`Idempotency-Key`** header, and it is **required** on
`remember`. Duplicate delivery is routine once a queue is involved, and a duplicate write against a
quota-limited provider is expensive as well as incorrect.

- Same key, same payload → one effect; the original result is returned.
- Same key, different payload → `422`.
- The key's retention window is documented in the contract.

## Errors

Every error returns a stable machine-readable code from the pattern's error catalogue, a
human-readable message with no payload content, and the correlation ID.

| Status | Used for |
|---|---|
| `400` | Malformed request |
| `401` | Missing or invalid identity |
| `403` | Authenticated but not permitted — includes every fail-closed denial |
| `404` | Not found, where disclosure is safe |
| `409` | Conflict |
| `422` | Valid syntax, rejected by policy or validation |
| `429` | Caller exceeded **its own** rate limit |
| `503` | Could not accept the write — enqueue failed, or dependency unavailable |

A provider's `429` is **not** the caller's `429`: provider throttling results in the write being
parked and a `202`, not an error. Never return a provider's raw error text.

## Rate limits

Per-caller limits are domain configuration. Responses carry `RateLimit-Limit`, `RateLimit-Remaining`
and `RateLimit-Reset`. A caller that exceeds its limit gets `429` with `Retry-After`.

## Pagination

Cursor-based: `page_size` + `page_token`, returning `next_page_token`. No offset pagination. A maximum
page size is enforced server-side.

## MCP

OpenAPI is the v1 interface. MCP is a **planned** interface, declared in `pattern.yaml` and not
stubbed. When added, it is a second transport over the same contract and semantics — never a second
contract.
