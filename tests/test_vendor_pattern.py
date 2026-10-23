"""The domain consumer's vendoring script.

This is the first step of adopting a pattern, and until 011 it could only succeed against a
published release — which meant it could not succeed at all, because none existed. These tests
cover the two sources that make pre-release adoption a supported path rather than a workaround.

The script is template code a domain copies, so it is exercised by running it as a subprocess in a
throwaway project, exactly as a domain would.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "domain-consumer"
SCRIPT = "scripts/vendor_pattern.py"
PATTERN = "memory-manager"


def _project(tmp_path: Path, lock_body: str) -> Path:
    """A domain project, as `templates/domain-consumer` would produce one."""
    project = tmp_path / "domain-project"
    shutil.copytree(TEMPLATE, project)
    (project / "pattern.lock.yaml").write_text(
        "pattern:\n" + lock_body, encoding="utf-8"
    )
    return project


def _run(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT],
        cwd=project,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def platform_checkout(tmp_path: Path) -> Path:
    """A git repository shaped like the platform repo, holding the real pattern.

    A real clone rather than a stub: the point is that `git archive` produces a usable tree.
    """
    checkout = tmp_path / "platform"
    (checkout / "patterns").mkdir(parents=True)
    shutil.copytree(
        REPO / "patterns" / PATTERN,
        checkout / "patterns" / PATTERN,
        ignore=shutil.ignore_patterns(
            ".venv", "*.egg-info", "build", "__pycache__", ".*_cache", ".terraform"
        ),
    )
    run = lambda *args: subprocess.run(  # noqa: E731
        ["git", "-C", str(checkout), *args], check=True, capture_output=True
    )
    run("init", "--quiet", "--initial-branch", "main")
    run("config", "user.email", "test@example.invalid")
    run("config", "user.name", "Test")
    run("add", "-A")
    run("commit", "--quiet", "-m", "pattern")
    return checkout


# --- a local checkout -------------------------------------------------------------------


def test_a_local_path_vendors_the_pattern(
    tmp_path: Path, platform_checkout: Path
) -> None:
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n"
        f"  version: 0.1.0\n"
        f"  source: https://github.com/example-org/geap-platform-services\n"
        f"  path: {platform_checkout}\n"
        f"  unreleased: true\n"
        f"  manifestDigest:\n",
    )
    result = _run(project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (project / "vendor" / "pattern" / "pattern.yaml").is_file()
    assert (project / "vendor" / "pattern" / "src" / "memory_manager").is_dir()


def test_a_local_path_is_refused_without_the_unreleased_flag(
    tmp_path: Path, platform_checkout: Path
) -> None:
    """Otherwise a modified local checkout vendors while the lock still claims a version."""
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n  version: 0.1.0\n"
        f"  source: https://github.com/example-org/geap-platform-services\n"
        f"  path: {platform_checkout}\n  manifestDigest:\n",
    )
    result = _run(project)
    assert result.returncode != 0
    assert "unreleased: true" in result.stdout + result.stderr


def test_a_path_that_is_not_the_platform_repository_is_refused(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n  version: 0.1.0\n"
        f"  source: https://github.com/example-org/geap-platform-services\n"
        f"  path: {tmp_path}\n  unreleased: true\n  manifestDigest:\n",
    )
    result = _run(project)
    assert result.returncode != 0
    assert "does not look like the platform repository" in result.stdout + result.stderr


# --- a git ref --------------------------------------------------------------------------


def test_a_ref_vendors_and_records_the_resolved_commit(
    tmp_path: Path, platform_checkout: Path
) -> None:
    """`ref: main` must not mean two different things next week, so the commit is pinned."""
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n  version: 0.1.0\n"
        f"  source: {platform_checkout}\n  ref: main\n"
        f"  unreleased: true\n  manifestDigest:\n",
    )
    result = _run(project)
    assert result.returncode == 0, result.stdout + result.stderr

    head = subprocess.run(
        ["git", "-C", str(platform_checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    lock = (project / "pattern.lock.yaml").read_text(encoding="utf-8")
    assert f"resolvedCommit: {head}" in lock


def test_an_unknown_ref_is_refused(tmp_path: Path, platform_checkout: Path) -> None:
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n  version: 0.1.0\n"
        f"  source: {platform_checkout}\n  ref: no-such-branch\n"
        f"  unreleased: true\n  manifestDigest:\n",
    )
    result = _run(project)
    assert result.returncode != 0
    assert not (project / "vendor" / "pattern").exists()


def test_a_ref_vendor_says_it_was_not_checksum_verified(
    tmp_path: Path, platform_checkout: Path
) -> None:
    """Silence here would imply a verification that did not happen."""
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n  version: 0.1.0\n"
        f"  source: {platform_checkout}\n  ref: main\n"
        f"  unreleased: true\n  manifestDigest:\n",
    )
    assert "not checksum-verified" in _run(project).stdout


# --- the lock's own rules ----------------------------------------------------------------


def test_the_vendored_digest_matches_the_source_manifest(
    tmp_path: Path, platform_checkout: Path
) -> None:
    """The digest is what `verify_pattern_lock.py` checks, whatever the source was."""
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n  version: 0.1.0\n"
        f"  source: {platform_checkout}\n  ref: main\n"
        f"  unreleased: true\n  manifestDigest:\n",
    )
    assert _run(project).returncode == 0
    expected = hashlib.sha256(
        (platform_checkout / "patterns" / PATTERN / "pattern.yaml").read_bytes()
    ).hexdigest()
    assert f"manifestDigest: {expected}" in (project / "pattern.lock.yaml").read_text(
        encoding="utf-8"
    )

    verify = subprocess.run(
        [sys.executable, "scripts/verify_pattern_lock.py"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr


def test_two_sources_at_once_are_refused(
    tmp_path: Path, platform_checkout: Path
) -> None:
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n  version: 0.1.0\n"
        f"  source: {platform_checkout}\n  tag: {PATTERN}/v0.1.0\n  ref: main\n"
        f"  unreleased: true\n  manifestDigest:\n",
    )
    result = _run(project)
    assert result.returncode != 0
    assert "more than one source" in result.stdout + result.stderr


def test_no_source_at_all_is_refused(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        f"  name: {PATTERN}\n  version: 0.1.0\n"
        f"  source: https://github.com/example-org/geap-platform-services\n"
        f"  manifestDigest:\n",
    )
    result = _run(project)
    assert result.returncode != 0
    assert "names no source" in result.stdout + result.stderr


def test_the_shipped_template_lock_is_still_refused_as_placeholders(
    tmp_path: Path,
) -> None:
    """The template ships `<pattern-name>` and friends; they are not values."""
    project = tmp_path / "pristine"
    shutil.copytree(TEMPLATE, project)
    result = _run(project)
    assert result.returncode != 0
    assert "not filled in" in result.stdout + result.stderr
