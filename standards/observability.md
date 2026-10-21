# Observability standards

## Structured logs

JSON to stdout. Cloud Logging picks it up; nothing writes log files.

Required fields on every record:

| Field | Notes |
|---|---|
| `timestamp` | RFC 3339 |
| `severity` | `DEBUG` `INFO` `WARNING` `ERROR` `CRITICAL` |
| `correlation_id` | Propagated from the caller, generated if absent, returned in the response |
| `caller_id` | The authenticated caller, never a human identity |
| `domain` | The configured domain |
| `operation` | `remember` `recall` `list` `correct` `forget` or a worker operation |
| `decision` | `allowed` `denied` `parked` `deferred`, where applicable |
| `reason_code` | A stable code from the error catalogue, where applicable |
| `message` | Human-readable, **no payload content** |

## Prohibited fields — asserted by test

Never emitted in logs, traces, span attributes, metric labels or error responses:

- memory content, or any fragment of it;
- any value classified sensitive or restricted;
- PII — names, addresses, contact details, free-text user utterances;
- tokens, credentials, secrets, full authorization headers;
- raw provider error bodies.

Log the attribute **name**, never the attribute **value**. A test asserts this list against emitted
records and fails the build on violation (control `C-06`). This is the most common real-world leak
path, which is why it is tested rather than documented.

## Traces

OpenTelemetry to Cloud Trace. One span per tool invocation, one per policy decision, one per provider
call, one per worker processing attempt. Span attributes follow the same prohibited-field list —
a span attribute is a log field.

The correlation ID links logs, traces and audit events. A request that cannot be traced end to end
through all three is an observability defect.

## Required metrics

| Metric | Type | Labels |
|---|---|---|
| `tool_invocations` | counter | operation, caller, decision |
| `tool_latency` | histogram | operation — p50/p95/p99 |
| `queue_depth` | gauge | — |
| `queue_age_oldest` | gauge | — |
| `retry_attempts` | counter | operation, reason |
| `dead_letter_depth` | gauge | — |
| `provider_requests` | counter | operation, status |
| `provider_throttled` | counter | — 429s, separated from other errors |
| `quota_consumed` | counter | **domain** — for shared-quota attribution |
| `policy_denials` | counter | reason_code |
| `extension_errors` | counter | extension_id |

`provider_throttled` and `quota_consumed` by domain exist because quota is shared across all domains
in one project. Without per-domain attribution, a contention incident cannot be triaged — the prior
art's assessment records this telemetry as absent, and it is a required control (`C-18`, `C-19`).

## Audit events

Separate from logs, to the platform-owned audit sink. Never suppressible by domain configuration.

Required events: memory write, memory deletion, policy denial, configuration change, role grant or
revocation, exception invoked.

Each carries: correlation ID, caller, domain, operation, scope **identifiers**, decision, reason,
timestamp. **Never the value.** An audit event proves *that* something happened to *which* record, not
what it contained.

## Health and readiness

`/healthz` — liveness, no dependencies. `/readyz` — readiness, including provider reachability and
configuration validity. Neither reveals internal topology, versions or configuration detail to an
unauthenticated caller.
