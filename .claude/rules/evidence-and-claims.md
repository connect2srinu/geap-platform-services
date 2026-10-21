# Evidence and claims

## The rule

Never state that something passed, built, deployed or is secure unless you ran it and saw the output
in this session. Not "the tests should pass". Not "this is now compliant".

## Four statuses, always distinguished

| Status | Means | Example |
|---|---|---|
| **Passed** | Ran, exited zero, output seen | `pytest -q` → `41 passed` |
| **Failed** | Ran, did not succeed | `ruff check` → `3 errors` |
| **Skipped** | Deliberately not run | integration tests without cloud credentials |
| **Unavailable** | Could not run — tool missing, no network, no permission | `actionlint: command not found` |

**Unavailable is not passed.** Reporting an unavailable check as anything other than unavailable is
the failure mode this rule exists to prevent.

## Evidence labels in documents

Architecture and design documents use these, and the design-artifact validator checks the vocabulary:

| Label | Means |
|---|---|
| `VERIFIED` | Observed directly — file read, command run. Cite how. |
| `PROPOSED` | A recommendation. Not a decision. |
| `OPEN` | Needs a human decision before it can be built. |
| `ASSUMPTION` | Taken as true to make progress. Recorded, not hidden. |

A document making factual claims about the codebase states its method: what was read, which branch,
what date. Borrowed from the prior repository's reference architecture, which does this well.

## Assumptions

Document them; do not invent requirements to fill a gap. If a decision is missing, record it as
`OPEN` with the question and what would resolve it. An invented requirement is indistinguishable from
a real one three months later, and that is how designs rot.

## Managed services

A mock does not prove a managed-service integration works. A unit test against a fake client proves
your code calls the fake correctly. Say exactly that, and keep live verification a separate,
explicitly labelled step.
