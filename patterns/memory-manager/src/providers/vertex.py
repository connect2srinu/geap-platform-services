"""The Vertex AI Memory Bank adapter.

Every call and keyword below was checked against the installed
``google-cloud-aiplatform[agent_engines]==2.3.0`` on 2026-10-22, not against documentation. The
surface is ``client.agent_engines.memories``:

    generate(name, direct_memories_source=..., scope=...)  -> operation with generated_memories
    get(name)                                              -> Memory
    list(name)                                             -> Iterator[Memory]
    rollback(name, target_revision_id=...)                 -> operation
    delete(name)                                           -> operation
    revisions.list(name)                                   -> Iterator[MemoryRevision]

Two things the inspection corrected, which the design had assumed differently:

* Revisions and rollback live on the **memories** sub-client, not on ``agent_engines`` itself, and
  ``rollback`` takes ``target_revision_id`` rather than a revision object.
* ``retrieve`` is a **similarity search** over a scope, so it is not the right call for "give me
  everything in this scope". ``list`` is, and that is what :meth:`retrieve` below uses, filtering by
  scope in the adapter. Paging is handled by the SDK's own iterator rather than by a page token,
  which sidesteps the broken pager the probe found.

The import is deferred into the constructor so the rest of the pattern, its tests and CI do not need
the SDK installed. It is declared as the ``provider`` extra in ``pyproject.toml``.
"""

from __future__ import annotations

from typing import Any

from ..observability import MetricSink, NullMetrics
from .encoding import decode_fact_text
from .memory_bank import (
    MAX_FACTS_PER_WRITE,
    MemoryAction,
    MemoryRevision,
    ProviderThrottled,
    ProviderUnavailable,
    StoredMemory,
    WriteOutcome,
    WriteResult,
)

Scope = tuple[tuple[str, str], ...]

#: Provider error text that means "throttled". Matched case-insensitively on the exception's string
#: because the SDK raises google.api_core errors whose types we do not import here.
_THROTTLE_MARKERS = ("resource_exhausted", "429", "quota", "rate limit")

_ACTION = {
    "CREATED": MemoryAction.CREATED,
    "UPDATED": MemoryAction.UPDATED,
    "DELETED": MemoryAction.DELETED,
}


def _is_throttle(error: BaseException) -> bool:
    text = str(error).lower()
    return any(marker in text for marker in _THROTTLE_MARKERS)


def _wrap(error: BaseException) -> ProviderUnavailable:
    """Turn a provider error into ours, keeping no provider text.

    The message is fixed. A provider's string can carry a resource name or a fragment of the fact,
    and this exception's text can reach a log, so none of it is copied through (S-4).
    """
    if _is_throttle(error):
        return ProviderThrottled("the memory store throttled the request")
    return ProviderUnavailable("the memory store is unavailable")


class VertexMemoryBank:
    """A :class:`~.memory_bank.MemoryBank` backed by Vertex AI Memory Bank.

    ``bank`` is the full Agent Engine resource name, e.g.
    ``projects/<number>/locations/<region>/reasoningEngines/<id>``.
    """

    def __init__(
        self,
        *,
        project: str,
        location: str,
        bank: str,
        client: Any | None = None,
        metrics: MetricSink | None = None,
    ) -> None:
        self._bank = bank
        self._metrics = metrics or NullMetrics()
        if client is not None:
            self._memories = client
            return
        try:
            import vertexai  # noqa: PLC0415 - deferred so the SDK is optional
        except (
            ImportError
        ) as exc:  # pragma: no cover - exercised only without the extra
            raise ProviderUnavailable(
                "the provider SDK is not installed; install the 'provider' extra"
            ) from exc
        self._memories = vertexai.Client(
            project=project, location=location
        ).agent_engines.memories

    # -- writes ----------------------------------------------------------------------

    def write(self, facts: list[str], scope: Scope) -> WriteResult:
        if len(facts) > MAX_FACTS_PER_WRITE:
            raise ValueError(
                f"the provider accepts at most {MAX_FACTS_PER_WRITE} facts per write, got {len(facts)}"
            )
        if not facts:
            return WriteResult(outcome=WriteOutcome.APPLIED)

        self._metrics.increment("provider_requests", operation="generate")
        try:
            operation = self._memories.generate(
                name=self._bank,
                direct_memories_source={
                    "direct_memories": [{"fact": f} for f in facts]
                },
                scope=dict(scope),
            )
        except Exception as exc:  # noqa: BLE001 - every provider failure becomes ours
            wrapped = _wrap(exc)
            if isinstance(wrapped, ProviderThrottled):
                self._metrics.increment("provider_throttled", operation="generate")
            raise wrapped from exc

        # Per-domain attribution. The project quota is shared, so without this a contention
        # incident shows writes failing but not whose traffic caused it.
        self._metrics.increment(
            "quota_consumed", operation="generate", facts=str(len(facts))
        )

        generated = (
            getattr(getattr(operation, "response", None), "generated_memories", None)
            or []
        )
        affected: list[tuple[str, MemoryAction]] = []
        for item in generated:
            memory = getattr(item, "memory", None)
            name = getattr(memory, "name", None)
            if name is None:
                continue
            raw_action = getattr(item, "action", None)
            action = _ACTION.get(str(getattr(raw_action, "name", raw_action)).upper())
            affected.append((name, action or MemoryAction.UPDATED))

        return WriteResult(outcome=WriteOutcome.APPLIED, affected=tuple(affected))

    # -- reads -----------------------------------------------------------------------

    def retrieve(self, scope: Scope) -> list[StoredMemory]:
        """Every memory in a scope.

        Uses ``list`` and filters by scope, not ``retrieve``: the latter is a similarity search and
        would silently return a *ranked subset*, which is the wrong answer to "show me everything".
        The SDK's iterator handles paging.
        """
        wanted = dict(scope)
        self._metrics.increment("provider_requests", operation="list")
        try:
            found = [
                self._to_stored(m)
                for m in self._memories.list(name=self._bank)
                if (getattr(m, "scope", None) or {}) == wanted
            ]
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc
        return found

    def get(self, name: str) -> StoredMemory:
        try:
            return self._to_stored(self._memories.get(name=name))
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def revisions(self, name: str) -> list[MemoryRevision]:
        try:
            return [
                MemoryRevision(
                    name=name,
                    revision=self._revision_id(getattr(r, "name", "") or ""),
                    text=getattr(r, "fact", "") or "",
                )
                for r in self._memories.revisions.list(name=name)
            ]
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    # -- remediation -------------------------------------------------------------------

    def rollback(self, name: str, revision: str) -> StoredMemory:
        try:
            self._memories.rollback(name=name, target_revision_id=revision)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc
        return self.get(name)

    def delete(self, name: str) -> None:
        try:
            self._memories.delete(name=name)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    # -- translation ---------------------------------------------------------------------

    @staticmethod
    def _revision_id(resource_name: str) -> str:
        """A revision's id is the last path segment of its resource name."""
        return resource_name.rsplit("/", 1)[-1] if resource_name else ""

    def _to_stored(self, memory: Any) -> StoredMemory:
        expire = getattr(memory, "expire_time", None)
        scope = getattr(memory, "scope", None) or {}
        return StoredMemory(
            name=getattr(memory, "name", "") or "",
            text=getattr(memory, "fact", "") or "",
            scope=tuple(sorted(scope.items())),
            expire_time=expire.isoformat() if expire is not None else None,
        )


def topic_of(stored: StoredMemory) -> str | None:
    """The topic a stored memory claims, or None when its prefix will not decode."""
    decoded = decode_fact_text(stored.text)
    return decoded.topic if decoded else None
