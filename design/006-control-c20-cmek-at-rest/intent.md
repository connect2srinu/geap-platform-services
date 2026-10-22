---
artifact: intent
feature: 006-control-c20-cmek-at-rest
track: full
status: draft
patterns_touched: [memory-manager]
---

# Intent — Control C-20: memory content at rest under a customer-managed key

> Stage 1. Approval at **Gate A** is required before design work begins, and before any remote
> branch or pull request is created.

## Method

Produced on 2026-10-21 from `main` at `69eee1b`. Read:

- `standards/security.md`, C-01 to C-19. **VERIFIED**: none addresses encryption at rest.
- `templates/terraform-gcp/main.tf`.
- `design/001-memory-manager/design.md`: D1, and the L1–L10 live checks.
- The Checkov log on PR #1 (job 119555466293).

This intent was reframed by the requester on 2026-10-21. It split off from 005, which removes the
queue Checkov was failing on, rather than keying it.

## Business objective

Memory content belongs to end users, and the platform governs it. When it is held at rest, it should
be encrypted under a key the enterprise controls. Revoking that key then renders the content
unreadable (crypto-shredding), and every use of the key is auditable. Today no control requires
this, so no design is obliged to answer the question.

## Requester and stakeholders

| Role | Who |
|---|---|
| Requester | Platform team — connect2srinu |
| Security reviewer | Approves the control text (Gate C) |
| Affected domains | All adopters of any pattern that stores memory content |

## Reusable or domain-specific

Reusable. This is an enterprise control in `standards/security.md`, which applies to every pattern.

**Full track:** it adds a control and changes the security posture.

## Scope

1. **Add C-20 to `standards/security.md`.** Memory content at rest, in any store a pattern provisions
   or depends on, is encrypted under a customer-managed key (Cloud KMS). A store that cannot use one
   needs an approved exception with an owner and an expiry, and is **disclosed to every adopting
   domain**. It is never a configuration toggle. C-20 needs a stated verification method.
2. **Decide whether C-20 is non-overridable** (the `nonOverridableControls` list).
3. **Answer the Memory Bank question with a probe, not a guess.** Does Memory Bank support a
   customer-managed key? This is the store where the facts actually live, so C-20 means little if
   it only covers a queue. The probe is added to 001's live-check list as **L11** (T-23/T-24, in
   `design/001-memory-manager/tasks.md`). Its result decides whether the bank complies with C-20 or
   carries a disclosed exception.
4. **Record CMEK as an explicit input to v0.2.0's design.** When the asynchronous queue returns, it
   must be created with `kms_key_name` from the start. Change 005 records this in the reference
   Terraform header too.

`standards/**` is a high-contention file, so this ships as its own PR, merged on its own
(`docs/onboarding/developer-guide.md`).

## Non-goals

- Adding `kms_key_name` to the v0.1.0 Pub/Sub topics. 005 deletes them.
- CMEK for logs, traces or the audit sink. C-06 already forbids content there, which is the
  stronger control.
- Provisioning any KMS key here. The control comes first; which Terraform creates the key is a
  design question (Q3).
- Applying any Terraform (CLAUDE.md rule 17).

## Acceptance criteria

1. `standards/security.md` contains C-20, with a requirement, a verification method and its threat
   rationale. `design/_template/controls-check.md` and `design-check-controls` assess it.
2. The C-20 text states that a store without customer-managed key support needs a disclosed,
   owned, expiring exception. No configuration key can waive it.
3. L11 exists in 001's live-check list with a defined probe and pass/fail criteria. Its result is
   recorded as **VERIFIED** (with output), not assumed.
4. If L11 says no: the memory-manager adopter documentation discloses that bank content is
   encrypted under Google-managed keys, and names the exception's owner and expiry.
5. A v0.2.0 design input states that the async queue is created with a customer-managed key.
6. `make verify` passes, including the design-artifact validator.

## Constraints and dependencies

- **ADR-0003:** one platform-owned project, one bank per domain. Key ownership has to fit that model
  (Q3).
- **001 Gate C will need a `--recheck` for C-20** once C-20 is in the catalogue.

## Open questions

| ID | Question | Who decides |
|---|---|---|
| Q1 | Is C-20 non-overridable? | Security reviewer |
| Q2 | Does Memory Bank support a customer-managed key? Answered by L11, live | Platform architect (runs the probe with platform credentials) |
| Q3 | Key ownership: one platform key per domain, one per project, or domain-owned | Platform architect + security reviewer |
| Q4 | Key rotation period and destroy-schedule policy | Security reviewer |

## Assumptions

- **ASSUMPTION**: Pub/Sub supports `kms_key_name`. This is documented provider behaviour, but it
  is not verified in this repository.
- **ASSUMPTION**: CKV_GCP_83's check is for `kms_key_name`, despite its "CSEK" title.

## Approval

**Gate A** — approved in session on 2026-10-21 by the requester (connect2srinu), in the reframed
form. `status` stays `draft` here: only a human sets `approved`.
