# Demo — a feature from idea to a client using it

The whole lifecycle in one page, in the order it happens: **build** a feature through its gates,
**release** it, **test** it as a client, then **adopt** it as a domain. You can run it in front of
people in about 45 minutes.

Everything typed into `claude` is shown as `>`; everything else is a shell command. Where a step
says **YOU**, no tool does it for you. That is the point of the gate.

```
 BUILD                                                    RELEASE           CLIENT
 intent.md ─▶ YOU approve ─▶ design.md ─▶ YOU approve ─▶  tag + workflow ─▶ test locally
                                          │                 YOU approve      conformance
                                          ▼                 the release      adopt a version
                              branch ─▶ implement ─▶ PR ─▶ CI ─▶ YOU approve ─▶ merge
```

**First time on this machine?** Do [getting-started.md](getting-started.md) first. It ends with
`make verify` passing.

## The gates

| # | Gate | Who | How it is recorded | What enforces it |
|---|---|---|---|---|
| 1 | `intent.md` approved | Requester / platform lead | `status: approved`, `approved_by`, `approved_date` in its front matter, **edited by hand** | `/feature-start` will not write a design before it; the validator prints the gate state |
| 2 | `design.md` approved | Platform architect | the same | No implementation code before it (CLAUDE.md); the validator prints `both approved - implementation may proceed` |
| 3 | Pull request approved | ≥1 reviewer | GitHub review | Branch protection: 11 required checks, up to date with `main`, conversations resolved |
| 4 | Merge | Repository admin | the merge itself | Never done by Claude Code (`gh pr merge` is denied in `.claude/settings.json`) |
| 5 | Release | Maintainer, then `release` environment reviewers | tag + workflow dispatch | `release.yml` checks; required reviewers on the `release` environment |

