# Implementing 001 — Memory Manager v0.1.0, end to end

Execution guide for the governed-memory-write feature: platform build → publish → adopt as a domain →
run locally against a **real** Memory Bank.

Keystroke-level script: [session script](../onboarding/cli-session-script.md).
Generic command sequence: [CLI runbook](../onboarding/cli-runbook.md). Narrative:
[worked example](../onboarding/worked-example.md). This document is the feature-specific overlay.

---

# 0. Decisions already taken

| # | Decision | Consequence |
|---|---|---|
| D-A | **`GenerateMemories` with `direct_memories_source`** — supply pre-extracted facts, let Memory Bank consolidate | **Consolidation can rewrite a fact after your privacy gate passed it.** See §0.1 — this is the single most important thing the design must handle. |
| D-B | **Topic config in versioned YAML**, behind a `topic-provider` extension point | No database in v0.1.0; a domain needing runtime topic changes supplies its own provider later. |
| D-C | **v0.1.0 = structured facts only.** Gemini extraction is v0.2.0 | The `User message → filter and extract` branch of your flowchart is deferred. Validation, policy, storage and recall ship first. |

## 0.1 The consolidation problem — read before Stage 2

Your guarantee is *"sensitive material must not appear in stored evidence, application logs, or
extraction traces."* With `GenerateMemories`, the sequence is:

```
validate fact  →  PASS  →  GenerateMemories  →  Memory Bank consolidates  →  stored text ≠ validated text
                   ↑                                                              ↑
              your gate ran here                               but this is what actually persists
```

Pre-write validation alone **cannot** uphold the guarantee, because the provider mutates the content
after the gate. The prior art hit the same class of problem with provider-side generation and turned
it off (`geap-memory/docs/memory-bank-assumption-validation.md`, **MB-05**, status `BY DESIGN`:
*"provider extraction stores ungoverned memories"*).

**Required mitigation — make this an acceptance criterion:** a **post-write verification** step.

1. Validate the supplied facts → approved set.
2. `GenerateMemories` with `direct_memories_source`.
3. **Read back** the consolidated memories for that scope.
4. **Re-run the sensitivity classifier on the consolidated text.**
5. If a consolidated memory now carries prohibited content: **delete it**, emit an audit event, raise
   an alert.

Costs: one extra read per write (and reads consume the shared quota), plus a window — however
brief — in which unverified content exists in the bank. Both belong in `design.md` and in
`controls-check.md` under `C-05`. If that window is unacceptable, `CreateMemory` is the alternative
and the ADR should say so.

---

# 1. Prerequisites

## 1.1 Google Cloud

> **Not verified in this session.** The Memory Bank surface has been moving; confirm each step
> against the current documentation. The configuration *shape* below is taken from the prior art's
> live-exercised adapter, which is stronger evidence than the commands.

```bash
export GOOGLE_CLOUD_PROJECT=e2eml-222003          # confirm this is the intended project
export GOOGLE_CLOUD_LOCATION=us-central1
gcloud config set project "$GOOGLE_CLOUD_PROJECT"
```

```bash
gcloud services enable aiplatform.googleapis.com secretmanager.googleapis.com \
  pubsub.googleapis.com run.googleapis.com artifactregistry.googleapis.com logging.googleapis.com
```

```bash
gcloud auth application-default login
```

```bash
gcloud billing projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(billingEnabled)'
```

Memory Bank lives on an **Agent Engine** resource. Create one and keep its ID:

```bash
python3 - <<'PY'
import os, vertexai
client = vertexai.Client(
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"],
)
engine = client.agent_engines.create()
print("AGENT_PLATFORM_MEMORY_BANK_ID =", engine.api_resource.name.split("/")[-1])
PY
```

```bash
export AGENT_PLATFORM_MEMORY_BANK_ID=<the id printed above>
```

**Reference, not guesswork:** `geap-memory/apps/control-plane-api/integrations/vertex_memory_store.py`
is a live-exercised adapter on `google-cloud-aiplatform[agent_engines]>=1.112,<3.0`, using
`client.memory_banks.memories` with `create(fact=..., scope=...)` and `retrieve(scope=...)`, and
`geap-memory/.../tests/test_vertex_memory_store_gcp.py` shows the exact client construction
(`project`, `location`, `resource_id`) behind `RUN_GCP_INTEGRATION_TESTS=1`.

It does **not** implement `GenerateMemories`/`direct_memories_source` — that call is new work under
D-A. Reuse the client construction, scope handling and contract-test pattern; write the generate path.

## 1.2 Local

```bash
cd /home/sgadire1/projects/geap/geap-platform-services
make deps
```

