"""Request-level errors.

Mirrors `contracts/errors.md`. A test asserts this enum matches the contract, because an error code
the contract does not publish is one an agent cannot handle.

Every error carries a code, a message **free of payload content**, and the correlation ID
(security rule S-4). A provider's raw text never reaches a caller.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    TOO_MANY_FACTS = "TOO_MANY_FACTS"
    IDEMPOTENCY_KEY_MISSING = "IDEMPOTENCY_KEY_MISSING"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    TOKEN_INVALID = "TOKEN_INVALID"
    CALLER_NOT_REGISTERED = "CALLER_NOT_REGISTERED"
    CALLER_NOT_PERMITTED = "CALLER_NOT_PERMITTED"
    SCOPE_NOT_RESOLVABLE = "SCOPE_NOT_RESOLVABLE"
    SCOPE_IN_BODY_REFUSED = "SCOPE_IN_BODY_REFUSED"
    RATE_LIMITED = "RATE_LIMITED"
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


#: HTTP status per code. A provider throttle is 503, never the caller's 429 — the caller did
#: nothing wrong, and shaping their behaviour would be the wrong fix.
_STATUS: dict[ErrorCode, int] = {
    ErrorCode.MALFORMED_REQUEST: 400,
    ErrorCode.TOO_MANY_FACTS: 400,
    ErrorCode.IDEMPOTENCY_KEY_MISSING: 400,
    ErrorCode.IDEMPOTENCY_KEY_REUSED: 422,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.TOKEN_INVALID: 401,
    ErrorCode.CALLER_NOT_REGISTERED: 403,
    ErrorCode.CALLER_NOT_PERMITTED: 403,
    ErrorCode.SCOPE_NOT_RESOLVABLE: 403,
    ErrorCode.SCOPE_IN_BODY_REFUSED: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.CONFIGURATION_INVALID: 503,
    ErrorCode.PROVIDER_UNAVAILABLE: 503,
}

_RETRYABLE = frozenset({ErrorCode.RATE_LIMITED, ErrorCode.PROVIDER_UNAVAILABLE})

#: Safe, fixed messages. Built here rather than from an exception's text so a provider's error
#: string or a payload fragment can never reach a caller by accident.
_MESSAGE: dict[ErrorCode, str] = {
    ErrorCode.MALFORMED_REQUEST: "The request does not match the schema.",
    ErrorCode.TOO_MANY_FACTS: "At most 5 facts per request.",
    ErrorCode.IDEMPOTENCY_KEY_MISSING: "The Idempotency-Key header is required.",
    ErrorCode.IDEMPOTENCY_KEY_REUSED: "That idempotency key was used with a different payload.",
    ErrorCode.UNAUTHENTICATED: "No credentials were presented.",
    ErrorCode.TOKEN_INVALID: "The token could not be verified.",
    ErrorCode.CALLER_NOT_REGISTERED: "The caller is not registered for this domain.",
    ErrorCode.CALLER_NOT_PERMITTED: "The caller may not perform this operation.",
    ErrorCode.SCOPE_NOT_RESOLVABLE: "The subject could not be resolved to a memory scope.",
    ErrorCode.SCOPE_IN_BODY_REFUSED: "Scope is derived from the caller and cannot be supplied.",
    ErrorCode.RATE_LIMITED: "The caller's rate limit was exceeded.",
    ErrorCode.CONFIGURATION_INVALID: "The service configuration is unusable.",
    ErrorCode.PROVIDER_UNAVAILABLE: "The memory store is unavailable. Retry with the same key.",
}


def error_response(
    code: ErrorCode, correlation_id: str, *, retry_after: int | None = None
) -> JSONResponse:
    """Build the one and only error shape this service returns."""
    body: dict[str, Any] = {
        "code": code.value,
        "message": _MESSAGE[code],
        "correlationId": correlation_id,
        "retryable": code in _RETRYABLE,
    }
    headers = {"X-Correlation-Id": correlation_id}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=_STATUS[code], content=body, headers=headers)
