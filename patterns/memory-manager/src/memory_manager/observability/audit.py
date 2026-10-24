"""The audit events this pattern emits, and how.

`AUDIT_EVENTS` is the authoritative list. Tests assert it matches `pattern.yaml` exactly and
matches what the source emits, both in both directions. That pairing exists because the manifest
once declared seven events the code emitted none of: a declared-and-unemitted event tells a
reviewer the coverage is there when it is not, and an emitted-and-undeclared event is invisible
to anyone reading the contract.

Emission is a structured log line, as metrics are, so the service carries no audit client and the
prohibited-field rule is enforced in one place.

**An audit record names things; it never carries them.** Identifiers, counts, decisions and
reason codes. The end user is identified by the HMAC pseudonym the service already derives, never
by the raw subject, so a record cannot be reversed to a person by anyone without the key
(security rules S-4 and S-8).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Protocol

#: Every audit event the pattern emits. Keep in step with pattern.yaml; a test enforces it.
#:
#: `role_grant` and `role_revocation` are deliberately absent. This service never grants or
#: revokes a role — roles arrive in configuration and in IAM — so declaring them would assert a
#: responsibility it cannot discharge.
AUDIT_EVENTS: frozenset[str] = frozenset(
    {
        "memory_write",
        "memory_recall",
        "memory_deletion",
        "memory_remediation",
        "memory_write_unverified",
        "policy_denial",
        "configuration_change",
        "exception_invoked",
        "idempotency_replay",
    }
)

#: Field names that would carry payload into an audit record. The first seven are
#: `pattern.yaml`'s `prohibitedLogFields` verbatim — a test asserts that, so the manifest and this
#: list cannot drift. The rest are the names a value tends to arrive under.
_PROHIBITED_FIELDS: frozenset[str] = frozenset(
    {
        "memory_content",
        "pii",
        "sensitive_value",
        "restricted_value",
        "secrets",
        "authorization_header",
        "provider_error_body",
        "value",
        "fact",
        "text",
        "subject",
        "user_id",
        "email",
        "token",
        "secret",
        "payload",
    }
)

#: A field value longer than this is content, not an identifier or a code.
_MAX_FIELD_LENGTH = 128


class AuditSink(Protocol):
    """Where the pattern records what it did. Identifiers and decisions, never values."""

    def emit(self, event: str, **fields: str) -> None: ...


class NullAudit:
    """Discards everything.

    The default on `Deployment`, so a component constructed without a sink still runs — in a
    test, or in `verify_write` called directly. `bootstrap` always supplies a real one, and a
    test asserts that, because a deployment that silently audits nothing is the defect this
    module was written for.
    """

    def emit(self, event: str, **fields: str) -> None:
        return None


class LoggingAudit:
    """Emits one structured line per audit event.

    Rejects an undeclared event and a field that would carry payload. Both are programming
    errors; catching them here costs a test and catching them later costs a log retention
    policy.
    """

    def __init__(self, *, domain: str, logger: logging.Logger | None = None) -> None:
        self._domain = domain
        self._logger = logger or _default_logger()

    def emit(self, event: str, **fields: str) -> None:
        if event not in AUDIT_EVENTS:
            raise ValueError(
                f"'{event}' is not a declared audit event; add it to AUDIT_EVENTS and pattern.yaml"
            )
        for name, value in fields.items():
            if name.lower() in _PROHIBITED_FIELDS:
                raise ValueError(
                    f"field '{name}' would carry payload into an audit record (S-4)"
                )
            if len(value) > _MAX_FIELD_LENGTH:
                raise ValueError(
                    f"field '{name}' is too long to be an identifier; it looks like content"
                )
        self._logger.info(
            json.dumps(
                {"audit": event, "domain": self._domain, **fields}, sort_keys=True
            )
        )


def _default_logger() -> logging.Logger:
    logger = logging.getLogger("memory_manager.audit")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
