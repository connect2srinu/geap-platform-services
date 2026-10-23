"""The domain-consumer template: the thing a team actually starts from.

Everything here was a real defect found by the adoption rehearsal on 2026-10-23. The template's
configuration could not validate, its smoke test was written against a superseded async API, its
agent documentation described endpoints that do not exist, and its Dockerfile named a module that
does not exist. All four were correct once and rotted, because nothing executed them.

These tests execute them.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "domain-consumer"
PATTERN = REPO / "patterns" / "memory-manager"
CONFIG_SCHEMA = PATTERN / "src" / "memory_manager" / "config.schema.json"
OPENAPI = PATTERN / "contracts" / "openapi.yaml"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --- the configuration a domain starts from ---------------------------------------------


def test_the_template_config_validates_against_the_pattern_schema() -> None:
    """A domain starting from the template must not start from something that cannot start."""
    jsonschema.validate(
        _yaml(TEMPLATE / "config" / "domain-config.yaml"),
        json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8")),
        format_checker=jsonschema.FormatChecker(),
    )


def test_the_template_config_carries_no_secret_values() -> None:
    text = (TEMPLATE / "config" / "domain-config.yaml").read_text(encoding="utf-8")
    for forbidden in ("hmacKey", "secretValue", "BEGIN PRIVATE KEY", "password:"):
        assert forbidden not in text


def test_the_template_config_names_a_fail_closed_default_in_its_comments() -> None:
    """Omitting the classifier stores nothing. A team must not discover that in production."""
    text = (TEMPLATE / "config" / "domain-config.yaml").read_text(encoding="utf-8")
    assert "FAIL CLOSED" in text


# --- the entry point --------------------------------------------------------------------


def test_the_template_dockerfile_starts_a_module_that_exists() -> None:
    """`pattern.api.main:app` shipped for weeks and has never existed."""
    text = (TEMPLATE / "Dockerfile").read_text(encoding="utf-8")
    assert "pattern.api.main" not in text
    assert "memory_manager.asgi:create" in text
    assert "--factory" in text


def test_the_template_dockerfile_copies_only_files_the_template_ships() -> None:
    """It copied a uv.lock the template does not contain, so the build failed at COPY."""
    text = (TEMPLATE / "Dockerfile").read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("COPY ") or "--from=" in line:
            continue
        for token in line.split()[1:-1]:
            if token.startswith("--"):
                continue
            source = token.rstrip("/")
            if any(ch in source for ch in "*?["):
                continue
            # vendor/ is produced by scripts/vendor_pattern.py, not shipped by the template.
            if source == "vendor" or source.startswith("vendor/"):
                continue
            assert (
                TEMPLATE / source
            ).exists(), (
                f"Dockerfile copies {source!r}, which the template does not ship"
            )


# --- what agent teams are told --------------------------------------------------------


def _published_paths() -> set[str]:
    """Paths as a caller sees them: the server's base path plus the path item."""
    spec = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    base = ""
    for server in spec.get("servers", []):
        url = str(server.get("url", ""))
        if "/" in url.removeprefix("https://").removeprefix("http://"):
            base = (
                "/"
                + url.removeprefix("https://").removeprefix("http://").split("/", 1)[1]
            )
            break
    return {f"{base.rstrip('/')}{path}" for path in spec["paths"]}


def test_the_agent_api_doc_describes_only_endpoints_that_exist() -> None:
    """It documented list, correct and forget as endpoints. None of them exist."""
    text = (TEMPLATE / "docs" / "agent-api.md").read_text(encoding="utf-8")
    published_paths = _published_paths()
    import re

    for referenced in set(re.findall(r"`(/v1/[^`\s]+)`", text)):
        bare = referenced.split("?")[0]
        assert (
            bare in published_paths
        ), f"agent-api.md documents {referenced}, which contracts/openapi.yaml does not publish"


