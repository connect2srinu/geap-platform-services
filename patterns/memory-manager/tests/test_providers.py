"""The provider boundary, the fact encoding, and the fake's fidelity.

The fake is only useful if it reproduces what the probe actually observed on 2026-10-22, including
the inconvenient parts. These tests pin that behaviour, so a later convenience change to the fake
fails here rather than quietly making the pattern's tests meaningless.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))

from memory_manager.providers import (  # noqa: E402
    FakeMemoryBank,
    MemoryAction,
    MemoryBank,
    ProviderThrottled,
    ProviderUnavailable,
    WriteOutcome,
    decode_fact_text,
    encode_fact_text,
)
from memory_manager.providers.memory_bank import MAX_FACTS_PER_WRITE  # noqa: E402

SCOPE = (("user_id", "pseudo-1"),)
OTHER_SCOPE = (("user_id", "pseudo-2"),)


def brand(text: str, field: str = "brand") -> str:
    return encode_fact_text("preferred_brands", field, text)


# --- encoding -------------------------------------------------------------------------


def test_encode_then_decode_round_trips() -> None:
    encoded = encode_fact_text("preferred_brands", "brand", "Prefers Horizon.")
    decoded = decode_fact_text(encoded)
    assert decoded is not None
    assert (decoded.topic, decoded.field, decoded.text) == (
        "preferred_brands",
        "brand",
        "Prefers Horizon.",
    )


def test_field_is_optional() -> None:
    decoded = decode_fact_text(encode_fact_text("preferred_brands", None, "Likes it."))
    assert decoded is not None
    assert decoded.field is None


@pytest.mark.parametrize(
    "stored",
    [
        "Prefers Horizon.",
        "[topic=] Prefers Horizon.",
        "[topic=Bad_Case] x",
        "[field=brand] x",
    ],
)
def test_a_missing_or_malformed_prefix_decodes_to_none(stored: str) -> None:
    """Distinct from a successful decode: an unattributable memory must be remediated, not
    assumed harmless."""
    assert decode_fact_text(stored) is None


@pytest.mark.parametrize("forged", ["brand]extra[field=other", "[topic=other", "a]b"])
def test_a_bracket_in_the_prefix_is_refused(forged: str) -> None:
    """Without this, a crafted field name could close the prefix and open another, so a fact could
    claim a topic it was never validated against."""
    with pytest.raises(ValueError, match="must not contain a bracket"):
        encode_fact_text("preferred_brands", forged, "x")


def test_a_bracket_in_the_topic_is_refused() -> None:
    with pytest.raises(ValueError, match="must not contain a bracket"):
        encode_fact_text("preferred_brands]x[topic=other", "brand", "x")


# --- the fake satisfies the boundary ------------------------------------------------------


def test_the_fake_satisfies_the_protocol() -> None:
    assert isinstance(FakeMemoryBank(), MemoryBank)


# --- fidelity: what the probe observed ------------------------------------------------------


def test_a_first_write_creates() -> None:
    bank = FakeMemoryBank()
    result = bank.write([brand("Prefers Horizon.")], SCOPE)
    assert result.outcome is WriteOutcome.APPLIED
    assert [a for _, a in result.affected] == [MemoryAction.CREATED]


def test_a_conflicting_value_updates_rather_than_creating() -> None:
    """Observed live: a second write for the same attribute returned UPDATED on a first-write
    memory. Consolidation acted."""
    bank = FakeMemoryBank()
    bank.write([brand("Prefers size medium.")], SCOPE)
    result = bank.write([brand("Prefers size large.")], SCOPE)
    assert [a for _, a in result.affected] == [MemoryAction.UPDATED]
    assert len(bank.retrieve(SCOPE)) == 1


def test_an_identical_fact_submitted_twice_leaves_one_memory() -> None:
    """The backstop the idempotency design leans on."""
    bank = FakeMemoryBank()
    bank.write([brand("Prefers Horizon.")], SCOPE)
    result = bank.write([brand("Prefers Horizon.")], SCOPE)
    assert [a for _, a in result.affected] == [MemoryAction.UPDATED]
    assert len(bank.retrieve(SCOPE)) == 1


def test_consolidation_replaces_the_stored_text() -> None:
    """This is why read-back re-classification exists: what is stored is not what was submitted."""
    bank = FakeMemoryBank()
    bank.write([brand("Prefers size medium.")], SCOPE)
    bank.write([brand("Prefers size large.")], SCOPE)
    assert "large" in bank.retrieve(SCOPE)[0].text


def test_the_prefix_survives_consolidation() -> None:
    bank = FakeMemoryBank()
    bank.write([brand("Prefers size medium.")], SCOPE)
    bank.write([brand("Prefers size large.")], SCOPE)
    decoded = decode_fact_text(bank.retrieve(SCOPE)[0].text)
    assert decoded is not None
    assert decoded.topic == "preferred_brands"


def test_different_fields_do_not_consolidate_into_each_other() -> None:
    bank = FakeMemoryBank()
    bank.write([brand("Prefers Horizon.", "brand")], SCOPE)
    bank.write([brand("Rated four.", "rating")], SCOPE)
    assert len(bank.retrieve(SCOPE)) == 2


def test_scopes_are_isolated() -> None:
    bank = FakeMemoryBank()
    bank.write([brand("Prefers Horizon.")], SCOPE)
    bank.write([brand("Prefers Horizon.")], OTHER_SCOPE)
    assert len(bank.retrieve(SCOPE)) == 1
    assert len(bank.retrieve(OTHER_SCOPE)) == 1


def test_a_read_immediately_after_a_write_reflects_the_content() -> None:
    bank = FakeMemoryBank()
    name = bank.write([brand("Prefers Horizon.")], SCOPE).memory_names[0]
    assert "Horizon" in bank.get(name).text


# --- the provider's five-fact limit -----------------------------------------------------------


def test_five_facts_are_accepted() -> None:
    bank = FakeMemoryBank()
    facts = [brand(f"Fact {i}.", f"field_{i}") for i in range(MAX_FACTS_PER_WRITE)]
    assert len(bank.write(facts, SCOPE).affected) == MAX_FACTS_PER_WRITE


def test_six_facts_are_refused_as_a_programming_error() -> None:
    """A caller that has not enforced the contract's cap is a defect, not a provider error."""
    bank = FakeMemoryBank()
    facts = [brand(f"Fact {i}.", f"field_{i}") for i in range(MAX_FACTS_PER_WRITE + 1)]
    with pytest.raises(ValueError, match="at most 5 facts"):
        bank.write(facts, SCOPE)


