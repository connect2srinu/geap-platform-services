"""Per-fact reason codes.

These mirror `contracts/openapi.yaml` exactly. A test asserts they match, because a reason code the
contract does not publish is one an agent cannot handle.
"""

from __future__ import annotations

from enum import Enum


class ReasonCode(str, Enum):
    """Why a fact was stored or refused. Published in the contract."""

    ACCEPTED = "ACCEPTED"
    TOPIC_UNKNOWN = "TOPIC_UNKNOWN"
    TOPIC_DISABLED = "TOPIC_DISABLED"
    TOPIC_NOT_APPROVED = "TOPIC_NOT_APPROVED"
    TOPIC_SENSITIVE = "TOPIC_SENSITIVE"
    TOPIC_RESTRICTED = "TOPIC_RESTRICTED"
    FIELD_UNKNOWN = "FIELD_UNKNOWN"
    VALUE_TYPE_INVALID = "VALUE_TYPE_INVALID"
    VALUE_PROHIBITED = "VALUE_PROHIBITED"
    INFERENCE_NOT_PERMITTED = "INFERENCE_NOT_PERMITTED"
    CLASSIFIER_ERROR = "CLASSIFIER_ERROR"


#: The order the checks run in, as named steps. Asserted by a test, because the order is a design
#: decision rather than an implementation detail:
#:
#: * structural checks run before the classifier, so a malformed fact never reaches a domain's
#:   classifier and never costs a provider call;
#: * **sensitivity is checked before the caller's grant.** A sensitive topic is not storable by
#:   anyone, so `TOPIC_SENSITIVE` is the truthful answer. Reporting `TOPIC_NOT_APPROVED` would
#:   invite an agent team to request a grant that can never be given.
CHECK_ORDER: tuple[str, ...] = (
    "topic_known",
    "topic_enabled",
    "topic_classification",
    "caller_granted",
    "field_known",
    "value_type",
    "basis_permitted",
    "policy_provider",
    "classifier",
)
