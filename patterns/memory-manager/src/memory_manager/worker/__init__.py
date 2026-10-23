"""Post-write verification and remediation.

The write gate decides what *may* be stored. This package checks what *was* stored, because the
provider consolidates and can rewrite a fact after the gate has passed it.
"""

from .verification import (
    Remediation,
    VerificationOutcome,
    VerificationResult,
    verify_write,
)

__all__ = [
    "Remediation",
    "VerificationOutcome",
    "VerificationResult",
    "verify_write",
]
