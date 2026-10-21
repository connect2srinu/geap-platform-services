# <domain> memory API — for agent teams

Generated from the pattern's OpenAPI specification at adoption time. Regenerate after any pattern
upgrade.

> **The contract is identical across every domain.** An agent written against this API works against
> another domain's deployment, with a different endpoint and a role that domain grants. If this
> document differs from the pattern contract, that is a defect — report it.

## Endpoint

```
<cloud-run-service-url>
```

## Authentication

Present a Google-signed ID token for your registered workload identity. Never a downloaded key.

## Operations

| Operation | Method | Path | Notes |
|---|---|---|---|
| `remember` | POST | `/v1/memories` | Returns `202`. Requires `Idempotency-Key`. |
| `recall` | GET | `/v1/memories` | Synchronous read |
| `list` | GET | `/v1/memories:list` | Cursor-paginated |
| `correct` | POST | `/v1/memories:correct` | Requires `Idempotency-Key` |
| `forget` | POST | `/v1/memories:forget` | Requires `Idempotency-Key` |

<!-- Replace with the generated operation reference. -->

## Behaviours that catch integrators out

| Behaviour | What it means for you |
|---|---|
| `remember` returns `202` | The write is **durably enqueued**, not applied. A read immediately after may not show it. |
| `503` from `remember` | The write was **not** accepted. Retry. |
| `Idempotency-Key` required | Stable key per logical write. Same key + same payload → one effect. Same key + different payload → `422`. |
| `429` | **Your** rate limit. Honour `Retry-After`. |
| Provider throttling | Parked and retried; you still receive `202`, not an error. |
| `403` | Fail-closed denial, with a reason code. |

Every response carries a correlation ID. Keep it — it is the only way this domain can trace your
request, and the one thing to quote in a defect report.

## Roles available from this domain

| Role | Operations |
|---|---|
| `<reader-agent-role>` | read, list |
| `<writer-agent-role>` | read, list, write, correct |

Request one via [`role-request.md`](role-request.md).

## Error codes

<!-- Replace with the pattern's error catalogue. -->

## Do not

Call the memory bank directly. That IAM binding grants access to this service's identity only, by
design — a direct path would bypass every policy, audit and privacy control this domain configured.
