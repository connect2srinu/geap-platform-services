---
artifact: intent
feature: 011-onboarding-that-works
status: approved
approved_by: Srinivasa reddy
approved_date: 2026-10-23
---

# Onboarding a domain can actually complete

## Why

A domain adoption rehearsal was run on 2026-10-23 from `main` at `b0fce54`: a customer domain
project built in a separate directory, following `docs/onboarding/domain-adoption.md` literally.

**The pattern held up.** The conformance suite passed 26/26 against the domain's own running build —
verified by the thirty requests in its log, and by a dead port failing all 26. A twelve-case policy
matrix behaved correctly throughout, including a medication and an email address refused inside an
otherwise allowed brand-preference fact. Nothing refused reached the logs.

**The materials around it did not.** Seven separate defects stop a domain completing adoption, and
three of them do worse than fail — they mislead. The step-10 smoke test reports
`SMOKE TEST FAILED — 3 checks` against a build that is working correctly, and `docs/agent-api.md`
tells agent teams that `remember` returns `202` and is "durably enqueued, not applied" when the
service is synchronous. A team following these conclude the platform is broken, and they are right
to.

Every one of them is drift, not carelessness. The async design, the old config shape and the old
entry point were all correct once. They rotted because **nothing exercises the onboarding path**.
Correcting seven documents leaves the eighth to rot next quarter, so the deliverable is a rehearsal
that runs in CI, with the documents generated from or checked against what it produces.

## Scope

The seven blockers, as found:

| # | Defect | Where |
|---|---|---|
| 1 | Vendoring requires a published release tarball; no release exists, so step 1 cannot run | `templates/domain-consumer/scripts/vendor_pattern.py` |
| 2 | Step 3 says run `/domain-onboard`, which does not exist; the guide never mentions `templates/domain-consumer/` | `docs/onboarding/domain-adoption.md` |
| 3 | The template's domain config carries `rbac:` and `privacy:` from the superseded design and omits `topics`, `callers`, `identity`, `quota` — five schema errors | `templates/domain-consumer/config/domain-config.yaml` |
| 4 | The smoke test expects `202` and posts `{"fact": {...}, "extraction_mode": ...}`; fails against a correct build | `templates/domain-consumer/scripts/smoke_test.py` |
| 5 | Agent API doc describes `list`, `correct`, `forget` endpoints that do not exist, and `202` queue semantics | `templates/domain-consumer/docs/agent-api.md` |
| 6 | Service defaults to `/app/config/domain.yaml`; the guide says create `domain-config.yaml`; Terraform sets no `CONFIG_PATH` — the container cannot start as documented | `asgi.py`, the guide, `domain-runtime/main.tf` |
| 7 | Template Dockerfile runs `pattern.api.main:app`, which does not exist, and copies a `uv.lock` the template does not ship | `templates/domain-consumer/Dockerfile` |

Plus `docs/onboarding/demo.md`'s local-run section, which fails the same way and was the original
reason for this feature.

And the thing that stops it recurring: **a CI job that performs the rehearsal** — generate a domain
project from the template, apply a configuration, implement sample extensions, boot it, and run the
conformance suite against it. If that job passes, the documented path works.

## Not in scope

- **The `value`-on-recall contract question.** Recall returns the fact text in the `value` field,
  not the structured value that was written, because only the encoded text is persisted. That is a
  contract change and belongs in its own feature. Recording it here so it is not lost:
  `OPEN`, raised 2026-10-23.
- Container build, image scanning and push. No image is built by this work.
- Cloud Run deployment and live IAM. This repository applies no infrastructure.
- Live Memory Bank verification through a domain build. The pattern was verified live separately
  (19/19); the rehearsal uses the fake bank deliberately, so CI needs no credentials.
- Any change to the API contract, the error catalogue, an extension point, or a security control.
  If this work appears to need one, it stops and returns to design.
- Publishing a release. Decided 2026-10-23: blocker 1 is fixed by teaching `vendor_pattern.py`
  to take a git ref or local path instead. A release is still the right thing eventually; it is no
  longer a prerequisite for adoption, and it is not part of this work.

## How we'll know it works

1. A CI job generates a domain project from `templates/domain-consumer/`, configures it, boots it
   and runs the conformance suite against it. It passes, and it fails if the template's
   configuration, Dockerfile entry point or smoke test is wrong.
2. The template's `config/domain-config.yaml` validates against the pattern's config schema.
3. `scripts/smoke_test.py` passes against a correctly working build, and fails against a broken one.
4. `docs/agent-api.md` describes only endpoints that exist in `contracts/openapi.yaml`, enforced by
   a check rather than by review.
5. A container started with no `CONFIG_PATH` set finds the configuration the guide tells a domain to
   create — by one change, not by documenting the discrepancy.
6. `docs/onboarding/domain-adoption.md` names only skills and templates that exist.
7. Repeating the rehearsal from a clean directory completes every step with no manual intervention
   and no undocumented knowledge. Verified by doing it.
8. `demo.md`'s local-run section produces the responses it claims.

## Open questions

| Question | Who decides |
|---|---|
| ~~Blocker 1 is circular: a domain cannot vendor without a release.~~ **Decided 2026-10-23:** `vendor_pattern.py` accepts a git ref or a local path, so adoption works before a release exists. Pre-release adoption becomes a supported path rather than a workaround, and the release stays honest — it is published once a domain has adopted the pattern, not before. | Platform lead — decided |
| Should `agent-api.md` and `smoke_test.py` be **generated** from `contracts/openapi.yaml` rather than checked against it? Generation cannot drift; it is also more machinery. | Platform lead |
| `metadata.status` is `proposed`, and the adoption guide says not to adopt a `proposed` pattern. Does completing this work plus the live verification move it to `beta`? | Platform lead |
| `VERIFIED` — every defect above was reproduced by running it, not by reading. Evidence in the rehearsal findings. | — |

## Approval

Approved by Srinivasa reddy, 2026-10-23, instructed in session.

Carries one decision: blocker 1 is resolved by making `vendor_pattern.py` accept a git ref or a
local path, not by publishing a release first.
