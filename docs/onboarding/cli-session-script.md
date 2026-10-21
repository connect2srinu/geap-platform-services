# CLI session script — Memory Manager 001, keystroke by keystroke

No explanation, just the sequence. **Why** each step exists:
[implementing 001](../operations/implementing-001-memory-manager.md). **Narrative:**
[worked example](worked-example.md).

Legend:

| | |
|---|---|
| `$` | type at your shell |
| `>` | type **inside** an interactive `claude` session |
| **CHECK** | confirm this before continuing |
| **YOU** | a human action — no tool does this for you |

---

## Claude CLI mechanics you need

| Need | How |
|---|---|
| Start a session in this repo | `cd <repo> && claude` |
| See available skills / commands | type `/` and read the list |
| Continue the last conversation | `claude -c` |
| Pick an older conversation | `claude -r` |
| One-shot, no session | `claude -p "<prompt>"` |
| Reset context, same session | `/clear` |
| Leave | `/exit` or `Ctrl-D` |
| See what it is actually doing | `claude --debug` |
| Fewer approval prompts while implementing | `claude --permission-mode acceptEdits` |

Project skills live in `.claude/skills/` and are discovered **per project** — they appear only when
`claude` starts inside this repository. If `/design-start-feature` is not in the `/` list, you are in
the wrong directory.

`/permissions`, `/config` and `/hooks` open interactive panels. They work in a real terminal.

---

# Session 0 — setup (once)

```
$ cd /home/sgadire1/projects/geap/geap-platform-services
$ make deps
$ make verify
```

**CHECK** three `PASSED` lines, plus `All checks passed!` from ruff. Nothing should say
`unavailable`.

> On Debian, Ubuntu and WSL the system Python is **externally managed** (PEP 668), so a bare
> `pip install` fails with `externally-managed-environment`. `make deps` creates a project `.venv`
> and installs into it. Do not pass `--break-system-packages` — it risks the OS Python.

```
$ git add -A
$ git commit -m "Establish platform foundation: SDLC, skills, standards, validators"
$ gh repo create geap-platform-services --private --source=. --remote=origin --push
```

**CHECK** `git log --oneline` shows a commit; `git remote -v` shows `origin`.

**YOU** — edit `.github/CODEOWNERS`, replace every `@<org>/...` placeholder.

```
$ gh api repos/:owner/:repo/codeowners/errors
```

**CHECK** the `errors` array is empty. On a personal account teams do not exist — accept that Gate E
is self-review and write that down as a known limitation.

GCP:

```
$ export GOOGLE_CLOUD_PROJECT=<your project>
$ export GOOGLE_CLOUD_LOCATION=us-central1
$ gcloud config set project "$GOOGLE_CLOUD_PROJECT"
$ gcloud services enable aiplatform.googleapis.com secretmanager.googleapis.com pubsub.googleapis.com run.googleapis.com artifactregistry.googleapis.com logging.googleapis.com
$ gcloud auth application-default login
```

