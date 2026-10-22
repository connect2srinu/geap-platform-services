---
artifact: change
feature: 007-single-maintainer-governance
track: light
status: draft
---

# Change — State honestly that Gate E is unenforced here, and make CODEOWNERS match a real account

> **Light track.** Use only when *every* statement below is true. If any becomes false during the
> work, stop and escalate to the full track — this is one-way and automatic.
>
> - [x] No change to any API contract, tool API, or `pattern.yaml`
> - [x] No change to a security control or the security posture
> - [x] No new managed service, dependency, or extension point
> - [x] No architectural change

## What and why

- **Gate E can't be met here.** It requires a GitHub review approval, and GitHub does not let a
  pull request's author approve it. This repository has one maintainer, so a required approval can
  only be satisfied by switching enforcement off for admins. That would make every other setting
  advisory.
- **`main` has no protection at all today.** **VERIFIED**:
  `gh api repos/connect2srinu/geap-platform-services/branches/main/protection` → `404 Branch not
  protected`.
- **`.github/CODEOWNERS` matches nobody.** **VERIFIED**: `codeowners/errors` returns 14 errors,
  every one `Invalid owner` on an `@<org>/…` placeholder.

| | |
|---|---|
| Classification | `documentation` + config fix |
| Patterns touched | none |

## Approach

- **`docs/operations/repository-administration.md`** gets a new §0, "Two profiles". The
  single-maintainer profile, which this repository runs, has:
  - required status checks;
  - conversation resolution;
  - no force-push and no deletion on `main`;
  - `enforce_admins: true`;
  - **0** required approvals, and no code-owner review.

  It says plainly that **Gate E is not enforced here**, that the mitigation is CI plus the
  design-artifact validator, not review, and what that leaves unmitigated. It forbids
  `enforce_admins: false` as a workaround. The organization profile, with ≥ 1 approval and real
  CODEOWNERS teams, is the existing §1 onward. §7 is updated to match.
- **`.github/CODEOWNERS`**: every path names `@connect2srinu`, the real maintainer. Each path's
  intended team is kept as a `# team:` comment, so an organization can swap them back in. The header
  says why. The file is kept rather than deleted, because its path-to-team map is the design for
  the organization profile.

**Branch protection itself is a repository setting, not a commit.** It is applied separately with
`gh api`, at the time the requester chooses (see the sequencing note), and verified with
`gh api …/branches/main/protection`.

### Sequencing note — the required-check set must not deadlock the open PRs

`enforce_admins: true` means nobody can merge past a red required check, including the
maintainer. As of 2026-10-21:

- **#3 (003)** fails only `Infrastructure policy scan`, which only 005 fixes.
- **#4 (005)** fails `Lint and format`, `Type check` and `Secret scanning`, which only 003 fixes.

If all 11 checks are required before either merges, neither can merge. The order that avoids this:

1. Apply protection without `Infrastructure policy scan`.
2. Merge 003, then rebase and merge 005.
3. Add `Infrastructure policy scan` to the required set.
4. Merge 002 and 004.

The alternative is to apply protection only after both 003 and 005 have merged.

## Controls delta

| Control | Effect | Status |
|---|---|---|
| — | Repository governance documentation and review assignment. No control in `standards/security.md` changes. Gate E's non-enforcement is a property of the repository, now disclosed rather than implied | Unchanged posture, disclosed |

## Verification

| Check | Command | Result |
|---|---|---|
| No placeholders left | `grep -c '<org>' .github/CODEOWNERS` | **passed** — `0` |
| CODEOWNERS parses on GitHub | `gh api 'repos/connect2srinu/geap-platform-services/codeowners/errors?ref=design/007-single-maintainer-governance'` | **not yet run** — needs the push |
| Design artifacts | `make validate-design` | see the commit's run |
| Protection applied as specified | `gh api …/branches/main/protection` | **not yet run** — applied separately |

## Approval

**Gate A** — given in session on 2026-10-21 by the requester (connect2srinu), as an explicit
decision: "here is the decision … Record in docs/operations/repository-administration.md … fix
.github/CODEOWNERS in the same pass". Restate this in the PR description. `status` stays `draft`
here: only a human sets `approved`.

Gate A inline (in the PR description) and Gate E (human review). Gate F for merge.
