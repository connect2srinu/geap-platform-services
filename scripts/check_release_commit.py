#!/usr/bin/env python3
"""Verify that a release-track change touches metadata and notes only.

A release commit bumps a version and writes release notes. If it also changes src/, contracts/,
tests/ or conformance/, it is a feature pretending to be a release -- and it would publish code
that never went through Gates A-D.

    python3 scripts/check_release_commit.py --base origin/main
    python3 scripts/check_release_commit.py --files <path> [<path> ...]

Exits non-zero when a release-track change touches forbidden paths. Exits 0 when the change is
not a release at all (no pattern.yaml version bump), since the normal tracks apply then.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, Report  # noqa: E402

# Paths a release-track change may touch.
ALLOWED = [
    re.compile(r"^patterns/[^/]+/pattern\.yaml$"),
    re.compile(r"^patterns/[^/]+/CHANGELOG\.md$"),
    re.compile(r"^patterns/[^/]+/docs/upgrade\.md$"),
    re.compile(r"^patterns/[^/]+/README\.md$"),
    re.compile(r"^docs/releases/.+\.md$"),
    re.compile(r"^README\.md$"),
]

# Paths that are frozen by the preceding feature work.
FROZEN = re.compile(
    r"^patterns/[^/]+/(src|contracts|tests|conformance|extensions|config)/"
)


def changed_files(base: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        sys.exit(f"error: git diff failed: {exc.stderr.strip()}")
    return [line for line in out.stdout.splitlines() if line.strip()]


def is_release_change(files: list[str], base: str | None) -> bool:
    """A release is identified by a version bump in some pattern.yaml."""
    manifests = [f for f in files if re.fullmatch(r"patterns/[^/]+/pattern\.yaml", f)]
    if not manifests:
        return False
    if base is None:
        return True
    for manifest in manifests:
        try:
            diff = subprocess.run(
                ["git", "diff", f"{base}...HEAD", "--", manifest],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        except subprocess.CalledProcessError:
            return True
        if re.search(r"^\+\s+version:\s", diff, re.MULTILINE):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Base ref to diff against, e.g. origin/main")
    parser.add_argument(
        "--files", nargs="*", help="Explicit file list instead of a git diff"
    )
    args = parser.parse_args()

    if args.files is not None:
        files, base = args.files, None
    elif args.base:
        files, base = changed_files(args.base), args.base
    else:
        parser.error("pass --base <ref> or --files <path> ...")

    report = Report("Release commit check")

    if not files:
        print("No changed files; nothing to check.")
        return 0

    if not is_release_change(files, base):
        print(
            "Not a release-track change (no pattern.yaml version bump).\n"
            "The full or light track applies; this check does not."
        )
        return 0

    print(f"Release-track change detected across {len(files)} file(s).\n")

    for f in files:
        if FROZEN.search(f):
            report.error(
                f,
                "frozen by the preceding feature work -- a release must not change "
                "src/contracts/tests/conformance/extensions/config "
                "(.claude/rules/sdlc-gates.md, release track)",
            )
        elif any(p.match(f) for p in ALLOWED):
            report.ok()
        else:
            report.warn(
                f,
                "not a recognised release-track path; confirm it belongs in a release",
            )

    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
