"""A light-track change.md carries no gate approval.

On the light track Gate A is recorded in the PR description and Gate E as a GitHub review
(.claude/rules/sdlc-gates.md). An approval in change.md's front matter would be a second record that
can disagree with the first, so the validator rejects it.
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


def validate_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: str
) -> list[str]:
    folder = tmp_path / "design" / "900-example"
    folder.mkdir(parents=True)
    (folder / "change.md").write_text(
        "---\n"
        "artifact: change\n"
        "feature: 900-example\n"
        "track: light\n"
        f"{extra}"
        "---\n\n# Change\n\nVERIFIED by reading.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vda, "REPO_ROOT", tmp_path)
    report = Report("test")
    vda.validate_folder(folder, SCHEMA, report)
    return report.errors


@pytest.mark.parametrize("status", ["draft", "in-review", "superseded"])
def test_unapproved_status_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    assert validate_change(tmp_path, monkeypatch, f"status: {status}\n") == []


@pytest.mark.parametrize(
    "extra",
    [
        "status: approved\napproved_by: Example Reviewer\napproved_date: 2026-10-21\n",
        "status: draft\napproved_by: Example Reviewer\n",
        "status: draft\napproved_date: 2026-10-21\n",
    ],
)
def test_approval_in_change_md_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: str
) -> None:
    errors = validate_change(tmp_path, monkeypatch, extra)
    assert len(errors) == 1
    assert "change.md records no gate approval" in errors[0]


def test_template_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    template = (REPO_ROOT / "design" / "_template" / "change.md").read_text(
        encoding="utf-8"
    )
    folder = tmp_path / "design" / "900-example"
    folder.mkdir(parents=True)
    (folder / "change.md").write_text(
        template.replace("feature: NNN-slug", "feature: 900-example"), encoding="utf-8"
    )
    monkeypatch.setattr(vda, "REPO_ROOT", tmp_path)
    report = Report("test")
    vda.validate_folder(folder, SCHEMA, report)
    assert report.errors == []
