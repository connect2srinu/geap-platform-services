# Memory API — for agent teams

The tool API your agents call. **It is identical across every domain**: same paths, same request
and response shapes, same reason codes. What differs is the topic vocabulary and what the domain's
classifier permits — both configuration, not contract. An agent written against one domain works
against another.

Base URL: `https://<service-host>/v1`

## Operations

| Operation | Method | Path | Notes |
|---|---|---|---|
| remember | `POST` | `/v1/memories` | **Synchronous.** Requires `Idempotency-Key`. At most 5 facts. |
| recall | `GET` | `/v1/memories` | Optional `?topic=<id>` |
| liveness | `GET` | `/v1/healthz` | No dependencies |
| readiness | `GET` | `/v1/readyz` | Configuration valid and the bank reachable |

There is no separate `list`, `correct` or `forget` endpoint. Recall *is* the listing. A correction
is a new fact on the same topic and field: the provider consolidates it with what is already
stored, which is why a second, contradicting fact updates rather than duplicating.

## Authentication

Two headers, both required:

| Header | What it is |
|---|---|
| `Authorization: Bearer <token>` | The **end user's** token. The memory scope is derived from its subject, server-side. |
| `X-Agent-ID` | Your registered caller id. A caller absent from the domain's registry is refused. |

A scope supplied in the request body is refused by schema. You cannot read another end user's
memory by asking for it.

## remember

```http
POST /v1/memories
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7
```

```json
{"facts": [
  {"topic": "example_preference", "field": "preference",
   "value": "Horizon", "fact": "Prefers the organic brand Horizon.", "basis": "stated"}
]}
```

`basis` is `stated` (default) or `inferred`. A topic may forbid inferred facts.

**Always `200`, never `202`.** The write has been attempted and verified by the time you get a
response. Nothing is queued.

```json
{"outcome": "written", "stored": 1,
 "results": [{"index": 0, "topic": "example_preference",
              "reasonCode": "ACCEPTED", "memoryId": "4216…"}]}
```

| `outcome` | Meaning |
|---|---|
| `written` | Stored, and re-read and re-checked afterwards |
| `written_unverified` | Stored, but the service could not re-read it to confirm. Treat as stored, and expect an operator to look |
| `noop` | Nothing was stored. Every fact was refused — see each `reasonCode` |

**A refused fact is not an error.** The request succeeded; the policy said no. Do not retry it, and
do not surface it to the user as a failure.

| `reasonCode` | Why |
|---|---|
| `ACCEPTED` | Stored |
| `TOPIC_UNKNOWN` | Not in this domain's vocabulary |
| `TOPIC_DISABLED` | Known, switched off |
| `TOPIC_NOT_APPROVED` | Your caller is not granted this topic |
| `TOPIC_SENSITIVE` / `TOPIC_RESTRICTED` | Not storable by anyone. Asking for a grant will not help |
| `FIELD_UNKNOWN` | Not a field this topic declares |
| `VALUE_TYPE_INVALID` | Wrong type for the declared field |
| `VALUE_PROHIBITED` | The content was refused. **An allowed topic does not permit its content** |
| `INFERENCE_NOT_PERMITTED` | `basis: inferred` where the topic forbids it |
| `CLASSIFIER_ERROR` | The domain's classifier failed, so the fact was denied. Failing closed is deliberate |

## recall

```http
GET /v1/memories?topic=example_preference
```

```json
{"values": [{"topic": "example_preference", "field": "preference",
             "value": "Prefers the organic brand Horizon.",
             "fact": "Prefers the organic brand Horizon."}],
 "withheld": 0}
```

Only the caller's own scope, only topics your caller is granted, and only topics still eligible.

`withheld` counts memories deliberately not returned — stored before a policy tightened, or
unreadable. Non-zero is not an error; it means the service declined to hand something back.

> **`value` currently carries the fact text, not the structured value you wrote.** Only the
> encoded text is persisted, so the original typed value cannot be recovered. Treat `value` and
> `fact` as the same string for now. Tracked as an open contract question.

## Errors

Request-level failures use one shape:

```json
{"code": "RATE_LIMITED", "message": "…", "correlationId": "…", "retryable": true}
```

Retry only when `retryable` is true, honouring `Retry-After`.

| Code | Status | Retry? |
|---|---|---|
| `MALFORMED_REQUEST` · `TOO_MANY_FACTS` · `IDEMPOTENCY_KEY_MISSING` | 400 | No — fix the request |
| `IDEMPOTENCY_KEY_REUSED` | 422 | No — same key, different body |
| `UNAUTHENTICATED` · `TOKEN_INVALID` | 401 | No |
| `CALLER_NOT_REGISTERED` · `CALLER_NOT_PERMITTED` · `SCOPE_IN_BODY_REFUSED` | 403 | No |
| `SCOPE_NOT_RESOLVABLE` | 403 | No |
| `RATE_LIMITED` | 429 | **Yes**, after `Retry-After` |
| `CONFIGURATION_INVALID` | 500 | No — operator action |
| `PROVIDER_UNAVAILABLE` | 503 | **Yes**, after `Retry-After` |

An error never carries memory content, a fact value, your token or the provider's own message.
Quote the `correlationId` when you report a problem.

## Idempotency

Every `remember` needs an `Idempotency-Key`. Replaying the same key with the same body returns the
original outcome. Reusing it with a **different** body is `IDEMPOTENCY_KEY_REUSED`, not a silent
overwrite. Generate one per logical write and reuse it across retries of that write.

## Requesting access

[`role-request.md`](role-request.md). You are granted specific operations on specific topics; both
are checked on every call.
