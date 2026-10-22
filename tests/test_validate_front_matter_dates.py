"""`format: date` in the design-artifact schema is enforced, not just annotated.

jsonschema ignores `format` unless a format checker is passed, which let
`approved_date: 10/21/2026` through. These tests run the real `validate_folder` against a temporary
design tree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import validate_design_artifacts as vda  # noqa: E402
from _common import Report  # noqa: E402

SCHEMA = json.loads(vda.SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, approved_date: str
) -> list[str]:
    folder = tmp_path / "design" / "900-example"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text(
        "---\n"
        "artifact: intent\n"
        "feature: 900-example\n"
        "track: full\n"
        "status: approved\n"
        "approved_by: Example Reviewer\n"
        f"approved_date: {approved_date}\n"
        "---\n\n# Intent\n\nVERIFIED by reading.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vda, "REPO_ROOT", tmp_path)
    report = Report("test")
    vda.validate_folder(folder, SCHEMA, report)
    return report.errors


@pytest.mark.parametrize("value", ["2026-10-21", '"2026-10-21"'])
def test_iso_date_passes_quoted_or_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    assert validate_intent(tmp_path, monkeypatch, value) == []


@pytest.mark.parametrize("value", ["10/21/2026", '"2026-13-45"', "21 October 2026"])
def test_non_iso_date_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    errors = validate_intent(tmp_path, monkeypatch, value)
    assert len(errors) == 1
    assert "front matter invalid at approved_date" in errors[0]
    assert "is not a 'date'" in errors[0]
