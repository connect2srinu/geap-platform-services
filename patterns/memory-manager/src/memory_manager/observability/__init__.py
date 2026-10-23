"""Telemetry and the write budget.

One place that defines what the pattern emits, so `pattern.yaml`'s declared metrics and the code
cannot drift apart — a manifest promising telemetry nothing emits is worse than one promising less,
because the alerts built on it look configured and fire never.
"""

from .budget import BudgetExhausted, WriteBudget
from .metrics import METRICS, LoggingMetrics, MetricSink, NullMetrics

__all__ = [
    "METRICS",
    "BudgetExhausted",
    "LoggingMetrics",
    "MetricSink",
    "NullMetrics",
    "WriteBudget",
]
