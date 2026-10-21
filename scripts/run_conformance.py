#!/usr/bin/env python3
"""Run a pattern's conformance suite against a running deployment.

Domain teams run this in THEIR OWN CI against THEIR OWN build. It is the mechanism by which a
domain demonstrates that its customized deployment still honours the pattern contract and the
mandatory controls.

    python3 scripts/run_conformance.py --pattern memory-manager --base-url https://<host>

The platform cannot observe whether a domain runs this. See standards/pattern-contract.md on
the limits of enforcement.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, RED, RESET, YELLOW  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", required=True, help="Pattern name, e.g. memory-manager")
    parser.add_argument("--base-url", help="Base URL of the deployment under test")
    parser.add_argument("--list", action="store_true", help="List the suite without running it")
    args = parser.parse_args()

    suite = REPO_ROOT / "patterns" / args.pattern / "conformance"
    if not suite.is_dir():
        print(f"{RED}error{RESET}: no conformance suite at {suite}")
        return 2

    tests = sorted(suite.glob("test_*.py"))
    if not tests:
        print(
            f"{YELLOW}unavailable{RESET}: the conformance suite at "
            f"{suite.relative_to(REPO_ROOT)} is empty.\n"
            f"  The pattern's design is not yet approved, so no conformance tests exist.\n"
            f"  This is NOT a pass -- there is nothing to run."
        )
        return 3

    if args.list:
        for t in tests:
            print(t.relative_to(REPO_ROOT))
        return 0

    if not args.base_url:
        print(f"{RED}error{RESET}: --base-url is required to run the suite")
        return 2

    cmd = [sys.executable, "-m", "pytest", "-q", str(suite)]
    print(f"Running: {' '.join(cmd)}  (target {args.base_url})")
    try:
        return subprocess.call(cmd, env={"CONFORMANCE_BASE_URL": args.base_url, "PATH": "/usr/bin:/bin"})
    except FileNotFoundError:
        print(f"{YELLOW}unavailable{RESET}: pytest is not installed")
        return 3


if __name__ == "__main__":
    sys.exit(main())
