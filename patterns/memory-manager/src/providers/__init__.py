"""The managed-service boundary.

`memory_bank` defines the shape the pattern depends on; `fake` is an in-memory double that models the
behaviour **verified against a real bank on 2026-10-22**, not behaviour that would merely be
convenient. `encoding` is the fact-text format, which is pure and shared by both.

The binding to the provider SDK is deliberately not here yet. Writing it against a surface that is not
installed in this environment would mean inventing method names, and a mock built on invented names
proves nothing. It is the next task, to be written with every call checked against the installed
package — the way the probe was.
"""

from .encoding import ENCODED_PREFIX, decode_fact_text, encode_fact_text
from .fake import FakeMemoryBank
from .memory_bank import (
    MemoryAction,
    MemoryBank,
    MemoryRevision,
    ProviderThrottled,
    ProviderUnavailable,
    StoredMemory,
    WriteOutcome,
    WriteResult,
)

__all__ = [
    "ENCODED_PREFIX",
    "FakeMemoryBank",
    "MemoryAction",
    "MemoryBank",
    "MemoryRevision",
    "ProviderThrottled",
    "ProviderUnavailable",
    "StoredMemory",
    "WriteOutcome",
    "WriteResult",
    "decode_fact_text",
    "encode_fact_text",
]
