---
name: domain-onboard
description: Helps a consuming domain adopt a published platform pattern. Use when the user asks to "onboard a domain", "set up a consumer project", "adopt the pattern for X", or "generate a domain scaffold". Produces a domain-owned project with a pinned pattern reference, domain configuration, extension-point stubs, Dockerfile, Terraform deployment configuration, a GitHub Actions CI/CD pipeline, IAM requirements, secrets integration, observability configuration, an operational runbook, agent-team API documentation and a role-grant template, and upgrade instructions. The resulting project lets the domain build and publish its own container image.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(git tag -l*)
  - Bash(python3 scripts/validate_pattern_manifest.py*)
user-invocable: true
---

# domain-onboard — Generate a domain consumer project

## Purpose

Give a domain team everything needed to configure, build, deploy and operate a pattern **without the
platform team in the loop at runtime**.

## When to use

A domain has selected a pattern and a published version and wants its project scaffolded.

## Required inputs

- Pattern name and the **published version** to pin
- Domain name (neutral identifier, not a real enterprise name in examples)
- Target GCP project and region
- Which extension points the domain will implement

Ask for anything missing. In particular, confirm the version — "latest" is not a pinned dependency.

## Steps

### 1. Confirm the pattern and version

```bash
git tag -l '<pattern>/v*' | sort -V
```

Check the version exists and its status. **Warn if the pattern is `proposed`** — its design is not
approved and its contracts may change. Proceed only if the user accepts that.

### 2. Read the pattern's contract

`pattern.yaml`: configuration schema, extension points, required secrets, cloud permissions,
infrastructure split, compatibility. The scaffold must match what the pattern actually declares, not
what a template assumes.

### 3. Generate the project

From `templates/domain-consumer/`:

```
<domain>-<pattern>/
├── README.md
├── pattern.lock.yaml          pinned pattern name + version + manifest digest
├── config/domain-config.yaml  the domain's configuration
├── extensions/                the domain's extension implementations
├── Dockerfile                 DOMAIN-OWNED build
├── .github/workflows/         DOMAIN-OWNED CI/CD
├── infrastructure/terraform/  DOMAIN-OWNED deployment
├── conformance/               runner for the pattern's conformance suite
├── docs/
│   ├── runbook.md
│   ├── upgrade.md
│   ├── agent-api.md           agent-facing API documentation
│   └── role-request.md        template for agent teams requesting a role
└── .env.example               secret NAMES only
```

### 4. Domain configuration

Generate `domain-config.yaml` against the pattern's schema, with every required key and a comment
explaining each. Use neutral placeholders — no real identifiers, no secret values.

State clearly in comments which keys the domain may change and which are platform-fixed.

### 5. Extension stubs

For each extension point the domain will implement: a stub implementing the interface, with the
default's behaviour as a starting point and a comment on what to change.

**Security-relevant stubs start at the fail-closed default**, with a comment that loosening them is a
deliberate act requiring review. A stub that starts permissive is a trap.

### 6. Container build — domain-owned

A Dockerfile that builds **from the vendored pattern source**:

- pinned base image, non-root user, no build secrets in any layer, minimal final image.
- A comment making explicit that the domain owns this image, its registry and its scanning.

The platform team never builds or operates this image.

### 7. Deployment — Terraform, domain-owned

From `templates/terraform-gcp/`, Cloud Run, targeting the **platform-owned shared GCP project**:

- the service, its dedicated service account, Pub/Sub topic and subscription, secret references;
- internal ingress by default;
- **no primitive roles**;
- a clear separation between what the domain provisions and what the platform provisions.

**The Memory Bank, its IAM binding, the audit sink and quota alerting are platform-owned.** The
domain's Terraform must not attempt to create them; it consumes their outputs. Say so in the README —
this is the enforcement seam described in `standards/pattern-contract.md`.

### 8. CI/CD — GitHub Actions, domain-owned

From `templates/cicd-github-actions/`: lint, test, **run the pattern conformance suite**, build the
image, scan it, push to the domain's registry, deploy with Terraform, smoke test.

The conformance step is the domain's demonstration that its customization still honours the contract.
Note in the template that the platform cannot observe this run — which is exactly why it matters.

### 9. IAM, secrets, observability

- IAM: least privilege per component, derived from `spec.cloudPermissions`.
- Secrets: Secret Manager references by name; `.env.example` with names and empty values.
- Observability: the pattern's required metrics, audit sink configuration, and the
  prohibited-log-field list — restated in the runbook, because the domain owns the code that could
  violate it.

### 10. Runbook and agent-facing docs

Runbook: deploy, roll back, common failures, dead-letter triage and replay, quota-contention
response, alert response, escalation.

`docs/agent-api.md`: generated from the pattern's OpenAPI spec — what agent teams call, with examples.
`docs/role-request.md`: how an agent team requests a role from this domain.

The domain publishes its endpoint and grants roles; the platform never brokers that relationship.

### 11. Upgrade instructions

How to move to a newer pattern version, pointing at `pattern-upgrade`.

### 12. Report

What was generated, the pinned version, what the domain must fill in, and what it must not change.

## Outputs

A complete domain-owned project. Nothing deployed, nothing built, nothing pushed.

## Validation rules

- Pattern version exists and is pinned, not floating
- Configuration validates against the pattern's schema
- No real identifiers, no secret values, no primitive roles
- Security-relevant extension stubs fail closed
- Platform-owned infrastructure is consumed, not recreated

## Approval requirements

Generating a scaffold needs no gate. **Deploying it is the domain's decision and action** — never
performed here.

## Failure and recovery

| Situation | Do this |
|---|---|
| Version does not exist | List available versions; stop. |
| Pattern is `proposed` | Warn clearly; proceed only on acknowledgement. |
| Extension points unknown | Generate stubs for all declared ones with defaults. |
| Target project unknown | Ask. Do not invent a project ID. |
| Asked to deploy | Decline. Hand over the commands. |

## Does not

Deploy. Build or push images. Create cloud resources. Invent IAM policies or project identifiers.
