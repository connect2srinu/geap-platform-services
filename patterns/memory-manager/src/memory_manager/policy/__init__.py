"""Authorization and classification decisions.

This package decides; it never writes. No provider call, no I/O, no clock — a decision is a pure
function of the facts submitted, the caller, the domain's topic vocabulary and the extensions. That
is what makes the decision order testable without a Memory Bank.
"""

from .pipeline import FactOutcome, ValidationPipeline, validate_facts
from .reasons import CHECK_ORDER, ReasonCode

__all__ = [
    "CHECK_ORDER",
    "FactOutcome",
    "ReasonCode",
    "ValidationPipeline",
    "validate_facts",
]
