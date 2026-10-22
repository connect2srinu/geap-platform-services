---
artifact: intent
feature: 001-memory-manager
status: approved
approved_by: Srinivasa reddy
approved_date: 2026-10-21
---

# Memory Manager v0.1.0 — a governed write path for agent memory

## Why

Agents need somewhere to store and retrieve customer memory, and every agent team currently has to
solve authorization, privacy classification and audit for itself. One domain-owned service should do
it once, so agents only call a tool API.

## Scope

An authenticated agent submits **already-structured facts**. The service:

1. derives the agent's permissions from its authenticated identity;
2. resolves the user and owning memory scope **server-side**, never from the request body;
3. loads the domain's topic configuration and selects eligible topics — enabled and non-sensitive only;
4. validates every fact: topic, field, value type, sensitivity, ownership, and whether an inference
   is permitted;
5. writes approved facts to Memory Bank, then **reads them back and re-classifies**, because
   consolidation can rewrite a fact after the gate;
6. returns a no-op result when nothing qualifies.

Plus `recall` for the same scope, so a write can be proven.

## Not in scope

- Gemini extraction from raw user messages — v0.2.0
- A configuration database — topics are versioned YAML behind a `topic-provider` extension point
- `correct`, `forget`, `list`, MCP, an async queue or worker

## How we'll know it works

1. A fact in an allowed, non-sensitive topic is stored and comes back from `recall`.
2. A fact in a sensitive or restricted topic is **not** stored; the response is a no-op, not an error.
3. A fact labelled as an allowed topic whose **value** carries prohibited content is **rejected** —
   the label does not grant passage.
4. An unknown topic is rejected.
5. Scope comes from the authenticated identity; a request trying to set another user's scope is refused.
6. An inference beyond what the input supports is not stored unless the topic permits inferences.
7. Read-back re-classification deletes or rolls back a consolidated memory that now carries
   prohibited content.
8. No prohibited content reaches logs, traces, error responses or stored evidence — proven by a test
   that fails if the redaction is removed.
9. Nothing qualifying → no-op, no wasted provider call.
10. Every write, rejection and remediation emits an audit event with a correlation ID.

## Open questions

| Question | Who decides |
|---|---|
| Does Memory Bank support a customer-managed encryption key? **OPEN** — probe reported UNAVAILABLE, Cloud KMS not enabled | Platform architect |
| Does retention-from-last-write meet Legal's definition? **OPEN** | Legal |

## Approval

Approved 2026-10-21.