Create the Agent Engine that Memory Bank lives on — see
[implementing 001 §1.1](../operations/implementing-001-memory-manager.md#11-google-cloud), then:

```
$ export AGENT_PLATFORM_MEMORY_BANK_ID=<the id>
```

---

# Session 1 — Intent

```
$ cd /home/sgadire1/projects/geap/geap-platform-services
$ claude
```

```
> /sdlc-status
```

**CHECK** it reports `001-memory-manager`, Stage 1, **Gate A open**.

```
> /design-start-feature
```

Paste the scoped description from
[implementing 001 §2](../operations/implementing-001-memory-manager.md#2-stage-1--intent-gate-a).

It will ask clarifying questions. Answer them. It will **stop** and ask for Gate A approval.

```
> /exit
```

**YOU** — read `design/001-memory-manager/intent.md`. Then edit its front matter by hand:

```yaml
status: approved
approved_by: <your name>
approved_date: <today>
```

Do not script this. The step's entire value is that a person read the document.

```
$ python3 scripts/validate_design_artifacts.py design/001-memory-manager
```

**CHECK** `PASSED`.

```
$ git checkout -b design/001-memory-manager
$ git add -A && git commit -m "001: intent for Memory Manager v0.1.0"
$ git push -u origin design/001-memory-manager
$ gh pr create --draft --title "001: Memory Manager v0.1.0 — governed fact writes" --body "Design folder: design/001-memory-manager/"
```

**CHECK** `gh pr view` shows a draft PR.

---

# Session 2 — Design

```
$ claude
> /sdlc-status
```

**CHECK** Gate A closed, **Gate B open**.

```
> /design-session
```

Answer its design questions. Expect `design.md` and **proposed** ADRs — not written ones.

```
> /exit
```

**YOU** — read `design.md`. Require the validation order, the `topic-provider` extension point, the
no-op contract, post-write verification, and the error catalogue. Then approve by hand.

```
$ python3 scripts/validate_design_artifacts.py design/001-memory-manager
$ git add -A && git commit -m "001: design approved" && git push
```

---

# Session 3 — Controls

```
$ claude
> /design-check-controls
> /exit
```

**YOU** — read `controls-check.md`. Most controls should say `Implemented, not verified`. If many say
`Verified` before any code exists, that is wrong — push back.

Pay attention to `C-05` (the consolidation gap) and `C-06` (facts and values are payload).

**YOU** — a **security reviewer**, ideally not you, approves by hand.

```
$ git add -A && git commit -m "001: controls assessed" && git push
```

---

# Session 4 — Plan

```
$ claude
> /design-plan-implementation
> /exit
```

**YOU** — read `tasks.md`. Check that no two tasks own the same file, and that every acceptance
criterion maps to a task. Approve by hand.

```
$ python3 scripts/validate_design_artifacts.py design/001-memory-manager
$ git add -A && git commit -m "001: implementation plan approved" && git push
```

**Nothing above this line wrote application code. That is the point.**

---

# Sessions 5…N — Implement, one task per session

```
$ claude --permission-mode acceptEdits
> implement T-01 from design/001-memory-manager/tasks.md
```

Then, in the same session:

```
> run make verify and report the result
```

**CHECK** the output is real — a command and its exit status, not a claim.

```
> /exit
$ git add -A && git commit -m "001: T-01 OpenAPI contract and error catalogue" && git push
```

Repeat per task. `/clear` between tasks in one session, or a fresh session each time — a fresh
session keeps context clean and is what you want when a task is self-contained.

When an architectural decision gets approved along the way:

```
> /design-record-decision
```

After the provider task (T-06), run the **live** test — a mock proves nothing about Memory Bank:

```
$ RUN_GCP_INTEGRATION_TESTS=1 pytest -q patterns/memory-manager/tests/test_memory_bank_gcp.py
```

**CHECK** whether consolidation rewrote your fact. Record what you observe in the ADR.

Once implementation has changed the security posture:

```
$ claude
> /design-check-controls --recheck
> /exit
```

---

# Session N+1 — Review

```
$ claude
> /design-open-pr
> /exit
```

Independent review, fresh context:

```
$ claude -p "/code-review high"
```

```
$ gh pr checks --watch
```

**YOU** — a human approves the PR in GitHub. Gate E.

---

# Session N+2 — Close

```
$ claude
> /design-close-feature
> /exit
```

**YOU** — read `closeout.md`, then:

```
$ gh pr merge --squash --delete-branch
```

---

# Session N+3 — Release v0.1.0

```
$ git checkout main && git pull
$ claude
> /pattern-validate
> /exit
```

**CHECK** no blockers.

```
$ git checkout -b release/memory-manager-v0.1.0
```

**YOU** — edit only: `pattern.yaml` (`version: 0.1.0`, `status: proposed` → `alpha`), `CHANGELOG.md`,
`docs/releases/memory-manager-v0.1.0.md` (from `_template.md`), README table.

```
$ python3 scripts/check_release_commit.py --base origin/main
```

**CHECK** `PASSED`. A failure means you touched `src/` or `contracts/` — that is a feature, not a
release.

```
$ git add -A && git commit -m "release: memory-manager v0.1.0"
$ git push -u origin release/memory-manager-v0.1.0
$ gh pr create --title "release: memory-manager v0.1.0" --body "Release track. Metadata and notes only."
$ claude
> /pattern-publish
> /exit
```

After Gate E and merge:

```
$ git checkout main && git pull
$ git tag memory-manager/v0.1.0 && git push origin memory-manager/v0.1.0
$ gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=true
$ gh run watch
```

**CHECK** green. Then the real publish:

```
$ gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=false
$ gh release view memory-manager/v0.1.0
```

---

# Session N+4 — Switch hats: adopt as the Customer domain

Still in the platform repo:

```
$ claude
> /domain-onboard
```

Answer: pattern `memory-manager`, version `0.1.0`, domain `customer`, your project, your region.

```
> /exit
$ cd ../customer-memory-manager
$ python3 -m venv .venv && .venv/bin/python -m pip install -r scripts/requirements.txt
$ .venv/bin/python scripts/vendor_pattern.py
$ .venv/bin/python scripts/verify_pattern_lock.py
```

**CHECK** the lock verifies.

**YOU** — fill `config/topics.yaml` (four topics) and implement `extensions/pii_classifier.py`.
Until the classifier exists it denies everything and stores nothing — that is fail-closed working.

Run it locally against the real bank:

```
$ cp .env.example .env
```

**YOU** — set `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `AGENT_PLATFORM_MEMORY_BANK_ID`,
`DOMAIN_NAME=customer`, `AUTH_ENABLED=false` (**local only**).

```
$ export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json
$ python3 -m uvicorn pattern.api.main:app --reload --port 8080
```

In a second terminal, the three cases from
[implementing 001 §8.3](../operations/implementing-001-memory-manager.md#83-exercise-it):
allowed fact → `202`; blocked topic → no-op; **allowed topic carrying prescription content →
rejected**.

```
$ pytest -q vendor/pattern/conformance/
```

**CHECK** it collects tests. Zero collected is **unavailable**, not a pass.

---

# When a skill refuses

That is the design, not a fault.

| It says | Do |
|---|---|
| "intent.md is not approved" | Approve Gate A by hand. |
| "design.md is not approved" | Approve Gate B. |
| "an upstream gate is open" | `/sdlc-status`, then approve whatever it names. |
| "I will not merge / publish / apply" | Run the command yourself. Those are denied in `.claude/settings.json`. |
| "I cannot mark this approved" | Correct. Only you can. |

# Taking this to your office machine

1. The flow needs: `git`, `gh`, `python3`, `make`, and `claude`. Terraform and Docker only at deploy.
2. Project skills travel with the repository — clone it and they are there.
3. `.claude/settings.json` travels too, including the deny list.
4. The six administrator settings do **not** travel. Redo them per repository:
   [repository administration](../operations/repository-administration.md).
5. `make verify` works without Claude Code. Every validator is plain Python — CI does not depend on
   an AI being present, and neither do you.
