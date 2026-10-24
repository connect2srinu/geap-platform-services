"""Telemetry, audit and the write budget.

One place that defines what the pattern emits, so `pattern.yaml`'s declared metrics and audit
events and the code cannot drift apart — a manifest promising telemetry nothing emits is worse
than one promising less, because the alerts built on it look configured and fire never, and an
audit event nobody emits tells a reviewer there is a trail where there is none.
"""

from .audit import AUDIT_EVENTS, AuditSink, LoggingAudit, NullAudit
from .budget import BudgetExhausted, WriteBudget
from .metrics import METRICS, LoggingMetrics, MetricSink, NullMetrics

__all__ = [
    "AUDIT_EVENTS",
    "METRICS",
    "AuditSink",
    "BudgetExhausted",
    "LoggingAudit",
    "LoggingMetrics",
    "MetricSink",
    "NullAudit",
    "NullMetrics",
    "WriteBudget",
]
