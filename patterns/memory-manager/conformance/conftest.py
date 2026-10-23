"""Conformance fixtures.

The suite is **black box**. It talks to a running service over HTTP and imports nothing from the
pattern, so it tests the build a domain actually deployed rather than the source they started from.

Two ways to run it:

* **against your deployment** — ``CONFORMANCE_BASE_URL=https://… pytest conformance/``
* **against the reference implementation** — set nothing, and it starts the reference app in
  process with the fake bank. This is what the platform's CI does, and it proves the suite itself
  works before a domain ever runs it.

Credentials come from the environment. The suite never ships a token.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

BASE_URL = os.environ.get("CONFORMANCE_BASE_URL")
AGENT_ID = os.environ.get("CONFORMANCE_AGENT_ID", "writer-agent")
READER_ID = os.environ.get("CONFORMANCE_READER_ID", "reader-agent")
TOKEN = os.environ.get("CONFORMANCE_END_USER_TOKEN", "conformance-end-user")

#: The topics the suite expects the domain to have configured. A domain whose vocabulary differs
#: overrides these; the contract is about behaviour per classification, not about these names.
ALLOWED_TOPIC = os.environ.get("CONFORMANCE_ALLOWED_TOPIC", "preferred_brands")
ALLOWED_FIELD = os.environ.get("CONFORMANCE_ALLOWED_FIELD", "brand")
SENSITIVE_TOPIC = os.environ.get("CONFORMANCE_SENSITIVE_TOPIC", "health_conditions")


def _reference_client() -> Any:
    """Start the reference implementation in process, with the fake bank."""
    pattern = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(pattern / "src"))

    from fastapi.testclient import TestClient

    from memory_manager.extensions import (
        CallerContext,
        Classification,
        ClassificationResult,
        Fact,
        PolicyDecision,
        Topic,
        TopicField,
    )
    from memory_manager.api.auth import IdentityConfig, LocalHeaderVerifier
    from memory_manager.api.main import Caller, Deployment, create_app
    from memory_manager.observability import WriteBudget
    from memory_manager.providers import FakeMemoryBank

    class AllowAll:
        def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
            return ClassificationResult(allowed=True)

        def decide(
            self, caller: CallerContext, operation: str, topic: str
        ) -> PolicyDecision:
            return PolicyDecision(allowed=True)

    topics = {
        ALLOWED_TOPIC: Topic(
            id=ALLOWED_TOPIC,
            classification=Classification.NON_SENSITIVE,
            enabled=True,
            fields=(
                TopicField(name=ALLOWED_FIELD, value_type="string", max_length=128),
            ),
        ),
        SENSITIVE_TOPIC: Topic(
            id=SENSITIVE_TOPIC, classification=Classification.SENSITIVE, enabled=True
        ),
    }
    deployment = Deployment(
        domain="example-domain",
        topics=topics,
        callers={
            AGENT_ID: Caller(
                caller_id=AGENT_ID,
                operations=frozenset({"remember", "recall"}),
                granted_topics=frozenset(topics),
            ),
            READER_ID: Caller(
                caller_id=READER_ID,
                operations=frozenset({"recall"}),
                granted_topics=frozenset({ALLOWED_TOPIC}),
            ),
        },
        bank=FakeMemoryBank(),
        budget=WriteBudget(writes_per_minute=6000, max_instances=1),
        classifier=AllowAll(),
        policy=AllowAll(),
        identity=IdentityConfig(
            issuer="https://issuer.example-domain.invalid",
            jwks_uri="https://issuer.example-domain.invalid/.well-known/jwks.json",
            audience="memory-manager",
            subject_hmac_key="conformance-only-key",
        ),
        verifier=LocalHeaderVerifier(environment="local"),
        auth_enabled=False,
    )
    return TestClient(create_app(deployment, environment="local"))


@pytest.fixture(scope="session")
def client() -> Iterator[Any]:
    """An HTTP client for the service under test."""
    if BASE_URL:
        import httpx2 as httpx

        with httpx.Client(base_url=BASE_URL.rstrip("/"), timeout=30) as live:
            yield live
    else:
        yield _reference_client()


@pytest.fixture
def writer() -> dict[str, str]:
    return {"X-Agent-ID": AGENT_ID, "Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def reader() -> dict[str, str]:
    return {"X-Agent-ID": READER_ID, "Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def idempotency_key() -> str:
    import uuid

    return str(uuid.uuid4())
