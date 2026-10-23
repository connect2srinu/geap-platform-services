"""Shared types for the extension points.

Frozen dataclasses throughout: an extension receives a value it cannot mutate, so it cannot alter
what the caller submitted on its way through a decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

ValueType = Literal["string", "number", "boolean"]
FactBasis = Literal["stated", "inferred"]


class Classification(str, Enum):
    """How a domain classifies a topic. Only NON_SENSITIVE is eligible for storage."""

    NON_SENSITIVE = "non-sensitive"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class ExtensionError(Exception):
    """Raised by an extension that cannot reach a decision.

    The dispatcher turns this into a **denial** plus an `extension_errors` metric. It is never a
    bypass: an extension that fails is not an extension that approved.
    """


@dataclass(frozen=True, slots=True)
class TopicField:
    name: str
    value_type: ValueType
    max_length: int | None = None


@dataclass(frozen=True, slots=True)
class Topic:
    id: str
    classification: Classification
    enabled: bool
    allow_inferred: bool = False
    fields: tuple[TopicField, ...] = ()

    @property
    def is_eligible(self) -> bool:
        """Eligible for storage: enabled and non-sensitive. Both, not either."""
        return self.enabled and self.classification is Classification.NON_SENSITIVE


@dataclass(frozen=True, slots=True)
class Fact:
    """A fact as submitted. `text` is what the Memory Bank stores and is classified in full."""

    topic: str
    value: str | float | bool
    text: str
    field_name: str | None = None
    basis: FactBasis = "stated"


@dataclass(frozen=True, slots=True)
class CallerContext:
    """The authenticated caller and the scope resolved **server-side** from its token.

    `scope` never comes from a request body. `subject_pseudonym` is an HMAC of the end-user subject;
    the raw subject is not carried here, so an extension cannot log it even by accident.
    """

    caller_id: str
    domain: str
    scope: tuple[tuple[str, str], ...]
    subject_pseudonym: str
    operations: frozenset[str] = frozenset()
    granted_topics: frozenset[str] = frozenset()
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """A classifier's verdict on one fact.

    `allowed` is the only thing the pipeline acts on. `reason` is a short code for logs and metrics
    and **must not contain the value** — see security rule S-4.
    """

    allowed: bool
    reason: str = ""
    categories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(self.reason) > 64:
            raise ValueError(
                "reason is a short code, not a message; it must not carry the value"
            )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """A policy provider's verdict on a caller's request.

    A provider may **refine** a decision but never overturn a platform denial: the pipeline treats
    `allowed=True` as "no further objection", not as an override.
    """

    allowed: bool
    reason: str = ""
    restricted_topics: frozenset[str] = field(default_factory=frozenset)
