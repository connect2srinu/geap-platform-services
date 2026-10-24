# Repository administration

The settings a workflow **names** but cannot create. `release.yml` points here because its
`environment: release` key names a gate; it does not configure one, and a gate that nobody
configured is a comment.

Everything below is set in GitHub by someone with admin on the repository. Nothing in this
repository can set it, and nothing in CI will fail if it is missing — which is exactly why it is
written down.

## Current state

Checked and changed 2026-10-24 with `gh api`. Re-check rather than trust this table; it ages.

| Setting | State | Matters because |
|---|---|---|
| `release` environment with required reviewers | **configured** — one reviewer, `connect2srinu` | `release.yml` calls this the second human gate before publishing |
| Required status checks on `main` | **10 checks**, `Domain rehearsal` now among them | the rehearsal exists to stop the onboarding path rotting; if it is not required, it can fail and the pull request still merges |
| Secret scanning | **enabled** | `security.yml` says in a comment that an administrator enables it and that the gitleaks job does not replace it |
| Push protection | **enabled** | stops a credential reaching the remote at all, rather than reporting it afterwards |
| Dependabot security updates | **enabled** | the weekly `Dependency vulnerabilities` job reports; Dependabot is what opens the fix |
| Non-provider patterns, validity checks | **disabled** — the API accepted the change twice and still reports disabled | they need GitHub Advanced Security, which this repository does not have |
| Repository visibility | **public** | the settings above are free for a public repository, and a leaked credential in a public repository is leaked the moment it is pushed |

**The one reviewer on the `release` environment is also the person who tags and dispatches.**
That makes the gate a deliberate pause, not an independent review. Add a second reviewer, and
turn on *Prevent self-review*, as soon as there is somebody to add — until then, enabling it
would lock the only reviewer out of their own release.

## 1. The `release` environment

`release.yml`'s `publish` job declares `environment: release`. GitHub will happily run a job
naming an environment that has no protection rules — it simply does not pause. Required
reviewers are what turn the key into a gate.

```bash
gh api -X PUT repos/:owner/:repo/environments/release \
  -f 'reviewers[][type]=User' -F 'reviewers[][id]=<numeric-user-id>' \
  -F 'deployment_branch_policy=null'
```

A user's numeric id comes from `gh api users/<login> --jq .id`. The same thing is done in
Settings → Environments → New environment → Required reviewers, which is easier to get right.

Reviewers should not be only the person who dispatches the workflow. One person tagging,
dispatching and approving is one gate wearing three hats.

## 2. Required status checks on `main`

The ten required today:

```
Lint and format · Type check · Unit tests · Domain rehearsal · Manifest and boundary
Contract specifications · Dependency vulnerabilities · Secret scanning
Infrastructure policy scan · Format and validate
```

`Domain rehearsal` was added on 2026-10-24. It is the job that builds a domain project from the
template, vendors the pattern, boots it and runs the conformance suite — the check that exists
because seven onboarding defects reached `main` together once, and for its first months it was
not required, so it could fail without blocking a merge.

To add another, without rewriting the rest of the protection rule:

```bash
echo '{"contexts":["<job name>"]}' | gh api -X POST \
  repos/:owner/:repo/branches/main/protection/required_status_checks/contexts --input -
```

A check only becomes selectable in the UI after it has reported on at least one pull request.

## 3. Secret scanning and push protection

Settings → Code security and analysis → enable **Secret scanning** and **Push protection**.

The repository also runs gitleaks in `security.yml`, which scans **commit history** rather than
the working tree — that is why `.gitleaksignore` carries per-finding fingerprints of the form
`<commit>:<path>:<rule>:<line>` rather than path or rule exclusions. A fingerprint silences one
reviewed finding at one commit; a path exclusion would silence everything that file ever carries.

GitHub's own scanning is not a duplicate of that job: it covers provider patterns gitleaks does
not, and push protection refuses the push rather than reporting it after the fact.

## 4. Dependabot

Settings → Code security and analysis → **Dependabot security updates**.

The weekly job in `security.yml` tells you a dependency is vulnerable. Dependabot is what opens
the pull request that fixes it. Without it, the weekly report is something somebody has to
remember to read.

## 5. What needs no configuration

The `publish` job requests `id-token: write` and `attestations: write` for provenance
attestation. Those are declared in the workflow and need no repository setting. The attestation
is what lets an adopting domain verify that a release artifact was built by this workflow from
this tag, rather than uploaded by hand.