> On Debian, Ubuntu and WSL the system Python is **externally managed** (PEP 668) and refuses a
> bare `pip install`. `make deps` creates a project `.venv` and installs into it — do not pass
> `--break-system-packages`.


Phase 0 of the [CLI runbook](../onboarding/cli-runbook.md) — first commit, remote, CODEOWNERS teams,
branch protection — if not already done. **Until branch protection exists, every gate is
honour-system.**

---

# 2. Stage 1 — Intent (Gate A)

```bash
cd /home/sgadire1/projects/geap/geap-platform-services && claude
```

```
/design-start-feature
```

Paste this as the request:

> Memory Manager v0.1.0: a governed write path for agent memory.
>
> An authenticated agent submits **already-structured facts**. The API derives the agent's
> permissions from its authenticated identity, resolves the user and owning memory scope
> **server-side** (never from the request body), loads the agent's approved topic configuration,
> and selects eligible topics — only enabled, non-sensitive topics qualify. Sensitive, restricted
> and unknown topics are excluded.
>
> Every fact is validated before writing: topic, field, value type, sensitivity and ownership.
> Reject unsupported inferences and facts carrying prohibited information **even when labelled as an
> allowed topic**. Approved facts are written via `GenerateMemories` with `direct_memories_source`.
> Nothing qualifying returns a no-op result, not an error.
>
> Because consolidation can rewrite a fact after validation, the write is followed by a
> **post-write verification**: read back the consolidated memories, re-run the sensitivity
> classifier, and delete plus audit anything that now carries prohibited content.
>
> Also in scope: `recall` for the same scope, so a write can be proven.
>
> Out of scope for v0.1.0: Gemini extraction from raw user messages (v0.2.0), a configuration
> database (topics are versioned YAML behind a `topic-provider` extension point), `correct`,
> `forget`, `list`, MCP.
>
> Topic configuration shape — classification drives eligibility:
> preferred_brands (non-sensitive, extraction allowed), preferred_cuisines (non-sensitive, allowed),
> medical_conditions (sensitive, blocked), prescription_details (restricted, blocked).

Acceptance criteria to insist on — these are the ones that make the feature real rather than plausible:

1. A fact in an allowed, non-sensitive topic is stored and is retrievable by `recall`.
2. A fact in a sensitive or restricted topic is **not** stored; the response is a no-op, not an error.
3. A fact labelled `preferred_brands` whose **value** carries prescription content is **rejected** —
   the label does not grant passage.
4. An unknown topic is rejected (fail closed).
5. Scope comes from the authenticated identity; a request body attempting to set another user's scope
   is refused.
6. A broader inference than the input supports is not stored — "I like Horizon" must not become
   "always buys organic".
7. Post-write verification deletes and audits a consolidated memory that now carries prohibited
   content.
8. No prohibited content appears in logs, traces, error responses or stored evidence — proven by a
   test that fails if redaction is removed.
9. Nothing qualifying → no-op result, no provider call wasted.
10. Every write, rejection and post-write deletion emits an audit event with a correlation ID.

Then approve Gate A **by hand**:

```yaml
status: approved
approved_by: <your name>
approved_date: <today>
```

```bash
python3 scripts/validate_design_artifacts.py design/001-memory-manager
```

```bash
git checkout -b design/001-memory-manager
git add -A && git commit -m "001: intent for Memory Manager v0.1.0" && git push -u origin design/001-memory-manager
gh pr create --draft --title "001: Memory Manager v0.1.0 — governed fact writes" --body "Design folder: design/001-memory-manager/"
```

---

# 3. Stage 2 — Design (Gate B)

```
/design-session
```

Require these in `design.md` before approving:

- **The validation order**, explicitly: identity → scope resolution → topic config load → topic
  eligibility → per-fact schema → value-level sensitivity scan → ownership → write → **post-write
  verification**. Every step fails closed.
- **`topic-provider` extension point** — interface, YAML default, `failureMode: deny`.
- **The topic config schema**: topic id, classification (`non-sensitive` / `sensitive` /
  `restricted`), extraction allowed, value type, field constraints.
- **Scope key shape**, and why it cannot come from the request body.
- **The no-op contract** — what status and body a fully-filtered request returns. Not an error.
- **Post-write verification** including what happens when the delete itself fails.
- **The consolidation window** — how long unverified content can exist, and the accepted risk.
- **Idempotency** on the write.
- **Error catalogue** distinguishing *rejected by policy* from *nothing qualified* from
  *provider unavailable*. The agent must be able to tell these apart.

Propose ADRs for: the `GenerateMemories` choice **with the consolidation risk and its mitigation
stated**, and the YAML-with-extension-point topic configuration.

