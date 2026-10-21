# Security standards and control catalogue

The baseline rules for day-to-day coding are in `.claude/rules/security-baseline.md`. This document is
the **normative control catalogue**: `controls-check.md` at Gate C is generated from it.

## How a control is assessed

Each control is assessed as:

| Field | Meaning |
|---|---|
| **Requirement** | What must be true |
| **Applicability** | Whether it applies to this change, and why |
| **Implementation** | How it is satisfied — specific files, resources, configuration |
| **Verification** | How it is proven — a named test, a scan, a manual procedure |
| **Status** | `Verified` · `Implemented, not verified` · `Gap` · `Not applicable` · `Exception approved` |
| **Evidence** | Command output, test name, scan report, or the exception record |

**Rules that are not negotiable:**

- A control is **never** marked `Verified` without evidence that would fail if the control were
  removed. Code that looks correct is `Implemented, not verified`.
- `Not applicable` requires a stated reason. "Not relevant" is not a reason.
- `Gap` is an acceptable outcome. An undisclosed gap is not.
- An `Exception approved` names an approver, a date, an expiry and a compensating control.
- Controls are **re-assessed** when implementation changes the design or the security posture.

## Non-overridable controls

These cannot be weakened by domain configuration. A domain may make them stricter. If configuration
could switch one off, the design is wrong. Declared per pattern in
`spec.security.nonOverridableControls`.

`C-01` authentication · `C-02` authorization fail-closed · `C-05` sensitive-data redaction before
persistence · `C-06` logging restrictions · `C-07` audit completeness · `C-08` secret handling ·
`C-11` least-privilege IAM · `C-16` domain isolation.

## Catalogue

### Identity and access

| ID | Requirement | Verification |
|---|---|---|
| **C-01** | Every caller is authenticated. Deployed environments require a Google-signed ID token mapped to exactly one registered caller. Development header shortcuts are **refused** outside local environments, not merely defaulted off. | Test: unauthenticated request → 401. Test: dev shortcut with production-like config → startup refusal. |
| **C-02** | Authorization decisions fail closed. Unknown caller, unknown attribute, unmapped scope, or a classifier error → deny. | Test per deny path, each failing if the check is removed. |
| **C-03** | RBAC is driven by versioned domain configuration, validated against a schema. Roles grant the narrowest capability that works; read-only can never write. | Test: read-only role attempting a write → 403. Schema validation test. |
| **C-04** | Cross-caller and cross-domain access is explicit and recorded. Default is no access. | Test: caller A cannot read caller B's scope. |

### Data protection

| ID | Requirement | Verification |
|---|---|---|
| **C-05** | Data is classified before persistence; sensitive and restricted values are redacted or refused per domain policy. The classifier is a domain extension; the **obligation** is platform and defaults to deny-all. | Test: unclassifiable value → refused, not stored. Test: default classifier denies. |
| **C-06** | Memory content, PII, secrets and full auth headers never reach logs, traces or error responses. | Automated test asserting the prohibited-field list against emitted records. |
| **C-07** | Every memory write, deletion, denial and policy decision emits an audit event with a correlation ID to the platform audit sink. | Test per event type. Sink configured in platform-owned Terraform. |
| **C-08** | Secrets are referenced by name and resolved from Secret Manager at runtime. Never in source, images, Terraform variables, logs or committed `.env`. | Secret scanning in CI; a repository test forbidding credential-shaped literals. |
| **C-09** | Data classification and retention are declared in configuration, and retention is enforced. | Test: expired value removed by the retention path. |

### Platform and supply chain

| ID | Requirement | Verification |
|---|---|---|
| **C-10** | Network exposure is minimal: internal ingress by default; public ingress requires an approved exception. | Terraform policy scan (`checkov`/`tfsec`). |
| **C-11** | One service account per component, least privilege, no primitive roles. Memory Bank access is granted to the Memory Manager service account only — never to an agent — constrained by IAM Conditions on scope where supported. | Terraform policy scan; a test asserting no primitive role in any module. |
| **C-12** | Containers run as a non-root user, from a pinned base image, with no build secrets in any layer. | Container scan in CI; Dockerfile lint. |
| **C-13** | Dependencies are pinned, lockfiles committed, and scanned for known vulnerabilities on every PR. | Dependency scan job. |
| **C-14** | Published release artifacts carry provenance attestation and checksums. | `actions/attest-build-provenance` and `SHA256SUMS` in `.github/workflows/release.yml`; verified by re-computing the checksums from the published tarball. |
| **C-15** | Infrastructure is reviewed as code and policy-scanned. No manual console changes to platform-owned resources. | `terraform validate` + policy scan in CI. |

### Isolation, reliability and cost

| ID | Requirement | Verification |
|---|---|---|
| **C-16** | Domains are isolated. In a shared project, isolation is by per-domain service account and IAM Conditions on scope. One domain cannot read or write another's memory. | Test: two domains, neither can access the other's scope. IAM Conditions test against a live bank. |
| **C-17** | Transient failures and provider throttling are handled with bounded retry, exponential backoff, dead-lettering and idempotency. Retry must not amplify load against a rate-limited dependency. | Test: injected 429 → parked, not hot-looped. Test: duplicate delivery → single effect. |
| **C-18** | Required telemetry exists: tool invocations, queue depth, retry count, dead-letter depth, provider 429s, latency percentiles, per-domain quota attribution. | Test asserting metric emission; dashboard reference in the runbook. |
| **C-19** | Shared-quota contention between domains is bounded by per-domain budgets, and cost is attributable per domain. | Test: a domain exceeding its budget is throttled locally, not globally. |

## Threats this catalogue is answering

- An agent reading or writing another customer's or another domain's memory.
- Sensitive or health-related content persisted without classification or consent.
- Memory content leaking through logs, traces or error messages — the most common real-world leak.
- A compromised agent identity escalating through over-broad IAM.
- One domain exhausting shared quota and causing an outage for another.
- A supply-chain compromise reaching a domain through a published pattern release.
