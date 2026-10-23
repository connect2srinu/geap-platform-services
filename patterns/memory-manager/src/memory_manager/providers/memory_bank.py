"""The Memory Bank boundary.

A Protocol rather than a base class, so the fake and the real adapter are interchangeable without
either inheriting from the other, and so a test never needs the provider SDK installed.

The shape follows what the live probe established on 2026-10-22; nothing here is speculative:

* a write accepts **at most five facts** and reports, per memory, whether it was created or updated;
* submitting an identical fact twice updates the existing memory rather than creating a second;
* a read immediately after a write reflects the consolidated content;
* revisions are listable and a rollback removes the rolled-back revision from both listing and
  retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

#: The provider accepts no more than this many facts per write. Verified live; the contract caps
#: `remember` at the same number rather than splitting a larger batch across calls.
MAX_FACTS_PER_WRITE = 5


class ProviderUnavailable(Exception):
    """The bank could not be reached, or refused the operation.

    Mapped to `503 PROVIDER_UNAVAILABLE`. The write was not accepted; a retry with the same
    idempotency key is correct.
    """


class ProviderThrottled(ProviderUnavailable):
    """The provider throttled the request.

    A subclass of :class:`ProviderUnavailable` so callers that do not care about the distinction
    behave correctly by default. It is **never** surfaced as the caller's `429`: the caller did
    nothing wrong, and shaping their behaviour would be the wrong fix.
    """


class MemoryAction(str, Enum):
    """What the provider did to a memory."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


class WriteOutcome(str, Enum):
    """The result of a write, before read-back verification."""

    APPLIED = "APPLIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class StoredMemory:
    """A memory as the provider holds it.

    ``text`` is the consolidated content, which may differ from what was submitted — that is the
    whole reason read-back re-classification exists.
    """

    name: str
    text: str
    scope: tuple[tuple[str, str], ...]
    revision: str = ""
    expire_time: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryRevision:
    name: str
    revision: str
    text: str


@dataclass(frozen=True, slots=True)
class WriteResult:
    """What one write did, per affected memory."""

    outcome: WriteOutcome
    affected: tuple[tuple[str, MemoryAction], ...] = ()

    @property
    def memory_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.affected)


@runtime_checkable
class MemoryBank(Protocol):
    """The operations the pattern needs from a Memory Bank.

    Runtime-checkable, so a test can assert an implementation satisfies the shape. Note that an
    `isinstance` check verifies method *names* only, not signatures -- mypy covers those.

    Every method raises :class:`ProviderUnavailable` (or :class:`ProviderThrottled`) rather than
    returning an error value, so a failure cannot be mistaken for an empty result.
    """

    def write(
        self, facts: list[str], scope: tuple[tuple[str, str], ...]
    ) -> WriteResult:
        """Submit pre-extracted facts for storage, letting the provider consolidate.

        Raises ``ValueError`` when given more than :data:`MAX_FACTS_PER_WRITE` facts — a caller that
        has not enforced the contract's cap is a defect, not a provider error.
        """
        ...

    def retrieve(self, scope: tuple[tuple[str, str], ...]) -> list[StoredMemory]:
        """Return every memory in a scope."""
        ...

    def get(self, name: str) -> StoredMemory:
        """Return one memory by name, reflecting consolidated content."""
        ...

    def revisions(self, name: str) -> list[MemoryRevision]:
        """Return a memory's revisions, newest first."""
        ...

    def rollback(self, name: str, revision: str) -> StoredMemory:
        """Restore a memory to a revision. The rolled-back revision is no longer retrievable."""
        ...

    def delete(self, name: str) -> None:
        """Remove a memory and its revisions."""
        ...
