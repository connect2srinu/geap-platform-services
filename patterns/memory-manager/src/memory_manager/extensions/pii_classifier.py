"""Extension point: classify a fact before it is persisted.

The **obligation** to classify is the platform's and cannot be configured away. The **vocabulary** —
what counts as prohibited in this domain — is the domain's.

Required. Defaults to deny-all.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import CallerContext, ClassificationResult, Fact


@runtime_checkable
class PiiClassifier(Protocol):
    """Decides whether a fact's content may be stored.

    Called twice per fact: once before the write, and again on the content that came back after
    provider consolidation, because consolidation can rewrite a fact after the first check passed.

    Implementations must:

    - be **pure and side-effect free** — they are called on the request path;
    - never log, trace or transmit `fact.text` or `fact.value`;
    - raise :class:`~.types.ExtensionError` when they cannot decide, rather than guessing.

    A raised error becomes a denial, never an approval.
    """

    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        """Return whether this fact's content may be stored."""
        ...


class DenyAllClassifier:
    """The platform default: refuses everything.

    This is deliberate and is not a placeholder. A domain that has not supplied a classifier has not
    told us what is sensitive in its data, and the safe reading of "I don't know" is "don't store
    it". The opposite default — storing everything until someone writes a classifier — fails open on
    exactly the data this pattern exists to protect.

    The service logs loudly at startup when this is in force.
    """

    #: Surfaced at startup so an operator sees why nothing is being stored.
    startup_warning = (
        "pii-classifier is not configured; the deny-all default is in force and no fact will be "
        "stored. Configure extensions.piiClassifier."
    )

    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        return ClassificationResult(allowed=False, reason="NO_CLASSIFIER_CONFIGURED")
