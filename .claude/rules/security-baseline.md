# Security baseline

The full control catalogue is `standards/security.md`. This file holds the rules that apply while
writing code, every time.

## Fail closed

Every authorization, classification and validation decision denies by default. An unknown caller, an
unknown attribute, an unmapped scope, a classifier that errors — all deny. Never "allow if not
explicitly denied".

## Never log or trace

- Memory content, in whole or in part.
- Any value classified sensitive or restricted.
- Personally identifiable information, including names and free-text user utterances.
- Tokens, credentials, secrets, full authorization headers.

Log **identifiers, decisions and counts**: correlation ID, caller ID, attribute *name*, decision,
reason code, latency, byte counts. Never the value. `standards/observability.md` carries the
prohibited-field list, and a test asserts it.

## Secrets

Named in configuration, resolved from Secret Manager at runtime. Never in source, `.env` files that
are committed, container images, Terraform variables, logs, or error messages. `.env.example` carries
names and empty values only.

## Identity

Callers present a Google-signed ID token mapped to exactly one registered caller. Service-to-service
uses Workload Identity, never a downloaded key file. Development header shortcuts must be impossible
to enable in a deployed environment — not merely defaulted off, but refused when the environment is
not local, and that refusal must be tested.

## Least privilege

One service account per component, each with the narrowest role set that works. No primitive roles
(`roles/owner`, `roles/editor`, `roles/viewer`) anywhere, ever. Memory Bank access is granted to the
Memory Manager's service account only — never to an agent directly — and constrained by IAM
Conditions on scope where the provider supports it.

## Writing down a control

A control is `Verified` only with evidence: a test that fails when the control is removed, a scan
output, or an explicitly approved exception with an owner and an expiry date. "Implemented" is not
"verified". Never mark a control compliant because the code looks right.
