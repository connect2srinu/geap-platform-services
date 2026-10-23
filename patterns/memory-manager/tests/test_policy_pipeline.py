"""The validation pipeline must deny by default, in the order the design fixed.

Security rules S-2 (deny by default) and S-3 (classify before persisting) live here. Every test
below fails if the check it guards is removed or reordered.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))

from memory_manager.extensions import (  # noqa: E402
    CallerContext,
    Classification,
    ClassificationResult,
    DenyAllClassifier,
    DenyAllPolicyProvider,
    ExtensionError,
    Fact,
    PolicyDecision,
    Topic,
    TopicField,
)
from memory_manager.policy import (  # noqa: E402
    CHECK_ORDER,
    ReasonCode,
    ValidationPipeline,
    validate_facts,
)

BRANDS = Topic(
    id="preferred_brands",
    classification=Classification.NON_SENSITIVE,
    enabled=True,
    fields=(
        TopicField(name="brand", value_type="string", max_length=16),
        TopicField(name="rating", value_type="number"),
        TopicField(name="is_favourite", value_type="boolean"),
    ),
)
TOPICS = {
    "preferred_brands": BRANDS,
    "disabled_topic": Topic(
        id="disabled_topic", classification=Classification.NON_SENSITIVE, enabled=False
    ),
    "health_conditions": Topic(
        id="health_conditions", classification=Classification.SENSITIVE, enabled=True
    ),
    "prescription_details": Topic(
        id="prescription_details",
        classification=Classification.RESTRICTED,
        enabled=True,
    ),
    "open_topic": Topic(
        id="open_topic", classification=Classification.NON_SENSITIVE, enabled=True
    ),
}
CALLER = CallerContext(
    caller_id="writer-agent",
    domain="example-domain",
    scope=(("user_id", "pseudo-1"),),
    subject_pseudonym="hmac-abc",
    operations=frozenset({"remember"}),
    granted_topics=frozenset(TOPICS) - {"open_topic"},
)


class AllowAll:
    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        return ClassificationResult(allowed=True)

    def decide(
        self, caller: CallerContext, operation: str, topic: str
    ) -> PolicyDecision:
        return PolicyDecision(allowed=True)


class Raises:
    """Signals failure the documented way."""

    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        raise ExtensionError("cannot decide")

    def decide(
        self, caller: CallerContext, operation: str, topic: str
    ) -> PolicyDecision:
        raise ExtensionError("cannot decide")

    def resolve(self, fact: Fact, caller: CallerContext) -> Fact:
        raise ExtensionError("cannot resolve")


class RaisesUnexpectedly:
    """Domain code failing the undocumented way, which must behave identically."""

    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        raise KeyError("a bug in the domain's classifier")

    def decide(
        self, caller: CallerContext, operation: str, topic: str
    ) -> PolicyDecision:
        raise RuntimeError("a bug in the domain's policy provider")

    def resolve(self, fact: Fact, caller: CallerContext) -> Fact:
        raise AttributeError("a bug in the domain's resolver")


class RecordingMetrics:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def increment(self, metric: str, **labels: str) -> None:
        self.calls.append((metric, labels))


def pipeline(
    *,
    classifier: object = None,
    policy: object = None,
    resolver: object = None,
    metrics: object = None,
) -> ValidationPipeline:
    return ValidationPipeline(
        topics=TOPICS,
        classifier=classifier or AllowAll(),  # type: ignore[arg-type]
        policy=policy or AllowAll(),  # type: ignore[arg-type]
        resolver=resolver,  # type: ignore[arg-type]
        metrics=metrics,  # type: ignore[arg-type]
    )


def fact(**kw: object) -> Fact:
    base: dict[str, object] = {
        "topic": "preferred_brands",
        "value": "Horizon",
        "text": "Prefers Horizon.",
        "field_name": "brand",
    }
    base.update(kw)
    return Fact(**base)  # type: ignore[arg-type]


# --- the happy path, so the refusals below mean something ---------------------------------


def test_a_valid_fact_is_accepted() -> None:
    outcome = pipeline().validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.ACCEPTED
    assert outcome.accepted is True
    assert outcome.fact is not None


# --- deny by default: the shipped defaults refuse everything --------------------------------


def test_default_classifier_refuses_a_valid_fact() -> None:
    """S-3. An unconfigured deployment stores nothing."""
    outcome = pipeline(classifier=DenyAllClassifier()).validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.VALUE_PROHIBITED
    assert outcome.fact is None


def test_default_policy_provider_refuses_a_valid_fact() -> None:
    """S-2."""
    outcome = pipeline(policy=DenyAllPolicyProvider()).validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.TOPIC_NOT_APPROVED


# --- each refusal, with its published reason code ---------------------------------------------


@pytest.mark.parametrize(
    ("submitted", "expected"),
    [
        (fact(topic="no_such_topic"), ReasonCode.TOPIC_UNKNOWN),
        (fact(topic="disabled_topic", field_name=None), ReasonCode.TOPIC_DISABLED),
        (fact(topic="health_conditions", field_name=None), ReasonCode.TOPIC_SENSITIVE),
        (
            fact(topic="prescription_details", field_name=None),
            ReasonCode.TOPIC_RESTRICTED,
        ),
        (fact(topic="open_topic", field_name=None), ReasonCode.TOPIC_NOT_APPROVED),
        (fact(field_name="not_a_field"), ReasonCode.FIELD_UNKNOWN),
        (fact(field_name=None), ReasonCode.FIELD_UNKNOWN),
        (fact(value=42), ReasonCode.VALUE_TYPE_INVALID),
        (fact(value=True), ReasonCode.VALUE_TYPE_INVALID),
        (fact(value="x" * 17), ReasonCode.VALUE_TYPE_INVALID),
        (fact(basis="inferred"), ReasonCode.INFERENCE_NOT_PERMITTED),
    ],
)
def test_each_refusal_reports_its_own_reason(
    submitted: Fact, expected: ReasonCode
) -> None:
    assert pipeline().validate(0, submitted, CALLER).reason is expected


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        ("rating", 4, ReasonCode.ACCEPTED),
        ("rating", 4.5, ReasonCode.ACCEPTED),
        # bool is a subclass of int in Python, so without an explicit guard True would be
        # accepted as a number. It must not be.
        ("rating", True, ReasonCode.VALUE_TYPE_INVALID),
        ("rating", "four", ReasonCode.VALUE_TYPE_INVALID),
        ("is_favourite", True, ReasonCode.ACCEPTED),
        ("is_favourite", 1, ReasonCode.VALUE_TYPE_INVALID),
        ("brand", "Horizon", ReasonCode.ACCEPTED),
    ],
)
def test_value_types_are_checked_per_field(
    field_name: str, value: object, expected: ReasonCode
) -> None:
    outcome = pipeline().validate(0, fact(field_name=field_name, value=value), CALLER)
    assert outcome.reason is expected


def test_an_inference_is_accepted_when_the_topic_opts_in() -> None:
    topics = dict(TOPICS)
    topics["preferred_brands"] = Topic(
        id="preferred_brands",
        classification=Classification.NON_SENSITIVE,
        enabled=True,
        allow_inferred=True,
        fields=BRANDS.fields,
    )
    p = ValidationPipeline(topics=topics, classifier=AllowAll(), policy=AllowAll())  # type: ignore[arg-type]
    assert p.validate(0, fact(basis="inferred"), CALLER).reason is ReasonCode.ACCEPTED


# --- the order is a design decision, not an accident ---------------------------------------------


def test_sensitivity_is_reported_before_the_callers_grant() -> None:
    """A sensitive topic is not storable by anyone. TOPIC_NOT_APPROVED would invite an agent team
    to request a grant that can never be given."""
    ungranted = CallerContext(
        caller_id="writer-agent",
        domain="example-domain",
        scope=(("user_id", "p"),),
        subject_pseudonym="hmac",
        granted_topics=frozenset(),
    )
    outcome = pipeline().validate(
        0, fact(topic="health_conditions", field_name=None), ungranted
    )
    assert outcome.reason is ReasonCode.TOPIC_SENSITIVE


def test_structural_checks_run_before_the_classifier() -> None:
    """A malformed fact must never reach a domain's classifier."""

    class Tripwire:
        called = False

        def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
            Tripwire.called = True
            return ClassificationResult(allowed=True)

    pipeline(classifier=Tripwire()).validate(0, fact(value=42), CALLER)
    assert Tripwire.called is False


