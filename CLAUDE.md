# GEAP Platform Services — operating rules for Claude Code

This repository **publishes reusable patterns**. It is not a deployed service. The platform team does
not build or operate domain container images or runtimes. Domain teams adopt a versioned pattern, own
and customize the code, and deploy it independently to Cloud Run in the platform-owned GCP project.

Never hardcode a business domain's rules (Customer, Inventory, Manufacturing, Supply Chain) into
reusable pattern code. Domain behaviour arrives through configuration and declared extension points.

## Before you change anything

1. **Read the standards that apply.** Load only what the task touches:

   | Task touches | Read |
   |---|---|
   | Architecture, layering, diagrams | `standards/architecture.md` |
   | Any code | `standards/coding.md` |
   | Auth, data classification, secrets, IAM | `standards/security.md` |
   | Tests | `standards/testing.md` |
   | Logs, metrics, traces, audit | `standards/observability.md` |
   | Endpoints, contracts, versioning | `standards/api-design.md` |
   | Config, extension points | `standards/configuration.md` |
   | A pattern's manifest or contract | `standards/pattern-contract.md` |
   | Versions, changelogs, publishing | `standards/release-management.md` |

2. **Find the design folder.** Work belongs to one: `design/NNN-slug/`. If none applies, use the
   `design-start-feature` skill. Do not invent a folder by hand.
3. **Determine the stage and which gates are open.** Use the `sdlc-status` skill.
4. **Never bypass a gate.** → @.claude/rules/sdlc-gates.md
5. **Do not implement before Gate B (design) and Gate D (task plan) are approved.** Writing
   application code without an approved design is the single most damaging thing you can do here.

## While you work

6. **Follow the approved design and `tasks.md`.** One coherent task at a time. If implementation
   reveals a material architecture change, stop and return to design review — do not improvise.
7. **Preserve the platform/domain boundary.** → @.claude/rules/platform-vs-domain.md
8. **Security and privacy are not negotiable.** Mandatory controls cannot be disabled by domain
   configuration. Memory content and PII must never reach logs or traces.
   → @.claude/rules/security-baseline.md
9. **Tests and documentation change with the code**, in the same commit, not afterwards.
10. **Record approved architecture decisions** with `design-record-decision`. Only approved ones, and
    not every minor implementation detail.
11. **Do not modify unrelated components.** No opportunistic refactoring. If you spot something,
    report it instead of fixing it.
12. **Preserve existing contracts** unless a change is approved. The tool API is identical across
    domains by design — changing it breaks every agent team.

## Before you report

13. **Run the available checks:** `make verify`, or the specific target for what you changed.
14. **Never claim a test, scan, build or deployment succeeded without output proving it.**
    → @.claude/rules/evidence-and-claims.md
15. **Report passed, failed, skipped and unavailable separately.** "Unavailable" means the tool is not
    installed or could not run — say so plainly rather than implying a pass.

## Approvals and dangerous actions

16. **Ask for explicit confirmation before:** deleting anything, force-pushing, merging, publishing a
    release, pushing an image, or running `terraform apply`. Skills must never do these silently.
17. This repository **applies no infrastructure**. Terraform here is reference material, validated
    with `init -backend=false` and `validate` only.

## Prefer the project skills

18. Thirteen skills cover the lifecycle. Use them instead of improvising a process.
    → [docs/onboarding/skill-catalog.md](docs/onboarding/skill-catalog.md)
