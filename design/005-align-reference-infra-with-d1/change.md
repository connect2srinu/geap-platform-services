---
artifact: change
feature: 005-align-reference-infra-with-d1
track: light
status: draft
---

# Change — Remove the queue and worker from the reference Terraform, per D1

> **Light track.** Use only when *every* statement below is true. If any becomes false during the
> work, stop and escalate to the full track — this is one-way and automatic.
>
> - [x] No change to any API contract, tool API, or `pattern.yaml`
> - [x] No change to a security control or the security posture
> - [x] No new managed service, dependency, or extension point
> - [x] No architectural change

## What and why

The approved design for 001 (`design/001-memory-manager/design.md`, D1) is synchronous: "No
Pub/Sub, no worker deployment, no `202` … dead-lettering is not applicable (there is no queue)".
`templates/terraform-gcp` predates that design and still provisions the rejected architecture:

- two Pub/Sub topics (`writes`, `dead_letter`) and two subscriptions;
- publish and subscribe IAM on them;
- a worker Cloud Run service and a worker service account.

**VERIFIED**: Checkov fails on PR #1 with CKV_GCP_83 on both topics (job 119555466293). It is
failing on infrastructure that v0.1.0 explicitly rejected. Removing that infrastructure is the
correct reason for the check to go green, rather than adding a key to topics that shouldn't exist.

| | |
|---|---|
| Classification | `defect` (reference material contradicts an approved design) |
| Patterns touched | none (`templates/` only) |

## Approach

- **`templates/terraform-gcp/main.tf`:** remove `google_service_account.worker`, both
  `google_pubsub_topic`s, both `google_pubsub_subscription`s, `api_publish` and `worker_subscribe`,
  and `google_cloud_run_v2_service.worker`. Update the ownership header and the API SA's
  description. The header now says asynchronous writes return in v0.2.0 with a customer-managed key
  (see 006).
- **`outputs.tf`:** remove `worker_service_account`, `writes_topic` and `dead_letter_subscription`.
- **`variables.tf`:** `max_writes_per_minute` is now described as the API's in-process domain
  budget, not "the worker's rate governor".
- **`templates/domain-consumer/README.md`:** drop the `output worker_service_account` step, which
  would otherwise point at an output this change removes.

**Kept deliberately: `audit_publish`.** This binding lets the service account publish to the
**platform audit sink** topic. It is not the retry queue, and it is the C-07 path. It loses its
worker member and keeps the API's. The 001 design and DEC-2 route audit through Cloud Logging
instead, so this binding may go too. Removing an audit path is a control question, though, so it
belongs to 001's T-39/T-40, not here.

> **Flag for 001 (T-39/T-40).** 001's design routes audit events through Cloud Logging, to a
> dedicated log name with a platform-owned log sink. DEC-2 chose the Cloud Logging API. So once
> 001 is implemented, `audit_publish` may grant publish on a topic **nothing publishes to**. Its
> presence would then look like an audit path that doesn't exist. Whether to remove it, or
> re-point the sink at it, is decided in T-39/T-40. Removing an audit path needs a C-07 controls
> recheck (`design-check-controls --recheck`), not a cleanup commit.

**Not in this change: `pattern.yaml`.** The requester asked for the manifest corrections the 001
design lists (`design.md` lines 473–478) to be folded in here. They are not: changing
`pattern.yaml` fails the first light-track statement above, and the rules don't let this change take
the light track with it. The 001 design already places these edits in implementation ("made during
implementation, not here"), and 001's T-41 owns `pattern.yaml`. **OPEN** for the requester: keep
them in 001 T-41 (recommended), or make them a separate full-track change.

**Reported, not fixed** — the rest of `templates/domain-consumer` still describes the async
contract:

- `docs/agent-api.md` lists `/v1/memories` returning `202`.
- `scripts/smoke_test.py` asserts `202`.
- `docs/runbook.md` covers dead-letter and queue-age triage.

That is tool-API documentation, and agent teams code against `agent-api.md`. It is rewritten
against 001's OpenAPI contract by **001 task T-44**, which depends on T-03 so it cannot run
before the contract exists, or be forgotten. Rewriting it now would mean inventing the contract.

**Forward requirement for v0.2.0:** when the asynchronous queue returns, it must be created with a
customer-managed key from day one (control C-20, proposed in 006). This is recorded in the
`main.tf` header and in 006's intent.

## Controls delta

| Control | Effect | Status |
|---|---|---|
| C-11 | Removes one service account and its Pub/Sub roles. Least privilege improves; nothing is widened | Posture tightened, not changed in kind |
| C-15 | The policy scan passes again for the right reason: the failing resources are gone | Scan usable as evidence again |
| C-07 | The audit-sink binding is kept, for the API's service account | Unchanged |

## Verification

| Check | Command | Result |
|---|---|---|
| Format | `terraform fmt -check -diff templates/terraform-gcp` | **passed** — exit 0 |
| Validate | `terraform init -backend=false && terraform validate` | **passed** — `Success! The configuration is valid.` |
| Policy scan, before (main's Terraform) | `uvx checkov@3.2.334 -d . --framework terraform` | **failed** — `Passed checks: 3, Failed checks: 2`; CKV_GCP_83 on `writes`, `dead_letter` |
| Policy scan, after | same, on this branch | **passed** — `Passed checks: 1, Failed checks: 0, Skipped checks: 0` |
| No dangling references | grep for `worker`, `pubsub_topic.writes`, `pubsub_subscription` in `templates/terraform-gcp/*.tf` | **passed** — one hit, the explanatory header comment |
| Boundary and manifest | `check_platform_domain_boundary.py`; `validate_pattern_manifest.py` | **passed** — 4 and 25 checks |
| CI | the PR's checks | **not yet run** — needs the push |

The local Checkov version (3.2.334) may differ from the one `bridgecrewio/checkov-action@v12`
resolves in CI. The CI run is the authoritative result.

## Approval

**Gate A** — approved in session on 2026-10-21 by the requester (connect2srinu), "in the reframed
form": an alignment change on the light track. The manifest portion is held (see Approach). The
requester confirmed on 2026-10-21 that `pattern.yaml` stays in 001 T-41, that `audit_publish` is
kept, and that the template drift goes to 001 as T-44. Restate this in the PR description. `status` stays `draft` here: only a human sets `approved`.

Gate A inline (in the PR description) and Gate E (human review). Gate F for merge.
