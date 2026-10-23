"""The metrics this pattern emits, and how.

`METRICS` is the authoritative list. A test asserts it matches `pattern.yaml` exactly, in both
directions: a metric declared but never emitted makes an alert that never fires, and a metric
emitted but never declared is invisible to anyone reading the contract.

Emission is a structured log line, which Cloud Logging turns into a user metric. That keeps the
service free of a metrics client and means the prohibited-field rule is enforced in one place: a
label is a name or a code, never a value (security rule S-4).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Protocol

#: Every metric the pattern emits. Keep in step with pattern.yaml; a test enforces it.
METRICS: frozenset[str] = frozenset(
    {
        "tool_invocations",
        "tool_latency",
        "facts_evaluated",
        "policy_denials",
        "verification_outcomes",
        "remediations",
        "recall_withheld",
        "provider_requests",
        "provider_throttled",
        "quota_consumed",
        "quota_budget_exhausted",
        "extension_errors",
    }
)

#: Label values that would carry payload. Checked at emission rather than trusted, because the
#: cost of being wrong is memory content in a metric label, where it is retained and queryable.
_FORBIDDEN_LABELS: frozenset[str] = frozenset(
    {
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

#: A label value longer than this is almost certainly content rather than a code.
_MAX_LABEL_LENGTH = 64


class MetricSink(Protocol):
    """Where the pattern reports counts. Names and codes only."""

    def increment(self, metric: str, **labels: str) -> None: ...


class NullMetrics:
    """Discards everything. The default, so a component without a sink still runs."""

    def increment(self, metric: str, **labels: str) -> None:
        return None


class LoggingMetrics:
    """Emits a structured line per metric, for Cloud Logging to turn into a user metric.

    Rejects an undeclared metric and a label that looks like payload. Both are programming errors,
    and both are cheaper to catch here than in a log retention policy.
    """

    def __init__(self, *, domain: str, logger: logging.Logger | None = None) -> None:
        self._domain = domain
        self._logger = logger or _default_logger()

    def increment(self, metric: str, **labels: str) -> None:
        if metric not in METRICS:
            raise ValueError(
                f"'{metric}' is not a declared metric; add it to METRICS and pattern.yaml"
            )
        for name, value in labels.items():
            if name.lower() in _FORBIDDEN_LABELS:
                raise ValueError(
                    f"label '{name}' would carry payload into a metric (S-4)"
                )
            if len(value) > _MAX_LABEL_LENGTH:
                raise ValueError(
                    f"label '{name}' is too long to be a code; it looks like content"
                )
        self._logger.info(
            json.dumps(
                {"metric": metric, "domain": self._domain, **labels}, sort_keys=True
            )
        )


def _default_logger() -> logging.Logger:
    logger = logging.getLogger("memory_manager.metrics")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
