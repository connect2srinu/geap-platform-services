"""The telemetry contract: what is declared, what is emitted, and the write budget.

The first group exists because of a real defect found during the final review: seven of the twelve
metrics `pattern.yaml` declared were emitted nowhere, two of them (`provider_throttled` and
`quota_consumed`) referenced by the platform-owned alert policies. An alert built on a metric
nothing emits looks configured and fires never, which is worse than having no alert at all.
"""

from __future__ import annotations

import ast
import json
import logging
import sys
import time
from pathlib import Path

import pytest
import yaml

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))

from memory_manager.observability import (  # noqa: E402
    METRICS,
    BudgetExhausted,
    LoggingMetrics,
    NullMetrics,
    WriteBudget,
)

SRC = PATTERN / "src"
TERRAFORM = PATTERN / "infrastructure" / "terraform"


def _declared_metrics() -> set[str]:
    manifest = yaml.safe_load((PATTERN / "pattern.yaml").read_text(encoding="utf-8"))
    return set(manifest["spec"]["observability"]["requiredMetrics"])


def _emitted_metrics() -> set[str]:
    """Every string literal passed as the first argument to an `increment` call under src/.

    Parsed rather than grepped: a grep for the metric name also matches the declaration list and
    the docstrings, which is exactly how the original gap stayed invisible.
    """
    emitted: set[str] = set()
    for path in SRC.rglob("*.py"):
        if path == SRC / "observability" / "metrics.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "increment"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                emitted.add(node.args[0].value)
    return emitted


class TestMetricsContract:
    def test_metrics_constant_matches_the_manifest(self) -> None:
        assert set(METRICS) == _declared_metrics()

    def test_every_declared_metric_is_emitted_somewhere(self) -> None:
        missing = sorted(set(METRICS) - _emitted_metrics())
        assert not missing, f"declared but never emitted: {missing}"

    def test_every_emitted_metric_is_declared(self) -> None:
        undeclared = sorted(_emitted_metrics() - set(METRICS))
        assert not undeclared, f"emitted but not in the contract: {undeclared}"

    def test_alert_policies_reference_metrics_that_exist(self) -> None:
        """An alert naming a metric nothing emits is the failure this suite was written for."""
        nfr = TERRAFORM / "memory-bank-nfr" / "main.tf"
        if not nfr.is_file():  # pragma: no cover - the module is part of the pattern
            pytest.skip("platform-owned Terraform module not present")
        text = nfr.read_text(encoding="utf-8")
        for metric in ("provider_throttled", "remediations"):
            assert metric in text
            assert metric in METRICS


class TestLoggingMetrics:
    def test_emits_one_json_line_per_metric(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        sink = LoggingMetrics(domain="example-domain")
        with caplog.at_level(logging.INFO, logger="memory_manager.metrics"):
            sink.increment("policy_denials", reason_code="TOPIC_NOT_ALLOWED")
        payload = json.loads(caplog.records[-1].message)
        assert payload == {
            "metric": "policy_denials",
            "domain": "example-domain",
            "reason_code": "TOPIC_NOT_ALLOWED",
        }

    def test_refuses_an_undeclared_metric(self) -> None:
        with pytest.raises(ValueError, match="not a declared metric"):
            LoggingMetrics(domain="example-domain").increment("invented_metric")

    @pytest.mark.parametrize(
        "label", ["value", "fact", "text", "subject", "user_id", "email", "token"]
    )
    def test_refuses_a_label_that_would_carry_payload(self, label: str) -> None:
        with pytest.raises(ValueError, match="payload"):
            LoggingMetrics(domain="example-domain").increment(
                "policy_denials", **{label: "anything"}
            )

    def test_refuses_a_label_value_long_enough_to_be_content(self) -> None:
        with pytest.raises(ValueError, match="looks like content"):
            LoggingMetrics(domain="example-domain").increment(
                "policy_denials", reason_code="x" * 65
            )

    def test_null_sink_accepts_anything_and_returns_nothing(self) -> None:
        assert NullMetrics().increment("policy_denials", reason_code="x") is None


class TestWriteBudget:
    def test_capacity_is_the_domain_share_divided_by_the_instance_ceiling(self) -> None:
        assert WriteBudget(writes_per_minute=600, max_instances=10).capacity == 60

    def test_capacity_is_never_zero(self) -> None:
        """An instance that can never write is a worse failure than a slightly oversized share."""
        assert WriteBudget(writes_per_minute=3, max_instances=10).capacity == 1

    @pytest.mark.parametrize(
        ("writes", "instances"), [(0, 1), (-1, 1), (60, 0), (60, -1)]
    )
    def test_refuses_a_nonsensical_size(self, writes: int, instances: int) -> None:
        with pytest.raises(ValueError):
            WriteBudget(writes_per_minute=writes, max_instances=instances)

    def test_spends_down_to_the_capacity_then_refuses(self) -> None:
        budget = WriteBudget(writes_per_minute=60, max_instances=10)  # 6 per minute
        for _ in range(6):
            budget.take()
        with pytest.raises(BudgetExhausted):
            budget.take()

    def test_a_multi_fact_write_costs_its_fact_count(self) -> None:
        budget = WriteBudget(writes_per_minute=50, max_instances=10)  # 5 per minute
        budget.take(5)
        with pytest.raises(BudgetExhausted):
            budget.take(1)

    def test_refusal_carries_a_retry_after_the_caller_can_use(self) -> None:
        budget = WriteBudget(writes_per_minute=60, max_instances=1)
        budget.take(60)
        with pytest.raises(BudgetExhausted) as exhausted:
            budget.take(1)
        assert 1 <= exhausted.value.retry_after_seconds <= 60

    def test_refills_over_time_rather_than_at_a_window_boundary(self) -> None:
        """A fixed window lets a caller spend the minute in its first second, then starve."""
        budget = WriteBudget(writes_per_minute=60000, max_instances=1)  # 1000/second
        budget.take(60000)
        with pytest.raises(BudgetExhausted):
            budget.take(1)
        time.sleep(0.05)
        budget.take(1)  # partially refilled; no window boundary was crossed

    def test_never_refills_above_capacity(self) -> None:
        budget = WriteBudget(writes_per_minute=60000, max_instances=1)
        time.sleep(0.05)  # idle time must not bank extra budget
        budget.take(60000)
        with pytest.raises(BudgetExhausted):
            budget.take(1000)
