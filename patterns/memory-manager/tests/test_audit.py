"""The audit contract: what is declared, what is emitted, and what must never appear in it.

Written because `pattern.yaml` declared seven audit events and the code emitted **none** of them.
`verify_write` was the only component that took an `AuditSink`, `Deployment` had no sink to give
it, so even the two events it did emit went to a null sink in every real deployment. S-7 —
*every write, denial and deletion emits an audit event with a correlation ID* — was a sentence in
a standards document and nothing else.

The first group is the fix that matters, and it is the same one 011 used for the metrics gap: the
manifest and the source are compared in both directions, so a declared event nothing emits and an
emitted event nothing declares each fail the build. One of those directions would not have caught
the original defect; a declared-but-unemitted event is exactly what was there.
"""

from __future__ import annotations

import ast
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))

from memory_manager.extensions import (  # noqa: E402
    CallerContext,
    Classification,
    ClassificationResult,
    Fact,
    PolicyDecision,
    Topic,
    TopicField,
)
from memory_manager.api.auth import IdentityConfig, LocalHeaderVerifier  # noqa: E402
from memory_manager.api.main import Caller, Deployment, create_app  # noqa: E402
from memory_manager.bootstrap import build_deployment  # noqa: E402
from memory_manager.observability import (  # noqa: E402
    AUDIT_EVENTS,
    LoggingAudit,
    NullAudit,
    WriteBudget,
)
from memory_manager.providers import FakeMemoryBank  # noqa: E402

SRC = PATTERN / "src"
HMAC_KEY = "a-test-only-hmac-key"


# --- the manifest against the code ----------------------------------------------------


def _manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (PATTERN / "pattern.yaml").read_text(encoding="utf-8")
    )
    return loaded


def _declared_events() -> set[str]:
    return set(_manifest()["spec"]["observability"]["requiredAuditEvents"])


def _emitted_events() -> set[str]:
    """Every string literal passed as the first argument to an `emit` call under src/.

    Parsed rather than grepped. A grep for the event name also matches `AUDIT_EVENTS`, the
    manifest and every docstring that mentions it — which is precisely how a list of seven
    events nothing emitted stayed invisible through two reviews.
    """
    emitted: set[str] = set()
    for path in SRC.rglob("*.py"):
        if path == SRC / "observability" / "audit.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "emit"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                emitted.add(node.args[0].value)
    return emitted


class TestAuditContract:
    def test_audit_events_constant_matches_the_manifest(self) -> None:
        assert set(AUDIT_EVENTS) == _declared_events()

    def test_every_declared_event_is_emitted_somewhere(self) -> None:
        missing = sorted(set(AUDIT_EVENTS) - _emitted_events())
        assert not missing, f"declared but never emitted: {missing}"

    def test_every_emitted_event_is_declared(self) -> None:
        undeclared = sorted(_emitted_events() - set(AUDIT_EVENTS))
        assert not undeclared, f"emitted but not in the contract: {undeclared}"

    def test_role_events_are_not_declared(self) -> None:
        """This service never grants or revokes a role, so it must not claim to audit one."""
        assert not {"role_grant", "role_revocation"} & set(AUDIT_EVENTS)

    def test_prohibited_log_fields_are_all_refused(self) -> None:
        """Every field the manifest prohibits must actually be refused by the sink."""
        sink = LoggingAudit(domain="example-domain")
        for field in _manifest()["spec"]["observability"]["prohibitedLogFields"]:
            with pytest.raises(ValueError, match="payload"):
                sink.emit("memory_write", **{field: "x"})


# --- the sink -------------------------------------------------------------------------


