# Repository administration — the settings that are the real approval gates

Everything in this document must be configured **by hand** by a repository administrator in GitHub.
None of it can be committed to the repository.

> **This is the honest part of the enforcement story.** CI validates that artifacts exist and are
> well-formed. `CODEOWNERS` assigns reviewers. `PULL_REQUEST_TEMPLATE.md` prompts for checkboxes.
> **None of those require anything.** Without the settings below, a pull request can be merged with no
> review, no design and no passing checks — and the repository will look fully governed while that
> happens.

## 0. Two profiles — and which one this repository runs

This repository (`connect2srinu/geap-platform-services`, public, personal account) has **one
maintainer**. GitHub does not let a pull request's author approve it. With one maintainer, a
required approval can't be given by anyone, so it can only be met by turning enforcement off for
admins, which makes the protection theatrical.

| | **Single-maintainer profile** (this repository) | **Organization profile** (the office organization) |
|---|---|---|
| Required approvals | **0** | **≥ 1** |
| Require review from Code Owners | **off** | **on**, with real teams (§7) |
| Required status checks | **on** (§2) | **on** (§2) |
| Require conversation resolution | **on** | **on** |
| Allow force pushes / deletions on `main` | **off** / **off** | **off** / **off** |
| Include administrators (`enforce_admins`) | **on** | **on** |

**Gate E is not enforced in this repository.** No second human reviews a pull request before it
merges. That is a fact about the repository, not a temporary state, and nothing here should imply
otherwise. The mitigation is **CI plus the design-artifact validator**, not review:

- every required status check must pass, and an administrator cannot bypass them
  (`enforce_admins: true`);
- `scripts/validate_design_artifacts.py` fails an artifact approved out of order, approved by an AI
  agent, or approved with an undisclosed control gap;
- gates A to D are still recorded in the artifacts by a human, and gate F is still an explicit
  human merge.

What this does **not** mitigate: no second person reads the design, the code or the controls
assessment before merge. A defect the maintainer misses, which CI does not test, ships.

**Never set `enforce_admins: false` to get around the missing reviewer.** That turns every other
setting into a suggestion for the one person able to merge.

The organization profile is the one this document describes from §1 onward, and the one adopting
organizations should run. Gate E actually works there.

## 1. Branch protection / ruleset on `main` (organization profile)

| Setting | Value |
|---|---|
| Require a pull request before merging | **on** |
| Required approvals | **≥ 1** |
| Dismiss stale approvals on new commits | **on** |
| Require review from Code Owners | **on** |
| Require status checks to pass | **on** (see §2) |
| Require branches to be up to date | on |
| Require conversation resolution | on |
| Allow force pushes | **off** |
| Allow deletions | **off** |
| Include administrators | **on** — otherwise the gate is advisory for the people most able to bypass it |

## 2. Required status checks

Add these once each has run at least once (GitHub cannot require a check it has never seen):

- `Validate SDLC design artifacts`
- `Manifest and boundary`
- `Contract specifications`
- `Lint and format`
- `Type check`
- `Unit tests`
- `Conformance suites`
- `Dependency vulnerabilities`
- `Secret scanning`
- `Infrastructure policy scan`
- `Format and validate` (Terraform)

## 3. Security features

- **Secret scanning** — on
- **Push protection** — on
- **Dependabot alerts** — on
- **Dependabot security updates** — on
- Private vulnerability reporting — on

## 4. Environments

Create a `release` environment with **required reviewers**. `.github/workflows/release.yml` is manually
dispatched and references it. The `environment:` key in a workflow file names a gate; it does not
create or enforce one.

Domain repositories need the same for their `production` environment.

## 5. Tag protection

Protect `*/v*` so that only administrators can create pattern release tags. A published version is a
contract with every adopting domain and cannot be withdrawn once consumed.

## 6. Actions permissions

| Setting | Value |
|---|---|
| Default `GITHUB_TOKEN` permissions | **Read repository contents** |
| Allow GitHub Actions to create and approve pull requests | **off** |
| Allowed actions | Selected — the actions pinned in `.github/workflows/` |
| OIDC | enabled, for provenance attestation |

## 7. CODEOWNERS teams

**In this repository**, `.github/CODEOWNERS` names `@connect2srinu`, the one maintainer, on every
path. It assigns nothing that review could enforce (§0), but it matches a real account, and
`codeowners/errors` returns none.

**In the organization**, replace `@connect2srinu` with real GitHub teams.
**A CODEOWNERS file referencing non-existent teams silently matches nobody** — which looks identical
to a configured repository until the first unreviewed merge.

Teams referenced: `agent-platform`, `platform-architects`, `platform-leads`, `security-reviewers`.

## Verification

After configuring, verify rather than assume:

```bash
gh api repos/{owner}/{repo}/branches/main/protection
```

```bash
gh api repos/{owner}/{repo}/codeowners/errors
```

The second one returns CODEOWNERS entries that match no team — run it after step 7.

## What still cannot be enforced

Even with all of the above:

- That a reviewer actually **read** the design rather than clicking approve.
- That an adopting domain runs the conformance suite in its own CI.
- That an adopting domain has not forked the pattern and removed the checks.
- That a domain's own code does not log memory content.

For adopting domains, the only control that survives a fork is the **platform-owned Terraform** —
the memory bank, its IAM binding, the audit sink and quota alerting, provisioned in the
platform-owned project. See [`standards/pattern-contract.md`](../../standards/pattern-contract.md).
