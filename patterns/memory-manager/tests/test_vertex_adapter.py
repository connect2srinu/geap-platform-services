"""The Vertex adapter's translation, against a stub shaped like the real SDK.

The stub mirrors the surface checked against google-cloud-aiplatform 2.3.0 on 2026-10-22:
`memories.generate/get/list/delete/rollback` and `memories.revisions.list`, all keyword-only, with
`rollback` taking `target_revision_id`. Wrong keywords therefore fail here rather than in
production.

What this does NOT prove: that the live service behaves this way. That is the opt-in contract test.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))

from memory_manager.providers import (  # noqa: E402
    MemoryAction,
    MemoryBank,
    ProviderThrottled,
    ProviderUnavailable,
    encode_fact_text,
)
from memory_manager.providers.vertex import VertexMemoryBank, topic_of  # noqa: E402

BANK = "projects/1/locations/us-central1/reasoningEngines/9"
SCOPE = (("user_id", "pseudo-1"),)


class _Memory:
    def __init__(
        self, name: str, fact: str, scope: dict[str, str], expire: bool = False
    ) -> None:
        self.name = name
        self.fact = fact
        self.scope = scope
        self.expire_time = datetime(2027, 1, 1, tzinfo=UTC) if expire else None


class _Revision:
    def __init__(self, name: str, fact: str) -> None:
        self.name = name
        self.fact = fact


class _Revisions:
    def __init__(self, items: list[_Revision], raises: Exception | None = None) -> None:
        self._items = items
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    def list(self, *, name: str, config: Any = None) -> list[_Revision]:
        self.calls.append({"name": name})
        if self._raises is not None:
            raise self._raises
        return self._items


class StubMemories:
    """Keyword-only, exactly like the real client, so a wrong keyword raises TypeError."""

    def __init__(
        self,
        *,
        memories: list[_Memory] | None = None,
        raises: Exception | None = None,
        revisions: list[_Revision] | None = None,
    ) -> None:
        self._memories = memories or []
        self._raises = raises
        self.revisions = _Revisions(revisions or [], raises)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _maybe_raise(self) -> None:
        if self._raises is not None:
            raise self._raises

    def generate(
        self,
        *,
        name: str,
        direct_memories_source: Any = None,
        vertex_session_source: Any = None,
        direct_contents_source: Any = None,
        scope: Any = None,
        config: Any = None,
    ) -> Any:
        self.calls.append(
            (
                "generate",
                {"name": name, "source": direct_memories_source, "scope": scope},
            )
        )
        self._maybe_raise()

        class Action:
            def __init__(self, n: str) -> None:
                self.name = n

        class Generated:
            def __init__(self, memory: _Memory, action: str) -> None:
                self.memory = memory
                self.action = Action(action)

        class Response:
            def __init__(self, items: list[Generated]) -> None:
                self.generated_memories = items

        class Operation:
            def __init__(self, response: Response) -> None:
                self.response = response

        facts = [
            m["fact"] for m in (direct_memories_source or {}).get("direct_memories", [])
        ]
        made = [
            Generated(_Memory(f"memories/{i}", fact, dict(scope or {})), "CREATED")
            for i, fact in enumerate(facts)
        ]
        return Operation(Response(made))

    def get(self, *, name: str, config: Any = None) -> _Memory:
        self.calls.append(("get", {"name": name}))
        self._maybe_raise()
        found = next((m for m in self._memories if m.name == name), None)
        if found is None:
            raise RuntimeError("not found")
        return found

    def list(self, *, name: str, config: Any = None) -> list[_Memory]:
        self.calls.append(("list", {"name": name}))
        self._maybe_raise()
        return self._memories

    def rollback(
        self, *, name: str, target_revision_id: str, config: Any = None
    ) -> None:
        self.calls.append(
            ("rollback", {"name": name, "target_revision_id": target_revision_id})
        )
        self._maybe_raise()

    def delete(self, *, name: str, config: Any = None) -> None:
        self.calls.append(("delete", {"name": name}))
        self._maybe_raise()


def bank(**kw: Any) -> VertexMemoryBank:
    return VertexMemoryBank(
        project="example-project",
        location="us-central1",
        bank=BANK,
        client=StubMemories(**kw),
    )


def brand(text: str, field: str = "brand") -> str:
    return encode_fact_text("preferred_brands", field, text)


# --- it satisfies the boundary ------------------------------------------------------


def test_the_adapter_satisfies_the_protocol() -> None:
    assert isinstance(bank(), MemoryBank)


# --- the call shape is the one the SDK actually has -------------------------------------


def test_write_calls_generate_with_direct_memories_source() -> None:
    b = bank()
    b.write([brand("Prefers Horizon.")], SCOPE)
    call, args = b._memories.calls[0]  # type: ignore[attr-defined]
    assert call == "generate"
    assert args["name"] == BANK
    assert args["source"]["direct_memories"] == [{"fact": brand("Prefers Horizon.")}]
    assert args["scope"] == {"user_id": "pseudo-1"}


def test_rollback_passes_target_revision_id() -> None:
    """The SDK's keyword is target_revision_id, not 'revision'. A stub with keyword-only
    parameters makes a wrong keyword fail here rather than in production."""
    b = bank(memories=[_Memory("memories/1", brand("Clean."), {"user_id": "pseudo-1"})])
    b.rollback("memories/1", "rev-2")
    call, args = b._memories.calls[0]  # type: ignore[attr-defined]
    assert call == "rollback"
    assert args["target_revision_id"] == "rev-2"


def test_retrieve_uses_list_not_similarity_search() -> None:
    """`retrieve` on the SDK is a similarity search and would return a ranked subset - the wrong
    answer to 'show me everything in this scope'."""
    b = bank(memories=[_Memory("memories/1", brand("A."), {"user_id": "pseudo-1"})])
    b.retrieve(SCOPE)
    assert [c for c, _ in b._memories.calls] == ["list"]  # type: ignore[attr-defined]


def test_write_reports_the_action_per_memory() -> None:
    result = bank().write([brand("Prefers Horizon.")], SCOPE)
    assert [a for _, a in result.affected] == [MemoryAction.CREATED]
    assert result.memory_names == ("memories/0",)


# --- translation ----------------------------------------------------------------------


def test_scope_is_filtered_in_the_adapter() -> None:
    b = bank(
        memories=[
            _Memory("memories/1", brand("Mine."), {"user_id": "pseudo-1"}),
            _Memory("memories/2", brand("Theirs."), {"user_id": "pseudo-2"}),
        ]
    )
    found = b.retrieve(SCOPE)
    assert [m.name for m in found] == ["memories/1"]


def test_expire_time_is_carried_through_as_a_string() -> None:
    b = bank(
        memories=[
            _Memory("memories/1", brand("A."), {"user_id": "pseudo-1"}, expire=True)
        ]
    )
    assert b.retrieve(SCOPE)[0].expire_time == "2027-01-01T00:00:00+00:00"


def test_a_revision_id_is_the_last_path_segment() -> None:
    b = bank(revisions=[_Revision("memories/1/revisions/rev-7", brand("A."))])
    assert b.revisions("memories/1")[0].revision == "rev-7"


def test_topic_of_reads_the_prefix() -> None:
    b = bank(memories=[_Memory("memories/1", brand("A."), {"user_id": "pseudo-1"})])
    assert topic_of(b.retrieve(SCOPE)[0]) == "preferred_brands"


def test_topic_of_is_none_for_an_unattributable_memory() -> None:
    b = bank(memories=[_Memory("memories/1", "no prefix", {"user_id": "pseudo-1"})])
    assert topic_of(b.retrieve(SCOPE)[0]) is None


# --- the five-fact cap ------------------------------------------------------------------


def test_six_facts_are_refused_before_the_provider_is_called() -> None:
    b = bank()
    with pytest.raises(ValueError, match="at most 5 facts"):
        b.write([brand(f"F{i}.", f"f{i}") for i in range(6)], SCOPE)
    assert b._memories.calls == []  # type: ignore[attr-defined]


def test_an_empty_write_does_not_call_the_provider() -> None:
    b = bank()
    assert b.write([], SCOPE).affected == ()
    assert b._memories.calls == []  # type: ignore[attr-defined]


# --- provider failures become ours, with no provider text ------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "429 RESOURCE_EXHAUSTED: quota exceeded",
        "Quota exceeded for memory writes",
        "rate limit hit",
    ],
)
def test_a_throttle_is_recognised(message: str) -> None:
    b = bank(raises=RuntimeError(message))
    with pytest.raises(ProviderThrottled):
        b.write([brand("A.")], SCOPE)


def test_any_other_failure_is_unavailable() -> None:
    b = bank(raises=RuntimeError("500 internal"))
    with pytest.raises(ProviderUnavailable):
        b.write([brand("A.")], SCOPE)


def test_the_providers_text_never_reaches_our_exception() -> None:
    """S-4. A provider string can carry a resource name or a fragment of the fact, and this
    exception's text can reach a log."""
    leaky = RuntimeError(
        "failed writing 'Prefers Horizon' to projects/secret/locations/x"
    )
    b = bank(raises=leaky)
    with pytest.raises(ProviderUnavailable) as caught:
        b.write([brand("Prefers Horizon.")], SCOPE)
    assert "Horizon" not in str(caught.value)
    assert "projects/secret" not in str(caught.value)


@pytest.mark.parametrize("operation", ["retrieve", "get", "revisions", "delete"])
def test_every_read_and_delete_wraps_failures(operation: str) -> None:
    b = bank(raises=RuntimeError("boom"))
    with pytest.raises(ProviderUnavailable):
        if operation == "retrieve":
            b.retrieve(SCOPE)
        elif operation == "get":
            b.get("memories/1")
        elif operation == "revisions":
            b.revisions("memories/1")
        else:
            b.delete("memories/1")
