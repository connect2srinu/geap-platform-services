---
artifact: intent
feature: 011-tested-local-run
status: draft
---

# A local run that actually runs

## Why

`docs/onboarding/demo.md` is the first page a teammate opens, and its local-run section does not
work. Every instruction in it was checked against `main` at `b0fce54` on 2026-10-23 and every one
fails: it copies a `.env.example` that does not exist, starts `pattern.api.main:app` which is not a
module, sets `AUTH_ENABLED` and `DOMAIN_NAME` which the service does not read, and omits the
required `Authorization` header. Its opening example — the one meant to show a fact being stored —
returns `noop` / `FIELD_UNKNOWN`, because the payload has no `field` and `preferred_brands`
declares one. Someone following it concludes the service is broken.

None of this is careless. The instructions were right when they were written; the entry point, the
package layout and the startup wiring all moved afterwards. They drifted because **nothing executes
them**. Prose that no check runs will drift again, so correcting the words is not the fix.

The fix is to make the documented path a committed, exercised artifact: a configuration and a
sample extension that the test suite boots, with the document quoting them rather than describing
them from memory.

## Scope

- A local-run example in `patterns/memory-manager/examples/local/`: a domain configuration, a
  sample PII classifier and policy provider, and a `.env.example` carrying names and empty values.
- A test that boots the service from that example and exercises the four demo calls, so the example
  cannot rot between releases.
- Rewriting the local-run section of `docs/onboarding/demo.md` against it, including the exact
  commands and the responses they actually produce.
- A check that the commands and payloads in the document match the example, so the two cannot drift
  apart again silently.

## Not in scope

- The deployed Cloud Run path, and anything requiring `terraform apply`. This repository applies no
  infrastructure.
- Live Memory Bank verification. That exists as `design/001-memory-manager/spike/verify_live.py` and
  is deliberately separate: it writes to a real bank and costs quota.
- CMEK and control C-20. Tracked in PR #5 and unaffected by this.
- Any change to the API contract, the error catalogue, an extension point, `pattern.yaml`, or a
  security control. If this work appears to need one, it stops here.
- `docs/onboarding/domain-adoption.md` and `developer-guide.md` beyond anything the shared commands
  make wrong. Checked: neither carries the stale references. `ASSUMPTION` — grep-level, not a
  line-by-line read.

## How we'll know it works

1. `patterns/memory-manager/examples/local/` holds a configuration that validates against the
   pattern's own config schema.
2. A test in the pattern's suite boots the service from that example and passes as part of
   `make verify`.
3. That test exercises all four demo behaviours: a fact stored, a sensitive topic refused, an
   allowed topic carrying prohibited content refused, and a recall returning the stored value.
4. The test asserts no payload, value or raw subject reaches the emitted log records (S-4).
5. Every command and request body printed in `demo.md`'s local-run section appears verbatim in the
   example or the test, enforced by a check that fails when they diverge.
6. Following `demo.md` from a clean checkout, with no prior knowledge, brings the service up and
   produces the documented responses. Verified by doing it, not by reading it.
7. Deleting a required field from the example configuration makes the new test fail.

## Open questions

| Question | Who decides |
|---|---|
| Should the sample classifier be a regex stand-in, or should the example ship with the deny-all defaults and demonstrate fail-closed first? A stand-in demonstrates more; the defaults are what a real domain starts from. | Platform lead |
| Does the shipped sample classifier risk being mistaken for production-ready, and is a naming convention (`sample_`, a loud docstring) enough to prevent that? | Platform lead |
| `VERIFIED` — the four behaviours above were all produced by hand against `main` on 2026-10-23, so the target state is known to be reachable. | — |

## Approval

A human sets `status: approved` with `approved_by` and `approved_date` (ISO, `YYYY-MM-DD`).
