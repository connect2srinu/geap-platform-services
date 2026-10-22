#!/usr/bin/env python3
"""Vendor the pinned platform pattern into vendor/pattern/.

Downloads the release tarball named by pattern.lock.yaml, verifies its checksum against the
published SHA256SUMS, extracts it, and records the manifest digest back into the lock file.

    python3 scripts/vendor_pattern.py            # vendor the pinned version
    python3 scripts/vendor_pattern.py --check    # verify what is vendored, change nothing

Vendoring rather than forking is deliberate: you receive only the pattern, your own code stays
outside vendor/, and an upgrade is a directory swap instead of a monorepo merge.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
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
VENDOR = ROOT / "vendor" / "pattern"


def load_lock() -> dict:
    if not LOCK.is_file():
        sys.exit(f"error: {LOCK.name} not found")
    data = yaml.safe_load(LOCK.read_text(encoding="utf-8"))
    lock = data.get("pattern") if isinstance(data, dict) else None
    if not isinstance(lock, dict):
        sys.exit(f"error: {LOCK.name} has no 'pattern:' block")
    for key in ("name", "version", "source", "tag"):
        if not lock.get(key) or str(lock[key]).startswith("<"):
            sys.exit(f"error: {LOCK.name} field '{key}' is not filled in")
    return lock


def download(lock: dict, into: Path) -> Path:
    """Fetch the release assets with gh, which already holds the repository credentials."""
    repo = str(lock["source"]).removeprefix("https://github.com/").removesuffix(".git")
    tag = str(lock["tag"])
    print(f"Downloading {tag} from {repo}")
    try:
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                tag,
                "--repo",
                repo,
                "--dir",
                str(into),
                "--pattern",
                "*.tar.gz",
                "--pattern",
                "SHA256SUMS",
            ],
            check=True,
        )
    except FileNotFoundError:
        sys.exit("error: the GitHub CLI (gh) is required to download a pattern release")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"error: could not download {tag}: exit {exc.returncode}")

    archives = sorted(into.glob("*.tar.gz"))
    if len(archives) != 1:
        sys.exit(
            f"error: expected exactly one tarball in the release, found {len(archives)}"
        )
    return archives[0]


def verify_checksum(archive: Path, sums: Path) -> None:
    """A published checksum is worth nothing unless it is actually checked."""
    if not sums.is_file():
        sys.exit(
            "error: SHA256SUMS not published with this release — refusing to vendor unverified source"
        )
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected = None
    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and Path(parts[1]).name == archive.name:
            expected = parts[0]
            break
    if expected is None:
        sys.exit(f"error: SHA256SUMS has no entry for {archive.name}")
    if actual != expected:
        sys.exit(
            f"error: checksum mismatch for {archive.name}\n"
            f"  expected {expected}\n  actual   {actual}\n"
            "  Do not use this download."
        )
    print(f"checksum verified: {archive.name}")


def extract(archive: Path, name: str) -> None:
    if VENDOR.exists():
        shutil.rmtree(VENDOR)
    VENDOR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp)
        with tarfile.open(archive) as tar:
            # The tarball is published by the platform team, but extraction still refuses
            # paths that escape the staging directory.
            for member in tar.getmembers():
                target = (staged / member.name).resolve()
                if not str(target).startswith(str(staged.resolve())):
                    sys.exit(
                        f"error: archive member escapes the extraction directory: {member.name}"
                    )
            tar.extractall(staged, filter="data")
        inner = staged / name
        if not inner.is_dir():
            sys.exit(f"error: the tarball does not contain a '{name}/' directory")
        shutil.copytree(inner, VENDOR)
    print(f"vendored into {VENDOR.relative_to(ROOT)}")


def record_digest(lock: dict) -> None:
    manifest = VENDOR / "pattern.yaml"
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    text = LOCK.read_text(encoding="utf-8")
    if "manifestDigest:" in text:
        import re

        text = re.sub(r"(manifestDigest:\s*).*", rf"\g<1>{digest}", text, count=1)
    else:
        text = text.rstrip("\n") + f"\n  manifestDigest: {digest}\n"
    LOCK.write_text(text, encoding="utf-8")
    print(f"recorded manifest digest {digest[:16]}…")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="verify only; change nothing"
    )
    args = parser.parse_args()

    lock = load_lock()

    if args.check:
        return subprocess.call(
            [sys.executable, str(ROOT / "scripts" / "verify_pattern_lock.py")]
        )

    with tempfile.TemporaryDirectory() as tmp:
        into = Path(tmp)
        archive = download(lock, into)
        verify_checksum(archive, into / "SHA256SUMS")
        extract(archive, str(lock["name"]))

    record_digest(lock)
    print(
        f"\n{lock['name']} v{lock['version']} vendored.\n"
        "  Your code stays outside vendor/. Do not edit the vendored pattern:\n"
        "  scripts/verify_pattern_lock.py fails the build when it drifts."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
