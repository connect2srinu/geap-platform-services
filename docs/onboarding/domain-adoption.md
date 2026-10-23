# Domain adoption guide

For a domain team adopting a published platform pattern.

## The eleven steps

| # | Step | Owner |
|---|---|---|
| 1 | Discover an approved pattern | You |
| 2 | Select a published version | You |
| 3 | Copy `templates/domain-consumer/` into your own repository | You |
| 4 | Apply domain configuration | You |
| 5 | Implement permitted extensions | You |
| 6 | Run the pattern conformance tests | **You, in your CI** |
| 7 | Build your own container image | **You** |
| 8 | Scan and publish it to your registry | **You** |
| 9 | Deploy to the platform GCP project | **You**, via Terraform |
| 10 | Validate functionality, IAM, policy and observability | You |
| 11 | Operate and upgrade independently | You |

The platform team provisions your memory bank, its IAM binding, the audit sink and your quota
allocation. Everything else is yours.

## 1–2. Discover and select

```bash
git tag -l 'memory-manager/v*' | sort -V
```

Check `metadata.status` in the release's `pattern.yaml`. **Do not adopt a `proposed` pattern for
production** — its design is not approved and its contracts may change.

**Pin the version.** "Latest" is not a dependency.

If no release exists yet, you can still adopt: see `ref:` and `path:` under step 3. That is for
evaluation and pre-release work, and your lock file records it as `unreleased: true` so nobody
mistakes it for a published version.

## 3. Start your project

Copy `templates/domain-consumer/` into your own repository. It gives you a configuration file,
sample extensions, a Dockerfile, a smoke test, the vendoring scripts, a runbook, agent-facing API
documentation and a role-request template.

Then fill in `pattern.lock.yaml` and vendor the pattern:

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r scripts/requirements.txt
.venv/bin/python scripts/vendor_pattern.py
```

`pattern.lock.yaml` names **exactly one** source:

| Key | What it does |
|---|---|
| `tag:` | A published release. The tarball is checksum-verified against the published `SHA256SUMS`. **Use this in production.** |
| `ref:` | A branch, tag or commit. The resolved commit is written back to the lock, so `ref: main` cannot mean two things next week. |
| `path:` | A local checkout of the platform repository, for developing against an unreleased pattern. |

`ref:` and `path:` also require `unreleased: true`. Neither is checksum-verified — there is no
published `SHA256SUMS` for them — and the script says so when it runs.

Your code lives outside `vendor/`. An upgrade is then a directory swap, not a merge.

## 4. Configure your topics and callers

`config/domain-config.yaml`, validated against the pattern's schema **at startup** — the service
refuses to start on invalid configuration rather than defaulting. Never a default that weakens a
security control.

## 5. Implement extensions

Only at declared extension points. Security-relevant stubs start **fail-closed**; loosening one is a
deliberate act that needs review on your side.

An extension may *refine* a decision; it can never *override* a mandatory control. An extension that
raises becomes a denial plus a metric, never a bypass.

## 6. Conformance — the step that matters

```bash
CONFORMANCE_BASE_URL=http://localhost:8080 \
CONFORMANCE_AGENT_ID=<your-writer-agent> \
CONFORMANCE_READER_ID=<your-reader-agent> \
CONFORMANCE_ALLOWED_TOPIC=<a non-sensitive, enabled topic> \
CONFORMANCE_ALLOWED_FIELD=<a field on that topic> \
CONFORMANCE_SENSITIVE_TOPIC=<a sensitive or restricted topic> \
pytest -q vendor/pattern/conformance/
```

**`CONFORMANCE_BASE_URL` is the whole point.** Without it the suite starts the pattern's own
reference implementation in process and tests *that* — which proves the suite works, and proves
nothing whatsoever about your build. Point it at your running service.

Run it in your CI, against your build. It is how you demonstrate that your customization still
honours the contract.

**An empty suite that collects zero tests is `unavailable`, not a pass.** The reference pipeline fails
the build on a zero-test collection for exactly that reason.

The platform team cannot see this run. If you remove the job, nothing outside your team notices. That
is the model — see [the limits of enforcement](../../standards/security.md).

## 7–8. Build and publish your image

You own the image, the registry and the scanning. Pin the base image by digest; run as non-root; no
secrets in any layer. A failing scan blocks the push.

## 9. Deploy

Terraform, into the platform-owned project, prefixed `<domain>-<pattern>`. Pin the image **by digest**.

Give the platform team your service account emails so the memory bank IAM binding can be created:

```bash
terraform -chdir=infrastructure/terraform output api_service_account
```

Agree your `max_writes_per_minute` allocation. The project quota is shared across every domain; your
allocation is your share of it, not a limit you can raise unilaterally.

## 10. Validate

Functional smoke test · IAM least privilege, no primitive roles · policy denials behave as configured
· audit events reaching the sink · metrics present, including `quota_consumed` · **no memory content
or PII in logs**.

## 11. Operate and upgrade

Runbook: `docs/runbook.md`. To upgrade, change the version in `pattern.lock.yaml`, re-run
`scripts/vendor_pattern.py`, and run the conformance suite against the new build before you
deploy it. `docs/upgrade.md` in your project carries the per-version notes.

## What you may change, and what you must not

**May:** configuration · extensions · prompts · privacy vocabulary · Terraform variables · scaling ·
your CI · your image.

**Must not:** the tool API contract or error catalogue · non-overridable controls · the audit event
schema or sink · the prohibited-log-field list · required metrics · the idempotency contract ·
platform-owned memory bank IAM · `pattern.lock.yaml` without an upgrade.

## If you fork

You can. Teams own the code. But: the conformance suite, boundary checks and manifest digest check all
run in your CI and can be removed. The platform-owned memory bank IAM binding, audit sink and quota
alerting **cannot** — they are outside your application.

So the platform controls what your service account may do to a bank. It does not control what your
code does before it gets there. That is a real responsibility, not a formality.
