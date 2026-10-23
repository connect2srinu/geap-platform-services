#!/usr/bin/env python3
"""Vendor the pinned platform pattern into vendor/pattern/.

    python3 scripts/vendor_pattern.py            # vendor the pinned source
    python3 scripts/vendor_pattern.py --check    # verify what is vendored, change nothing

Vendoring rather than forking is deliberate: you receive only the pattern, your own code stays
outside vendor/, and an upgrade is a directory swap instead of a monorepo merge.

`pattern.lock.yaml` names exactly one source:

  tag:   a published release. The tarball's checksum is verified against the published
         SHA256SUMS. This is what a production adoption uses.
  ref:   a branch, tag or commit in the platform repository, fetched with `git archive`. For
         adopting a pattern that has not been released yet. The resolved **commit** is written
         back to the lock, because two domains can otherwise both claim the same version from
         different commits, and the manifest digest only catches drift within one project.
  path:  a local checkout of the platform repository. For developing against an unreleased
         pattern on one machine. Requires `unreleased: true` in the lock, so a locally modified
         pattern cannot quietly masquerade as a version.

Only `tag:` is checksum-verified — there is no published SHA256SUMS for the other two, and this
script says so rather than implying a verification it did not perform. `verify_pattern_lock.py`
still compares the manifest digest whichever source was used, so an edited `pattern.yaml` fails
either way.
"""

from __future__ import annotations

import argparse
import hashlib
import re
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


#: Exactly one of these names where the pattern comes from.
SOURCES = ("tag", "ref", "path")


def _filled(lock: dict, key: str) -> bool:
    """A placeholder like `<x.y.z>` is not a value; the template ships full of them."""
    value = lock.get(key)
    return bool(value) and not str(value).startswith("<")


def load_lock() -> dict:
    if not LOCK.is_file():
        sys.exit(f"error: {LOCK.name} not found")
    data = yaml.safe_load(LOCK.read_text(encoding="utf-8"))
    lock = data.get("pattern") if isinstance(data, dict) else None
    if not isinstance(lock, dict):
        sys.exit(f"error: {LOCK.name} has no 'pattern:' block")
    for key in ("name", "version", "source"):
        if not _filled(lock, key):
            sys.exit(f"error: {LOCK.name} field '{key}' is not filled in")

    given = [key for key in SOURCES if _filled(lock, key)]
    if not given:
        sys.exit(
            f"error: {LOCK.name} names no source. Set exactly one of: "
            + ", ".join(f"{key}:" for key in SOURCES)
        )
    if len(given) > 1:
        sys.exit(
            f"error: {LOCK.name} names more than one source ({', '.join(given)}); "
            "exactly one of tag:, ref: or path: may be set"
        )

    # An unreleased source is a deliberate, declared choice. Without this, a local checkout could
    # be vendored while the lock still claims a released version.
    if given[0] in ("ref", "path") and lock.get("unreleased") is not True:
        sys.exit(
            f"error: a '{given[0]}:' source is not a published release.\n"
            f"  Add 'unreleased: true' to {LOCK.name} to say so deliberately.\n"
            "  Nothing downstream treats it as released, and pattern-release reports it."
        )

    lock["_source_kind"] = given[0]
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


def archive_from_git(lock: dict, into: Path) -> tuple[Path, str]:
    """Produce the same tree a release tarball would, from a ref or a local checkout.

    VERIFIED 2026-10-23: `git archive <ref> patterns/<name>` reproduces the released tarball's
    tree with a byte-identical pattern.yaml, so the lock's digest check is unaffected. It is also
    cleaner — it takes only what is committed, where the release `tar` takes the runner's working
    tree minus three cache directories.
    """
    name = str(lock["name"])
    kind = lock["_source_kind"]

    if kind == "path":
        repo = Path(str(lock["path"])).expanduser().resolve()
        if not (repo / "patterns" / name).is_dir():
            sys.exit(
                f"error: {repo} does not look like the platform repository: "
                f"no patterns/{name}/ in it"
            )
        ref = "HEAD"
    else:
        repo = into / "clone"
        source = str(lock["source"])
        print(f"Cloning {source}")
        try:
            subprocess.run(
                ["git", "clone", "--quiet", "--filter=blob:none", source, str(repo)],
                check=True,
            )
        except FileNotFoundError:
            sys.exit("error: git is required to vendor from a ref")
        except subprocess.CalledProcessError as exc:
            sys.exit(f"error: could not clone {source}: exit {exc.returncode}")
        ref = str(lock["ref"])

    resolved = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if resolved.returncode != 0:
        sys.exit(f"error: '{ref}' is not a commit in {repo}")
    commit = resolved.stdout.strip()

    archive = into / f"{name}-{commit[:12]}.tar"
    with archive.open("wb") as handle:
        written = subprocess.run(
            ["git", "-C", str(repo), "archive", commit, f"patterns/{name}"],
            stdout=handle,
        )
    if written.returncode != 0:
        sys.exit(f"error: patterns/{name} is not present at {ref}")
    print(f"vendoring {name} from {kind} {ref} at commit {commit[:12]}")
    print("  not checksum-verified: this source is not a published release")
    return archive, commit


def record_commit(commit: str) -> None:
    """Pin the resolved commit, so 'ref: main' cannot mean two different things next week."""
    text = LOCK.read_text(encoding="utf-8")
    if re.search(r"^\s*resolvedCommit:", text, re.M):
        text = re.sub(r"(resolvedCommit:)[ \t]*.*", rf"\g<1> {commit}", text, count=1)
    else:
        text = text.rstrip("\n") + f"\n  resolvedCommit: {commit}\n"
    LOCK.write_text(text, encoding="utf-8")
    print(f"recorded resolved commit {commit[:12]}")


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
        # A release tarball holds `<name>/`; a git archive holds `patterns/<name>/`.
        inner = staged / name
        if not inner.is_dir():
            inner = staged / "patterns" / name
        if not inner.is_dir():
            sys.exit(f"error: the archive does not contain a '{name}/' directory")
        shutil.copytree(inner, VENDOR)
    print(f"vendored into {VENDOR.relative_to(ROOT)}")


def record_digest(lock: dict) -> None:
    manifest = VENDOR / "pattern.yaml"
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    text = LOCK.read_text(encoding="utf-8")
    if "manifestDigest:" in text:
        text = re.sub(r"(manifestDigest:)[ \t]*.*", rf"\g<1> {digest}", text, count=1)
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

    commit = None
    with tempfile.TemporaryDirectory() as tmp:
        into = Path(tmp)
        if lock["_source_kind"] == "tag":
            archive = download(lock, into)
            verify_checksum(archive, into / "SHA256SUMS")
        else:
            archive, commit = archive_from_git(lock, into)
        extract(archive, str(lock["name"]))

    record_digest(lock)
    if commit is not None:
        record_commit(commit)
    print(
        f"\n{lock['name']} v{lock['version']} vendored.\n"
        "  Your code stays outside vendor/. Do not edit the vendored pattern:\n"
        "  scripts/verify_pattern_lock.py fails the build when it drifts."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