def test_an_empty_write_is_a_no_op() -> None:
    bank = FakeMemoryBank()
    result = bank.write([], SCOPE)
    assert result.affected == ()
    assert bank.retrieve(SCOPE) == []


# --- revisions and remediation ------------------------------------------------------------------


def test_revisions_accumulate_newest_first() -> None:
    bank = FakeMemoryBank()
    name = bank.write([brand("Clean.")], SCOPE).memory_names[0]
    bank.write([brand("Prohibited content.")], SCOPE)
    history = bank.revisions(name)
    assert len(history) == 2
    assert "Prohibited" in history[0].text


def test_rollback_restores_the_clean_revision() -> None:
    bank = FakeMemoryBank()
    name = bank.write([brand("Clean.")], SCOPE).memory_names[0]
    clean = bank.revisions(name)[0].revision
    bank.write([brand("Prohibited content.")], SCOPE)
    restored = bank.rollback(name, clean)
    assert "Clean." in restored.text


def test_rollback_makes_the_prohibited_revision_unreachable() -> None:
    """Observed live: after rollback the prohibited revision was listed 0 times and retrievable 0
    times. A rollback that left it reachable would not be a remediation."""
    bank = FakeMemoryBank()
    name = bank.write([brand("Clean.")], SCOPE).memory_names[0]
    clean = bank.revisions(name)[0].revision
    bank.write([brand("Prohibited content.")], SCOPE)
    bank.rollback(name, clean)

    assert all("Prohibited" not in r.text for r in bank.revisions(name))
    assert "Prohibited" not in bank.get(name).text


def test_delete_removes_the_memory_and_its_revisions() -> None:
    bank = FakeMemoryBank()
    name = bank.write([brand("Prefers Horizon.")], SCOPE).memory_names[0]
    bank.delete(name)
    assert bank.retrieve(SCOPE) == []
    assert bank.revisions(name) == []
    with pytest.raises(KeyError):
        bank.get(name)


def test_rollback_to_an_unknown_revision_raises() -> None:
    bank = FakeMemoryBank()
    name = bank.write([brand("Prefers Horizon.")], SCOPE).memory_names[0]
    with pytest.raises(KeyError, match="no such revision"):
        bank.rollback(name, "rev-99")


# --- throttling maps to unavailable, not to the caller's fault ---------------------------------------


def test_a_throttle_is_a_provider_unavailable() -> None:
    """ProviderThrottled subclasses ProviderUnavailable so a caller that does not care about the
    distinction still behaves correctly."""
    bank = FakeMemoryBank(throttle_after=1)
    bank.write([brand("First.")], SCOPE)
    with pytest.raises(ProviderUnavailable):
        bank.write([brand("Second.", "other")], SCOPE)


def test_a_throttle_is_distinguishable_when_it_matters() -> None:
    bank = FakeMemoryBank(throttle_after=0)
    with pytest.raises(ProviderThrottled):
        bank.write([brand("First.")], SCOPE)
