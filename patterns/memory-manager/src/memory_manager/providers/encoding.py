"""The stored fact-text format.

A fact is stored with a machine-readable prefix so that a memory read back later can be attributed to
a topic and field without a side table:

    [topic=preferred_brands][field=brand] The user prefers the organic brand Horizon.

The probe confirmed on 2026-10-22 that this prefix **survives provider consolidation** — both
memories in the test scope kept it after an update. That is the single assumption this module rests
on, and read-back verification depends on it: without an intact prefix, a consolidated memory cannot
be matched to the topic whose rules should judge it.

Pure functions, no provider import, so the format is testable on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ENCODED_PREFIX = re.compile(
    r"^\[topic=([a-z][a-z0-9_]{2,48})\](?:\[field=([a-z][a-z0-9_]{1,48})\])?\s*"
)

#: Characters that would let a value forge a second prefix and misattribute itself to another topic.
_FORBIDDEN_IN_PREFIX = ("[", "]")


@dataclass(frozen=True, slots=True)
class DecodedFact:
    """What a stored memory's text says about itself."""

    topic: str
    field: str | None
    text: str


def encode_fact_text(topic: str, field: str | None, text: str) -> str:
    """Prefix a fact's text with its topic and field.

    Refuses a topic or field containing a bracket. Without that check a crafted field name could
    close the prefix early and open another, so a fact could claim a topic it was never validated
    against — the decode side would believe it.
    """
    for part, label in ((topic, "topic"), (field, "field")):
        if part is None:
            continue
        if any(ch in part for ch in _FORBIDDEN_IN_PREFIX):
            raise ValueError(f"{label} must not contain a bracket")

    prefix = f"[topic={topic}]"
    if field is not None:
        prefix += f"[field={field}]"
    return f"{prefix} {text}"


def decode_fact_text(stored: str) -> DecodedFact | None:
    """Read a stored memory's prefix back.

    Returns ``None`` when the prefix is absent or malformed. That is deliberately distinct from a
    successful decode: a memory the pattern cannot attribute to a topic must be **remediated**, not
    silently treated as belonging to no topic and therefore harmless.
    """
    match = ENCODED_PREFIX.match(stored)
    if match is None:
        return None
    return DecodedFact(
        topic=match.group(1),
        field=match.group(2),
        text=stored[match.end() :],
    )
