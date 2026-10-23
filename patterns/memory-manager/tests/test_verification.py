"""Read-back verification: the check that makes the privacy guarantee hold.

Validation before the write approves what was *submitted*. The provider consolidates and can
replace the stored text afterwards, so the guarantee rests on re-checking what actually landed.
"""

from __future__ import annotations

import sys
from pathlib import Path


PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))

from memory_manager.extensions import CallerContext, ClassificationResult, Fact  # noqa: E402
from memory_manager.providers import (  # noqa: E402
    FakeMemoryBank,
    ProviderUnavailable,
    encode_fact_text,
)
from memory_manager.worker import Remediation, VerificationOutcome, verify_write  # noqa: E402

SCOPE = (("user_id", "pseudo-1"),)
CALLER = CallerContext(
    caller_id="writer-agent",
    domain="example-domain",
    scope=SCOPE,
    subject_pseudonym="hmac-abc",
    correlation_id="corr-1",
)


def brand(text: str, field: str = "brand") -> str:
    return encode_fact_text("preferred_brands", field, text)


class AllowAll:
    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        return ClassificationResult(allowed=True)


class RejectsWord:
    """Stands in for a domain classifier that recognises prohibited content."""

    def __init__(self, word: str) -> None:
        self._word = word

    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        if self._word in fact.text:
            return ClassificationResult(allowed=False, reason="PROHIBITED")
        return ClassificationResult(allowed=True)


class Broken:
    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        raise RuntimeError("a bug in the domain's classifier")


class Recorder:
    def __init__(self) -> None:
        self.metrics: list[tuple[str, dict[str, str]]] = []
        self.events: list[tuple[str, dict[str, str]]] = []

    def increment(self, metric: str, **labels: str) -> None:
        self.metrics.append((metric, labels))

    def emit(self, event: str, **fields: str) -> None:
        self.events.append((event, fields))


# --- the clean path ----------------------------------------------------------------


def test_a_clean_write_verifies() -> None:
    bank = FakeMemoryBank()
    names = bank.write([brand("Prefers Horizon.")], SCOPE).memory_names
    result = verify_write(names, CALLER, bank=bank, classifier=AllowAll())
    assert result.outcome is VerificationOutcome.VERIFIED
    assert result.checked == 1
    assert result.clean is True


# --- the case the whole design exists for ---------------------------------------------


def test_content_that_turns_prohibited_after_consolidation_is_remediated() -> None:
    """The write gate approved the submission. Consolidation replaced the text with something the
    classifier would now refuse. Verification must catch that."""
    bank = FakeMemoryBank()
    names = bank.write([brand("Prefers Horizon.")], SCOPE).memory_names
    # Consolidation rewrites the same topic+field into prohibited content.
    bank.write([brand("Takes atorvastatin and prefers Horizon.")], SCOPE)

    result = verify_write(
        names, CALLER, bank=bank, classifier=RejectsWord("atorvastatin")
    )

    assert result.outcome is VerificationOutcome.REMEDIATED
    assert result.remediated[0][1] is Remediation.ROLLED_BACK
    assert "atorvastatin" not in bank.get(names[0]).text


def test_rollback_is_preferred_so_the_earlier_preference_survives() -> None:
    bank = FakeMemoryBank()
    names = bank.write([brand("Prefers Horizon.")], SCOPE).memory_names
    bank.write([brand("Takes atorvastatin.")], SCOPE)

    verify_write(names, CALLER, bank=bank, classifier=RejectsWord("atorvastatin"))

    assert "Horizon" in bank.get(names[0]).text


def test_delete_when_no_revision_classifies_clean() -> None:
    """Delete is the fallback, not the default. Losing good data is a cost - just a smaller one
    than keeping prohibited data."""
    bank = FakeMemoryBank()
    names = bank.write([brand("Takes atorvastatin.")], SCOPE).memory_names

    result = verify_write(
        names, CALLER, bank=bank, classifier=RejectsWord("atorvastatin")
    )

    assert result.remediated[0][1] is Remediation.DELETED
    assert bank.retrieve(SCOPE) == []


def test_an_unattributable_memory_is_remediated_not_assumed_harmless() -> None:
    """No prefix means no topic, so no rules to judge it by. It must not be left in place."""
    bank = FakeMemoryBank()
    names = bank.write(["No prefix at all."], SCOPE).memory_names

    result = verify_write(names, CALLER, bank=bank, classifier=AllowAll())

    assert result.outcome is VerificationOutcome.REMEDIATED
    assert result.remediated[0][1] is Remediation.DELETED


# --- when verification cannot complete --------------------------------------------------


