# Operational runbook — <domain> <pattern>

Owned and maintained by the domain team.

## Service summary

| | |
|---|---|
| API | `<cloud-run-api-service>` |
| Worker | `<cloud-run-worker-service>` |
| Retry queue | `<pubsub-topic>` |
| Dead letter | `<pubsub-dlq-subscription>` |
| Memory bank | `<platform-provisioned>` — platform-owned |
| Quota allocation | `<max_writes_per_minute>` of the shared project quota |

## Deploy

Push to `main`; the pipeline builds, scans, pushes and deploys behind the `production`
environment gate.

## Roll back

```bash
gcloud run services update-traffic <service> --to-revisions=<previous-revision>=100 --region=<region>
```

Roll back the image, not the configuration, unless the configuration caused the failure.
A configuration rollback may require a Terraform apply.

## Alerts and responses

### Dead-letter depth rising

Writes have exhausted their retry attempts.

1. Inspect without acknowledging:
   ```bash
   gcloud pubsub subscriptions pull <dlq-subscription> --limit=10 --format=json
   ```
2. Classify: provider rejection, policy denial, malformed payload, or a bug.
3. Fix the cause. Replay selectively — never blind-replay the whole queue into a provider
   that may still be rejecting.

### Provider throttling (`provider_throttled` rising)

The shared project quota is contended. **This may not be your traffic.**

1. Check `quota_consumed` by domain — it is labelled per domain precisely for this.
2. If another domain is responsible, escalate to the platform team; you cannot fix it locally.
3. If it is yours, confirm the rate governor is enforcing `max_writes_per_minute`; writes should be
   parking in the queue, not failing.
4. Do not raise your own limit to push through — that shifts the outage to another domain.

### Queue age rising

The worker is not keeping up, or is down.

1. Check worker instance count and logs.
2. Confirm `min_instance_count >= 1` — a pull subscription needs a running consumer.
3. Check whether the governor is throttling because of provider 429s.

### Policy denials spiking

1. Check `policy_denials` by `reason_code`.
2. A configuration change is the usual cause. Check recent deployments.
3. A spike on one caller usually means a role or credential change.

## Escalation

| Issue | Escalate to |
|---|---|
| Shared quota contention caused by another domain | Platform team |
| Memory bank IAM or provisioning | Platform team |
| Audit sink not receiving events | Platform team |
| A suspected pattern defect | Platform team, with the correlation ID |
| Your configuration, extensions or deployment | Your team |

## What you cannot fix locally

The memory bank, its IAM binding, the audit sink and quota allocation are platform-owned.
Changing them is not within your access, by design.
