"""An in-memory Memory Bank that models the behaviour the probe verified.

A test double is only worth having if it is faithful. This one reproduces what was observed against a
real bank on 2026-10-22, including the parts that are inconvenient:

* **Consolidation rewrites.** A write whose fact shares a topic and field with an existing memory
  *updates* that memory rather than creating a second, and the stored text becomes the new text. This
  is what makes read-back re-classification necessary, so the fake must do it.
* **Identical facts deduplicate.** Submitting exactly the same fact twice reports ``UPDATED`` and
  leaves one memory, which is the backstop the idempotency design leans on.
* **The prefix survives.** Consolidation does not strip the ``[topic=…]`` prefix.
* **Revisions accumulate, and a rollback removes the rolled-back revision** from both listing and
  retrieval — not merely from the current content.
* **At most five facts per write**, rejected as a programming error rather than a provider error.

What it deliberately does *not* model: network latency, eventual consistency, and quota. Those are
real and are covered by the live contract test, not by a double that would only ever confirm its own
assumptions.
"""

from __future__ import annotations

from itertools import count

from .encoding import decode_fact_text
from .memory_bank import (
    MAX_FACTS_PER_WRITE,
    MemoryAction,
    MemoryRevision,
    ProviderThrottled,
    StoredMemory,
    WriteOutcome,
    WriteResult,
)

Scope = tuple[tuple[str, str], ...]


class FakeMemoryBank:
    """An in-memory bank for tests.

    ``throttle_after`` makes the next write raise :class:`ProviderThrottled`, so the mapping of a
    provider throttle to `503` can be tested without a real quota.
    """

    def __init__(self, *, throttle_after: int | None = None) -> None:
        self._memories: dict[str, StoredMemory] = {}
        self._revisions: dict[str, list[MemoryRevision]] = {}
        self._ids = count(1)
        self._writes = 0
        self._throttle_after = throttle_after

    # -- writes -------------------------------------------------------------------------

    def write(self, facts: list[str], scope: Scope) -> WriteResult:
        if len(facts) > MAX_FACTS_PER_WRITE:
            raise ValueError(
                f"the provider accepts at most {MAX_FACTS_PER_WRITE} facts per write, got {len(facts)}"
            )
        if not facts:
            return WriteResult(outcome=WriteOutcome.APPLIED)

        self._writes += 1
        if self._throttle_after is not None and self._writes > self._throttle_after:
            raise ProviderThrottled("quota exhausted")

        affected: list[tuple[str, MemoryAction]] = []
        for text in facts:
            existing = self._consolidation_target(text, scope)
            if existing is None:
                affected.append((self._create(text, scope), MemoryAction.CREATED))
            else:
                affected.append((self._update(existing, text), MemoryAction.UPDATED))
        return WriteResult(outcome=WriteOutcome.APPLIED, affected=tuple(affected))

    def _consolidation_target(self, text: str, scope: Scope) -> str | None:
        """Which existing memory this fact consolidates into, if any.

        Matching on topic and field reproduces what was observed: a conflicting value for the same
        attribute updated the existing memory instead of adding a second one.
        """
        decoded = decode_fact_text(text)
        if decoded is None:
            return None
        for name, memory in self._memories.items():
            if memory.scope != scope:
                continue
            other = decode_fact_text(memory.text)
            if other is None:
                continue
            if (other.topic, other.field) == (decoded.topic, decoded.field):
                return name
        return None

    def _create(self, text: str, scope: Scope) -> str:
        name = f"memories/fake-{next(self._ids)}"
        revision = "rev-1"
        self._memories[name] = StoredMemory(
            name=name, text=text, scope=scope, revision=revision
        )
        self._revisions[name] = [
            MemoryRevision(name=name, revision=revision, text=text)
        ]
        return name

    def _update(self, name: str, text: str) -> str:
        current = self._memories[name]
        revision = f"rev-{len(self._revisions[name]) + 1}"
        self._memories[name] = StoredMemory(
            name=name, text=text, scope=current.scope, revision=revision
        )
        # Newest first, matching the provider's listing order.
        self._revisions[name].insert(
            0, MemoryRevision(name=name, revision=revision, text=text)
        )
        return name

    # -- reads --------------------------------------------------------------------------

    def retrieve(self, scope: Scope) -> list[StoredMemory]:
        return [m for m in self._memories.values() if m.scope == scope]

    def get(self, name: str) -> StoredMemory:
        try:
            return self._memories[name]
        except KeyError:
            raise KeyError(f"no such memory: {name}") from None

    def revisions(self, name: str) -> list[MemoryRevision]:
        return list(self._revisions.get(name, []))

    # -- remediation --------------------------------------------------------------------

    def rollback(self, name: str, revision: str) -> StoredMemory:
        """Restore a memory to a revision and drop every revision newer than it.

        Dropping the newer revisions is the behaviour that matters: the probe confirmed the
        rolled-back revision was afterwards neither listable nor retrievable. A rollback that left
        the prohibited text reachable would not be a remediation.
        """
        history = self._revisions.get(name)
        if history is None:
            raise KeyError(f"no such memory: {name}")
        index = next((i for i, r in enumerate(history) if r.revision == revision), None)
        if index is None:
            raise KeyError(f"no such revision: {revision}")

        target = history[index]
        self._revisions[name] = history[index:]
        current = self._memories[name]
        self._memories[name] = StoredMemory(
            name=name, text=target.text, scope=current.scope, revision=target.revision
        )
        return self._memories[name]

    def delete(self, name: str) -> None:
        self._memories.pop(name, None)
        self._revisions.pop(name, None)
