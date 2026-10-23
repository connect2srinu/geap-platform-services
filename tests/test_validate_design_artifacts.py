"""The design-artifact validator must actually refuse the things it claims to refuse.

Each test here fails if the corresponding check is removed from the validator.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate_design_artifacts.py"


def write(
    folder: Path, name: str, front: dict, body: str = "VERIFIED nothing.\n"
) -> None:
    lines = "\n".join(f"{k}: {v}" for k, v in front.items())
    (folder / name).write_text(f"---\n{lines}\n---\n\n# t\n\n{body}", encoding="utf-8")


def run(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(folder)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def approved(**extra: object) -> dict:
    base = {
        "artifact": "intent",
        "feature": "099-probe",
        "status": "approved",
        "approved_by": "A Human",
        "approved_date": "2026-10-22",
    }
    base.update(extra)  # type: ignore[arg-type]
    return base


def test_well_formed_folder_passes(tmp_path: Path) -> None:
    folder = tmp_path / "099-probe"
    folder.mkdir()
    write(folder, "intent.md", approved())
    result = run(folder)
    assert result.returncode == 0, result.stdout


def test_ai_approver_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "099-probe"
    folder.mkdir()
    write(folder, "intent.md", approved(approved_by="Claude"))
    result = run(folder)
    assert result.returncode == 1
    assert "is an AI" in result.stdout


def test_non_iso_date_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "099-probe"
    folder.mkdir()
    write(folder, "intent.md", approved(approved_date="10/22/2026"))
    result = run(folder)
    assert result.returncode == 1
    # Either guard may report first: the schema's format checker or the explicit ISO check.
    assert "ISO 8601" in result.stdout or "is not a 'date'" in result.stdout


def test_design_approved_before_intent_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "099-probe"
    folder.mkdir()
    write(folder, "intent.md", approved(status="draft"))
    write(folder, "design.md", approved(artifact="design"))
    result = run(folder)
    assert result.returncode == 1
    assert "approved while intent.md is 'draft'" in result.stdout


def test_missing_intent_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "099-probe"
    folder.mkdir()
    write(folder, "design.md", approved(artifact="design"))
    result = run(folder)
    assert result.returncode == 1
    assert "intent.md is required" in result.stdout


def test_approved_with_todo_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "099-probe"
    folder.mkdir()
    write(folder, "intent.md", approved(), body="TODO finish this\n")
    result = run(folder)
    assert result.returncode == 1
    assert "TODO" in result.stdout


def test_feature_name_must_match_folder(tmp_path: Path) -> None:
    folder = tmp_path / "099-probe"
    folder.mkdir()
    write(folder, "intent.md", approved(feature="098-other"))
    result = run(folder)
    assert result.returncode == 1
    assert "does not match folder" in result.stdout


def test_schema_is_valid_json() -> None:
    schema = json.loads(
        (REPO_ROOT / "schemas" / "design-artifacts.schema.json").read_text()
    )
    assert schema["properties"]["artifact"]["enum"] == ["intent", "design"]
    assert "track" not in schema["properties"]