def test_check_order_matches_the_documented_order() -> None:
    assert CHECK_ORDER.index("topic_classification") < CHECK_ORDER.index(
        "caller_granted"
    )
    assert CHECK_ORDER.index("value_type") < CHECK_ORDER.index("classifier")
    assert CHECK_ORDER[-1] == "classifier"


# --- an extension that fails is not an extension that approved -------------------------------------


def test_a_raising_classifier_denies_and_is_counted() -> None:
    metrics = RecordingMetrics()
    outcome = pipeline(classifier=Raises(), metrics=metrics).validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.CLASSIFIER_ERROR
    assert ("extension_errors", {"extension_id": "pii-classifier"}) in metrics.calls


def test_a_raising_policy_provider_denies_and_is_counted() -> None:
    metrics = RecordingMetrics()
    outcome = pipeline(policy=Raises(), metrics=metrics).validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.TOPIC_NOT_APPROVED
    assert ("extension_errors", {"extension_id": "policy-provider"}) in metrics.calls


@pytest.mark.parametrize("broken", [Raises(), RaisesUnexpectedly()])
def test_any_classifier_failure_denies_not_500s(broken: object) -> None:
    """A classifier raising KeyError has still failed to approve. Propagating it would turn a
    denial into a 500 - a worse answer and a worse signal."""
    outcome = pipeline(classifier=broken).validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.CLASSIFIER_ERROR


