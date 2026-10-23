# Demo — a feature from idea to a domain running it

The whole lifecycle, in the order it happens: **build** a feature through its gates, **release**
it, then **adopt and test** it as a client. Three acts, about 45 minutes. Everything typed into
`claude` is shown as `>`; everything else is a shell command. Where a step says **YOU**, no tool
does it for you — that is the point of the gate.

```
 BUILD                                                     RELEASE            CLIENT
 intent.md ─▶ YOU approve ─▶ design.md ─▶ YOU approve ─▶   tag + workflow ─▶  adopt, configure,
                                          │                  YOU approve        run, test,
                                          ▼                  the release        conformance
                              branch ─▶ implement ─▶ PR ─▶ CI ─▶ YOU approve ─▶ merge
```

Setup, once — on a new machine, follow [getting-started.md](getting-started.md); otherwise, from the
repository root:

```bash
make deps && make verify
```

## The gates

| Gate | Who | Recorded as | What enforces it |
|---|---|---|---|
| `intent.md` approved | Requester / platform lead | `status: approved`, `approved_by`, `approved_date` in its front matter, **edited by hand** | `/feature-start` will not write a design before it; the validator prints the gate state |
| `design.md` approved | Platform architect | the same | No implementation code before it (CLAUDE.md); the validator prints `both approved - implementation may proceed` |
| Pull request approved | ≥1 reviewer | GitHub review | Branch protection: the required checks, up to date with `main`, conversations resolved |
| Merge | Repository admin | the merge | Never Claude Code: `gh pr merge` is denied in `.claude/settings.json` |
| Release | Maintainer, then the `release` environment's reviewers | tag + workflow dispatch | `release.yml` checks, and the environment's required reviewers |

On a single-maintainer repository GitHub will not let you approve your own PR, so the PR gate is
unenforced there — and the repository says so rather than pretending otherwise.

---

# Act 1 — Build a feature (platform team)

## 1. Start it

```bash
claude
```

```
> /feature-start
```

Describe what you want. It asks a few questions, writes **`design/NNN-slug/intent.md`** — half a
page — and **stops**.

> Point out to the audience: it stopped. It will not write a design, let alone code, until a person
> approves the intent.

## 2. **YOU** approve the intent

Read it. Then edit the front matter by hand:

```yaml
status: approved
approved_by: <your name>
approved_date: 2026-10-22
```

By hand, deliberately. A scripted approval is not an approval — the step's whole value is that a
person read the document.

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

It prints the gate state: `awaiting approval of intent.md` → `intent approved - design.md not
written yet`.

## 3. Design

```
> /feature-start
```

Run it again — the same skill handles both steps. It checks the intent is approved first; if it
isn't, it stops and says so. Before designing, it **verifies provider assumptions** — reads the installed SDK rather than the
documentation, and writes a throwaway probe in `spike/` if something needs a live answer. This has
caught three contract-level defects that would otherwise have surfaced mid-implementation.

Then it writes **`design/NNN-slug/design.md`** — two to three pages — and **stops** again.

## 4. **YOU** approve the design

Same edit. Then:

```bash
python3 scripts/validate_design_artifacts.py design/NNN-slug
```

```
design/NNN-slug: both approved - implementation may proceed
```

**That line is the demo's punchline.** Nothing before it could write product code.

## 5. Branch and implement

```bash
git checkout -b design/NNN-slug && git push -u origin design/NNN-slug
```

```bash
gh pr create --draft --title "NNN: <title>" --body "Design: design/NNN-slug/"
```

```
> implement the first item in design/NNN-slug/design.md
```

Tests ship in the same commit. Repeat per checklist item, committing as you go.

```bash
make verify
```

## 6. Review and merge

```
> /feature-review
```

It compares the diff against the design, runs the checks, and reports each as
**passed / failed / skipped / unavailable**. Unavailable is not a pass.

```bash
gh pr ready && gh pr checks --watch
```

**YOU** approve the PR in GitHub, then:

```bash
gh pr merge --squash --delete-branch
```

---

# Act 2 — Publish a release (platform team)

```bash
git checkout main && git pull
```

```
> /pattern-release
```

It validates readiness, checks the version bump against the **real contract diff**, and produces a
checklist plus the exact commands. **It publishes nothing.** A published version cannot be withdrawn
once a domain has consumed it.

