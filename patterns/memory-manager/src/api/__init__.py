"""Transport: request validation, error mapping, correlation.

This layer translates. It makes no policy decision of its own — every allow or refuse comes from
`policy/`, and every store or read from `providers/`. Keeping it that thin is what let the decision
order be tested without a web server.
"""

from .errors import ErrorCode, error_response
from .models import (
    FactIn,
    FactResultOut,
    RecallResponse,
    RecalledValueOut,
    RememberRequest,
    RememberResponse,
)

__all__ = [
    "ErrorCode",
    "FactIn",
    "FactResultOut",
    "RecallResponse",
    "RecalledValueOut",
    "RememberRequest",
    "RememberResponse",
    "error_response",
]
