"""Wiring: configuration and environment in, a working deployment out.

The wiring is part of the pattern because every mistake it can make is silent. A deny-all default
left in place where a real classifier was meant looks exactly like a healthy service that stores
nothing; a missing write budget looks healthy until it exhausts a quota three other domains share.
Both are startup failures here, and these tests are what keep them that way.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))
# Also the pattern root: the extension-loading tests name classes in this module by dotted path,
# which is how a domain names its own.
sys.path.insert(0, str(PATTERN))

from memory_manager.extensions import (  # noqa: E402
    CallerContext,
    ClassificationResult,
    DenyAllClassifier,
    DenyAllPolicyProvider,
    Fact,
)
from memory_manager.api.auth import JwtSubjectVerifier, LocalHeaderVerifier  # noqa: E402
from memory_manager.api.main import ConfigurationError  # noqa: E402
from memory_manager.bootstrap import build_deployment, load_config  # noqa: E402
from memory_manager.providers import FakeMemoryBank  # noqa: E402

EXAMPLE = PATTERN / "config" / "example.domain.yaml"
HMAC_KEY = "a-test-only-hmac-key"


class AllowAll:
    """Stands in for a domain's real classifier, loaded by module path."""

    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        return ClassificationResult(allowed=True)


class Unconstructable:
    def __init__(self) -> None:
        raise RuntimeError("this domain's classifier needs an argument nobody passed")


@pytest.fixture(autouse=True)
def _local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("SUBJECT_HMAC_KEY", HMAC_KEY)
    monkeypatch.delenv("MAX_INSTANCES", raising=False)


def config(**overrides: Any) -> dict[str, Any]:
    """The shipped example, with its extension paths cleared.

    The example names the *domain's* own classes, which by definition do not exist here. Clearing
    them leaves the deny-all defaults, which is the right baseline for everything but the
    extension-loading tests.
    """
    loaded: dict[str, Any] = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    loaded["extensions"] = {}
    loaded.update(overrides)
    return loaded


# --- configuration validation ---------------------------------------------------------


def test_the_shipped_example_is_valid() -> None:
    """The example a domain copies must pass the schema it is copied against."""
    assert load_config(EXAMPLE)["domain"]["name"] == "example-domain"


def test_a_missing_file_names_the_path(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="configuration not found"):
        load_config(tmp_path / "absent.yaml")