**Once, before the first release, an admin sets up in GitHub settings** (none of this travels with
a clone): a **`release` environment with required reviewers** — without it, GitHub creates the
environment on first use **with no reviewers**, and the second human gate does not exist — and tag
protection on `*/v*`. *Neither was configured as of 2026-10-23.*

The release commit is a normal PR that changes metadata and notes only. `release.yml` refuses to
publish without each of these:

| File | Change |
|---|---|
| `patterns/<name>/pattern.yaml` | `metadata.version` matching the tag; `metadata.status` moved off `proposed` (to `alpha`, `beta` or `certified`) |
| `patterns/<name>/CHANGELOG.md` | `## [Unreleased]` becomes `## [<version>] — <date>` |
| `docs/releases/<name>-v<version>.md` | Release notes, stating whether **live verification** was performed |

Then PR, review, merge, and:

```bash
git tag memory-manager/v0.1.0 && git push origin memory-manager/v0.1.0
```

```bash
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=true
```

```bash
gh run watch
```

Dry run first — it builds from the **tag**, never a branch, validates, builds the tarball, writes
`SHA256SUMS` and attests provenance without creating a Release. Its publish job waits for a
`release` environment reviewer — **YOU** approve it on the run's page, in the dry run and the real
run alike. Only then:

```bash
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=false
```

```bash
gh release view memory-manager/v0.1.0
```

---

# Act 3 — Adopt and test it (clients)

Two kinds of client consume a pattern, and both are tested here:

| Client | Consumes | What it tests |
|---|---|---|
| **Domain team** | A pattern version, which it configures, extends, builds and deploys | That its customised build still honours the contract: steps 4 and 5 |
| **Agent team** | A domain's deployed service, through the tool API (`contracts/openapi.yaml`) | That calls behave as the contract says: the calls in step 4 |

