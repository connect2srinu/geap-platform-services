"""The extension points must fail closed, and the configuration must validate.

Security rules S-2 (deny by default) and S-3 (classify before persisting) are only real if these
tests fail when the defaults are loosened.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN))

from extensions import (  # noqa: E402
    CallerContext,
    Classification,
    ClassificationResult,
    DenyAllClassifier,
    DenyAllPolicyProvider,
    EntityResolver,
    ExtensionError,
    Fact,
    NoOpEntityResolver,
    PiiClassifier,
    PolicyDecision,
    PolicyProvider,
    Topic,
    TopicProvider,
    YamlTopicProvider,
)

CALLER = CallerContext(
    caller_id="writer-agent",
    domain="example-domain",
    scope=(("user_id", "pseudo-1"),),
    subject_pseudonym="hmac-abc123",
    operations=frozenset({"remember"}),
    granted_topics=frozenset({"preferred_brands"}),
)
FACT = Fact(
    topic="preferred_brands", value="Horizon", text="Prefers the brand Horizon."
)


# --- the required defaults deny -----------------------------------------------------------


def test_default_classifier_denies_everything() -> None:
    """S-3. 'No classifier configured' must mean 'store nothing', never 'store everything'."""
    result = DenyAllClassifier().classify(FACT, CALLER)
    assert result.allowed is False
    assert result.reason == "NO_CLASSIFIER_CONFIGURED"


def test_default_policy_provider_denies_everything() -> None:
    """S-2. An unconfigured domain has not said who may do what, so nobody may."""
    decision = DenyAllPolicyProvider().decide(CALLER, "remember", "preferred_brands")
    assert decision.allowed is False
    assert decision.reason == "NO_POLICY_PROVIDER_CONFIGURED"


def test_required_defaults_announce_themselves_at_startup() -> None:
    """An operator must be able to tell 'storing nothing' from 'broken'."""
    for default in (DenyAllClassifier, DenyAllPolicyProvider):
        assert "not configured" in default.startup_warning


def test_default_entity_resolver_is_a_pass_through() -> None:
    """Permissive is safe here: resolution cannot grant storage."""
    assert NoOpEntityResolver().resolve(FACT, CALLER) is FACT


# --- the protocols accept a domain's own implementation --------------------------------------


def test_a_substitute_classifier_satisfies_the_protocol() -> None:
    class DomainClassifier:
        def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
            return ClassificationResult(allowed=True)

    assert isinstance(DomainClassifier(), PiiClassifier)


def test_a_substitute_policy_provider_satisfies_the_protocol() -> None:
    class DomainPolicy:
        def decide(
            self, caller: CallerContext, operation: str, topic: str
        ) -> PolicyDecision:
            return PolicyDecision(allowed=True)

    assert isinstance(DomainPolicy(), PolicyProvider)


def test_the_platform_defaults_satisfy_their_own_protocols() -> None:
    assert isinstance(DenyAllClassifier(), PiiClassifier)
    assert isinstance(DenyAllPolicyProvider(), PolicyProvider)
    assert isinstance(NoOpEntityResolver(), EntityResolver)


# --- eligibility needs both conditions --------------------------------------------------------


@pytest.mark.parametrize(
    ("classification", "enabled", "eligible"),
    [
        (Classification.NON_SENSITIVE, True, True),
        (Classification.NON_SENSITIVE, False, False),
        (Classification.SENSITIVE, True, False),
        (Classification.RESTRICTED, True, False),
        (Classification.SENSITIVE, False, False),
    ],
)
def test_eligibility_requires_enabled_and_non_sensitive(
    classification: Classification, enabled: bool, eligible: bool
) -> None:
    """An enabled sensitive topic is still not eligible. Enabling is not permission."""
    topic = Topic(id="t", classification=classification, enabled=enabled)
    assert topic.is_eligible is eligible


def test_allow_inferred_defaults_to_false() -> None:
    assert (
        Topic(
            id="t", classification=Classification.NON_SENSITIVE, enabled=True
        ).allow_inferred
        is False
    )


def test_fact_basis_defaults_to_stated() -> None:
    assert FACT.basis == "stated"


# --- S-4: a reason code cannot smuggle the value out -------------------------------------------


def test_classification_reason_must_stay_a_short_code() -> None:
    with pytest.raises(ValueError, match="must not carry the value"):
        ClassificationResult(allowed=False, reason="x" * 65)


def test_caller_context_carries_no_raw_subject() -> None:
    """The raw end-user subject is absent by construction, so an extension cannot log it."""
    names = {f.name for f in dataclasses.fields(CallerContext)}
    assert "subject_pseudonym" in names
    assert not names & {"subject", "user_id", "email", "token"}


# --- extensions receive values they cannot mutate ------------------------------------------------


def test_facts_and_contexts_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        FACT.value = "tampered"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        CALLER.caller_id = "other"  # type: ignore[misc]


# --- the YAML provider ---------------------------------------------------------------------------


def test_yaml_provider_builds_topics_from_config() -> None:
    provider = YamlTopicProvider(
        [
            {
                "id": "preferred_brands",
                "classification": "non-sensitive",
                "enabled": True,
                "fields": [{"name": "brand", "valueType": "string", "maxLength": 128}],
            }
        ]
    )
    topics = provider.topics()
    assert topics["preferred_brands"].is_eligible is True
    assert topics["preferred_brands"].fields[0].value_type == "string"
    assert isinstance(provider, TopicProvider)


def test_yaml_provider_returns_a_copy() -> None:
    """A caller mutating the returned map must not corrupt the provider."""
    provider = YamlTopicProvider(
        [{"id": "t", "classification": "non-sensitive", "enabled": True}]
    )
    provider.topics().clear()
    assert provider.topics() != {}


@pytest.mark.parametrize(
    "bad",
    [
        [{"classification": "non-sensitive", "enabled": True}],
        [{"id": "t", "enabled": True}],
        [
            {"id": "t", "classification": "non-sensitive", "enabled": True},
            {"id": "t", "classification": "non-sensitive", "enabled": True},
        ],
        [
            {
                "id": "t",
                "classification": "non-sensitive",
                "enabled": True,
                "fields": "nope",
            }
        ],
        [
            {
                "id": "t",
                "classification": "non-sensitive",
                "enabled": True,
                "fields": [{"name": "f"}],
            }
        ],
    ],
)
def test_yaml_provider_raises_rather_than_guessing(bad: list[dict[str, Any]]) -> None:
    """An unparseable vocabulary is an error, not an empty one — an empty one hides it."""
    with pytest.raises(ExtensionError):
        YamlTopicProvider(bad)


# --- configuration ----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return json.loads((PATTERN / "config" / "config.schema.json").read_text())


def test_example_config_validates(schema: dict[str, Any]) -> None:
    cfg = yaml.safe_load((PATTERN / "config" / "example.domain.yaml").read_text())
    jsonschema.validate(cfg, schema, format_checker=jsonschema.FormatChecker())


def test_config_rejects_unknown_keys(schema: dict[str, Any]) -> None:
    """A typo must fail at startup, not be silently ignored."""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {
                "domain": {"name": "example-domain"},
                "topics": [
                    {"id": "t", "classification": "non-sensitive", "enabled": True}
                ],
                "callers": [
                    {
                        "id": "a",
                        "subject": "s",
                        "operations": ["recall"],
                        "topics": ["t"],
                    }
                ],
                "observability": {"logLevel": "INFO"},
                "disableClassifier": True,
            },
            schema,
        )


def test_config_has_no_key_that_could_switch_off_a_security_rule(
    schema: dict[str, Any],
) -> None:
    text = json.dumps(schema).lower()
    for forbidden in ("disable", "skipvalidation", "allowall", "bypass", "insecure"):
        assert forbidden not in text


def test_retention_is_one_period_for_the_domain(schema: dict[str, Any]) -> None:
    """Per-topic retention is impossible: TTL is bank-level and each domain has one bank."""
    retention = schema["properties"]["retention"]
    assert set(retention["properties"]) == {"days"}
    topic_props = schema["properties"]["topics"]["items"]["properties"]
    assert not any("retention" in k.lower() for k in topic_props)
