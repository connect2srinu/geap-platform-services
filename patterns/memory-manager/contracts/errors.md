# Error catalogue

Two levels, and the distinction matters to an integrating agent:

- **Per-fact `reasonCode`** — inside a `200`. The request was fine; this *fact* did not qualify.
- **Request-level `code`** — a `4xx` or `5xx`. The request itself failed.

An agent must be able to tell *"you asked for something we don't store"* from *"we couldn't store
it"* from *"you're not allowed"*. Collapsing those is the most common way a memory API becomes
unusable.

---

## Per-fact reason codes — returned inside `200`

| `reasonCode` | Means | What the agent should do |
|---|---|---|
| `ACCEPTED` | Stored. `memoryId` is present. | Nothing. |
| `TOPIC_UNKNOWN` | No such topic in this domain's configuration. | Stop sending it. Likely a typo or a topic from another domain. |
| `TOPIC_DISABLED` | The topic exists but the domain has turned it off. | Stop sending it. May be re-enabled later. |
| `TOPIC_NOT_APPROVED` | The topic exists and is enabled, but **this caller** has no grant for it. | Request the grant from the domain. |
| `TOPIC_SENSITIVE` | Classified sensitive; not eligible for storage. | Stop sending it. Not a permissions problem — the domain stores nothing in this topic. |
| `TOPIC_RESTRICTED` | Classified restricted; not eligible. | As above. |
| `FIELD_UNKNOWN` | The `field` is not part of the topic's schema. | Check the topic's fields. |
| `VALUE_TYPE_INVALID` | The value's type does not match the topic's declared type. | Fix the type. |
| `VALUE_PROHIBITED` | The topic is permitted, but the **value or `fact` text** carries prohibited content. | Do not retry as-is. **The label does not grant passage** — a permitted topic does not exempt its text. |
| `INFERENCE_NOT_PERMITTED` | `basis: inferred`, and the topic does not set `allowInferred: true`. | Send only what the user stated, or ask the domain to permit inferences for that topic. |
| `CLASSIFIER_ERROR` | The domain's classifier failed. **Fails closed** — nothing stored. | Retry later. Persisting means the domain has a broken classifier; report it. |

### `noop` is not a failure

A request where every fact is filtered returns `200` with `outcome: noop`. The agent did nothing
wrong by offering a fact the domain does not accept, and a `4xx` would teach agents to retry or to
treat governance as an outage. Check `results`, not just the status.

---

## Request-level error codes

| HTTP | `code` | Means | Retryable |
|---|---|---|---|
| `400` | `MALFORMED_REQUEST` | Does not match the schema. | No |
| `400` | `TOO_MANY_FACTS` | More than five facts. **A hard provider limit**, verified live — `GenerateMemories` accepts five per request. | No — split the call |
| `400` | `IDEMPOTENCY_KEY_MISSING` | The header is required on `remember`. | No |
| `422` | `IDEMPOTENCY_KEY_REUSED` | Same key, **different** payload, from the same caller for the same end user. Keys are namespaced per caller and scope, so two end users choosing the same string never collide. | No — use a new key |
| `401` | `UNAUTHENTICATED` | No token. | No |
| `401` | `TOKEN_INVALID` | Token failed verification against the configured issuer and JWKS. | No |
| `403` | `CALLER_NOT_REGISTERED` | The token is valid but the caller is not a registered agent for this domain. | No |
| `403` | `CALLER_NOT_PERMITTED` | Registered, but lacks the capability for this operation. | No |
| `403` | `SCOPE_NOT_RESOLVABLE` | The subject could not be resolved to a memory scope. | No |
| `403` | `SCOPE_IN_BODY_REFUSED` | The request tried to set a scope. **Scope is always derived server-side.** | No — remove it |
| `429` | `RATE_LIMITED` | **The caller's own** limit. Honour `Retry-After`. | Yes, after the delay |
| `503` | `CONFIGURATION_INVALID` | The service started but its configuration is unusable. | No — operator fix |
| `503` | `PROVIDER_UNAVAILABLE` | The Memory Bank is unreachable **or throttled the write**. The write was not accepted. | **Yes — retry with the same idempotency key** |

### The two that get confused

**`429` is never the provider's.** A provider `429 RESOURCE_EXHAUSTED` becomes
`503 PROVIDER_UNAVAILABLE`, because the *caller* did nothing wrong and shaping their behaviour would
be the wrong fix. `429` means this caller exceeded the limit the domain set for it.

This is a deliberate departure from `standards/engineering.md`, which maps a provider `429` to
"parked, with `202`". That rule assumes an asynchronous write. v0.1.0 is synchronous and has nowhere
to park, so the write fails and says so. Recorded in `design/001-memory-manager/design.md`.

**`503 PROVIDER_UNAVAILABLE` means the write did not happen.** Retry with the same key. Do not treat
it as "maybe stored" — the service does not return it once a write has been accepted.

---

## What is never in an error

Per security rule **S-4**:

- the fact text, the value, or any fragment of either
- the end user's identifier — audit carries an HMAC pseudonym, never the raw subject
- a provider's raw error text or resource names
- tokens, secrets, or configuration detail

An error carries a **code**, a message free of payload content, and the **correlation ID**. Keep the
correlation ID — it is the only thing that lets the domain trace a request, and the one thing worth
quoting in a defect report.

## The limit of the idempotency guarantee

A replay is recognised **by the instance that served the original request**. A domain runs several
instances; session affinity makes a retry likely to return to the same one, and provider
consolidation collapses an identical fact that reaches another, so a duplicate is normally
harmless rather than invisible.

It is not a distributed guarantee, and nothing here pretends otherwise. A shared idempotency
store would make it one, at the cost of a managed service in every domain's deployment; 001
weighed that and declined for v0.1.0. The residual is recorded in that design with an expiry.

Two consequences worth stating plainly:

* Only **completed** outcomes are recorded. A `429` or a `503` is never cached, so retrying the
  same key after a transient failure is correct and will be attempted properly.
* A recorded response outlives a configuration change. Tighten the classifier and a fact refused
  under the new rules still replays its earlier result until the entry expires — by default,
  fifteen minutes.
