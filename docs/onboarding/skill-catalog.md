# Skill catalog

Thirteen project skills covering the SDLC and the pattern lifecycle. Each lives in
`.claude/skills/<name>/SKILL.md`, is version-controlled, and is reviewed through pull requests like
any other code.

Invoke with `/<skill-name>` in Claude Code, or describe the task and let the skill trigger.

## Lifecycle skills

| Skill | Stage | Use when | Produces | Stops at |
|---|---|---|---|---|
| [`sdlc-status`](../../.claude/skills/sdlc-status/SKILL.md) | any | "where are we", start of session | A status report | — (read-only) |
| [`design-start-feature`](../../.claude/skills/design-start-feature/SKILL.md) | 1 Intent | Starting any new work | `intent.md` (or `change.md`) | **Gate A** |
| [`design-session`](../../.claude/skills/design-session/SKILL.md) | 2 Design | Intent approved | `design.md`, diagrams, proposed ADRs | **Gate B** |
| [`design-check-controls`](../../.claude/skills/design-check-controls/SKILL.md) | 3 Controls | Design approved; also `--recheck` after implementation | `controls-check.md` | **Gate C** |
| [`design-plan-implementation`](../../.claude/skills/design-plan-implementation/SKILL.md) | 4 Build | Controls approved | `tasks.md` | **Gate D** |
| [`design-record-decision`](../../.claude/skills/design-record-decision/SKILL.md) | 4 Build | A decision has been approved | `ADR-NNNN-*.md` | — |
| [`design-open-pr`](../../.claude/skills/design-open-pr/SKILL.md) | 5 Review | Implementation complete | PR summary, review report | **Gate E** |
| [`design-close-feature`](../../.claude/skills/design-close-feature/SKILL.md) | 6 Close | Review approved | `closeout.md`, doc updates | **Gate F** |

## Pattern lifecycle skills

| Skill | Use when | Produces | Stops at |
|---|---|---|---|
| [`pattern-create`](../../.claude/skills/pattern-create/SKILL.md) | A new reusable capability needs its own pattern | Pattern skeleton + design folder | — |
| [`pattern-validate`](../../.claude/skills/pattern-validate/SKILL.md) | Before release, or reviewing a pattern change | Validation report | — (read-only) |
| [`pattern-publish`](../../.claude/skills/pattern-publish/SKILL.md) | Preparing a release | Readiness checklist + commands | **Gate F — never publishes** |
| [`domain-onboard`](../../.claude/skills/domain-onboard/SKILL.md) | A domain adopts a pattern | A domain-owned project scaffold | — (never deploys) |
| [`pattern-upgrade`](../../.claude/skills/pattern-upgrade/SKILL.md) | Moving between pattern versions | A migration plan | — (never upgrades) |

For a narrated pass through all of this with a real feature, see the
[worked example](worked-example.md).

## A typical full-track feature

```
/sdlc-status                      where are we?
/design-start-feature             → intent.md            → GATE A (human)
                                    → branch + draft PR
/design-session                   → design.md            → GATE B (human)
/design-check-controls            → controls-check.md    → GATE C (security)
/design-plan-implementation       → tasks.md             → GATE D (human)
   …implement task by task, tests alongside code…
/design-check-controls --recheck  if the posture changed
/design-open-pr                   → PR ready             → GATE E (human review)
/design-close-feature             → closeout.md          → GATE F (merge, authorized)
```

## A light-track change

```
/design-start-feature   → change.md (Gate A inline in the PR)
   …fix, with a test…
/design-open-pr         → GATE E → GATE F
```

Escalation to the full track is automatic and one-way if the change turns out to touch a contract, a
control or the architecture.

## What no skill will do

- Approve a design, a controls assessment, or its own work
- Write implementation code before Gates B and D
- Merge a pull request
- Publish a release or push an image
- Run `terraform apply`
- Report an unexecuted or unavailable check as passing

These are not politeness. Several are denied outright in `.claude/settings.json`, and the ones that
matter most are backed by CI and branch protection — see
[repository-administration.md](../operations/repository-administration.md).

## Hooks

Two, both small, both advisory:

| Hook | Trigger | Behaviour |
|---|---|---|
| `warn_unapproved_implementation.py` | `Write`/`Edit` on `patterns/*/src/**` | Warns when no approved design exists. **Always exits 0 — never blocks.** |
| Deny list in `settings.json` | `terraform apply`, `gh pr merge`, `gh release create`, `git push --force`, `docker push`, `gcloud run deploy` | Blocked |

**Hooks are ergonomics, not enforcement.** A hook protects against accident, not intent. Mandatory
enforcement is CI plus branch protection plus CODEOWNERS.

## Maintaining skills

Skills are project assets. Changes go through the SDLC like anything else:

- One responsibility per skill. A skill needing "and" to describe it should be two.
- Document purpose, when to use, inputs, prerequisites, steps, outputs, validation rules, approval
  requirements, and failure/recovery behaviour.
- Progressive disclosure: `SKILL.md` holds the procedure; detail goes in sibling files loaded on
  demand.
- No machine-specific assumptions — a skill must work for every developer on the team.
