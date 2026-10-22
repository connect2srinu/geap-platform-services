---
name: feature-review
description: Review a finished implementation before the PR goes up. Use when the work is done and the user asks to "review", "open the PR", "check it against the design", or "is this ready". Compares the code with design.md, runs the checks, reports each honestly, and drafts the PR summary. Never approves or merges.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash(git status*)
  - Bash(git diff*)
  - Bash(git log*)
  - Bash(make verify)
  - Bash(make lint)
  - Bash(make test)
  - Bash(python3 scripts/*)
  - Bash(gh pr view*)
  - Bash(gh pr diff*)
  - Bash(gh pr checks*)
  - Bash(gh pr edit*)
user-invocable: true
---

# feature-review

## 1. Compare with the design

```bash
git diff $(git merge-base HEAD origin/main)...HEAD
```

For each change: is it in the approved design? Report anything outside it — a deviation or scope
creep, either way the reviewer needs to know.

## 2. Run the checks

```bash
make verify
```

Report every check as **passed / failed / skipped / unavailable**, with its command and output.
Unavailable is not a pass. Never write "tests pass" without output showing it.

## 3. Check the security rules

For each of the eight rules in `standards/security.md` that the design said it touches: does the named
test exist, and does it fail when the behaviour is removed? A rule with no such test is not satisfied.

Also check every new log line, trace attribute and error response for memory content, PII or secrets.

## 4. Draft the PR summary

```markdown
## What and why
<summary; link design/NNN-slug/>

## Design conformance
<matches, or the deviations and who approved them. "None" is a valid answer; silence is not.>

## Verification
| Check | Command | Result |

## Security
<rules touched, and the test covering each>

## Risks
<unresolved items, and where a reviewer should look closely>
```

## 5. Stop

Mark ready only when the checks pass and the design is matched. Otherwise leave it draft and list what
is missing — an honest blocker list beats wasting a reviewer's time.

**Never approve or merge.** A human does both.