def test_invalid_yaml_is_a_configuration_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("topics: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="not valid YAML"):
        load_config(bad)


def test_a_schema_violation_names_the_field(tmp_path: Path) -> None:
    broken = config()
    broken["topics"][0]["classification"] = "confidential"
    path = tmp_path / "broken.yaml"
    path.write_text(yaml.safe_dump(broken), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="topics/0/classification"):
        load_config(path)


def test_an_unknown_key_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    """A silently ignored key is a setting the operator believes is in force and is not."""
    extra = config()
    extra["qouta"] = {"maxWritesPerMinute": 100}  # a plausible typo
    path = tmp_path / "typo.yaml"
    path.write_text(yaml.safe_dump(extra), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(path)


# --- the write budget ------------------------------------------------------------------


def test_budget_is_the_domain_share_divided_by_the_instance_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_INSTANCES", "4")
    deployment = build_deployment(config())  # example declares 100 writes/minute
    assert deployment.budget is not None
    assert deployment.budget.capacity == 25


def test_a_single_instance_gets_the_whole_share() -> None:
    deployment = build_deployment(config())
    assert deployment.budget is not None
    assert deployment.budget.capacity == 100


def test_configuration_without_a_quota_refuses_to_build() -> None:
    without = config()
    del without["quota"]
    with pytest.raises(ConfigurationError, match="maxWritesPerMinute is required"):
        build_deployment(without)


def test_a_non_numeric_instance_ceiling_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_INSTANCES", "four")
    with pytest.raises(ConfigurationError, match="MAX_INSTANCES"):
        build_deployment(config())


# --- extensions ------------------------------------------------------------------------


def test_omitted_extensions_fall_back_to_the_deny_all_defaults() -> None:
    """Omitting them is legitimate, and means the domain stores nothing until it supplies one."""
    bare = config()
    bare["extensions"] = {}
    deployment = build_deployment(bare)
    assert isinstance(deployment.classifier, DenyAllClassifier)
    assert isinstance(deployment.policy, DenyAllPolicyProvider)


@pytest.mark.parametrize(
    "path", ["tests.test_bootstrap.AllowAll", "tests.test_bootstrap:AllowAll"]
)
def test_a_named_extension_is_loaded(path: str) -> None:
    named = config()
    named["extensions"] = {"piiClassifier": path}
    loaded = build_deployment(named).classifier
    # By name, not isinstance: pytest imports this module under a different name than the
    # bootstrap's importlib does, so the two AllowAll classes are not the same object.
    assert type(loaded).__name__ == "AllowAll"
    assert not isinstance(loaded, DenyAllClassifier)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("AllowAll", "dotted path"),
        ("no.such.module:Thing", "could not be imported"),
        ("tests.test_bootstrap:Absent", "has no attribute"),
        ("tests.test_bootstrap:Unconstructable", "could not be constructed"),
    ],
)
def test_a_named_extension_that_cannot_load_stops_startup(
    path: str, expected: str
) -> None:
    """Never a silent fallback: a deployment storing nothing must not look like a healthy one."""
    broken = config()
    broken["extensions"] = {"piiClassifier": path}
    with pytest.raises(ConfigurationError, match=expected):
        build_deployment(broken)


# --- callers and identity ----------------------------------------------------------------


def test_a_caller_granted_an_unknown_topic_is_refused() -> None:
    wrong = config()
    wrong["callers"][0]["topics"] = ["no_such_topic"]
    with pytest.raises(ConfigurationError, match="topics that do not exist"):
        build_deployment(wrong)


def test_callers_carry_their_operations_and_topics() -> None:
    deployment = build_deployment(config())
    first = config()["callers"][0]
    caller = deployment.callers[first["id"]]
    assert caller.operations == frozenset(first["operations"])
    assert caller.granted_topics == frozenset(first["topics"])


def test_the_hmac_key_comes_from_the_environment_not_the_config_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The config file is versioned; a secret in it is a secret in git."""
    monkeypatch.delenv("SUBJECT_HMAC_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="SUBJECT_HMAC_KEY"):
        build_deployment(config())
    assert "SUBJECT_HMAC_KEY" not in EXAMPLE.read_text(encoding="utf-8")


def test_local_uses_the_header_verifier_and_the_fake_bank() -> None:
    deployment = build_deployment(config(), environment="local")
    assert isinstance(deployment.verifier, LocalHeaderVerifier)
    assert isinstance(deployment.bank, FakeMemoryBank)


def test_a_deployed_environment_uses_real_token_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fake bank and the header shortcut must be unreachable outside local."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv(
        "MEMORY_BANK_ID", "projects/0/locations/us-central1/reasoningEngines/0"
    )
    try:
        deployment = build_deployment(config(), environment="production")
    except (
        Exception
    ) as exc:  # the provider extra is not installed in the default dev env
        assert "provider" in str(exc).lower() or "agentplatform" in str(exc).lower()
        return
    assert isinstance(deployment.verifier, JwtSubjectVerifier)
    assert not isinstance(deployment.bank, FakeMemoryBank)


# --- the whole thing starts ---------------------------------------------------------------


def test_the_example_configuration_produces_a_service_that_serves() -> None:
    """End to end through the entry point the container actually runs."""
    from fastapi.testclient import TestClient

    from memory_manager.api.main import create_app

    app = create_app(
        build_deployment(config(), environment="local"), environment="local"
    )
    assert TestClient(app).get("/healthz").status_code == 200