On a single-maintainer repository, GitHub will not let you approve your own PR. Gate 3 is then
unenforced, and the repository says so rather than pretending otherwise (see
[developer-guide.md](developer-guide.md#repository-settings-an-admin-must-configure-by-hand)).

---

## 1. Build a feature (platform team)

### 1.1 Start it

```bash
claude
```

```
> /feature-start
```

Describe what you want. It asks a few questions, writes **`design/NNN-slug/intent.md`** (half a
page: objective, scope, non-goals, how we will know it works) and **stops**.

> Point out to the audience: it stopped. It will not write a design, let alone code, until a person
> approves the intent.

### 1.2 **YOU** approve the intent

Read it. Then edit the front matter by hand:

```yaml
status: approved
approved_by: <your name>
approved_date: 2026-10-23
```

Do it by hand, deliberately. A scripted approval is not an approval: the step's whole value is that
a person read the document.

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

It prints the gate state: `awaiting approval of intent.md`, then `intent approved - design.md not
written yet`.

### 1.3 Design

```
> /feature-start
```

Run it again: the same skill handles both steps. It checks that the intent is approved first; if it
isn't, it stops and says so. Before designing, it **verifies provider assumptions** by reading the
installed SDK rather than the documentation, and writes a throwaway probe in
`design/NNN-slug/spike/` if something needs a live answer. In this repository that caught the
five-fact request limit and a retention model the provider cannot support, before any code existed.

Then it writes **`design/NNN-slug/design.md`** (two to three pages: approach, contract,
configuration, the security rules it touches with the test for each, risks, and a task checklist)
and **stops** again.

### 1.4 **YOU** approve the design

Same edit. Then:

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

```
design/NNN-slug: both approved - implementation may proceed
```

**That line is the demo's punchline.** Nothing before it could write product code.

### 1.5 Branch and implement

```bash
git checkout -b design/NNN-slug && git push -u origin design/NNN-slug
```

```bash
gh pr create --draft --title "NNN: <title>" --body "Design: design/NNN-slug/"
```

```
> implement the first task in design/NNN-slug/design.md
```

Tests ship in the same commit. Repeat per checklist item, committing as you go.

```bash
make verify
```

One feature, one branch, one PR. Fix incidental defects in the same branch.

### 1.6 Review and merge

```
> /feature-review
```

It compares the diff with the design, runs the checks, and reports each as **passed / failed /
skipped / unavailable**. Unavailable is not a pass. It drafts the PR description and leaves the
approval to you.

```bash
gh pr ready && gh pr checks --watch
```

**YOU** approve the PR in GitHub, then:

```bash
gh pr merge --squash --delete-branch
```

---

## 2. Release a version (platform team)

A release publishes one pattern at one version, as a GitHub Release that domains download. **It
cannot be withdrawn once a domain has consumed it**, which is why there are two human steps in
front of it and no automatic trigger.

### 2.1 Before the first release: admin setup

Do this once, in GitHub settings. It is not in the repository and does not travel with a clone.

- Create a **`release` environment with required reviewers**. Without it, GitHub creates the
  environment automatically on first use, **with no reviewers**, and the second human gate does
  not exist. *(Not configured as of 2026-10-23.)*
- Add tag protection for `*/v*`, so only maintainers can create release tags.

### 2.2 Prepare

```bash
git checkout main && git pull
```

```
> /pattern-release
```

It validates readiness, checks the version bump against the **real contract diff** (a breaking
change in a patch release is the thing it exists to stop), and produces a checklist plus the exact
commands. **It publishes nothing.**

The release commit is a normal PR that changes metadata and notes only:

| File | Change |
|---|---|
| `patterns/<name>/pattern.yaml` | `metadata.version`; `metadata.status` from `proposed` to `alpha`, `beta` or `certified`. The workflow refuses `proposed` |
| `patterns/<name>/CHANGELOG.md` | `## [Unreleased]` becomes `## [<version>] — <date>`. The workflow requires that heading |
| `docs/releases/<name>-v<version>.md` | Release notes. The workflow requires the file, and requires it to state whether **live verification** was performed |

PR, review, merge.

### 2.3 Tag and publish

```bash
git tag memory-manager/v0.1.0 && git push origin memory-manager/v0.1.0
```

Dry run first. It builds from the **tag**, never from a branch, checks the manifest version against
the tag, runs the manifest, boundary and conformance checks, builds the tarball, writes
`SHA256SUMS` and attests provenance, all without creating a Release:

```bash
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=true
```

```bash
gh run watch
```

The publish job waits for a `release` environment reviewer, in the dry run and the real run alike:
**YOU** approve it on the run's page. Check the dry run's artifacts. Only then:

```bash
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=false
```

```bash
gh release view memory-manager/v0.1.0
```

*Status on 2026-10-23: no version has been released; `memory-manager` is `proposed`.*

---

## 3. What a client is

Two kinds of client consume a pattern, and they test different things:

| Client | Consumes | Tests |
|---|---|---|
| **Agent team** | A domain's deployed service, through the tool API (`contracts/openapi.yaml`) | That calls behave as the contract says: section 4 |
| **Domain team** | A released pattern version, which it configures, extends, builds and deploys | That its customised build still honours the contract: section 4 for behaviour, then section 5 |

---

## 4. Test it as a client

Works today, with no release and no cloud access: the reference implementation runs locally
against an in-memory fake Memory Bank.

### 4.1 Start the service

Follow [getting-started.md step 6](getting-started.md#6-run-the-service-locally-5-minutes). It
leaves the service on `localhost:8080` with a demo classifier that blocks medication terms.

### 4.2 Four calls

**Allowed.** Stored and verified:

```bash
curl -s -X POST localhost:8080/v1/memories -H 'Content-Type: application/json' -H 'X-Agent-ID: writer-agent' -H 'Authorization: Bearer user-123' -H "Idempotency-Key: $(uuidgen)" -d '{"facts":[{"topic":"preferred_brands","field":"brand","value":"Horizon","fact":"The user prefers the organic brand Horizon.","basis":"stated"}]}'
```

```
{"outcome":"written","stored":1,"results":[{"index":0,"topic":"preferred_brands","reasonCode":"ACCEPTED","memoryId":"fake-1"}]}
```

**A disabled, sensitive topic.** A no-op, not an error. Agents must not read governance as an
outage:

```bash
curl -s -X POST localhost:8080/v1/memories -H 'Content-Type: application/json' -H 'X-Agent-ID: writer-agent' -H 'Authorization: Bearer user-123' -H "Idempotency-Key: $(uuidgen)" -d '{"facts":[{"topic":"health_conditions","value":"diabetes","fact":"The user has diabetes.","basis":"stated"}]}'
```

```
{"outcome":"noop","stored":0,"results":[{"index":0,"topic":"health_conditions","reasonCode":"TOPIC_DISABLED"}]}
```

**The one that matters: an allowed topic carrying prohibited content.**

```bash
curl -s -X POST localhost:8080/v1/memories -H 'Content-Type: application/json' -H 'X-Agent-ID: writer-agent' -H 'Authorization: Bearer user-123' -H "Idempotency-Key: $(uuidgen)" -d '{"facts":[{"topic":"preferred_brands","field":"brand","value":"Horizon","fact":"The user takes 20mg atorvastatin and prefers Horizon.","basis":"stated"}]}'
```

```
{"outcome":"noop","stored":0,"results":[{"index":0,"topic":"preferred_brands","reasonCode":"VALUE_PROHIBITED"}]}
```

**Rejected.** The topic label does not grant passage: the content is classified in full. This is
the single best thing to show.

**Read back, and isolation between end users:**

```bash
curl -s "localhost:8080/v1/memories?topic=preferred_brands" -H 'X-Agent-ID: writer-agent' -H 'Authorization: Bearer user-123'
```

```bash
curl -s "localhost:8080/v1/memories" -H 'X-Agent-ID: writer-agent' -H 'Authorization: Bearer user-456'
```

The first returns the Horizon fact. The second, a different end user, returns
`{"values":[],"withheld":0}`. The scope comes from the token, never from the request.

### 4.3 What a caller may not do

| Call | Result |
|---|---|
| `X-Agent-ID: reader-agent` (granted `recall` only) posting a fact | `403 CALLER_NOT_PERMITTED` |
| `X-Agent-ID: stranger` (not registered) | `403 CALLER_NOT_REGISTERED` |
| `remember` without `Idempotency-Key` | `400 IDEMPOTENCY_KEY_MISSING` |

### 4.4 Prove nothing leaked

Run the server with its output captured (`… 2>&1 | tee server.log`), make the calls, then:

```bash
grep -iE "atorvastatin|diabetes|Horizon|user-123" server.log || echo "clean - no payload in logs"
```

`Horizon` appearing would also be a finding: it is memory content.

### 4.5 The conformance suite

The contract a domain must keep, as tests. Against the reference implementation:

```bash
.venv/bin/pytest -q patterns/memory-manager/conformance
```

Against any running build, including a domain's deployment:

```bash
CONFORMANCE_BASE_URL=https://<service> CONFORMANCE_END_USER_TOKEN=<token> \
  .venv/bin/pytest -q patterns/memory-manager/conformance
```

The variables are in [conformance/README.md](../../patterns/memory-manager/conformance/README.md).

---

## 5. Adopt a version (domain team)

Needs a released version (section 2). A domain gets a **separate project**, not a fork of this
repository: a fork would carry every pattern, all the standards and the whole process, and turn
each upgrade into a monorepo merge.

### 5.1 Create the project

```bash
cp -R templates/domain-consumer ../customer-memory-manager && cd ../customer-memory-manager
```

```bash
git init -b main
```

Fill in `pattern.lock.yaml`: `name`, `version`, `source` (this repository's URL) and `tag`
(`memory-manager/v<version>`). Leave `manifestDigest`; vendoring fills it in.

### 5.2 Vendor the pattern

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r scripts/requirements.txt
```

```bash
.venv/bin/python scripts/vendor_pattern.py && .venv/bin/python scripts/verify_pattern_lock.py
```

`vendor_pattern.py` downloads the release with `gh`, verifies the published `SHA256SUMS` before
extracting, and refuses unverified source. `verify_pattern_lock.py` fails the build if the vendored
tree is later edited.

```bash
git add -A && git commit -m "Adopt memory-manager v<version>"
```

### 5.3 Make it the domain's own

- **Configuration**: topics, callers, identity, quota. Start from the pattern's own example,
  `vendor/pattern/config/example.domain.yaml`, not the template's `config/domain-config.yaml`,
  which predates the implementation and does not pass the schema (2026-10-23). It is validated at
  startup; the service refuses to start on invalid configuration rather than defaulting.
- **Extensions**: the PII classifier and the policy provider, in your own package, named by
  dotted path under `extensions:` in the configuration (the local demo in
  [getting-started.md](getting-started.md#6-run-the-service-locally-5-minutes) shows the shape).
  **Until you implement them, the service denies everything and stores nothing.** That is the
  fail-closed default working.

### 5.4 Test, build, deploy

1. Run sections 4.2 to 4.4 against your build locally, with your configuration and your
   extensions.
2. Run conformance in your CI: `pytest -q vendor/pattern/conformance/`. The platform **cannot see
   this run**. If a domain deletes the job, nothing outside its team notices. That is the model,
   and `standards/security.md` says so.
3. Build, scan and push your image; deploy with your Terraform. See
   [domain-adoption.md](domain-adoption.md).
4. After deploying, smoke-test the real service:
   ```bash
   python3 scripts/smoke_test.py --base-url https://<service-url>
   ```

---

## What to tell your teammates

**The process is two documents and two gates.** `intent.md`, then `design.md`, then code. No
controls assessment, no task plan, no closeout.

**Security is tests, not paperwork.** Eight rules in `standards/security.md`, each naming the test
that proves it. A rule without a passing test is not satisfied.

**The gates are where the value is.** Each stop is a person reading something before the next thing
gets expensive. In this repository that caught an async design that was later reversed, a retention
model the provider cannot support, and a five-fact request limit, all before any code existed.

**What the platform cannot enforce.** Domains own their code. Conformance and boundary checks run in
their CI, which we cannot see. Only platform-owned Terraform (the bank, its IAM binding, the audit
sink) survives a fork. Do not claim more.
