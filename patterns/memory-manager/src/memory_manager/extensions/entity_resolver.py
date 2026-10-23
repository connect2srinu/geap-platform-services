"""Extension point: resolve an entity reference to a domain-internal identifier.

This is domain identity resolution — it is wrong for any domain other than the one that wrote it,
which is precisely why it is an extension point and not platform code.

Optional. Defaults to a no-op pass-through. On failure: **skip**, not deny — a resolver that cannot
map a reference has not found prohibited content, it has simply not enriched the fact.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import CallerContext, Fact


@runtime_checkable
class EntityResolver(Protocol):
    """Rewrites entity references in a fact into domain-internal identifiers.

    Unlike the classifier and the policy provider, a failure here is tolerated: the fact proceeds
    unresolved, with an ``extension_errors`` metric. That is safe because resolution enriches a fact
    rather than deciding whether it may be stored.

    Must not widen a fact's content — returning something with different `topic` or `basis` is a
    defect, and the pipeline asserts it.
    """

    def resolve(self, fact: Fact, caller: CallerContext) -> Fact:
        """Return the fact with entity references resolved, or unchanged."""
        ...


class NoOpEntityResolver:
    """The platform default: returns the fact untouched.

    Safe as a permissive default because resolution cannot grant storage — the classifier and the
    policy provider have already decided that, and both default to deny.
    """

    def resolve(self, fact: Fact, caller: CallerContext) -> Fact:
        return fact
