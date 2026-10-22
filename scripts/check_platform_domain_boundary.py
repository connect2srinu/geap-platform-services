#!/usr/bin/env python3
"""Structural checks on the platform/domain boundary and the layering rules.

Catches the failure modes that matter most in a reusable pattern:
  1. Business-domain names hardcoded in reusable pattern source.
  2. Real enterprise identifiers in code, manifests, templates or examples.
  3. Layering violations (providers importing api, src importing extension implementations).
  4. Primitive IAM roles anywhere in Terraform or manifests.

This runs against THIS repository. A fork can delete it -- see standards/pattern-contract.md
on the limits of enforcement.

Usage:
    python3 scripts/check_platform_domain_boundary.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, Report  # noqa: E402

# Business domains that must never be hardcoded into reusable pattern code.
DOMAIN_NAMES = re.compile(
    r"\b(customer|inventory|manufacturing|supply[_ -]?chain)\b", re.I
)
# Real enterprise identifiers that must not appear anywhere in published assets.
ENTERPRISE_IDENTIFIERS = re.compile(r"\b(kroger|cooklist|ksa)\b", re.I)
PRIMITIVE_ROLES = re.compile(r"roles/(owner|editor|viewer)\b")

SCAN_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".tf", ".md", ".sh", ".toml"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".terraform",
    "design",
    "docs",
}


def iter_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix in SCAN_EXTENSIONS:
            out.append(p)
    return out


def main() -> int:
    report = Report("Platform/domain boundary checks")

    patterns_dir = REPO_ROOT / "patterns"
    templates_dir = REPO_ROOT / "templates"

    # 1. No business-domain names in reusable pattern source.
    if patterns_dir.is_dir():
        for path in iter_files(patterns_dir):
            rel = path.relative_to(REPO_ROOT)
            parts = rel.parts
            in_source = len(parts) > 2 and parts[2] in (
                "src",
                "contracts",
                "extensions",
            )
            if not in_source or path.suffix == ".md":
                continue
            for i, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                if line.lstrip().startswith("#"):
                    continue
                if DOMAIN_NAMES.search(line):
                    report.error(
                        f"{rel}:{i}",
                        "business-domain name in reusable pattern code "
                        "(.claude/rules/platform-vs-domain.md)",
                    )
        report.ok()

    # 2. No real enterprise identifiers in published assets.
    for root in (patterns_dir, templates_dir, REPO_ROOT / "schemas"):
        if not root.is_dir():
            continue
        for path in iter_files(root):
            rel = path.relative_to(REPO_ROOT)
            for i, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                if ENTERPRISE_IDENTIFIERS.search(line):
                    report.error(
                        f"{rel}:{i}",
                        "real enterprise identifier in a published asset; use a neutral placeholder",
                    )
    report.ok()

    # 3. Layering: providers must not import api; src must not import extension implementations.
    if patterns_dir.is_dir():
        for path in patterns_dir.rglob("src/**/*.py"):
            rel = path.relative_to(REPO_ROOT)
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "providers" in path.parts and re.search(
                r"^\s*from\s+\S*\bapi\b", text, re.M
            ):
                report.error(
                    str(rel),
                    "providers/ imports api/ -- dependencies point downward only",
                )
            if (
                re.search(r"^\s*from\s+extensions\.", text, re.M)
                and "dispatch" not in path.name
            ):
                report.error(
                    str(rel),
                    "src/ imports an extension implementation directly; only the dispatcher may",
                )
    report.ok()

    # 4. No primitive IAM roles.
    for root in (patterns_dir, templates_dir):
        if not root.is_dir():
            continue
        for path in iter_files(root):
            if path.suffix not in {".tf", ".yaml", ".yml", ".json"}:
                continue
            rel = path.relative_to(REPO_ROOT)
            for i, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                if PRIMITIVE_ROLES.search(line):
                    report.error(
                        f"{rel}:{i}", "primitive IAM role is forbidden (control C-11)"
                    )
    report.ok()

    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
