#!/usr/bin/env python3
"""Verify the vendored pattern matches pattern.lock.yaml.

Run in the domain's CI. Detects a vendored pattern that has been edited locally or a lock
file that no longer matches what is vendored -- either of which silently breaks the
contract the domain agreed to.

Exits non-zero on drift.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit(
        "error: PyYAML is required.\n"
        "  python3 -m venv .venv && .venv/bin/python -m pip install -r scripts/requirements.txt\n"
        "  then run this with .venv/bin/python"
    )

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "pattern.lock.yaml"
VENDORED_MANIFEST = ROOT / "vendor" / "pattern" / "pattern.yaml"


def main() -> int:
    if not LOCK.is_file():
        print("error: pattern.lock.yaml not found")
        return 1
    if not VENDORED_MANIFEST.is_file():
        print(
            "error: vendor/pattern/pattern.yaml not found -- run scripts/vendor_pattern.py"
        )
        return 1

    lock = yaml.safe_load(LOCK.read_text(encoding="utf-8"))["pattern"]
    expected_version = str(lock["version"])
    expected_digest = str(lock["manifestDigest"])

    raw = VENDORED_MANIFEST.read_bytes()
    actual_digest = hashlib.sha256(raw).hexdigest()
    manifest = yaml.safe_load(raw.decode("utf-8"))
    actual_version = str(manifest["metadata"]["version"])

    failures = []
    if actual_version != expected_version:
        failures.append(
            f"version mismatch: lock says {expected_version}, vendored pattern is {actual_version}"
        )
    if expected_digest not in ("<sha256>", "") and actual_digest != expected_digest:
        failures.append(
            "manifest digest mismatch: the vendored pattern.yaml has been modified.\n"
            f"  expected {expected_digest}\n  actual   {actual_digest}"
        )

    if failures:
        print("Pattern lock verification FAILED:")
        for f in failures:
            print(f"  - {f}")
        print("\nIf the change was intentional, use the pattern-upgrade workflow.")
        return 1

    print(f"Pattern lock verified: {lock['name']} v{actual_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
