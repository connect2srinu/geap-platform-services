"""The per-instance replay cache behind the `Idempotency-Key` contract.

`contracts/openapi.yaml` promises that the same key with the same payload yields one effect and
returns the original result, and that the same key with a different payload returns `422`. This
is what makes both true.

**It is per instance, deliberately.** 001 considered a shared idempotency store and rejected it
for v0.1.0: it would put a managed service into every domain's deployment. It named three
compensating controls instead — provider consolidation, session affinity, and this cache. Across
instances the guarantee is therefore best-effort, which is a residual risk with an expiry, not a
promise quietly broken.

Two details that are not obvious and are both load-bearing:

* **The key namespace is per caller and per scope, not global.** An idempotency key is a string
  the client chose, and nothing stops two end users picking the same one. A global namespace
  gets this wrong in both directions: the second end user either receives the first's response,
  carrying a `memoryId` from a scope they cannot read (security rule S-8), or is refused `422`
  for a collision they cannot see and cannot fix. So the entry is filed under a digest of the
  caller, the scope **and** the key; the fingerprint then only has to identify the body.
* **Only completed outcomes are recorded.** Caching a `PROVIDER_UNAVAILABLE` would turn a
  five-second outage into a permanent failure for that key, with the caller following the
  `Retry-After` we gave them into a wall.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

#: Long enough to cover any plausible client retry budget, short enough to bound memory.
DEFAULT_RETENTION_SECONDS = 900

#: A hard ceiling independent of expiry. Both are needed: expiry alone lets a flood of unique
#: keys grow memory before anything ages out, and a cap alone lets a quiet instance hold a key
#: long past any plausible retry.
DEFAULT_MAX_ENTRIES = 10_000


class KeyReused(Exception):
    """The key is known on this instance, but the request is not the one it recorded."""


@dataclass(frozen=True, slots=True)
class _Entry:
    fingerprint: str
    response: dict[str, Any]
    stored_at: float


def _digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def scoped_key(
    caller_id: str, scope: tuple[tuple[str, str], ...], idempotency_key: str
) -> str:
    """Where an entry is filed: one namespace per caller and end-user scope.

    Two end users who happen to choose the same key never meet. Nothing they can do to their own
    keys affects anyone else's, which is both the S-8 property and the reason a second end user
    is not refused for a collision they cannot see.
    """
    return _digest(
        {
            "caller": caller_id,
            "scope": [list(pair) for pair in scope],
            "key": idempotency_key,
        }
    )


def fingerprint(body: Any) -> str:
    """Identify the request *within* its namespace: the body, canonically.

    This is what distinguishes "the same key with the same payload" from "the same key with a
    different payload". Who asked is already settled by :func:`scoped_key`.
    """
    return _digest(body)


class ReplayCache:
    """Bounded, expiring, thread-safe record of what each idempotency key did here."""

    def __init__(
        self,
        *,
        retention_seconds: int = DEFAULT_RETENTION_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        if retention_seconds < 1:
            raise ValueError("retention_seconds must be at least 1")
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._retention = retention_seconds
        self._max_entries = max_entries
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def lookup(self, key: str, request_fingerprint: str) -> dict[str, Any] | None:
        """The recorded response, ``None`` if unseen, or raise if the request differs.

        Raising rather than returning a sentinel because the caller must not be able to treat a
        reused key as a cache miss and write anyway.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if time.monotonic() - entry.stored_at > self._retention:
                del self._entries[key]
                return None
            if entry.fingerprint != request_fingerprint:
                raise KeyReused(key)
            self._entries.move_to_end(key)
            return entry.response

    def record(
        self, key: str, request_fingerprint: str, response: dict[str, Any]
    ) -> None:
        """Record a **completed** outcome. Never call this for a retryable failure."""
        with self._lock:
            self._entries[key] = _Entry(
                fingerprint=request_fingerprint,
                response=response,
                stored_at=time.monotonic(),
            )
            self._entries.move_to_end(key)
            self._evict()

    def _evict(self) -> None:
        """Expired first, then oldest. Called with the lock held."""
        now = time.monotonic()
        for key in [
            key
            for key, entry in self._entries.items()
            if now - entry.stored_at > self._retention
        ]:
            del self._entries[key]
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
