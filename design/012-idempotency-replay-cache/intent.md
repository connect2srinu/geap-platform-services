---
artifact: intent
feature: 012-idempotency-replay-cache
status: draft
---

# The idempotency the contract already promises

## Why

`remember` requires an `Idempotency-Key`, and `contracts/openapi.yaml` describes exactly what it
buys:

> A stable key per logical write. The same key with the same payload yields one effect and returns
> the original result; the same key with a different payload returns `422`.

**Neither half is implemented.** The service checks the header is present and discards it.
`IDEMPOTENCY_KEY_REUSED` appears in the error catalogue, in `contracts/openapi.yaml`, in the
conformance suite's list of codes, and in both onboarding guides as something a domain must not
change — and is raised nowhere in `src/`. Replaying a key with a different body writes silently.
`VERIFIED` by running it against a correct build on 2026-10-23: the rewritten post-deployment
smoke test reported it, which is what that tooling is for.

This is not an oversight in the design. 001 considered it and **accepted the residual risk**, with
three named compensating controls:

| Compensation named in 001's design | State |
|---|---|
| Provider consolidation dedups identical facts | **In place** — a property of `GenerateMemories`, verified live |
| Session affinity, so a retry reaches the same instance | **In place** — `session_affinity = true` in the domain-runtime module |
| **A per-instance replay cache** | **Never built** |

001 also chose `GenerateMemories` over `CreateMemory` specifically because "consolidation is what
makes duplicate delivery harmless without a shared idempotency store, which v0.1.0 has no room
for". That reasoning still holds. Two of three compensations exist. This feature builds the third.

So the question is not whether to add a shared idempotency store — that was asked and answered.
It is that an approved design named a control, the contract promises its effect, and the code
does not have it.

## Scope

- A bounded, expiring, per-instance record of `Idempotency-Key` → (payload fingerprint, response),
  consulted before a write.
- Same key, same payload: return the original response without writing again.
- Same key, different payload: `IDEMPOTENCY_KEY_REUSED`, `422`.
- Making the documented promise match what a deployment can actually honour, since a per-instance
  cache cannot guarantee either behaviour across instances. Whether that means implementing to the
  current wording and documenting a residual, or changing the wording, is an open question below.
- Whatever the resolution, the conformance suite must assert the behaviour a domain can rely on,
  and `docs/agent-api.md` must describe it truthfully.

## Not in scope

- **A shared idempotency store.** Firestore, Redis or Cloud SQL would make this correct across
  instances and is the right answer eventually. It adds a managed service to every domain's
  deployment, which is a full architecture decision and not this feature. 001 rejected it for
  v0.1.0 with reasons that still hold.
- Changing `GenerateMemories` to `CreateMemory`. Consolidation is load-bearing here.
- The `value`-on-recall question, still `OPEN` from 011.
- Any change to the reason codes, the extension points, or a security control.

## How we'll know it works

1. Replaying a key with an identical payload returns the original response, byte for byte, and the
   provider is called **once** — asserted by counting calls, not by inspecting the response.
2. Replaying a key with a different payload returns `422` / `IDEMPOTENCY_KEY_REUSED`.
3. Two different keys with identical payloads both write. The key is the identity, not the body.
4. The record expires, and the cache is bounded — a long-running instance cannot grow without
   limit, and a flood of unique keys cannot evict its way into unbounded memory.
5. The cached response carries no memory content into a log, a metric or an error (S-4).
6. The conformance suite covers whatever the contract ends up promising, and fails if the
   behaviour is removed.
7. The post-deployment smoke test's idempotency checks pass against a correct build. They fail
   today, which is what started this.
8. `docs/agent-api.md` and `contracts/errors.md` describe the real guarantee, including its limit.

## Open questions

| Question | Who decides |
|---|---|
| The contract says a different payload "returns `422`", with no qualification. A per-instance cache cannot promise that across instances. Implement to the wording and record the cross-instance gap as a residual risk — consistent with how 001 already treats it — or change the wording to describe a best-effort guarantee? Changing it is a contract change and would need its own approval. | Platform architect |
| Should the payload fingerprint cover the resolved caller and scope as well as the body? Two callers using the same key is possible; treating their writes as one would be wrong. | Platform architect |
| What expiry? Long enough to cover a client's retry budget, short enough to bound memory. 001 named no number. | Platform lead |
| `ASSUMPTION` — session affinity meaningfully raises the chance a retry reaches the same instance. It is configured, but its effect has not been measured here. | — |

## Approval

A human sets `status: approved` with `approved_by` and `approved_date` (ISO, `YYYY-MM-DD`).
