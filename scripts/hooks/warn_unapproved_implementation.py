#!/usr/bin/env python3
"""PreToolUse advisory hook: warn when pattern implementation code is edited without an
approved design.

This is ERGONOMICS, NOT ENFORCEMENT. It always exits 0 so it can never block legitimate work
and can never be mistaken for a control. Real enforcement is CI, branch protection and
CODEOWNERS -- see standards/pattern-contract.md.

Reads the Claude Code hook payload on stdin; writes a short note to stderr when relevant.
Any unexpected condition exits 0 silently: a broken advisory hook must not break the session.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WATCHED = re.compile(r"patterns/[^/]+/src/")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input") or {}
    target = tool_input.get("file_path") or ""
    if not target or not WATCHED.search(target.replace("\\", "/")):
        return 0

    project_dir = Path(payload.get("cwd") or ".")
    design_root = project_dir / "design"
    if not design_root.is_dir():
        return 0

    approved: list[str] = []
    pending: list[str] = []
    for folder in sorted(design_root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        for name in ("design.md", "change.md"):
            artifact = folder / name
            if not artifact.is_file():
                continue
            try:
                head = artifact.read_text(encoding="utf-8")[:600]
            except Exception:
                continue
            if re.search(r"^status:\s*approved\s*$", head, re.MULTILINE):
                approved.append(folder.name)
            else:
                pending.append(folder.name)

    if approved:
        return 0

    note = (
        "ADVISORY: editing pattern implementation code and no design/*/design.md is marked "
        "'status: approved'.\n"
        "  Gate B (design) and Gate D (task plan) precede implementation -- "
        ".claude/rules/sdlc-gates.md\n"
    )
    if pending:
        note += f"  Unapproved design folders found: {', '.join(pending)}\n"
    note += "  This hook does not block. It is not a control.\n"
    sys.stderr.write(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
