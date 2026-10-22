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
AI_APPROVERS = re.compile(
    r"\b(claude|gpt|copilot|codex|gemini|ai agent|assistant)\b", re.I
)
APPROVAL_FIELDS = ("approved_by", "approved_date")
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
        report.error(
            str(rel), "folder name must match NNN-slug (lowercase, kebab-case)"
        )
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

        if name not in expected and name not in FULL_TRACK + [
            "change.md",
            "closeout.md",
        ]:
            report.warn(
                artifact_rel, "not a recognised artifact name; it will not be validated"
            )
            continue

        if fm is None:
            report.error(artifact_rel, "missing or malformed YAML front matter")
            continue
        report.ok()

        try:
            # Without a format checker jsonschema treats `format` as an annotation, so
            # `approved_date: 10/21/2026` passed `format: date`.
            jsonschema.validate(fm, schema, format_checker=jsonschema.FormatChecker())
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

        # Light track: Gate A is recorded in the PR description and Gate E as a GitHub review
        # (.claude/rules/sdlc-gates.md). change.md's status is not a gate record, so an approval
        # here would be a second record that can disagree with the first.
        if name == "change.md":
            if fm.get("status") == "approved" or any(k in fm for k in APPROVAL_FIELDS):
                report.error(
                    artifact_rel,
                    "change.md records no gate approval: on the light track Gate A is in the PR "
                    "description and Gate E is a GitHub review (.claude/rules/sdlc-gates.md); "
                    "do not set status 'approved', approved_by or approved_date here",
                )
            else:
                report.ok()

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
        fm, body = parse_front_matter(controls, yaml)
        problems = check_controls(body, approved=(fm or {}).get("status") == "approved")
        for problem in problems:
            report.error(f"{rel}/controls-check.md", problem)
        if not problems:
            report.ok()


def check_controls(body: str, approved: bool) -> list[str]:
    """Return the problems in a controls-check body.

    Statuses are read from each control's own `### C-NN` section, never from the status legend or
    the summary table: both always contain every status name, which is how an earlier version of
    this check was satisfied by the template text alone.
    """
    problems: list[str] = []
    for control, status in control_statuses(body).items():
        if status is None:
            problems.append(f"{control}: no status recorded")
        elif status not in CONTROL_STATUSES:
            problems.append(f"{control}: unrecognised control status '{status}'")
        elif approved and status in ("Gap", "Exception approved"):
            if control not in approved_exceptions(body):
                problems.append(
                    f"{control}: approved with status '{status}' and no approved exception "
                    "(approver, date and expiry) recorded"
                )
    return problems


def control_statuses(body: str) -> dict[str, str | None]:
    sections = re.finditer(r"^### (C-\d{2})\b.*?(?=^#{1,3} |\Z)", body, re.M | re.S)
    statuses: dict[str, str | None] = {}
    for section in sections:
        row = re.search(
            r"^\|\s*\*\*Status\*\*\s*\|\s*([^|]*?)\s*\|", section.group(0), re.M
        )
        statuses[section.group(1)] = (row.group(1) or None) if row else None
    return statuses


def approved_exceptions(body: str) -> set[str]:
    """Controls with a complete row in the `## Approved exceptions` table.

    Columns: Control | Exception | Compensating control | Approver | Date | Expires. A row counts
    only when approver, date and expiry are all filled -- an exception with no owner or end date
    is not an exception.
    """
    section = re.search(
        r"^## Approved exceptions[ \t]*$(.*?)(?=^#{1,2} |\Z)", body, re.M | re.S
    )
    if not section:
        return set()
    found: set[str] = set()
    for row in re.findall(r"^\|(.*)\|[ \t]*$", section.group(1), re.M):
        cells = [c.strip() for c in row.split("|")]
        if len(cells) >= 6 and re.fullmatch(r"C-\d{2}", cells[0]) and all(cells[3:6]):
            found.add(cells[0])
    return found


def main(argv: list[str]) -> int:
    import json  # noqa: PLC0415

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
