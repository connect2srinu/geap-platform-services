"""The controls-check rule in scripts/validate_design_artifacts.py.

An approved assessment may contain a Gap only with a recorded exception that names an approver, a
date and an expiry. The status legend and summary table always contain every status name, so these
fixtures keep both to prove they cannot satisfy the rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_design_artifacts import check_controls  # noqa: E402

LEGEND = """\
Statuses: `Verified` · `Implemented, not verified` · `Gap` · `Not applicable` · `Exception approved`

## Summary

| Status | Count |
|---|---|
| Gap | 1 |
| Exception approved | 0 |
"""


def control(cid: str, status: str) -> str:
    return f"""
### {cid} — Example control

| | |
|---|---|
| **Requirement** | x |
| **Status** | {status} |
| **Evidence** | x |
"""


def exceptions(*rows: str) -> str:
    return (
        "\n## Approved exceptions\n\n"
        "| Control | Exception | Compensating control | Approver | Date | Expires |\n"
        "|---|---|---|---|---|---|\n"
        + "".join(r + "\n" for r in rows)
        + "\n## Approval\n\nGate C.\n"
    )


def test_template_legend_does_not_satisfy_an_approved_gap() -> None:
    body = LEGEND + "\n## Assessment\n" + control("C-05", "Gap") + exceptions()
    assert check_controls(body, approved=True) == [
        "C-05: approved with status 'Gap' and no approved exception "
        "(approver, date and expiry) recorded"
    ]


def test_every_unexcepted_gap_is_named() -> None:
    body = (
        LEGEND
        + control("C-05", "Gap")
        + control("C-06", "Verified")
        + control("C-09", "Gap")
    )
    problems = check_controls(body + exceptions(), approved=True)
    assert [p.split(":")[0] for p in problems] == ["C-05", "C-09"]


@pytest.mark.parametrize(
    "row",
    [
        "| C-05 | x | x |  | 2026-10-21 | 2027-01-01 |",
        "| C-05 | x | x | Reviewer |  | 2027-01-01 |",
        "| C-05 | x | x | Reviewer | 2026-10-21 |  |",
    ],
)
def test_incomplete_exception_row_does_not_count(row: str) -> None:
    body = LEGEND + control("C-05", "Gap") + exceptions(row)
    assert len(check_controls(body, approved=True)) == 1


def test_complete_exception_satisfies_gap() -> None:
    row = "| C-05 | x | x | Reviewer | 2026-10-21 | 2027-01-01 |"
    body = LEGEND + control("C-05", "Gap") + exceptions(row)
    assert check_controls(body, approved=True) == []


def test_exception_approved_status_also_needs_its_row() -> None:
    body = LEGEND + control("C-05", "Exception approved") + exceptions()
    assert len(check_controls(body, approved=True)) == 1


def test_exception_for_another_control_does_not_count() -> None:
    row = "| C-06 | x | x | Reviewer | 2026-10-21 | 2027-01-01 |"
    body = LEGEND + control("C-05", "Gap") + exceptions(row)
    assert len(check_controls(body, approved=True)) == 1


def test_unrecognised_status_is_reported() -> None:
    body = LEGEND + control("C-05", "Mostly fine") + exceptions()
    assert check_controls(body, approved=False) == [
        "C-05: unrecognised control status 'Mostly fine'"
    ]


def test_missing_status_row_is_reported() -> None:
    body = (
        LEGEND + "\n### C-05 — Example\n\n| | |\n|---|---|\n| **Requirement** | x |\n"
    )
    assert check_controls(body + exceptions(), approved=False) == [
        "C-05: no status recorded"
    ]


def test_empty_status_cell_is_reported() -> None:
    body = LEGEND + control("C-05", "") + exceptions()
    assert check_controls(body, approved=False) == ["C-05: no status recorded"]


def test_draft_with_gaps_passes() -> None:
    body = LEGEND + control("C-05", "Gap") + exceptions()
    assert check_controls(body, approved=False) == []


def test_template_itself_passes_as_draft() -> None:
    # The template's placeholder heading is "C-NN", not a control ID, so it is not assessed.
    text = (REPO_ROOT / "design" / "_template" / "controls-check.md").read_text(
        encoding="utf-8"
    )
    assert check_controls(text.split("---", 2)[2], approved=False) == []
