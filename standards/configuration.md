# Configuration standards

## Configuration over modification

A new domain must be supportable **without changing pattern source code**. If supporting a domain
requires editing `src/`, either the configuration model or an extension point is missing — fix that,
not the domain.

## Precedence

```
schema defaults  →  configuration file  →  environment variables  →  secret references
```

Later wins. Everything is validated against the pattern's configuration schema **at startup**, and the
service **refuses to start** on invalid configuration. Never degrade to a default when configuration
is wrong — a service running on silently-defaulted security configuration is worse than one that did
not start.

## Schema

Every pattern has `config/config.schema.json` (JSON Schema 2020-12) with:

- every key documented with a description;
- types, enums, bounds;
- `required` for anything without a safe default;
- **no default that weakens a security control** — security defaults fail closed;
- a safe example in `config/example.*.yaml` using neutral placeholders only.

## What a domain may set

Roles and role-to-caller bindings · sensitive and restricted attribute lists · category vocabulary ·
retention periods (within platform bounds) · per-caller rate limits · its quota budget (within the
platform allocation) · prompts and extraction instructions · extension-point implementations ·
resource sizing and scaling · log level.

## What a domain may not set

The tool API contract · mandatory controls (`standards/security.md`) · the audit event schema or
sink · the prohibited-log-field list · required metrics · the idempotency contract · platform-owned
Memory Bank IAM.

Configuration keys for these do not exist. Absence is the enforcement — a key that could switch off a
control is a design defect, not a configuration option.

## Extension points

Declared in `pattern.yaml` under `spec.extensionPoints`, each with:

| Field | Meaning |
|---|---|
| `id` | Stable identifier |
| `interface` | The protocol or abstract base the implementation satisfies |
| `required` | Whether a domain must provide one |
| `default` | The platform's default implementation |

Rules:

- Every extension point has a default. **Security-relevant defaults fail closed** — the PII classifier
  defaults to deny-all, not allow-all.
- An extension may **refine** a decision, never **override** a mandatory control. An extension that
  returns "allow" cannot overturn a platform denial.
- Extension failures are contained: an extension that raises is a denial plus an
  `extension_errors` metric, never a bypass.
- Extensions are loaded from a configured module path, validated against the interface at startup.
- Extension code lives in the **domain's** project. `extensions/` in this repository holds the
  interfaces and the defaults only.

## Secrets

Referenced by name, never by value:

```yaml
memory_bank:
  credentials: { secret: projects/<project-id>/secrets/<name>/versions/latest }
```

Resolved at runtime from Secret Manager. `pattern.yaml` lists required secret **names and purposes**.
`.env.example` carries names with empty values. A committed secret value is a build failure.

## Environments

The same artifact runs in every environment; only configuration differs. No environment name in a
conditional in `src/`. Development conveniences — header-based identity, mock providers — are refused
outside a local environment rather than defaulted off, and that refusal is tested.
