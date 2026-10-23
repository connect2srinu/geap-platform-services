---
artifact: intent
feature: 015-audit-events-that-exist
status: draft
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
- Correcting `pattern.yaml` to declare what is emitted, including removing what this component
  cannot emit and adding the two real events that were never declared.
- A manifest-versus-code check in **both** directions, modelled on the metrics check in
  `tests/test_observability.py`: a declared event that is emitted nowhere, and an emitted event
  that is undeclared, both fail the build.
- Emitting the replay event 012 left open.

## Not in scope

- **Where audit events go.** The central sink is platform-owned Terraform and already exists; a
  domain cannot switch it off. This feature is about what the service emits, not where it lands.
- The prohibited-log-field list itself. It stands; the new events must obey it.
- Role management. If `role_grant` and `role_revocation` belong to something, that something is
  not this pattern, and deciding where they live is a separate question.
- Any change to the API contract, the reason codes, or an extension point.
- Retrofitting audit to `recall` if it turns out S-7 does not require it — see the open question.

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

## Open questions

| Question | Who decides |
|---|---|
| Does S-7 require an audit event for `recall`? It says "write, denial and deletion", so a read is not named — but a read of someone's memory is exactly what an investigator would want a trail of. Adding it is cheap; the argument against is volume. | Platform architect |
| `configuration_change`: this service loads configuration at startup and never changes it at runtime, so the only honest event is "started with this configuration". Keep it under that meaning, or drop it as not this component's? | Platform architect |
| `role_grant` and `role_revocation`: remove from this manifest. Does anything else in the platform own them, or do they leave the catalogue entirely? | Platform lead |
| `ASSUMPTION` — the existing `memory_remediation` and `memory_write_unverified` events are correct and worth keeping; they just were never declared. Not yet reviewed against what an investigator needs. | — |

## Approval

A human sets `status: approved` with `approved_by` and `approved_date` (ISO, `YYYY-MM-DD`).
