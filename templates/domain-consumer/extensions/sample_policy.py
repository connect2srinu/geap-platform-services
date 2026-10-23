"""A WORKED EXAMPLE of a policy provider. Not production code.

**Do not ship this.** Your policy will consult your own roles, grants or entitlement service.

The one rule worth copying is the direction of travel: this runs *after* the platform's own
checks and can only narrow them. Returning ``allowed=True`` means "no further objection" — it
cannot overturn a platform denial, so a domain cannot widen access past what the pattern permits.
Raising becomes a denial plus a metric, never a bypass.
"""

from __future__ import annotations

from memory_manager.extensions import PolicyDecision

#: Belt and braces with the `operations` list in configuration: a mis-edit there is one line.
_READ_ONLY_CALLERS: frozenset[str] = frozenset({"example-reader-agent"})


class SamplePolicyProvider:
    def decide(self, caller, operation: str, topic: str) -> PolicyDecision:
        if operation != "recall" and caller.caller_id in _READ_ONLY_CALLERS:
            return PolicyDecision(allowed=False)
        return PolicyDecision(allowed=True)
