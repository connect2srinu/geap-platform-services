"""Shared helpers for repository validation scripts.

Standard library plus PyYAML and jsonschema only (scripts/requirements.txt), so that these run
in CI and on a developer machine without a project environment.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def require_deps() -> tuple[Any, Any]:
    """Import PyYAML and jsonschema, or exit with an actionable message."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        sys.exit(
            f"{RED}error{RESET}: PyYAML is not installed.\n"
            f"  Install the validation dependencies:\n"
            f"    make deps\n"
            f"  (creates .venv; the system Python is externally managed on Debian/Ubuntu)"
        )
    try:
        import jsonschema  # noqa: PLC0415
    except ImportError:
        sys.exit(
            f"{RED}error{RESET}: jsonschema is not installed.\n"
            f"  Install the validation dependencies:\n"
            f"    make deps\n"
            f"  (creates .venv; the system Python is externally managed on Debian/Ubuntu)"
        )
    return yaml, jsonschema


class Report:
    """Collects findings and renders a consistent pass/fail summary."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks = 0

    def ok(self) -> None:
        self.checks += 1

    def error(self, where: str, message: str) -> None:
        self.checks += 1
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")

    def finish(self) -> int:
        print(f"\n{self.title}")
        print("-" * len(self.title))
        for w in self.warnings:
            print(f"{YELLOW}warning{RESET} {w}")
        for e in self.errors:
            print(f"{RED}error{RESET}   {e}")
        passed = self.checks - len(self.errors)
        if self.errors:
            print(f"\n{RED}FAILED{RESET}  {passed}/{self.checks} checks passed, "
                  f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)")
            return 1
        print(f"\n{GREEN}PASSED{RESET}  {self.checks} checks, {len(self.warnings)} warning(s)")
        return 0


def parse_front_matter(path: Path, yaml_mod: Any) -> tuple[dict[str, Any] | None, str]:
    """Split a Markdown file into (front matter dict, body). Returns (None, body) if absent."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    raw = text[4:end]
    body = text[end + 5:]
    try:
        data = yaml_mod.safe_load(raw)
    except Exception:
        return None, body
    if not isinstance(data, dict):
        return None, body
    # YAML parses unquoted ISO dates into date objects. The schema expects strings, and
    # requiring authors to quote every date is a trap, so normalise here instead.
    for key, value in list(data.items()):
        if isinstance(value, (datetime.date, datetime.datetime)):
            data[key] = value.isoformat()
    return data, body
