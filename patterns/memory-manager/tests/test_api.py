"""The endpoints, end to end against the fake bank.

This is the first test that exercises the whole path: request schema, caller resolution, the
validation pipeline, the write, read-back verification, and the response shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN))

from extensions import (  # noqa: E402
    CallerContext,
    Classification,
    ClassificationResult,
    Fact,
    PolicyDecision,
    Topic,
    TopicField,
)
from src.api.auth import IdentityConfig, LocalHeaderVerifier  # noqa: E402
from src.api.main import Caller, ConfigurationError, Deployment, create_app  # noqa: E402
from src.providers import FakeMemoryBank  # noqa: E402

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


class RejectsWord:
    def __init__(self, word: str) -> None:
        self._word = word

    def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
        if self._word in fact.text:
            return ClassificationResult(allowed=False, reason="PROHIBITED")
        return ClassificationResult(allowed=True)

    def decide(
        self, caller: CallerContext, operation: str, topic: str
    ) -> PolicyDecision:
        return PolicyDecision(allowed=True)


def deployment(**kw: object) -> Deployment:
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
            subject_hmac_key="a-test-only-hmac-key",
        ),
        "verifier": LocalHeaderVerifier(environment="local"),
        "auth_enabled": False,
    }
    base.update(kw)
    return Deployment(**base)  # type: ignore[arg-type]


def client(**kw: object) -> TestClient:
    return TestClient(create_app(deployment(**kw), environment="local"))


def fact(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "topic": "preferred_brands",
        "field": "brand",
        "value": "Horizon",
        "fact": "Prefers the organic brand Horizon.",
    }
    base.update(kw)
    return base


#: The local verifier treats the bearer value as the subject, so this stands in for a real token.
END_USER = {"Authorization": "Bearer end-user-1"}
HEADERS = {"X-Agent-ID": "writer-agent", "Idempotency-Key": "key-0000001", **END_USER}


# --- the happy path -------------------------------------------------------------------


def test_a_valid_fact_is_stored_and_recalled() -> None:
    c = client()
    written = c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    assert written.status_code == 200
    body = written.json()
    assert body["outcome"] == "written"
    assert body["stored"] == 1
    assert body["results"][0]["reasonCode"] == "ACCEPTED"
    assert body["results"][0]["memoryId"]

    read = c.get("/v1/memories", headers={"X-Agent-ID": "writer-agent", **END_USER})
    assert read.status_code == 200
    assert "Horizon" in read.json()["values"][0]["fact"]


def test_every_response_carries_a_correlation_id() -> None:
    c = client()
    r = c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    assert r.headers["X-Correlation-Id"]


def test_a_supplied_correlation_id_is_echoed() -> None:
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={**HEADERS, "X-Correlation-Id": "corr-abc"},
    )
    assert r.headers["X-Correlation-Id"] == "corr-abc"


# --- a filtered request is a no-op, not an error -------------------------------------------


def test_a_sensitive_topic_is_a_noop_not_an_error() -> None:
    """The agent did nothing wrong by offering a fact the domain does not accept."""
    c = client()
    r = c.post(
        "/v1/memories",
        json={
            "facts": [
                fact(
                    topic="health_conditions",
                    field=None,
                    value="diabetes",
                    fact="Has diabetes.",
                )
            ]
        },
        headers=HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["outcome"] == "noop"
    assert r.json()["stored"] == 0
    assert r.json()["results"][0]["reasonCode"] == "TOPIC_SENSITIVE"


def test_the_label_does_not_grant_passage() -> None:
    """An allowed topic whose text carries prohibited content is refused."""
    c = client(classifier=RejectsWord("atorvastatin"))
    r = c.post(
        "/v1/memories",
        json={"facts": [fact(fact="Takes 20mg atorvastatin and prefers Horizon.")]},
        headers=HEADERS,
    )
    assert r.json()["outcome"] == "noop"
    assert r.json()["results"][0]["reasonCode"] == "VALUE_PROHIBITED"


def test_nothing_is_stored_when_nothing_qualifies() -> None:
    bank = FakeMemoryBank()
    c = client(bank=bank, classifier=RejectsWord("atorvastatin"))
    c.post(
        "/v1/memories",
        json={"facts": [fact(fact="Takes atorvastatin.")]},
        headers=HEADERS,
    )
    assert bank.retrieve((("user_id", "example-domain:writer-agent"),)) == []


# --- authentication and authorization ---------------------------------------------------------


def test_a_request_with_no_caller_is_401() -> None:
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={"Idempotency-Key": "k-0000001", **END_USER},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHENTICATED"


def test_an_unregistered_caller_is_403() -> None:
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={"X-Agent-ID": "nobody", "Idempotency-Key": "k-0000001", **END_USER},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "CALLER_NOT_REGISTERED"


def test_a_read_only_caller_cannot_write() -> None:
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={
            "X-Agent-ID": "reader-agent",
            "Idempotency-Key": "k-0000001",
            **END_USER,
        },
    )
    assert r.status_code == 403
    assert r.json()["code"] == "CALLER_NOT_PERMITTED"


def test_different_end_users_do_not_share_a_scope() -> None:
    """Scope follows the end user, not the agent - two agents acting for the same person see the
    same memory, and the same agent acting for two people does not."""
    c = client()
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    other = c.get(
        "/v1/memories",
        headers={"X-Agent-ID": "writer-agent", "Authorization": "Bearer end-user-2"},
    )
    assert other.json()["values"] == []


def test_two_agents_acting_for_the_same_end_user_see_the_same_memory() -> None:
    c = client()
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    read = c.get("/v1/memories", headers={"X-Agent-ID": "reader-agent", **END_USER})
    assert len(read.json()["values"]) == 1


# --- the request schema refuses before any code runs ---------------------------------------------


def test_six_facts_are_refused() -> None:
    c = client()
    r = c.post("/v1/memories", json={"facts": [fact()] * 6}, headers=HEADERS)
    assert r.status_code == 422


def test_a_scope_in_the_body_is_refused() -> None:
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()], "scope": "another-user"},
        headers=HEADERS,
    )
    assert r.status_code == 422


def test_a_missing_idempotency_key_is_400() -> None:
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={"X-Agent-ID": "writer-agent", **END_USER},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "IDEMPOTENCY_KEY_MISSING"


# --- provider failures -----------------------------------------------------------------------------


def test_a_throttled_write_is_503_not_429() -> None:
    """The caller did nothing wrong; shaping their behaviour would be the wrong fix."""
    c = client(bank=FakeMemoryBank(throttle_after=0))
    r = c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    assert r.status_code == 503
    assert r.json()["code"] == "PROVIDER_UNAVAILABLE"
    assert r.json()["retryable"] is True
    assert r.headers["Retry-After"]


def test_an_error_body_carries_no_payload() -> None:
    """Security rule S-4."""
    c = client(bank=FakeMemoryBank(throttle_after=0))
    r = c.post(
        "/v1/memories",
        json={"facts": [fact(fact="Prefers the organic brand Horizon.")]},
        headers=HEADERS,
    )
    assert "Horizon" not in r.text
    assert set(r.json()) == {"code", "message", "correlationId", "retryable"}


# --- recall re-classifies as a backstop ---------------------------------------------------------------


def test_recall_withholds_a_value_that_is_now_prohibited() -> None:
    bank = FakeMemoryBank()
    c = client(bank=bank)
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)

    # The same deployment, but the classifier now recognises the stored text as prohibited.
    strict = TestClient(
        create_app(
            deployment(bank=bank, classifier=RejectsWord("Horizon")),
            environment="local",
        )
    )
    read = strict.get(
        "/v1/memories", headers={"X-Agent-ID": "writer-agent", **END_USER}
    )
    assert read.json()["values"] == []
    assert read.json()["withheld"] == 1


def test_recall_can_filter_to_one_topic() -> None:
    c = client()
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    read = c.get(
        "/v1/memories?topic=health_conditions",
        headers={"X-Agent-ID": "writer-agent", **END_USER},
    )
    assert read.json()["values"] == []


# --- the dev shortcut is refused outside local ----------------------------------------------------------


def test_auth_disabled_outside_local_refuses_to_start() -> None:
    """Not defaulted off - refused. A shortcut that merely defaults off is one deployment away
    from being on."""
    with pytest.raises(ConfigurationError, match="only in a local environment"):
        create_app(deployment(auth_enabled=False), environment="production")


def test_auth_disabled_is_permitted_locally() -> None:
    create_app(deployment(auth_enabled=False), environment="local")


def test_auth_enabled_starts_anywhere() -> None:
    create_app(deployment(auth_enabled=True), environment="production")


# --- health ------------------------------------------------------------------------------------------------


def test_healthz_needs_no_credentials() -> None:
    assert client().get("/healthz").json() == {"status": "ok"}


def test_readyz_reports_the_provider() -> None:
    assert client().get("/readyz").status_code == 200


def test_readyz_fails_when_the_bank_is_unreachable() -> None:
    """Expected on a first deployment, until the platform-owned IAM binding exists."""

    class Unreachable(FakeMemoryBank):
        def retrieve(self, scope: object) -> list[object]:  # type: ignore[override]
            from src.providers import ProviderUnavailable

            raise ProviderUnavailable("no binding")

    assert client(bank=Unreachable()).get("/readyz").status_code == 503


# --- the end-user token is required, not optional ----------------------------------------------


def test_a_request_with_no_end_user_token_is_401() -> None:
    """The agent says who is asking; the token says whose memory it is. Both are required, and
    the scope cannot be guessed from the agent alone."""
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={"X-Agent-ID": "writer-agent", "Idempotency-Key": "k-0000001"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHENTICATED"


def test_recall_also_requires_an_end_user_token() -> None:
    c = client()
    r = c.get("/v1/memories", headers={"X-Agent-ID": "writer-agent"})
    assert r.status_code == 401


@pytest.mark.parametrize(
    "header",
    ["end-user-1", "Basic end-user-1", "Bearer", "Bearer   ", "bearer", ""],
)
def test_a_malformed_authorization_header_is_treated_as_absent(header: str) -> None:
    """Distinguishing 'your header shape was wrong' from 'your token was invalid' is worth
    nothing to a caller and something to someone probing."""
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={
            "X-Agent-ID": "writer-agent",
            "Idempotency-Key": "k-0000001",
            "Authorization": header,
        },
    )
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHENTICATED"


def test_a_lowercase_bearer_scheme_is_accepted() -> None:
    """The scheme is case-insensitive per RFC 7235; the token is not."""
    c = client()
    r = c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={
            "X-Agent-ID": "writer-agent",
            "Idempotency-Key": "k-0000001",
            "Authorization": "bearer end-user-1",
        },
    )
    assert r.status_code == 200


def test_the_raw_subject_never_appears_in_a_response() -> None:
    """S-7. The scope carries an HMAC pseudonym; the subject stays in the auth layer."""
    c = client()
    c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={**HEADERS, "Authorization": "Bearer alice@example.invalid"},
    )
    read = c.get(
        "/v1/memories",
        headers={
            "X-Agent-ID": "writer-agent",
            "Authorization": "Bearer alice@example.invalid",
        },
    )
    assert "alice" not in read.text


def test_the_scope_stored_in_the_bank_carries_the_pseudonym_not_the_subject() -> None:
    """S-7, checked where it matters.

    The earlier response-text assertion did not catch this: the scope never appears in a response,
    so replacing the pseudonym with the raw subject passed every test. This inspects what actually
    reached the bank.
    """
    bank = FakeMemoryBank()
    c = client(bank=bank)
    c.post(
        "/v1/memories",
        json={"facts": [fact()]},
        headers={**HEADERS, "Authorization": "Bearer alice@example.invalid"},
    )

    scopes = {dict(m.scope).get("user_id") for m in bank._memories.values()}  # type: ignore[attr-defined]
    assert scopes, "nothing was stored, so the assertion below would be vacuous"
    for user_id in scopes:
        assert user_id is not None
        assert "alice" not in user_id
        assert "@" not in user_id
        assert len(user_id) == 32, "expected a 32-character HMAC pseudonym"


def test_the_scope_is_namespaced_by_domain() -> None:
    """S-8 at the storage boundary: another domain's deployment cannot collide with this one."""
    bank = FakeMemoryBank()
    c = client(bank=bank)
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    stored = next(iter(bank._memories.values()))  # type: ignore[attr-defined]
    assert dict(stored.scope)["organization_id"] == "example-domain"
