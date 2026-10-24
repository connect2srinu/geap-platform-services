# Changelog

All notable changes to this pattern are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Every entry states what changed, whether it is **breaking**, the migration steps, and any
security-relevant change explicitly.

## [Unreleased]

Nothing yet.

## [0.1.0] — prepared, not published

The first adoptable version, `status: alpha`. Nothing is released until a human tags it and
dispatches `release.yml`; see `docs/releases/memory-manager-v0.1.0.md` for what is still
outstanding.

**Not breaking.** There is no previous version, so there is nothing to migrate from.

### Added

- The governed memory tool API: `POST /v1/memories` to remember and `GET /v1/memories` to
  recall, both synchronous. A write is made, read back and re-classified before the call
  returns, so a `200` means the fact is stored and has been checked — there is no queue and no
  `202`.
- Topic policy from the domain's own configuration. A topic absent from the vocabulary is
  rejected; only `non-sensitive` topics are eligible for storage; `allowInferred` is per topic
  and defaults to false.
- Two required extension points, `piiClassifier` and `policyProvider`, named by dotted path.
  A domain's policy runs after the platform's checks and can only narrow them.
- Read-back verification: a stored fact is re-classified after the provider's consolidation has
  had a chance to rewrite it, and remediated if it no longer passes.
- A per-instance write budget dividing the domain's agreed share of the shared project quota by
  `MAX_INSTANCES`, so one domain cannot starve the others.
- Idempotency. `Idempotency-Key` is mandatory on a write; a replay with the same key and body
  returns the recorded response. Keys are namespaced per caller and per end user.
- The Vertex AI Memory Bank adapter, behind a `MemoryBank` protocol, shipped as the optional
  `provider` extra. A fake implementation modelling the same consolidation, dedup and rollback
  behaviour is the default in a local environment.
- A domain consumer template with a vendoring script that verifies the published `SHA256SUMS`,
  and that also accepts a git ref or a local checkout for adopting before a release exists.
- A conformance suite a domain can run against its own build.

### Known limitations

- **The idempotency guarantee is per instance, not per fleet.** The replay cache is in process.
  Two concurrent requests carrying the same key that land on different instances will both be
  processed. Documented in `contracts/errors.md` and in the agent API documentation.
- `value` on recall returns the fact text rather than the structured value that was submitted.
- `memories.retrieve` paging is broken in the pinned SDK, so the adapter lists a scope with the
  SDK's own iterator instead.
- A write accepts at most five facts, which is the provider's own limit.

### Security

- Declared non-overridable controls: `C-01`, `C-02`, `C-05`, `C-06`, `C-07`, `C-08`, `C-11`, `C-16`.
- Both required extension points default to `deny-all` with `failureMode: deny`, so an
  unconfigured deployment stores nothing.
- An end-user subject is pseudonymised with HMAC before it is used, and the memory scope is
  derived server-side from the verified subject alone. A request body carrying a scope is
  refused.
- The local header verifier is refused outside a local environment at two independent points.
- Nine audit events, emitted and declared: `memory_write`, `memory_recall`, `memory_deletion`,
  `memory_remediation`, `memory_write_unverified`, `policy_denial`, `configuration_change`,
  `exception_invoked` and `idempotency_replay`. Each carries a correlation ID, identifiers and
  decisions — never a value, and never the raw end-user subject (S-7, S-4).
- **`role_grant` and `role_revocation` were removed from `requiredAuditEvents`.** This service
  never grants or revokes a role, so declaring them asserted coverage it could not deliver. A
  test now compares the manifest against the code in both directions, so a declared event that
  nothing emits, and an emitted event nothing declares, each fail the build.
- `recall` emits an audit event, which goes beyond what S-7 names. A read of someone's memory is
  what an investigator would want a trail of.