To try the API before adopting anything, run the pattern's own reference implementation:
[getting-started.md, step 6](getting-started.md#6-run-the-service-locally-5-minutes).

## 1. Start the project

Copy the template into a **separate project** — not a fork of the platform repo. A fork would carry
every pattern, all the standards and the whole process, and turn each upgrade into a monorepo merge.

```bash
cp -R templates/domain-consumer ../customer-memory-manager && cd ../customer-memory-manager
```

Fill in `pattern.lock.yaml`: a released `tag:`, or — before any release exists — `ref:` or `path:`
with `unreleased: true` ([domain-adoption.md](domain-adoption.md#3-start-your-project)).

```bash
git init -b main && git add -A && git commit -m "Adopt memory-manager"
```

## 2. Vendor the pattern

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r scripts/requirements.txt
```

```bash
.venv/bin/python scripts/vendor_pattern.py && .venv/bin/python scripts/verify_pattern_lock.py
```

`vendor_pattern.py` verifies the published `SHA256SUMS` before extracting, and refuses unverified
source. `verify_pattern_lock.py` fails the build if the vendored tree is later edited.

## 3. Make it the domain's own

Edit `config/topics.yaml`:

```yaml
topics:
  - { id: preferred_brands,    classification: non-sensitive, enabled: true }
  - { id: preferred_cuisines,  classification: non-sensitive, enabled: true }
  - { id: medical_conditions,  classification: sensitive,     enabled: false }
  - { id: prescription_details, classification: restricted,   enabled: false }
```

Write your own classifier and point `config/domain-config.yaml` at it. The template ships
`extensions/sample_classifier.py` as a worked example — read it, do not ship it.

**Leave the entry out and the service denies everything and stores nothing** — that is the
fail-closed default working, not a bug. Show the audience that first, then add the classifier and
show the same call succeeding.

## 4. Run it locally

Everything below is exercised by the `domain-rehearsal` CI job, so it works or the build is red.

The local run uses the **fake** memory bank: it models consolidation, dedup and rollback as
verified against the provider, and needs no credentials. For a run against a real bank, see
`design/001-memory-manager/spike/verify_live.py` — that one costs quota.

```bash
cp .env.example .env
```

Fill in `ENVIRONMENT=local`, `MAX_INSTANCES=1`, `SUBJECT_HMAC_KEY=any-local-value`, and
`CONFIG_PATH` pointing at your `config/domain-config.yaml`. `.env.example` carries names only;
never commit a filled-in `.env`.

```bash
.venv/bin/python -m uvicorn memory_manager.asgi:create --factory --port 8080
```

The factory form matters: a configuration error then arrives as a message naming the field,
instead of an import traceback from inside uvicorn's loader.

Three calls, in a second terminal. Both headers are required — `Authorization` carries the **end
user's** token, which is what the memory scope is derived from, and `X-Agent-ID` is your
registered caller.

Keep the token in a variable rather than typing it into each command; a real one does not belong
in your shell history. Locally the verifier treats the bearer value as the subject, so any string
works:

```bash
export END_USER_TOKEN=end-user-1
export AGENT=example-writer-agent
```

**Allowed:**

```bash
curl -s -X POST localhost:8080/v1/memories -H 'Content-Type: application/json' -H "X-Agent-ID: $AGENT" -H "Authorization: Bearer $END_USER_TOKEN" -H "Idempotency-Key: $(uuidgen)" -d '{"facts":[{"topic":"example_preference","field":"preference","value":"Horizon","fact":"Prefers the organic brand Horizon."}]}'
```

`{"outcome":"written","stored":1,...,"reasonCode":"ACCEPTED"}`

**Blocked topic** — a no-op, not an error. The request succeeded; the policy said no:

```bash
curl -s -X POST localhost:8080/v1/memories -H 'Content-Type: application/json' -H "X-Agent-ID: $AGENT" -H "Authorization: Bearer $END_USER_TOKEN" -H "Idempotency-Key: $(uuidgen)" -d '{"facts":[{"topic":"example_sensitive_topic","field":"detail","value":"x","fact":"Something sensitive."}]}'
```

`{"outcome":"noop","stored":0,...,"reasonCode":"TOPIC_DISABLED"}`

**The one that matters** — an allowed topic carrying prohibited content:

```bash
curl -s -X POST localhost:8080/v1/memories -H 'Content-Type: application/json' -H "X-Agent-ID: $AGENT" -H "Authorization: Bearer $END_USER_TOKEN" -H "Idempotency-Key: $(uuidgen)" -d '{"facts":[{"topic":"example_preference","field":"preference","value":"Horizon","fact":"Takes 20mg of something and prefers Horizon."}]}'
```

`{"outcome":"noop","stored":0,...,"reasonCode":"VALUE_PROHIBITED"}`

**Refused.** The label does not grant passage. This is the single best thing to show.

Read it back:

```bash
curl -s "localhost:8080/v1/memories?topic=example_preference" -H "X-Agent-ID: $AGENT" -H "Authorization: Bearer $END_USER_TOKEN"
```

Only the first fact comes back. `withheld: 0` — nothing was dropped on the way out.

Prove nothing leaked:

```bash
grep -riE "Horizon|20mg|$END_USER_TOKEN" server.log || echo "clean - no payload, no raw subject in logs"
```

`Horizon` appearing is also a finding — it is memory content.

## 5. Conformance

```bash
.venv/bin/pytest -q vendor/pattern/conformance/
```

Against a running build — your local one, or the deployed service:

```bash
CONFORMANCE_BASE_URL=http://localhost:8080 .venv/bin/pytest -q vendor/pattern/conformance/
```

Without `CONFORMANCE_BASE_URL` the suite tests the pattern's reference implementation, not your
build. The variables are in the suite's `README.md`.

After deploying, smoke-test the real service with `python3 scripts/smoke_test.py --base-url
https://<service-url> --agent-id <your-caller-id>`.

This is how the domain shows its customization still honours the contract. Say plainly that the
platform **cannot see this run** — if the domain deletes the job, nothing outside their team
notices. That is the model, and `standards/security.md` says so.

---

# What to tell your teammates

**The process is two documents and two gates.** `intent.md`, then `design.md`, then code. Nothing
else — no controls assessment, no task plan, no closeout.

**Security is tests, not paperwork.** Eight rules in `standards/security.md`, each naming the test
that proves it. A rule without a passing test is not satisfied.

**The gates are where the value is.** Each stop is a person reading something before the next thing
gets expensive. In this repository that caught an async design that was later reversed, a retention
model the provider cannot support, and a five-fact request limit — all before any code existed.

**What the platform cannot enforce.** Domains own their code. Conformance and boundary checks run in
their CI, which we cannot see. Only platform-owned Terraform — the bank, its IAM binding, the audit
sink — survives a fork. Do not claim more.
