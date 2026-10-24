# memory-manager v0.1.0 — release readiness

Prepared 2026-10-23. **Nothing has been published.** This document is the evidence a reviewer
needs in order to decide whether to tag the version, and it records what is still outstanding.

A published version is a contract with every adopting domain and cannot be withdrawn once
consumed, which is why this exists before the tag rather than after it.

## What is in this version

The governed memory tool API over a managed Memory Bank: a synchronous `remember` and `recall`,
topic policy from the domain's own configuration, two required extension points that fail closed,
read-back verification after the provider's consolidation, a per-instance write budget over the
shared project quota, and mandatory idempotency keys. See the changelog entry for the full list
and the known limitations.

## Verification

### Automated checks

| Check | Result | Evidence |
|---|---|---|
| `make verify` | **passed** | 388 tests; ruff clean; mypy `--strict` clean on 28 source files |
| Pattern manifest | **passed** | 32 checks, 0 warnings |
| Platform/domain boundary | **passed** | 4 checks, 0 warnings |
| Design artifacts | **passed** | front matter, ordering and approver checks |

### Conformance against a real build

**Passed.** `scripts/domain_rehearsal.py` builds a domain project from
`templates/domain-consumer/`, vendors the pattern, creates the project's own environment,
installs the vendored copy, boots the service and runs the pattern's conformance suite against it
over HTTP. All 12 steps passed, including `conformance against the domain build` and the S-4 log
check. This runs against the **fake** memory bank, so it proves the documented adoption path
works, not that the provider does.

### Live managed-service verification

**Performed, 2026-10-23**, against a real Vertex AI Memory Bank
(`geap-probe-tier1-main`, in the maintainer's sandbox project). Two runs, both recorded in
`design/001-memory-manager/design.md`:

- **Provider behaviour** — `spike/probe_memory_bank.py`: 8 passed, 0 failed, **2 unavailable**.
  Read-after-write p50 0.10 s, max 0.14 s over 10 trials.
- **The domain path** — `spike/live_domain_rehearsal.py`: **14 passed, 0 failed**. The real
  bootstrap reading a `domain-config.yaml`, the container entry point under a real ASGI server
  over HTTP, and real RS256 tokens verified against a JWKS endpoint, all against the real bank.
  A clean fact was written in 0.94–1.13 s and recalled; a second end user saw an empty scope; a
  replayed idempotency key returned the recorded response unchanged; the domain's own classifier
  refused an email address; `TOPIC_RESTRICTED` and `TOPIC_DISABLED` were each refused for their
  own reason; a recall-only caller was refused a write; and nothing prohibited appeared in 50
  lines of service log.

The S-8 check was confirmed to be discriminating: with `resolve_scope` changed to ignore the
pseudonym, exactly one check failed and the other thirteen still passed.

**The two unavailable checks are not passes:**

- **TTL** — requires a bank created with `ttl_config.granular_ttl_config`. Not created.
- **CMEK** — requires Cloud KMS, which is not enabled on the verification project. The pattern's
  encryption-at-rest claim is therefore **unproven**. It is tracked on the unmerged
  branch `design/006-control-c20-cmek-at-rest`, which is not on `main`.

Neither is on the request path. CMEK is set once, at bank creation, through
`CreateMemoryBankConfig.encryption_spec.kms_key_name`.

## Blockers

All four are cleared. Each was a human act or tracked work, not an oversight waved through.

| # | Blocker | Cleared |
|---|---|---|
| 1 | **`requiredAuditEvents` declared seven events and the code emitted none.** `Deployment` had no `AuditSink`, so even the two undeclared events in `verify_write` reached a null sink in any real deployment. S-7 was unimplemented. | 2026-10-24, `design/015-audit-events-that-exist`. Nine events now emitted and declared; `role_grant` and `role_revocation` removed because this service never grants or revokes a role; a both-directions test fails the build if either side drifts. |
| 2 | **`metadata.status` was `proposed`**, which `release.yml` refuses. | 2026-10-24, now `alpha`. |
| 3 | **The `release` GitHub environment did not exist**, so the second human gate imposed nothing. | 2026-10-24. Created with one required reviewer. Secret scanning, push protection and Dependabot were enabled at the same time, and `Domain rehearsal` became a required status check. |
| 4 | **`metadata.maintainer.contact` was a placeholder.** | 2026-10-24, now a real neutral address. |

**One caveat on blocker 3.** The single reviewer on the `release` environment is also the person
who tags and dispatches, so the gate is a deliberate pause rather than an independent review.
See `docs/operations/repository-administration.md`.

## Recommendation

**Ready to tag**, once the pull requests carrying the evidence above are on `main`.

Two things a reviewer should weigh rather than take on trust:

- **CMEK is unproven**, not merely unverified. Cloud KMS is not enabled on the verification
  project. It is not on the request path, so it does not block a release, but the pattern cannot
  claim encryption at rest until a bank is created with a key and the check passes.
- **`alpha`, not `beta` or `certified`.** The contract may still change. A domain adopting this
  should expect to take a breaking change, and the known limitations above are real.

A domain that wants to pilot before the release does not have to wait: `vendor_pattern.py`
accepts a git ref with `unreleased: true` in the lock file. The only thing a release adds to that
path is verification of the published `SHA256SUMS`.

## To publish, a human runs

Only once the evidence above is on `main`:

```bash
git tag memory-manager/v0.1.0 && git push origin memory-manager/v0.1.0
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=true
```

The dry run validates and builds the artifacts without creating the GitHub Release. Re-dispatch
with `-f dry_run=false` to publish.
