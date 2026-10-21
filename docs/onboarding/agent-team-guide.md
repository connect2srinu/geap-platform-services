# Agent team integration guide

For a team building an agent that uses a domain's deployed memory service.

## Who you talk to

**The domain**, not the platform team. The domain owns and hosts the service, grants roles, and
publishes its endpoint. The platform team publishes the pattern the domain adopted and does not broker
access.

| You need | Ask |
|---|---|
| The endpoint | The domain team |
| A role | The domain team — `docs/role-request.md` in their project |
| API documentation | The domain's `docs/agent-api.md` |
| A suspected pattern defect | The domain, who escalates to the platform team |

## The contract is the same everywhere

The tool API is **identical across every domain**. An agent written against one domain's deployment
works against another's, with a different endpoint and a role granted by that domain. Domains
configure policy *behind* the contract; they do not change its surface.

This is deliberate and is enforced by the pattern's conformance suite. If you find a domain whose API
differs from the contract, that is a defect — report it.

## Requesting a role

Use the domain's `docs/role-request.md`. Be accurate about:

- **Which operations you need.** Ask for read-only if you only read. Write access is granted where
  writing is the agent's job.
- **Your expected volume, peak and steady state.** This matters more than it looks: the domain holds an
  allocated share of a **shared project quota**, and a new high-volume consumer may require that
  allocation to be renegotiated with the platform team before your role is granted.
- **Your purpose and the data categories you need.** The domain checks these are consistent.

Present a **workload identity**, never a downloaded key.

## Calling the API

Read the domain's `docs/agent-api.md`, generated from the pattern's OpenAPI specification. Points that
catch integrators out:

| Behaviour | What it means for you |
|---|---|
| `remember` returns **`202`** | The write was **durably enqueued**, not applied. A subsequent read may not show it yet. |
| `503` from `remember` | The write was **not** accepted. Retry it. |
| `Idempotency-Key` is **required** on `remember` | Send a stable key per logical write. Retrying with the same key is safe; the same key with a different payload returns `422`. |
| `429` | **Your** rate limit, not the provider's. Honour `Retry-After`. |
| Provider throttling | Surfaces as a `202` with the write parked, not as an error. |
| `403` | Fail-closed denial. The domain's policy refused it; the response carries a reason code. |

Every response carries a correlation ID. **Keep it** — it is the only way the domain or the platform
team can trace your request, and the one thing to quote in a defect report.

## What never to send

Do not put secrets, credentials or content you have not been authorized to store into memory writes.
The service classifies and may refuse, but the obligation starts with you.

## What never to do

Do not call the memory bank directly, even if you discover a path to it. That IAM binding grants access
to the Memory Manager's service account only, by design — an agent granted direct access bypasses every
policy, audit and privacy control the domain configured.
