#!/usr/bin/env python3
"""Validate design artifacts: two documents per feature, nothing else.

Checks what a machine can check — the documents exist, their front matter is well formed, the
design is not approved before the intent, and nobody has recorded an AI as the approver.

It CANNOT check that a human read anything. That is the pull-request review.

    python3 scripts/validate_design_artifacts.py [design/NNN-slug ...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, Report, parse_front_matter, require_deps  # noqa: E402

yaml, jsonschema = require_deps()

SCHEMA_PATH = REPO_ROOT / "schemas" / "design-artifacts.schema.json"
ORDER = ["intent.md", "design.md"]
LABELS = {"VERIFIED", "ASSUMPTION", "OPEN"}
AI_APPROVERS = re.compile(
    r"\b(claude|gpt|copilot|codex|gemini|ai agent|assistant)\b", re.I
)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _rel(folder: Path) -> str:
    """Display path, tolerating a folder outside the repository (tests use tmp dirs)."""
    try:
        return str(folder.relative_to(REPO_ROOT))
    except ValueError:
        return str(folder)


def validate_folder(folder: Path, schema: dict, report: Report) -> None:
    rel = _rel(folder)

    if not re.fullmatch(r"[0-9]{3}-[a-z][a-z0-9-]*", folder.name):
        report.error(str(rel), "folder name must be NNN-slug, lowercase kebab-case")
        return
    report.ok()

    present = [p.name for p in folder.iterdir() if p.is_file() and p.suffix == ".md"]
    extra = sorted(set(present) - set(ORDER))
    if extra:
        report.warn(
            str(rel),
            f"not validated (only intent.md and design.md are): {', '.join(extra)}",
        )

    if "intent.md" not in present:
        report.error(str(rel), "intent.md is required")
        return
    report.ok()

    statuses: dict[str, str] = {}

    for name in ORDER:
        if name not in present:
            continue
        path, where = folder / name, f"{rel}/{name}"
        fm, body = parse_front_matter(path, yaml)

        if fm is None:
            report.error(where, "missing or malformed YAML front matter")
            continue
        report.ok()

        try:
            jsonschema.validate(fm, schema, format_checker=jsonschema.FormatChecker())
            report.ok()
        except jsonschema.ValidationError as exc:
            loc = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            report.error(where, f"front matter invalid at {loc}: {exc.message}")
            continue

        if fm.get("feature") != folder.name:
            report.error(
                where,
                f"feature '{fm.get('feature')}' does not match folder '{folder.name}'",
            )
        else:
            report.ok()

        statuses[name] = fm.get("status", "draft")

        approver = str(fm.get("approved_by", ""))
        if approver and AI_APPROVERS.search(approver):
            report.error(
                where, f"approved_by '{approver}' is an AI; a human must approve"
            )
        else:
            report.ok()

        date = str(fm.get("approved_date", ""))
        if date and not ISO_DATE.match(date):
            report.error(where, f"approved_date '{date}' must be ISO 8601 (YYYY-MM-DD)")
        else:
            report.ok()

        if fm.get("status") == "approved" and "TODO" in body:
            report.error(where, "approved but still contains TODO")
        else:
            report.ok()

        if not ({m for m in re.findall(r"\b[A-Z]{4,10}\b", body)} & LABELS):
            report.warn(where, "uses none of VERIFIED / ASSUMPTION / OPEN")

    # The design cannot be approved before the intent it rests on.
    if (
        statuses.get("design.md") == "approved"
        and statuses.get("intent.md") != "approved"
    ):
        report.error(
            f"{rel}/design.md",
            f"approved while intent.md is '{statuses.get('intent.md', 'missing')}'",
        )
    else:
        report.ok()

    # Report the gate state plainly, so a green run is never mistaken for an approval.
    if statuses.get("intent.md") != "approved":
        state = "awaiting approval of intent.md"
    elif "design.md" not in present:
        state = "intent approved - design.md not written yet"
    elif statuses.get("design.md") != "approved":
        state = "awaiting approval of design.md"
    else:
        state = "both approved - implementation may proceed"
    print(f"  {rel}: {state}")


def main(argv: list[str]) -> int:
    if not SCHEMA_PATH.is_file():
        sys.exit(f"error: schema not found at {SCHEMA_PATH}")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    if argv:
        folders = [Path(a).resolve() for a in argv]
    else:
        design = REPO_ROOT / "design"
        folders = (
            sorted(
                p for p in design.iterdir() if p.is_dir() and not p.name.startswith("_")
            )
            if design.is_dir()
            else []
        )

    report = Report("Design artifacts")
    if not folders:
        print("No design folders; nothing to validate.")
        return 0
    for folder in folders:
        if folder.is_dir():
            validate_folder(folder, schema, report)
        else:
            report.error(str(folder), "not a directory")
    return report.finish()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
