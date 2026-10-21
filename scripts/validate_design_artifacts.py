#!/usr/bin/env python3
"""Validate SDLC design artifacts.

Checks what a machine can check: that artifacts exist, carry well-formed front matter, use the
required evidence vocabulary, are internally consistent, and do not claim approval improperly.

It CANNOT check that a human actually read or approved anything. That is GitHub required reviews
and CODEOWNERS -- see docs/operations/repository-administration.md.

Usage:
    python3 scripts/validate_design_artifacts.py [design/NNN-slug ...]

With no arguments, validates every design folder.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, Report, parse_front_matter, require_deps  # noqa: E402

yaml, jsonschema = require_deps()

SCHEMA_PATH = REPO_ROOT / "schemas" / "design-artifacts.schema.json"
FULL_TRACK = ["intent.md", "design.md", "controls-check.md", "tasks.md"]
EVIDENCE_LABELS = {"VERIFIED", "PROPOSED", "OPEN", "ASSUMPTION"}
AI_APPROVERS = re.compile(r"\b(claude|gpt|copilot|codex|gemini|ai agent|assistant)\b", re.I)
CONTROL_STATUSES = {
    "Verified",
    "Implemented, not verified",
    "Gap",
    "Not applicable",
    "Exception approved",
}


def folder_track(folder: Path) -> str:
    return "light" if (folder / "change.md").is_file() else "full"


def validate_folder(folder: Path, schema: dict, report: Report) -> None:
    rel = folder.relative_to(REPO_ROOT)
    if not re.fullmatch(r"[0-9]{3}-[a-z][a-z0-9-]*", folder.name):
        report.error(str(rel), "folder name must match NNN-slug (lowercase, kebab-case)")
        return
    report.ok()

    track = folder_track(folder)
    expected = ["change.md"] if track == "light" else FULL_TRACK

    present = [p.name for p in folder.iterdir() if p.is_file() and p.suffix == ".md"]
    if not present:
        report.error(str(rel), "contains no Markdown artifacts")
        return

    # Required artifacts for the track. intent.md alone is a legitimate in-progress state.
    if track == "full" and "intent.md" not in present:
        report.error(str(rel), "full track requires intent.md")
    else:
        report.ok()

    statuses: dict[str, str] = {}

    for name in present:
        path = folder / name
        artifact_rel = f"{rel}/{name}"
        fm, body = parse_front_matter(path, yaml)

        if name not in expected and name not in FULL_TRACK + ["change.md", "closeout.md"]:
            report.warn(artifact_rel, "not a recognised artifact name; it will not be validated")
            continue

        if fm is None:
            report.error(artifact_rel, "missing or malformed YAML front matter")
            continue
        report.ok()

        try:
            jsonschema.validate(fm, schema)
            report.ok()
        except jsonschema.ValidationError as exc:
            loc = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            report.error(artifact_rel, f"front matter invalid at {loc}: {exc.message}")
            continue

        if fm.get("feature") != folder.name:
            report.error(
                artifact_rel,
                f"front matter feature '{fm.get('feature')}' does not match folder '{folder.name}'",
            )
        else:
            report.ok()

        if fm.get("track") != track:
            report.error(
                artifact_rel,
                f"front matter track '{fm.get('track')}' but folder looks like '{track}' track",
            )
        else:
            report.ok()

        statuses[name] = fm.get("status", "draft")

        approver = str(fm.get("approved_by", ""))
        if approver and AI_APPROVERS.search(approver):
            report.error(
                artifact_rel,
                f"approved_by '{approver}' looks like an AI agent; a human must approve a gate",
            )
        else:
            report.ok()

        if body.strip().count("TODO") and fm.get("status") == "approved":
            report.error(artifact_rel, "marked approved but still contains TODO")
        else:
            report.ok()

        used = {m for m in re.findall(r"\b[A-Z]{4,10}\b", body) if m in EVIDENCE_LABELS}
        if name in ("design.md", "intent.md", "change.md") and not used:
            report.warn(
                artifact_rel,
                "uses none of VERIFIED/PROPOSED/OPEN/ASSUMPTION "
                "(.claude/rules/evidence-and-claims.md)",
            )

    # Gate ordering: a later artifact cannot be approved before an earlier one.
    order = [a for a in FULL_TRACK if a in statuses]
    for i, name in enumerate(order):
        if statuses[name] != "approved":
            continue
        for earlier in order[:i]:
            if statuses[earlier] != "approved":
                report.error(
                    f"{rel}/{name}",
                    f"approved while {earlier} is '{statuses[earlier]}' -- gates are ordered",
                )
                break
        else:
            report.ok()

    # Controls: no undisclosed gap, and only recognised status values.
    controls = folder / "controls-check.md"
    if controls.is_file():
        text = controls.read_text(encoding="utf-8")
        fm, _ = parse_front_matter(controls, yaml)
        declared = set(re.findall(r"\|\s*(Verified|Implemented, not verified|Gap|Not applicable|Exception approved)\s*\|", text))
        unknown = set(re.findall(r"\*\*Status:\*\*\s*([A-Za-z, ]+)", text)) - CONTROL_STATUSES
        for u in sorted(unknown):
            report.error(f"{rel}/controls-check.md", f"unrecognised control status '{u.strip()}'")
        if not unknown:
            report.ok()
        if "Gap" in declared and (fm or {}).get("status") == "approved":
            if "Exception approved" not in text:
                report.error(
                    f"{rel}/controls-check.md",
                    "approved with a 'Gap' status and no approved exception recorded",
                )
            else:
                report.ok()
        else:
            report.ok()


def main(argv: list[str]) -> int:
    import json  # noqa: PLC0415

    if not SCHEMA_PATH.is_file():
        sys.exit(f"error: schema not found at {SCHEMA_PATH}")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    if argv:
        folders = [Path(a).resolve() for a in argv]
    else:
        design = REPO_ROOT / "design"
        folders = sorted(
            p for p in design.iterdir() if p.is_dir() and not p.name.startswith("_")
        ) if design.is_dir() else []

    report = Report("Design artifact validation")
    if not folders:
        print("No design folders found; nothing to validate.")
        return 0
    for folder in folders:
        if not folder.is_dir():
            report.error(str(folder), "not a directory")
            continue
        validate_folder(folder, schema, report)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