class TestLoggingAudit:
    def test_emits_one_json_line_per_event(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        sink = LoggingAudit(domain="example-domain")
        with caplog.at_level(logging.INFO, logger="memory_manager.audit"):
            sink.emit("memory_write", correlation_id="c-1", caller_id="writer-agent")
        assert json.loads(caplog.records[-1].message) == {
            "audit": "memory_write",
            "domain": "example-domain",
            "correlation_id": "c-1",
            "caller_id": "writer-agent",
        }

    def test_refuses_an_undeclared_event(self) -> None:
        with pytest.raises(ValueError, match="not a declared audit event"):
            LoggingAudit(domain="example-domain").emit("invented_event")

    @pytest.mark.parametrize("field", ["value", "fact", "text", "subject", "pii"])
    def test_refuses_a_field_that_would_carry_payload(self, field: str) -> None:
        with pytest.raises(ValueError, match="payload"):
            LoggingAudit(domain="example-domain").emit("memory_write", **{field: "x"})

    def test_refuses_a_value_long_enough_to_be_content(self) -> None:
        with pytest.raises(ValueError, match="looks like content"):
            LoggingAudit(domain="example-domain").emit("memory_write", note="x" * 129)

    def test_null_audit_discards(self) -> None:
        assert NullAudit().emit("anything", whatever="x") is None


# --- the paths ------------------------------------------------------------------------


class Recording(LoggingAudit):
    """Records every event *and* applies the real sink's rules.

    Subclassed rather than faked on purpose: a test double that accepted anything would let a
    prohibited field through the endpoint tests, which are the ones most likely to pass one.
    """

    def __init__(self) -> None:
        super().__init__(domain="example-domain")
        self.records: list[tuple[str, dict[str, str]]] = []

    def emit(self, event: str, **fields: str) -> None:
        super().emit(event, **fields)
        self.records.append((event, fields))

    def events(self) -> list[str]:
        return [name for name, _ in self.records]

    def one(self, event: str) -> dict[str, str]:
        matching = [fields for name, fields in self.records if name == event]
        assert matching, f"{event} was not emitted; got {self.events()}"
        return matching[0]


TOPICS = {
    "preferred_brands": Topic(
        id="preferred_brands",
        classification=Classification.NON_SENSITIVE,
        enabled=True,
        fields=(TopicField(name="brand", value_type="string", max_length=64),),
    ),
    "health_conditions": Topic(
        id="health_conditions", classification=Classification.SENSITIVE, enabled=True
    ),
}


class AllowAll:
    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        return ClassificationResult(allowed=True)

    def decide(
        self, caller: CallerContext, operation: str, topic: str
    ) -> PolicyDecision:
        return PolicyDecision(allowed=True)


class Raises:
    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        raise RuntimeError("the domain's classifier is broken")

    def decide(
        self, caller: CallerContext, operation: str, topic: str
    ) -> PolicyDecision:
        return PolicyDecision(allowed=True)


def client(audit: Recording, **kw: object) -> TestClient:
    base: dict[str, object] = {
        "domain": "example-domain",
        "topics": TOPICS,
        "callers": {
            "writer-agent": Caller(
                caller_id="writer-agent",
                operations=frozenset({"remember", "recall"}),
                granted_topics=frozenset(TOPICS),
            ),
            "reader-agent": Caller(
                caller_id="reader-agent",
                operations=frozenset({"recall"}),
                granted_topics=frozenset({"preferred_brands"}),
            ),
        },
        "bank": FakeMemoryBank(),
        "classifier": AllowAll(),
        "policy": AllowAll(),
        "identity": IdentityConfig(
            issuer="https://issuer.example-domain.invalid",
            jwks_uri="https://issuer.example-domain.invalid/.well-known/jwks.json",
            audience="memory-manager",
            subject_hmac_key=HMAC_KEY,
        ),
        "verifier": LocalHeaderVerifier(environment="local"),
        "budget": WriteBudget(writes_per_minute=6000, max_instances=1),
        "audit": audit,
        "auth_enabled": False,
    }
    base.update(kw)
    return TestClient(create_app(Deployment(**base), environment="local"))  # type: ignore[arg-type]


SECRET_FACT = "Prefers the organic brand Horizon."
END_USER = {"Authorization": "Bearer end-user-1"}
WRITER = {"X-Agent-ID": "writer-agent", **END_USER}


def body(topic: str = "preferred_brands") -> dict[str, object]:
    return {
        "facts": [
            {
                "topic": topic,
                "field": "brand",
                "value": "Horizon",
                "fact": SECRET_FACT,
            }
        ]
    }


def test_a_successful_write_emits_memory_write() -> None:
    audit = Recording()
    response = client(audit).post(
        "/v1/memories", json=body(), headers={**WRITER, "Idempotency-Key": "k-1"}
    )
    assert response.status_code == 200
    record = audit.one("memory_write")
    assert record["caller_id"] == "writer-agent"
    assert record["stored"] == "1"
    assert record["correlation_id"]


def test_a_recall_emits_memory_recall_with_counts() -> None:
    audit = Recording()
    api = client(audit)
    api.post("/v1/memories", json=body(), headers={**WRITER, "Idempotency-Key": "k-1"})
    api.get("/v1/memories", headers=WRITER)
    record = audit.one("memory_recall")
    assert record["served"] == "1"
    assert record["withheld"] == "0"


def test_a_refused_fact_emits_policy_denial_with_the_reason() -> None:
    audit = Recording()
    client(audit).post(
        "/v1/memories",
        json=body("health_conditions"),
        headers={**WRITER, "Idempotency-Key": "k-1"},
    )
    assert audit.one("policy_denial")["reason"] == "TOPIC_SENSITIVE"


def test_a_caller_without_the_operation_emits_policy_denial() -> None:
    audit = Recording()
    client(audit).post(
        "/v1/memories",
        json=body(),
        headers={
            "X-Agent-ID": "reader-agent",
            "Idempotency-Key": "k-1",
            **END_USER,
        },
    )
    assert audit.one("policy_denial")["reason"] == "CALLER_NOT_PERMITTED"


def test_a_replay_emits_idempotency_replay() -> None:
    audit = Recording()
    api = client(audit)
    headers = {**WRITER, "Idempotency-Key": "k-same"}
    api.post("/v1/memories", json=body(), headers=headers)
    api.post("/v1/memories", json=body(), headers=headers)
    assert audit.events().count("idempotency_replay") == 1


def test_a_reused_key_emits_policy_denial() -> None:
    audit = Recording()
    api = client(audit)
    headers = {**WRITER, "Idempotency-Key": "k-same"}
    api.post("/v1/memories", json=body(), headers=headers)
    other = body()
    other["facts"][0]["value"] = "Different"  # type: ignore[index]
    api.post("/v1/memories", json=other, headers=headers)
    assert "IDEMPOTENCY_KEY_REUSED" in [
        fields.get("reason")
        for name, fields in audit.records
        if name == "policy_denial"
    ]


def test_an_exhausted_budget_emits_policy_denial() -> None:
    audit = Recording()
    api = client(audit, budget=WriteBudget(writes_per_minute=1, max_instances=1))
    api.post("/v1/memories", json=body(), headers={**WRITER, "Idempotency-Key": "k-1"})
    api.post("/v1/memories", json=body(), headers={**WRITER, "Idempotency-Key": "k-2"})
    assert "RATE_LIMITED" in [
        fields.get("reason")
        for name, fields in audit.records
        if name == "policy_denial"
    ]


def test_a_failing_extension_emits_exception_invoked() -> None:
    audit = Recording()
    client(audit, classifier=Raises()).post(
        "/v1/memories", json=body(), headers={**WRITER, "Idempotency-Key": "k-1"}
    )
    assert audit.one("exception_invoked")["extension"] == "pii-classifier"


# --- S-4 and S-8, against emitted records rather than against the source ----------------


def test_no_audit_record_carries_the_fact_or_the_raw_subject() -> None:
    """Asserted over what was emitted, not over the code, so a new field cannot slip past."""
    audit = Recording()
    api = client(audit)
    headers = {**WRITER, "Idempotency-Key": "k-1"}
    api.post("/v1/memories", json=body(), headers=headers)
    api.post("/v1/memories", json=body(), headers=headers)
    api.get("/v1/memories", headers=WRITER)
    api.post(
        "/v1/memories",
        json=body("health_conditions"),
        headers={**WRITER, "Idempotency-Key": "k-2"},
    )
    assert audit.records, "nothing was emitted, so this proves nothing"
    for event, fields in audit.records:
        blob = json.dumps(fields)
        assert SECRET_FACT not in blob, f"{event} carried the fact"
        assert "Horizon" not in blob, f"{event} carried the value"
        assert "end-user-1" not in blob, f"{event} carried the raw subject"


def test_the_scope_owner_is_named_by_pseudonym_not_by_subject() -> None:
    audit = Recording()
    client(audit).post(
        "/v1/memories", json=body(), headers={**WRITER, "Idempotency-Key": "k-1"}
    )
    pseudonym = audit.one("memory_write")["subject_pseudonym"]
    assert pseudonym and pseudonym != "end-user-1"
    assert len(pseudonym) == 32


# --- the wiring, which is what was actually missing --------------------------------------


def test_bootstrap_gives_the_deployment_a_real_audit_sink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The original defect in one assertion: a deployment whose sink discards is not audited."""
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("SUBJECT_HMAC_KEY", HMAC_KEY)
    config = yaml.safe_load(
        (PATTERN / "config" / "example.domain.yaml").read_text(encoding="utf-8")
    )
    config["extensions"] = {}
    built = build_deployment(config, environment="local")
    assert isinstance(built.audit, LoggingAudit)
    assert not isinstance(built.audit, NullAudit)


def test_startup_emits_configuration_change(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("SUBJECT_HMAC_KEY", HMAC_KEY)
    config = yaml.safe_load(
        (PATTERN / "config" / "example.domain.yaml").read_text(encoding="utf-8")
    )
    config["extensions"] = {}
    with caplog.at_level(logging.INFO, logger="memory_manager.audit"):
        build_deployment(config, environment="local")
    records = [
        json.loads(r.message)
        for r in caplog.records
        if r.name == "memory_manager.audit"
    ]
    started = [r for r in records if r["audit"] == "configuration_change"]
    assert started, "startup emitted no configuration_change"
    assert started[0]["config_digest"]
    assert started[0]["pii_classifier"] == "default:deny-all"
