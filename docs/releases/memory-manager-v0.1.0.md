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

These must be cleared before the tag. Each is a human act or a tracked piece of work, not an
oversight that can be waved through.

| # | Blocker | Who clears it |
|---|---|---|
| 1 | **`requiredAuditEvents` is declared and not emitted.** The manifest names seven audit events; none is emitted. `Deployment` has no `AuditSink`, so even the two undeclared events in `verify_write` go to a null sink in any real deployment. Security rule S-7 is unimplemented. | the unmerged branch `design/015-audit-events-that-exist`; its intent awaits approval |
| 2 | **`metadata.status` is `proposed`.** `release.yml` refuses to publish a pattern whose design is not approved. Moving it to `alpha` is a governance act. | a human, in `patterns/memory-manager/pattern.yaml` |
| 3 | **The `release` GitHub environment does not exist.** `release.yml` names `environment: release` and its comment calls the required reviewers "the second human gate". The repository has no environments configured, so that gate currently imposes nothing. | a repository administrator — see `docs/operations/repository-administration.md` |
| 4 | **`metadata.maintainer.contact` is `<team-contact-placeholder>`.** An adopting domain has no one to contact. | a human, in `patterns/memory-manager/pattern.yaml` |

## Recommendation

**Do not tag until blocker 1 is closed.** Publishing a manifest that declares seven audit events
the code does not emit tells a reviewer the coverage is there when it is not, and a version
cannot be withdrawn once a domain has consumed it. A manifest that claims less is safer than one
that overclaims.

Blockers 2 to 4 are each a single deliberate act and can be done at any point.

A domain that wants to pilot this before the release does not have to wait: `vendor_pattern.py`
accepts a git ref with `unreleased: true` in the lock file. The only thing a release adds to that
path is verification of the published `SHA256SUMS`.

## To publish, a human runs

Only after the blockers above are cleared:

```bash
git tag memory-manager/v0.1.0 && git push origin memory-manager/v0.1.0
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=true
```

The dry run validates and builds the artifacts without creating the GitHub Release. Re-dispatch
with `-f dry_run=false` to publish.
