---
artifact: controls-check
feature: NNN-slug
track: full
status: draft
---

# Controls assessment — <feature title>

> Stage 3. Generated from the catalogue in `standards/security.md`. Approval at **Gate C**.
>
> A control is **never** `Verified` without evidence that would fail if the control were removed.
> `Gap` is an acceptable outcome; an undisclosed gap is not.

Statuses: `Verified` · `Implemented, not verified` · `Gap` · `Not applicable` · `Exception approved`

## Summary

| Status | Count |
|---|---|
| Verified | |
| Implemented, not verified | |
| Gap | |
| Not applicable | |
| Exception approved | |

## Assessment

Repeat per applicable control.

### C-NN — <control name>

| | |
|---|---|
| **Requirement** | From `standards/security.md` |
| **Applicability** | Applies / does not apply, and why |
| **Implementation** | Specific files, resources, configuration |
| **Verification** | The named test, scan, or procedure |
| **Status** | |
| **Evidence** | Command output, test name, scan report — or the gap |

## Non-applicable controls

| Control | Reason |
|---|---|

## Gaps

| Control | Gap | Risk | Plan | Owner |
|---|---|---|---|---|

## Approved exceptions

| Control | Exception | Compensating control | Approver | Date | Expires |
|---|---|---|---|---|---|

## Approval

Gate C. A security reviewer sets `status: approved`. CI fails an approved assessment that contains a
`Gap` with no recorded exception.
