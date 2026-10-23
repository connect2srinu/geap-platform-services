"""Read back what the provider stored, and re-classify it.

Validation before the write is not enough. The probe confirmed on 2026-10-22 that a write whose fact
shares a topic and field with an existing memory **updates** that memory and replaces its text. So
the content that ends up in the bank is not necessarily the content the classifier approved, and the
privacy guarantee rests on checking the result rather than the submission.

The sequence, per memory the write touched:

1. read it back;
2. decode its ``[topic=…]`` prefix to learn which topic's rules apply;
3. re-classify the consolidated text;
4. if it now carries prohibited content, **roll back** to the newest revision that classifies clean,
   and **delete** if no such revision exists.

Rollback is preferred because it keeps the end user's earlier, legitimate preference. Delete is the
fallback, not the default — losing good data is a cost, just a smaller one than keeping bad data.

When verification cannot complete, the result is ``WRITTEN_UNVERIFIED``. It is never reported as
verified, it raises an alert, and recall re-checks the value as a backstop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from extensions import CallerContext, Fact, PiiClassifier

from ..providers.encoding import decode_fact_text
from ..providers.memory_bank import MemoryBank, ProviderUnavailable


class VerificationOutcome(str, Enum):
    """What verification concluded about a write."""

    VERIFIED = "VERIFIED"
    REMEDIATED = "REMEDIATED"
    WRITTEN_UNVERIFIED = "WRITTEN_UNVERIFIED"


class Remediation(str, Enum):
    """What was done to a memory that failed re-classification."""

    ROLLED_BACK = "ROLLED_BACK"
    DELETED = "DELETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    outcome: VerificationOutcome
    checked: int = 0
    remediated: tuple[tuple[str, Remediation], ...] = ()
    unverified: tuple[str, ...] = field(default_factory=tuple)

    @property
    def clean(self) -> bool:
        return self.outcome is VerificationOutcome.VERIFIED


class MetricSink(Protocol):
    def increment(self, metric: str, **labels: str) -> None: ...


class AuditSink(Protocol):
    """Audit events carry identifiers and decisions, never values (security rule S-4)."""

    def emit(self, event: str, **fields: str) -> None: ...


class _Null:
    def increment(self, metric: str, **labels: str) -> None:
        return None

    def emit(self, event: str, **fields: str) -> None:
        return None


def verify_write(
    memory_names: tuple[str, ...],
    caller: CallerContext,
    *,
    bank: MemoryBank,
    classifier: PiiClassifier,
    metrics: MetricSink | None = None,
    audit: AuditSink | None = None,
) -> VerificationResult:
    """Re-classify every memory a write touched, remediating any that is now prohibited."""
    sink = metrics or _Null()
    log = audit or _Null()

    checked = 0
    remediated: list[tuple[str, Remediation]] = []
    unverified: list[str] = []

    for name in memory_names:
        try:
            stored = bank.get(name)
        except (ProviderUnavailable, KeyError):
            # Could not read it back. Not an approval -- the caller is told so, and recall re-checks.
            unverified.append(name)
            sink.increment("verification_outcomes", outcome="unreadable")
            continue

        decoded = decode_fact_text(stored.text)
        if decoded is None:
            # Unattributable: no topic, so no rules to judge it by. Remediate rather than assume
            # it is harmless -- a memory the pattern cannot reason about must not be left in place.
            remediated.append(
                (
                    name,
                    _remediate(
                        name,
                        caller,
                        bank=bank,
                        classifier=classifier,
                        sink=sink,
                        log=log,
                        reason="UNATTRIBUTABLE",
                    ),
                )
            )
            checked += 1
            continue

        probe = Fact(
            topic=decoded.topic,
            value=decoded.text,
            text=decoded.text,
            field_name=decoded.field,
        )
        try:
            verdict = classifier.classify(probe, caller)
        except Exception:  # noqa: BLE001 - domain code; an undecided classifier is not an approval
            unverified.append(name)
            sink.increment("extension_errors", extension_id="pii-classifier")
            sink.increment("verification_outcomes", outcome="classifier_failed")
            continue

        checked += 1
        if verdict.allowed:
            sink.increment("verification_outcomes", outcome="clean")
            continue

        remediated.append(
            (
                name,
                _remediate(
                    name,
                    caller,
                    bank=bank,
                    classifier=classifier,
                    sink=sink,
                    log=log,
                    reason="PROHIBITED_AFTER_CONSOLIDATION",
                ),
            )
        )

    if unverified:
        outcome = VerificationOutcome.WRITTEN_UNVERIFIED
        sink.increment("verification_outcomes", outcome="unverified")
        log.emit(
            "memory_write_unverified",
            correlation_id=caller.correlation_id,
            caller_id=caller.caller_id,
            domain=caller.domain,
            count=str(len(unverified)),
        )
    elif remediated:
        outcome = VerificationOutcome.REMEDIATED
    else:
        outcome = VerificationOutcome.VERIFIED

    return VerificationResult(
        outcome=outcome,
        checked=checked,
        remediated=tuple(remediated),
        unverified=tuple(unverified),
    )


def _remediate(
    name: str,
    caller: CallerContext,
    *,
    bank: MemoryBank,
    classifier: PiiClassifier,
    sink: MetricSink,
    log: AuditSink,
    reason: str,
) -> Remediation:
    """Roll back to the newest clean revision, else delete.

    Rollback keeps the end user's earlier legitimate preference, so it is preferred. Delete is the
    fallback when no revision classifies clean -- losing good data is a cost, just a smaller one
    than keeping prohibited data.
    """
    action = Remediation.FAILED
    try:
        for revision in bank.revisions(name):
            decoded = decode_fact_text(revision.text)
            if decoded is None:
                continue
            probe = Fact(
                topic=decoded.topic,
                value=decoded.text,
                text=decoded.text,
                field_name=decoded.field,
            )
            try:
                if not classifier.classify(probe, caller).allowed:
                    continue
            except Exception:  # noqa: BLE001 - an undecided classifier cannot clear a revision
                continue
            bank.rollback(name, revision.revision)
            action = Remediation.ROLLED_BACK
            break
        else:
            bank.delete(name)
            action = Remediation.DELETED
    except (ProviderUnavailable, KeyError):
        # The prohibited content is still there. This must be loud, never silent.
        action = Remediation.FAILED

    sink.increment("remediations", action=action.value, reason=reason)
    log.emit(
        "memory_remediation",
        correlation_id=caller.correlation_id,
        caller_id=caller.caller_id,
        domain=caller.domain,
        action=action.value,
        reason=reason,
    )
    return action
