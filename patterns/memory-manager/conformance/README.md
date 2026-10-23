# Conformance suite

**Run this in your own CI, against your own build.** It is how you show that your customisation
still honours the pattern's contract.

```bash
CONFORMANCE_BASE_URL=https://your-service pytest conformance/
```

With no `CONFORMANCE_BASE_URL` it starts the reference implementation in process with the fake
memory bank — which is what the platform's CI does, to prove the suite itself works.

## Configuration

| Variable | Default | What it is |
|---|---|---|
| `CONFORMANCE_BASE_URL` | *(unset)* | Your deployment. Unset runs against the reference. |
| `CONFORMANCE_AGENT_ID` | `writer-agent` | An agent with read and write |
| `CONFORMANCE_READER_ID` | `reader-agent` | An agent with read only |
| `CONFORMANCE_END_USER_TOKEN` | *(placeholder)* | A valid end-user token |
| `CONFORMANCE_ALLOWED_TOPIC` | `preferred_brands` | A non-sensitive, enabled topic |
| `CONFORMANCE_ALLOWED_FIELD` | `brand` | A field on that topic |
| `CONFORMANCE_SENSITIVE_TOPIC` | `health_conditions` | A sensitive or restricted topic |

Set the topic variables to names from **your** configuration. The contract is about behaviour per
classification, not about these particular names.

## What it checks

The shape a domain must not change: the per-fact reason codes and request-level error codes, the
five-fact cap, required idempotency, scope derived from the caller rather than supplied, read-only
grants that cannot write, errors that carry no payload, and `recall` reporting what it withheld.

A filtered fact is a `200` with `outcome: noop`, not an error — a build that returns `4xx` there
teaches agents to retry, or to read governance as an outage.

## What it cannot check

- **That the `withheld` count is accurate.** It verifies the field exists and is a count. Forcing a
  withhold from outside would need content the suite knows your classifier rejects, and it
  deliberately knows nothing about your vocabulary. Removing the field is caught; faking it is not.
- **That your classifier is correct.** The suite cannot know what your domain considers sensitive.
  It checks that a *sensitive-classified topic* is refused, not that you classified the right
  things.
- **Anything about the live provider.** Latency, eventual consistency and quota belong to a live
  smoke test.

## The honest part

**The platform team cannot see this run.** If you delete the job, nothing outside your team
notices. The only controls that survive that are the platform-owned memory bank IAM binding, the
audit sink and quota alerting — see [security standards](../../../standards/security.md).

So this suite is worth running because *you* want to know, not because anyone is checking.
