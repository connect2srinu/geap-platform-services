# Security — eight non-negotiables

Every rule below has a **required test**. A rule without a passing test is not satisfied, whatever a
document says. These cannot be switched off by domain configuration; a domain may make them stricter.

| # | Rule | Required test |
|---|---|---|
| **S-1** | Every caller is authenticated. Development shortcuts are **refused** outside a local environment, not merely defaulted off. | Unauthenticated request to 401. Dev shortcut with production-like config to startup refusal. |
| **S-2** | Authorization denies by default. Unknown caller, unknown topic, unmapped scope, or a classifier error all deny. | One test per deny path, each failing if the check is removed. |
| **S-3** | Data is classified before it is persisted. Anything unclassifiable is refused, not stored. | Unclassifiable value refused. Default classifier denies everything. |
| **S-4** | Memory content, PII, secrets and auth headers never appear in logs, traces or error responses. | A test asserting the prohibited-field list against emitted records. |
| **S-5** | Secrets are referenced by name and resolved from Secret Manager at runtime. Never in source, images, Terraform vars or logs. | Secret scanning in CI, plus a test forbidding credential-shaped literals. |
| **S-6** | One service account per component, least privilege, **no primitive roles** (owner, editor, viewer). Memory Bank access goes to the service, never to an agent. | Terraform policy scan; a test asserting no primitive role in any module. |
| **S-7** | Every write, denial and deletion emits an audit event with a correlation ID. | One test per event type. |
| **S-8** | One domain cannot read or write another domain's scope. | Two domains; neither can reach the other's scope. |

## How to use this

In `design.md`, list which rules the change touches and which test covers each. One line per rule.
That is the whole security review — there is no separate assessment document.

If a rule genuinely cannot be met, write it in `design.md` under **Risks** with: what is exposed, what
compensates for it, and an expiry date. Get a second person to agree. Do not hide it.

## Fail closed

Every authorization, classification and validation decision denies by default. An extension that
raises is a denial plus a metric, never a bypass.

## What the platform can and cannot enforce

Domain teams own and customize the code. The conformance suite and boundary checks run in **their**
CI, which we cannot observe — a fork can remove them.

Only **platform-owned Terraform** survives a fork: the memory bank, its IAM binding, the audit sink
and quota alerting, provisioned in the platform project.

So: we control **what a domain's service account may do to a bank**. We do not control what their
code does before it gets there. Do not claim more than that.