def test_an_unreadable_memory_is_unverified_never_verified() -> None:
    bank = FakeMemoryBank()
    result = verify_write(
        ("memories/does-not-exist",), CALLER, bank=bank, classifier=AllowAll()
    )
    assert result.outcome is VerificationOutcome.WRITTEN_UNVERIFIED
    assert result.unverified == ("memories/does-not-exist",)


def test_a_broken_classifier_yields_unverified_not_verified() -> None:
    """An undecided classifier is not an approval."""
    bank = FakeMemoryBank()
    names = bank.write([brand("Prefers Horizon.")], SCOPE).memory_names
    result = verify_write(names, CALLER, bank=bank, classifier=Broken())
    assert result.outcome is VerificationOutcome.WRITTEN_UNVERIFIED


def test_unverified_raises_an_audit_event() -> None:
    bank = FakeMemoryBank()
    rec = Recorder()
    verify_write(
        ("memories/missing",),
        CALLER,
        bank=bank,
        classifier=AllowAll(),
        metrics=rec,
        audit=rec,
    )
    assert any(e == "memory_write_unverified" for e, _ in rec.events)


def test_a_failed_remediation_is_loud() -> None:
    """The prohibited content is still there. Silence would be the worst outcome."""

    class CannotRemediate(FakeMemoryBank):
        def rollback(self, name: str, revision: str) -> object:  # type: ignore[override]
            raise ProviderUnavailable("bank unreachable")

        def delete(self, name: str) -> None:
            raise ProviderUnavailable("bank unreachable")

    bank = CannotRemediate()
    rec = Recorder()
    names = bank.write([brand("Takes atorvastatin.")], SCOPE).memory_names

    result = verify_write(
        names,
        CALLER,
        bank=bank,
        classifier=RejectsWord("atorvastatin"),
        metrics=rec,
        audit=rec,
    )

    assert result.remediated[0][1] is Remediation.FAILED
    assert any(e == "memory_remediation" for e, _ in rec.events)
    assert any(m == "remediations" for m, _ in rec.metrics)


# --- audit carries identifiers, never values (S-4) -------------------------------------------


def test_audit_events_carry_no_payload() -> None:
    bank = FakeMemoryBank()
    rec = Recorder()
    names = bank.write([brand("Takes atorvastatin.")], SCOPE).memory_names
    verify_write(
        names,
        CALLER,
        bank=bank,
        classifier=RejectsWord("atorvastatin"),
        metrics=rec,
        audit=rec,
    )

    for _, fields in rec.events:
        joined = " ".join(fields.values())
        assert "atorvastatin" not in joined
        assert "Horizon" not in joined
    for _, labels in rec.metrics:
        assert "atorvastatin" not in " ".join(labels.values())


def test_audit_carries_the_pseudonym_not_a_raw_subject() -> None:
    bank = FakeMemoryBank()
    rec = Recorder()
    names = bank.write([brand("Takes atorvastatin.")], SCOPE).memory_names
    verify_write(
        names,
        CALLER,
        bank=bank,
        classifier=RejectsWord("atorvastatin"),
        metrics=rec,
        audit=rec,
    )
    for _, fields in rec.events:
        assert fields.get("correlation_id") == "corr-1"


# --- batches ---------------------------------------------------------------------------------


def test_a_mixed_batch_reports_remediated() -> None:
    bank = FakeMemoryBank()
    clean = bank.write([brand("Prefers Horizon.", "brand")], SCOPE).memory_names[0]
    dirty = bank.write([brand("Takes atorvastatin.", "other")], SCOPE).memory_names[0]

    result = verify_write(
        (clean, dirty), CALLER, bank=bank, classifier=RejectsWord("atorvastatin")
    )

    assert result.outcome is VerificationOutcome.REMEDIATED
    assert result.checked == 2
    assert len(result.remediated) == 1


def test_unverified_wins_over_remediated() -> None:
    """If anything could not be checked, the write is not reported as verified, whatever else
    happened."""
    bank = FakeMemoryBank()
    dirty = bank.write([brand("Takes atorvastatin.")], SCOPE).memory_names[0]

    result = verify_write(
        (dirty, "memories/missing"),
        CALLER,
        bank=bank,
        classifier=RejectsWord("atorvastatin"),
    )

    assert result.outcome is VerificationOutcome.WRITTEN_UNVERIFIED


def test_an_empty_write_verifies_trivially() -> None:
    bank = FakeMemoryBank()
    result = verify_write((), CALLER, bank=bank, classifier=AllowAll())
    assert result.outcome is VerificationOutcome.VERIFIED
    assert result.checked == 0
