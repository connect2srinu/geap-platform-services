# SDLC gates

Six stages, six gates. A gate is a **human decision**, recorded in the design folder. Claude prepares
the artifact and stops; a person approves it.

```
Intent ──A──► Design ──B──► Controls ──C──► Build (plan ──D──► implement) ──► Review ──E──► Close ──F──► merge
```

| Gate | Approves | Approver | Recorded as |
|---|---|---|---|
| **A** | `intent.md` — scope, non-goals, acceptance criteria | Requester + platform lead | `Status: Approved` + approver + date in the artifact's front matter |
| **B** | `design.md` + diagrams + proposed ADRs | Platform architect | same |
| **C** | `controls-check.md` — every applicable control has evidence or an approved exception | Security reviewer | same |
| **D** | `tasks.md` — the implementation plan | Platform lead | same |
| **E** | The pull request | ≥1 human per CODEOWNERS | **GitHub review approval** |
| **F** | Merge; separately, publish or deploy | Repository admin | Explicit instruction from the user |

**Gate A is also the branch gate.** The feature branch and draft PR are created *after* intent
approval, never before. No remote branch, no PR, without explicit approval.

## What Claude may never do

- Mark its own artifact approved, or infer approval from silence.
- Write application code before Gates B and D.
- Merge, publish, release, push an image, or `terraform apply`.
- Downgrade a full-track change to the light track.

## Two tracks

A change takes the **light track** only if *every* statement is true:

- no change to any API contract, tool API, or `pattern.yaml`;
- no change to a security control or the security posture;
- no new managed service, dependency, or extension point;
- no architectural change.

| | Full track | Light track | Release track |
|---|---|---|---|
| **Typical** | New pattern · contract change · new managed service · security-posture change · major architecture change · new extension point | Defect fix · non-breaking dependency upgrade · docs · test-only · example or config fix | Publishing a version of an already-merged pattern |
| **Artifacts** | `intent.md`, `design.md`, `controls-check.md`, `tasks.md`, ADR(s), `closeout.md` | one `change.md` (intent + approach + verification + controls delta) | `docs/releases/<pattern>-v<version>.md` — the readiness checklist from `pattern-publish` |
| **Gates** | A, B, C, D, E, F | A (inline in the PR description), E, F | E, F only |

### Why the release track exists

A release necessarily edits `pattern.yaml` (the version bump), which the light-track test excludes.
Without a third track, every version bump would require a full intent → design → controls → task
cycle for a metadata change. That is overhead nobody would actually pay, and a rule people quietly
ignore is worse than no rule.

**A release commit changes metadata and notes only:**

| File | Change |
|---|---|
| `patterns/<name>/pattern.yaml` | `metadata.version`; possibly `metadata.status`; `spec.upgrade.from`; `spec.compatibility` |
| `patterns/<name>/CHANGELOG.md` | `[Unreleased]` → `[<version>] — <date>` |
| `patterns/<name>/docs/upgrade.md` | Migration guidance from the prior version |
| `README.md` | The patterns table |
| `docs/releases/<pattern>-v<version>.md` | Release notes + readiness checklist |

**It must not touch `src/`, `contracts/`, `tests/` or `conformance/`.** Those are frozen by the
feature work that preceded the release. A "release" that changes them is a feature in disguise and
belongs on the full track. `scripts/check_release_commit.py` enforces this, and
`.github/workflows/release.yml` runs it.

The release track does **not** get a `design/NNN-*` folder. Its artifact lives in `docs/releases/`.

**Escalation is one-way and automatic.** If a light-track change turns out to touch a contract, a
control or the architecture: stop, say so, and re-enter the full track. Going the other way requires
human approval.

**Security remediation** is always full-track on design and controls. The timeline may compress;
Gate C never disappears.

## Design folder naming

`design/NNN-slug/` where `NNN` is the next free three-digit integer and `slug` is kebab-case.
The branch is named identically: `design/NNN-slug`. One folder, one branch, one PR, one owner.

`design/000-platform-foundation/` is reserved for this repository's own foundation.
