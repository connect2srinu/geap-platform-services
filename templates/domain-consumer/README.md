# <domain>-<pattern> — domain-owned implementation

Generated from GEAP platform pattern `<pattern>` v`<version>`.

## What this project is

**This is your project.** Your team owns the code, the container image, the registry, the deployment
and the operations. The platform team published the pattern and provisioned the platform-owned
resources; it does not build or operate anything here.

## Ownership boundary

| You own | The platform owns |
|---|---|
| `config/domain-config.yaml` | The memory bank itself |
| `extensions/` — your implementations | The IAM binding granting access to it |
| `Dockerfile` and your image | The central audit sink |
| `.github/workflows/` | Quota alerting and allocation |
| `infrastructure/terraform/` | The pattern contracts and conformance suite |
| Operations and on-call | |

The platform-owned items are **consumed as inputs**, not created here. Attempting to create them in
your Terraform will fail, by design — that boundary is the one control that survives a fork of the
pattern source.

## What you may change, and what you must not

**May change:** configuration · extension implementations · prompts · privacy vocabulary · Terraform
variables · scaling · this CI pipeline · your image.

**Must not change:** the tool API contract or error catalogue · non-overridable controls · the audit
event schema or sink · the prohibited-log-field list · required metrics · the idempotency contract ·
`pattern.lock.yaml` without running an upgrade.

Changing something in the second list will fail the conformance suite. Since that suite runs in *your*
CI, nothing outside your team will notice if you remove it — which is why it is there.

## Getting started

1. **Vendor the pattern source** at the pinned version:
   ```bash
   python3 scripts/vendor_pattern.py
   ```
2. **Fill in the configuration** — `config/domain-config.yaml`. Every required key is commented.
3. **Implement your extensions** — `extensions/`. Security-relevant stubs start fail-closed; loosening
   one is a deliberate act that needs review.
4. **Run conformance locally:**
   ```bash
   pytest -q vendor/pattern/conformance/
   ```
5. **Provide your service account emails to the platform team** so they can create the memory bank IAM
   binding:
   ```bash
   terraform -chdir=infrastructure/terraform output api_service_account
   terraform -chdir=infrastructure/terraform output worker_service_account
   ```
6. **Agree your quota allocation** with the platform team. The project's Memory Bank quota is shared
   across every domain; `max_writes_per_minute` is your share of it.
7. **Build, scan, push, deploy** — see `.github/workflows/`.

## For agent teams integrating with this service

- API documentation: [`docs/agent-api.md`](docs/agent-api.md)
- Requesting a role: [`docs/role-request.md`](docs/role-request.md)

## Operations

[`docs/runbook.md`](docs/runbook.md) — deploy, roll back, dead-letter triage and replay,
quota-contention response, alert response, escalation.

## Upgrading

[`docs/upgrade.md`](docs/upgrade.md).
