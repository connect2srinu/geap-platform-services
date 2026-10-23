"""The per-instance write budget.

The project's Memory Bank quota is shared across every domain in the platform project, so a domain
is given a share and must stay inside it. That share is divided by the instance ceiling, because
the budget has to hold however many instances are running — a per-instance limit of the whole
domain share would let N instances consume N times the share.

A token bucket rather than a fixed window: a fixed window lets a caller spend the whole minute's
budget in its first second and then starve, which looks identical to an outage from outside.

This is local to one instance. It bounds a domain's own consumption; it cannot stop another domain
exhausting the shared pool, which is what the platform-owned quota alert is for.
"""

from __future__ import annotations

import threading
import time


class BudgetExhausted(Exception):
    """The instance's share of the domain's write budget is spent."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("write budget exhausted")
        self.retry_after_seconds = retry_after_seconds


class WriteBudget:
    """A token bucket sized to one instance's share of the domain's budget."""

    def __init__(self, *, writes_per_minute: int, max_instances: int) -> None:
        if writes_per_minute < 1:
            raise ValueError("writes_per_minute must be at least 1")
        if max_instances < 1:
            raise ValueError("max_instances must be at least 1")

        # Floor, but never below one: an instance that can never write is worse than one that
        # occasionally exceeds a tiny share, and a domain with fewer writes than instances has
        # mis-sized something anyway.
        self._capacity = max(1, writes_per_minute // max_instances)
        self._per_second = self._capacity / 60.0
        self._tokens = float(self._capacity)
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        """Writes per minute this instance may make."""
        return self._capacity

    def take(self, tokens: int = 1) -> None:
        """Spend budget, or raise :class:`BudgetExhausted`."""
        with self._lock:
            now = time.monotonic()
            self._tokens = min(
                float(self._capacity),
                self._tokens + (now - self._updated) * self._per_second,
            )
            self._updated = now
            if self._tokens < tokens:
                shortfall = tokens - self._tokens
                raise BudgetExhausted(max(1, int(shortfall / self._per_second) + 1))
            self._tokens -= tokens