Approve Gate B by hand, commit, push.

---

# 4. Stage 3 — Controls (Gate C)

```
/design-check-controls
```

The ones that will take real thought:

| Control | Why it is hard here |
|---|---|
| **C-05** redaction before persistence | Consolidation mutates after the gate. Satisfied only by validation **plus** post-write verification — say exactly that, and record the window as a `Gap` or an approved exception with the verification as compensating control. |
| **C-06** logging restrictions | Facts, values and rejection reasons are all payload. Log the **topic name and reason code**, never the value. |
| **C-02** fail closed | Unknown topic, unknown classification, classifier error, provider error — all deny. |
| **C-16** domain isolation | Scope derived server-side from identity; IAM Conditions on scope. |
| **C-17** retry | A failed `GenerateMemories` must not be retried in a way that double-consolidates. |

Most will read `Implemented, not verified` at this stage. That is correct. Have a **security
reviewer** approve, ideally not the author.

---

# 5. Stage 4 — Plan and implement

```
/design-plan-implementation
```

Expect roughly:

| Task | Owns |
|---|---|
| T-01 OpenAPI + error catalogue | `contracts/` |
| T-02 Topic config schema + example | `config/` |
| T-03 `topic-provider` interface + YAML default | `extensions/topic_provider.py` |
| T-04 `pii-classifier` interface + deny-all default | `extensions/pii_classifier.py` |
| T-05 Validation pipeline | `src/policy/` |
| T-06 Memory Bank adapter (generate + retrieve + delete) + fake client | `src/providers/` |
| T-07 Post-write verification | `src/worker/` |
| T-08 `remember` / `recall` endpoints | `src/api/` |
| T-09 Live contract test, opt-in | `tests/test_memory_bank_gcp.py` |
| T-10 Conformance suite | `conformance/` |

Approve Gate D by hand. **Then** implement, one task at a time:

```
implement T-01 from design/001-memory-manager/tasks.md
```

```bash
make verify
git add -A && git commit -m "001: T-01 OpenAPI contract and error catalogue" && git push
```

After the provider work lands, run the **live** contract test — a mock proves nothing about Memory
Bank:

```bash
RUN_GCP_INTEGRATION_TESTS=1 \
GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT \
GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION \
AGENT_PLATFORM_MEMORY_BANK_ID=$AGENT_PLATFORM_MEMORY_BANK_ID \
pytest -q patterns/memory-manager/tests/test_memory_bank_gcp.py
```

**This is where you discover what consolidation actually does to your facts.** Write "I like the
organic brand Horizon", read it back, and compare the stored wording with what you submitted. If it
is rewritten, D-A's risk is real and measured rather than theoretical — and that belongs in the ADR.

Then:

```
/design-check-controls --recheck
```

---

# 6. Stages 5 and 6

```
/design-open-pr
```

```bash
claude -p "/code-review high"
```

Human approves (Gate E). Then:

```
/design-close-feature
```

```bash
gh pr merge --squash --delete-branch
```

---

# 7. Publish v0.1.0

```bash
git checkout main && git pull
```

```
/pattern-validate
```

```bash
git checkout -b release/memory-manager-v0.1.0
```

Edit **only**: `pattern.yaml` (`version: 0.1.0`, `status: proposed` → `alpha`), `CHANGELOG.md`,
`docs/releases/memory-manager-v0.1.0.md` (from `_template.md` — **state the live-verification result
from §5**), and the README table.

```bash
python3 scripts/check_release_commit.py --base origin/main
```

```bash
git add -A && git commit -m "release: memory-manager v0.1.0" && git push -u origin release/memory-manager-v0.1.0
gh pr create --title "release: memory-manager v0.1.0" --body "Release track. Metadata and notes only."
```

```
/pattern-publish
```

After merge:

```bash
git checkout main && git pull
git tag memory-manager/v0.1.0 && git push origin memory-manager/v0.1.0
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=true
gh run watch
```

Then the real publish:

```bash
gh workflow run release.yml -f pattern=memory-manager -f version=0.1.0 -f dry_run=false
gh release view memory-manager/v0.1.0
```

---

# 8. Switch hats — adopt as the Customer domain

From the platform repository:

```
/domain-onboard
```

Answer: pattern `memory-manager`, version `0.1.0`, domain `customer`, project
`$GOOGLE_CLOUD_PROJECT`, region `$GOOGLE_CLOUD_LOCATION`.

```bash
cd ../customer-memory-manager
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements.txt
.venv/bin/python scripts/vendor_pattern.py
.venv/bin/python scripts/verify_pattern_lock.py
```

## 8.1 Configure the domain's topics

`config/topics.yaml`:

```yaml
topics:
  - id: preferred_brands
    classification: non-sensitive
    extraction: allowed
    value_type: string
  - id: preferred_cuisines
    classification: non-sensitive
    extraction: allowed
    value_type: string
  - id: medical_conditions
    classification: sensitive
    extraction: blocked
  - id: prescription_details
    classification: restricted
    extraction: blocked
```

Implement `extensions/pii_classifier.py`. **Until you do, it denies everything and nothing is
stored** — that is the fail-closed default working, not a bug.

## 8.2 Run it locally against the real Memory Bank

```bash
cp .env.example .env
```

Set in `.env` (names only in the committed example; real values stay local):

```
GOOGLE_CLOUD_PROJECT=<your project>
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_PLATFORM_MEMORY_BANK_ID=<your agent engine id>
DOMAIN_NAME=customer
MAX_WRITES_PER_MINUTE=20
AUTH_ENABLED=false
```

> `AUTH_ENABLED=false` is **local only**. The pattern must refuse to start with it set in a deployed
> environment — not merely default it off. Confirm that refusal is tested (`C-01`).

```bash
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json
python3 -m uvicorn pattern.api.main:app --reload --port 8080
```

## 8.3 Exercise it

Allowed fact:

```bash
curl -s -X POST localhost:8080/v1/memories \
  -H "Content-Type: application/json" -H "X-Agent-ID: local-test-agent" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"facts":[{"topic":"preferred_brands","value":"Horizon","fact":"The user prefers the organic brand Horizon."}]}'
```

Expect `202`.

Blocked topic — expect a **no-op**, not an error:

```bash
curl -s -X POST localhost:8080/v1/memories \
  -H "Content-Type: application/json" -H "X-Agent-ID: local-test-agent" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"facts":[{"topic":"medical_conditions","value":"diabetes","fact":"The user has diabetes."}]}'
```

The label-does-not-grant-passage case — an allowed topic carrying prescription content:

```bash
curl -s -X POST localhost:8080/v1/memories \
  -H "Content-Type: application/json" -H "X-Agent-ID: local-test-agent" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"facts":[{"topic":"preferred_brands","value":"Horizon","fact":"The user takes 20mg atorvastatin and prefers Horizon."}]}'
```

**This is the test that matters most.** It must be rejected.

Read back:

```bash
curl -s "localhost:8080/v1/memories?topic=preferred_brands" -H "X-Agent-ID: local-test-agent"
```

Confirm nothing leaked into the logs:

```bash
grep -riE "atorvastatin|diabetes|Horizon" <your log output> || echo "clean — no payload in logs"
```

`Horizon` appearing is also a finding: it is memory content.

Verify in the bank directly — the service is not the only witness:

```bash
python3 - <<'PY'
import os, vertexai
client = vertexai.Client(
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"],
)
# Confirm the adapter's surface against your installed SDK version before relying on this.
for memory in client.agent_engines.retrieve_memories(
    name=f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/locations/{os.environ['GOOGLE_CLOUD_LOCATION']}/reasoningEngines/{os.environ['AGENT_PLATFORM_MEMORY_BANK_ID']}",
    scope={"user_id": "local-test-user"},
):
    print(memory)
PY
```

Compare the stored wording with what you submitted. **Any difference is consolidation, and it is the
evidence D-A's ADR needs.**

## 8.4 Conformance

```bash
pytest -q vendor/pattern/conformance/
```

An empty suite is **unavailable**, not a pass.

---

# 9. Cleaning up

Memory Bank and Agent Engine resources cost money while they exist.

```bash
python3 - <<'PY'
import os, vertexai
client = vertexai.Client(
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"],
)
client.agent_engines.delete(
    name=f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/locations/{os.environ['GOOGLE_CLOUD_LOCATION']}/reasoningEngines/{os.environ['AGENT_PLATFORM_MEMORY_BANK_ID']}",
    force=True,
)
PY
```

**This deletes stored memories.** Confirm you want that before running it.

---

# Open questions for you

| # | Question | Blocks |
|---|---|---|
| Q1 | Is `e2eml-222003` the intended project, or is there a proper sandbox? It is a personal project and this will incur Agent Engine cost. | §1.1 |
| Q2 | What is the scope key shape — `user_id` alone, or `organization_id + user_id` as the prior art uses? It determines isolation and cannot be changed later without migrating stored memories. | Stage 2 |
| Q3 | Who is the security reviewer for Gate C? The `C-05` consolidation gap needs someone other than the author to accept it. | Stage 3 |
| Q4 | Is the post-write verification window acceptable, or does the guarantee require `CreateMemory` after all? | Stage 2 / ADR |
