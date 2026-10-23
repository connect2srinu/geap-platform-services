"""Extension point: decide whether a caller may perform an operation on a topic.

The platform enforces the *order* the checks run in and that they fail closed. Which callers hold
which grants is the domain's.

Required. Defaults to deny-all.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import CallerContext, PolicyDecision


@runtime_checkable
class PolicyProvider(Protocol):
    """Decides whether a caller may act on a topic.

    Runs **after** the platform's own checks, and can only narrow their outcome. Returning
    ``allowed=True`` means "no further objection" — it cannot overturn a platform denial, so a
    domain cannot widen access past what the pattern permits.

    Raise :class:`~.types.ExtensionError` rather than guessing; it becomes a denial.
    """

    def decide(
        self, caller: CallerContext, operation: str, topic: str
    ) -> PolicyDecision:
        """Return whether this caller may perform this operation on this topic."""
        ...


class DenyAllPolicyProvider:
    """The platform default: refuses everything.

    A domain that has not supplied a policy provider has not said who may do what, and the safe
    reading is that nobody may. Logged loudly at startup.
    """

    startup_warning = (
        "policy-provider is not configured; the deny-all default is in force and every request will "
        "be refused. Configure extensions.policyProvider."
    )

    def decide(
        self, caller: CallerContext, operation: str, topic: str
    ) -> PolicyDecision:
        return PolicyDecision(allowed=False, reason="NO_POLICY_PROVIDER_CONFIGURED")
