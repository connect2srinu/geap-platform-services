"""The ordered validation pipeline.

One fact in, one outcome out, through the checks in :data:`~.reasons.CHECK_ORDER`. Every step denies
by default (security rule S-2) and classification happens before anything is persisted (S-3).

An extension is domain code, so **any** exception from one is caught, not only
:class:`~extensions.types.ExtensionError`. A classifier that raises a ``KeyError`` has still failed to
approve the fact, and letting that propagate would turn a denial into a 500 — which is both a worse
answer and a worse signal. ``ExtensionError`` remains the documented way to say "I cannot decide";
it is not the only way the pipeline must survive.

The pipeline imports the extension *interfaces* — the Protocols and their value types. That is the
contract between platform and domain, not a dependency on a domain's implementation: the platform has
to know the shape it is calling. It never imports a concrete domain extension.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..extensions import (
    CallerContext,
    Classification,
    EntityResolver,
    Fact,
    PiiClassifier,
    PolicyProvider,
    Topic,
    TopicField,
)

from ..observability import AuditSink, NullAudit
from .reasons import ReasonCode


@dataclass(frozen=True, slots=True)
class FactOutcome:
    """What the pipeline decided about one fact.

    ``fact`` is the value to persist when accepted — possibly rewritten by the entity resolver, which
    is why it is returned rather than the caller's original.
    """

    index: int
    topic: str
    reason: ReasonCode
    fact: Fact | None = None

    @property
    def accepted(self) -> bool:
        return self.reason is ReasonCode.ACCEPTED


class MetricSink(Protocol):
    """Where the pipeline reports counts. Names and reason codes only — never a value (S-4)."""

    def increment(self, metric: str, **labels: str) -> None: ...


class _NullMetrics:
    def increment(self, metric: str, **labels: str) -> None:
        return None


_CLASSIFICATION_REASON = {
    Classification.SENSITIVE: ReasonCode.TOPIC_SENSITIVE,
    Classification.RESTRICTED: ReasonCode.TOPIC_RESTRICTED,
}

_PYTHON_TYPE: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
}


class ValidationPipeline:
    """Validates facts against a domain's configuration and extensions.

    Stateless and side-effect free apart from metrics, so the same instance can serve concurrent
    requests and a test can exercise the decision order without a provider.
    """

    def __init__(
        self,
        *,
        topics: dict[str, Topic],
        classifier: PiiClassifier,
        policy: PolicyProvider,
        resolver: EntityResolver | None = None,
        metrics: MetricSink | None = None,
        audit: AuditSink | None = None,
    ) -> None:
        self._topics = topics
        self._classifier = classifier
        self._policy = policy
        self._resolver = resolver
        self._metrics = metrics or _NullMetrics()
        self._audit = audit or NullAudit()

    # -- per-fact ----------------------------------------------------------------------

    def validate(self, index: int, fact: Fact, caller: CallerContext) -> FactOutcome:
        """Run the checks in order and return the first refusal, or ACCEPTED."""

        def refuse(reason: ReasonCode) -> FactOutcome:
            self._metrics.increment("policy_denials", reason_code=reason.value)
            return FactOutcome(index=index, topic=fact.topic, reason=reason)

        # 1. topic_known -- an unknown topic is refused, never inferred into existence.
        topic = self._topics.get(fact.topic)
        if topic is None:
            return refuse(ReasonCode.TOPIC_UNKNOWN)

        # 2. topic_enabled
        if not topic.enabled:
            return refuse(ReasonCode.TOPIC_DISABLED)

        # 3. topic_classification -- before the caller's grant, deliberately. A sensitive topic is
        #    not storable by anyone, so this is the truthful reason; TOPIC_NOT_APPROVED would invite
        #    a request for a grant that can never be given.
        if topic.classification is not Classification.NON_SENSITIVE:
            return refuse(_CLASSIFICATION_REASON[topic.classification])

        # 4. caller_granted
        if fact.topic not in caller.granted_topics:
            return refuse(ReasonCode.TOPIC_NOT_APPROVED)

        # 5. field_known -- only checked when the topic declares fields.
        field = self._field_for(topic, fact)
        if topic.fields and field is None:
            return refuse(ReasonCode.FIELD_UNKNOWN)

        # 6. value_type
        if not self._value_type_ok(field, fact.value):
            return refuse(ReasonCode.VALUE_TYPE_INVALID)

        # 7. basis_permitted -- an inference is refused unless the topic opted in.
        if fact.basis == "inferred" and not topic.allow_inferred:
            return refuse(ReasonCode.INFERENCE_NOT_PERMITTED)

        # 8. policy_provider -- may narrow the decision, never widen it. By this point the platform
        #    has already allowed the fact, so only a denial here changes anything.
        try:
            decision = self._policy.decide(caller, "remember", fact.topic)
        except Exception:  # noqa: BLE001 - domain code; any failure denies
            self._metrics.increment("extension_errors", extension_id="policy-provider")
            self._audit_extension_failure(caller, "policy-provider")
            return refuse(ReasonCode.TOPIC_NOT_APPROVED)
        if not decision.allowed or fact.topic in decision.restricted_topics:
            return refuse(ReasonCode.TOPIC_NOT_APPROVED)

        # 9. classifier -- last, so a malformed fact never reaches a domain's classifier. Classifies
        #    the fact TEXT as well as the value: a permitted topic does not exempt its content.
        try:
            verdict = self._classifier.classify(fact, caller)
        except Exception:  # noqa: BLE001 - domain code; any failure denies
            self._metrics.increment("extension_errors", extension_id="pii-classifier")
            self._audit_extension_failure(caller, "pii-classifier")
            return refuse(ReasonCode.CLASSIFIER_ERROR)
        if not verdict.allowed:
            return refuse(ReasonCode.VALUE_PROHIBITED)

        resolved = self._resolve(fact, caller)
        self._metrics.increment(
            "facts_evaluated", reason_code=ReasonCode.ACCEPTED.value
        )
        return FactOutcome(
            index=index, topic=fact.topic, reason=ReasonCode.ACCEPTED, fact=resolved
        )

    # -- helpers -----------------------------------------------------------------------

    @staticmethod
    def _field_for(topic: Topic, fact: Fact) -> TopicField | None:
        if not topic.fields or fact.field_name is None:
            return None
        return next((f for f in topic.fields if f.name == fact.field_name), None)

    @staticmethod
    def _value_type_ok(field: TopicField | None, value: str | float | bool) -> bool:
        if field is None:
            return True
        expected = _PYTHON_TYPE[field.value_type]
        # bool is a subclass of int, so a boolean must not satisfy "number".
        if expected is not bool and isinstance(value, bool):
            return False
        if not isinstance(value, expected):
            return False
        if isinstance(value, str) and field.max_length is not None:
            return len(value) <= field.max_length
        return True

    def _resolve(self, fact: Fact, caller: CallerContext) -> Fact:
        """Entity resolution enriches a fact. A failure skips it rather than refusing the fact.

        Safe to tolerate because resolution cannot grant storage — the classifier and the policy
        provider have already decided that. A resolver that returns a different topic or basis is a
        defect, and the original is kept.
        """
        if self._resolver is None:
            return fact
        try:
            resolved = self._resolver.resolve(fact, caller)
        except Exception:  # noqa: BLE001 - domain code; any failure skips
            self._metrics.increment("extension_errors", extension_id="entity-resolver")
            self._audit_extension_failure(caller, "entity-resolver")
            return fact
        if resolved.topic != fact.topic or resolved.basis != fact.basis:
            self._metrics.increment("extension_errors", extension_id="entity-resolver")
            self._audit_extension_failure(caller, "entity-resolver")
            return fact
        return resolved

    def _audit_extension_failure(self, caller: CallerContext, extension: str) -> None:
        """A domain extension failed. The denial is already decided; this records who and which.

        The exception itself is never carried: a domain's traceback can hold the fact it was
        judging (S-4).
        """
        self._audit.emit(
            "exception_invoked",
            correlation_id=caller.correlation_id,
            caller_id=caller.caller_id,
            domain=caller.domain,
            extension=extension,
        )


def validate_facts(
    facts: list[Fact],
    caller: CallerContext,
    *,
    topics: dict[str, Topic],
    classifier: PiiClassifier,
    policy: PolicyProvider,
    resolver: EntityResolver | None = None,
    metrics: MetricSink | None = None,
    audit: AuditSink | None = None,
) -> list[FactOutcome]:
    """Validate a batch, preserving submission order so each outcome keeps its index."""
    pipeline = ValidationPipeline(
        topics=topics,
        classifier=classifier,
        policy=policy,
        resolver=resolver,
        metrics=metrics,
        audit=audit,
    )
    return [pipeline.validate(i, fact, caller) for i, fact in enumerate(facts)]