@pytest.mark.parametrize("broken", [Raises(), RaisesUnexpectedly()])
def test_any_policy_failure_denies_not_500s(broken: object) -> None:
    outcome = pipeline(policy=broken).validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.TOPIC_NOT_APPROVED


@pytest.mark.parametrize("broken", [Raises(), RaisesUnexpectedly()])
def test_any_resolver_failure_skips(broken: object) -> None:
    outcome = pipeline(resolver=broken).validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.ACCEPTED


def test_a_policy_provider_can_narrow_by_restricted_topics() -> None:
    class Narrowing:
        def decide(
            self, caller: CallerContext, operation: str, topic: str
        ) -> PolicyDecision:
            return PolicyDecision(
                allowed=True, restricted_topics=frozenset({"preferred_brands"})
            )

    assert (
        pipeline(policy=Narrowing()).validate(0, fact(), CALLER).reason
        is ReasonCode.TOPIC_NOT_APPROVED
    )


# --- entity resolution enriches; it cannot grant or corrupt -------------------------------------------


def test_a_raising_resolver_skips_rather_than_denying() -> None:
    metrics = RecordingMetrics()
    outcome = pipeline(resolver=Raises(), metrics=metrics).validate(0, fact(), CALLER)
    assert outcome.reason is ReasonCode.ACCEPTED
    assert ("extension_errors", {"extension_id": "entity-resolver"}) in metrics.calls


def test_a_resolver_that_changes_the_topic_is_ignored() -> None:
    class Rewriting:
        def resolve(self, f: Fact, caller: CallerContext) -> Fact:
            return Fact(
                topic="open_topic", value=f.value, text=f.text, field_name=f.field_name
            )

    outcome = pipeline(resolver=Rewriting()).validate(0, fact(), CALLER)
    assert outcome.fact is not None
    assert outcome.fact.topic == "preferred_brands"


def test_a_resolver_that_changes_the_basis_is_ignored() -> None:
    class Rewriting:
        def resolve(self, f: Fact, caller: CallerContext) -> Fact:
            return Fact(
                topic=f.topic,
                value=f.value,
                text=f.text,
                field_name=f.field_name,
                basis="inferred",
            )

    outcome = pipeline(resolver=Rewriting()).validate(0, fact(), CALLER)
    assert outcome.fact is not None
    assert outcome.fact.basis == "stated"


# --- batches keep their indices ---------------------------------------------------------------------


def test_a_batch_preserves_order_and_indices() -> None:
    outcomes = validate_facts(
        [fact(), fact(topic="health_conditions", field_name=None), fact(value=42)],
        CALLER,
        topics=TOPICS,
        classifier=AllowAll(),  # type: ignore[arg-type]
        policy=AllowAll(),  # type: ignore[arg-type]
    )
    assert [o.index for o in outcomes] == [0, 1, 2]
    assert [o.reason for o in outcomes] == [
        ReasonCode.ACCEPTED,
        ReasonCode.TOPIC_SENSITIVE,
        ReasonCode.VALUE_TYPE_INVALID,
    ]


# --- the codes must match what the contract publishes --------------------------------------------------


def test_reason_codes_match_the_contract_exactly() -> None:
    spec = yaml.safe_load((PATTERN / "contracts" / "openapi.yaml").read_text())
    published = set(spec["components"]["schemas"]["FactReasonCode"]["enum"])
    assert {r.value for r in ReasonCode} == published


def test_every_reason_code_is_reachable_from_the_pipeline() -> None:
    """A published code no path can produce is a lie in the contract."""
    source = (PATTERN / "src" / "memory_manager" / "policy" / "pipeline.py").read_text()
    for code in ReasonCode:
        assert re.search(
            rf"ReasonCode\.{code.name}\b", source
        ), f"{code.name} is unreachable"
