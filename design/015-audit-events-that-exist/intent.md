---
artifact: intent
feature: 015-audit-events-that-exist
status: approved
approved_by: Srinivasa reddy
approved_date: 2026-10-24
---

# Audit events that actually exist

## Why

`standards/security.md` rule **S-7**: *every write, denial and deletion emits an audit event with
a correlation ID*. `pattern.yaml` declares seven required audit events. **`VERIFIED` 2026-10-23:
none of the seven is emitted anywhere in `src/`.**

| Declared | Emitted |
|---|---|
| `memory_write`, `memory_deletion`, `policy_denial`, `configuration_change`, `role_grant`, `role_revocation`, `exception_invoked` | none |

Two events *are* emitted — `memory_remediation` and `memory_write_unverified` — from
`verify_write`, the only component that takes an `AuditSink` at all. Neither is declared.
`Deployment` has no sink, so the `remember` path emits nothing for a successful write, which is
the first thing S-7 names.

Found while building 012's replay audit event: the event could not be written because there was
nowhere to write it to. This is the same defect as the metrics gap 011 found — declared in the
manifest, absent from the code, invisible because nothing compared the two. The fix that worked
there was a test that reads both and fails on a mismatch in either direction.

There is a second problem underneath, and it is the more interesting one. **Some of the seven are
not this component's events to emit.** The Memory Manager never grants or revokes a role: roles
live in a domain's configuration and in IAM. Declaring `role_grant` and `role_revocation` here
asserts a responsibility the component does not have and cannot discharge, so emitting them would
be theatre. A manifest that overclaims is worse than one that claims less, because a reviewer
reading it believes the coverage is there.

So this is not "emit seven events". It is: decide what this component is accountable for, declare
exactly that, emit it, and make the two impossible to drift apart.

## Scope

- An `AuditSink` on `Deployment`, reaching the `remember` and `recall` paths, not only
  `verify_write`.
- Emitting the events this component is genuinely responsible for, each carrying a correlation ID
  and identifiers only.
- **An audit event for `recall`** (decided 2026-10-24), so a read of someone's memory leaves a
  trail. This goes beyond what S-7 names.
- Correcting `pattern.yaml` to declare what is emitted, including removing what this component
  cannot emit and adding the two real events that were never declared.
- A manifest-versus-code check in **both** directions, modelled on the metrics check in
  `tests/test_observability.py`: a declared event that is emitted nowhere, and an emitted event
  that is undeclared, both fail the build.
- Emitting the replay event 012 left open.
- `pattern.yaml`: `metadata.status` from `proposed` to `alpha`, and a real
  `metadata.maintainer.contact` in place of the placeholder. Both are release blockers that only
  make sense once the manifest stops overclaiming, so they land here rather than separately.

## Not in scope

- **Where audit events go.** The central sink is platform-owned Terraform and already exists; a
  domain cannot switch it off. This feature is about what the service emits, not where it lands.
- The prohibited-log-field list itself. It stands; the new events must obey it.
- Role management. If `role_grant` and `role_revocation` belong to something, that something is
  not this pattern, and deciding where they live is a separate question.
- Any change to the API contract, the reason codes, or an extension point.

## How we'll know it works

1. A successful `remember` emits an audit event carrying the correlation ID, the caller and the
   decision — and no fact value, no raw subject, no provider message.
2. A policy denial emits one, with the reason code.
3. A remediation deletion emits one.
4. An extension failure emits one.
5. Every event the manifest declares is emitted somewhere in `src/`, and every event emitted is
   declared. Both directions fail the build, proven by breaking each.
6. Removing any single emitting call fails a specific test, not just the manifest check.
7. A test asserts no audit field matches the prohibited-field list, against emitted records
   rather than against the source.
8. The replay event from 012 is emitted, closing that task.
9. A `recall` emits an audit event naming the caller, the scope owner by pseudonym and how many
   values were served — and no fact text.
10. `role_grant` and `role_revocation` appear nowhere in `pattern.yaml`, and the both-directions
    check would fail if either were added back without an emitting call.

## Decisions

Taken 2026-10-24 by Srinivasa reddy, instructed in session.

| Question | Decision |
|---|---|
| Does S-7 require an audit event for `recall`? | **Yes, audit reads.** Beyond what S-7 names, accepting the extra volume, because a read of someone's memory is what an investigator would want a trail of. |
| `role_grant`, `role_revocation` | **Removed from this manifest.** The component never grants or revokes a role, so declaring them claims coverage it cannot deliver. Where they belong, if anywhere, is not this pattern's question. |
| `metadata.status`, `maintainer.contact` | Changed in **this branch**, so one pull request clears the audit gap and the two manifest blockers together. |
| `configuration_change` | **Kept, as "started with this configuration".** This service reads configuration at startup and never changes it at runtime, so that is the only honest meaning — and it is the event that tells an investigator which policy was in force. |

`ASSUMPTION`, unchanged: the existing `memory_remediation` and `memory_write_unverified` events
are correct and worth keeping; they were simply never declared. Not yet reviewed against what an
investigator needs.

## Approval

Approved by Srinivasa reddy, 2026-10-24, instructed in session.
