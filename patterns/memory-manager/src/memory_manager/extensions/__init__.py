"""Extension points a consuming domain implements.

Everything a domain needs is importable from here, so domain code never reaches into the pattern's
internals. The interfaces are `typing.Protocol`s: a domain implements the shape, it does not inherit
from us.

Two of the four are **required and default to deny-all**. An unconfigured deployment therefore stores
nothing, which is the failure mode worth having. Omitting a classifier must not mean "store
everything".
"""

from .entity_resolver import EntityResolver, NoOpEntityResolver
from .pii_classifier import DenyAllClassifier, PiiClassifier
from .policy_provider import DenyAllPolicyProvider, PolicyProvider
from .topic_provider import TopicProvider, YamlTopicProvider
from .types import (
    CallerContext,
    Classification,
    ClassificationResult,
    ExtensionError,
    Fact,
    FactBasis,
    PolicyDecision,
    Topic,
    TopicField,
    ValueType,
)

__all__ = [
    "CallerContext",
    "Classification",
    "ClassificationResult",
    "DenyAllClassifier",
    "DenyAllPolicyProvider",
    "EntityResolver",
    "ExtensionError",
    "Fact",
    "FactBasis",
    "NoOpEntityResolver",
    "PiiClassifier",
    "PolicyDecision",
    "PolicyProvider",
    "Topic",
    "TopicField",
    "TopicProvider",
    "ValueType",
    "YamlTopicProvider",
]