def test_the_agent_api_doc_does_not_promise_asynchronous_writes() -> None:
    """It told agent teams a write returns 202 and is queued. It is synchronous."""
    text = (TEMPLATE / "docs" / "agent-api.md").read_text(encoding="utf-8")
    # Saying "never 202" is the correction, so only a 202 presented as the outcome is wrong.
    import re

    for match in re.finditer(r"202", text):
        context = text[max(0, match.start() - 40) : match.start()].lower()
        assert (
            "never" in context or "not" in context
        ), f"agent-api.md presents 202 as an outcome: …{text[max(0, match.start() - 40): match.end() + 10]}…"
    for phrase in ("durably enqueued", "dead-letter", "eventually consistent"):
        assert phrase.lower() not in text.lower()


@pytest.mark.parametrize("code", ["ACCEPTED", "TOPIC_UNKNOWN", "VALUE_PROHIBITED"])
def test_the_agent_api_doc_uses_real_reason_codes(code: str) -> None:
    spec = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    assert code in spec["components"]["schemas"]["FactReasonCode"]["enum"]
    assert code in (TEMPLATE / "docs" / "agent-api.md").read_text(encoding="utf-8")


# --- secrets ----------------------------------------------------------------------------


def test_the_template_ships_an_env_example_with_names_and_no_values() -> None:
    """The guide said to copy one. There was none, and a populated one is a leak waiting."""
    env = TEMPLATE / ".env.example"
    assert env.is_file()
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "=" in line, f"not a NAME= line: {line!r}"
        name, _, value = line.partition("=")
        assert name and name.isupper(), f"not an environment variable name: {name!r}"
        assert value == "", f"{name} carries a value; .env.example holds names only"


def test_the_env_example_names_every_variable_the_service_requires() -> None:
    required = {"SUBJECT_HMAC_KEY", "CONFIG_PATH", "ENVIRONMENT", "MAX_INSTANCES"}
    text = (TEMPLATE / ".env.example").read_text(encoding="utf-8")
    missing = {name for name in required if f"{name}=" not in text}
    assert not missing, f"missing from .env.example: {sorted(missing)}"


# --- the sample extensions --------------------------------------------------------------


SAMPLES = ["sample_classifier.py", "sample_policy.py"]


@pytest.mark.parametrize("name", SAMPLES)
def test_a_sample_extension_says_plainly_that_it_is_not_production_code(
    name: str,
) -> None:
    """A worked example that reads like a finished one is how a regex list reaches production."""
    text = (TEMPLATE / "extensions" / name).read_text(encoding="utf-8")
    assert "Not production code" in text
    assert "**Do not ship this.**" in text


@pytest.mark.parametrize("name", SAMPLES)
def test_a_sample_extension_is_named_so_it_cannot_be_mistaken(name: str) -> None:
    assert name.startswith("sample_")


def test_the_template_config_points_at_the_samples_that_exist() -> None:
    """A dotted path to a module that is not there stops startup — correctly, but pointlessly."""
    config = _yaml(TEMPLATE / "config" / "domain-config.yaml")
    for key, path in (config.get("extensions") or {}).items():
        module, _, attribute = str(path).rpartition(".")
        source = TEMPLATE / (module.replace(".", "/") + ".py")
        assert (
            source.is_file()
        ), f"extensions.{key} points at {module}, which is not shipped"
        assert f"class {attribute}" in source.read_text(
            encoding="utf-8"
        ), f"extensions.{key} names {attribute}, which {source.name} does not define"


def test_the_sample_classifier_refuses_what_it_claims_to() -> None:
    """The example must actually work, or it teaches the wrong shape."""
    import sys
    from dataclasses import dataclass

    sys.path.insert(0, str(PATTERN / "src"))
    sys.path.insert(0, str(TEMPLATE))
    from extensions.sample_classifier import SampleClassifier  # noqa: PLC0415

    @dataclass
    class Probe:
        value: str
        text: str

    classifier = SampleClassifier()
    assert classifier.classify(Probe("Horizon", "Prefers Horizon."), None).allowed
    # Prohibited in the narrative, not the value: the case an allowed topic invites.
    refused = classifier.classify(
        Probe("Horizon", "Takes 20mg of something and prefers Horizon."), None
    )
    assert not refused.allowed
    assert refused.reason == "health"
    # The reason is a code, never the matched text.
    assert "20mg" not in str(refused.reason)
