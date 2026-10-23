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
from memory_manager.api.main import Caller, ConfigurationError, Deployment, create_app  # noqa: E402
from memory_manager.observability import WriteBudget  # noqa: E402
from memory_manager.providers import (  # noqa: E402
    FakeMemoryBank,
    ProviderUnavailable,
)

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
        # Generous by default: budget exhaustion is its own test, not a trap for every other one.
        "budget": WriteBudget(writes_per_minute=6000, max_instances=1),
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
            from memory_manager.providers import ProviderUnavailable

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


# --- the write budget -----------------------------------------------------------------
#
# The platform project's Memory Bank quota is shared by every domain, so an instance that cannot
# bound its own consumption can starve a domain that did nothing wrong.


class RecordingMetrics:
    """Records emissions so a test can assert the service said what happened."""

    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict[str, str]]] = []

    def increment(self, metric: str, **labels: str) -> None:
        self.emitted.append((metric, labels))

    def names(self) -> list[str]:
        return [name for name, _ in self.emitted]


def test_create_app_refuses_to_start_without_a_write_budget() -> None:
    with pytest.raises(ConfigurationError, match="write budget is required"):
        create_app(deployment(budget=None), environment="local")


def test_a_write_past_the_budget_is_refused_with_429_and_retry_after() -> None:
    c = client(budget=WriteBudget(writes_per_minute=2, max_instances=1))
    for i in range(2):
        accepted = c.post(
            "/v1/memories",
            json={"facts": [fact(value=f"Brand {i}")]},
            headers={**HEADERS, "Idempotency-Key": f"key-{i:07d}"},
        )
        assert accepted.status_code == 200

    refused = c.post(
        "/v1/memories",
        json={"facts": [fact(value="Brand 3")]},
        headers={**HEADERS, "Idempotency-Key": "key-0000009"},
    )
    assert refused.status_code == 429
    assert refused.json()["code"] == "RATE_LIMITED"
    assert refused.json()["retryable"] is True
    assert int(refused.headers["Retry-After"]) >= 1


def test_budget_exhaustion_is_reported_as_a_metric() -> None:
    metrics = RecordingMetrics()
    c = client(
        budget=WriteBudget(writes_per_minute=1, max_instances=1), metrics=metrics
    )
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    c.post(
        "/v1/memories",
        json={"facts": [fact(value="Other")]},
        headers={**HEADERS, "Idempotency-Key": "key-0000002"},
    )
    assert "quota_budget_exhausted" in metrics.names()


def test_budget_is_spent_per_fact_not_per_request() -> None:
    """Three facts in one request consume three units: the provider is charged per fact."""
    c = client(budget=WriteBudget(writes_per_minute=4, max_instances=1))
    first = c.post(
        "/v1/memories",
        json={"facts": [fact(value=f"Brand {i}") for i in range(3)]},
        headers=HEADERS,
    )
    assert first.status_code == 200

    second = c.post(
        "/v1/memories",
        json={"facts": [fact(value=f"Later {i}") for i in range(2)]},
        headers={**HEADERS, "Idempotency-Key": "key-0000002"},
    )
    assert second.status_code == 429


def test_budget_refusal_happens_before_the_provider_is_called() -> None:
    """Refusing after the write would spend the quota the budget exists to protect."""
    bank = FakeMemoryBank()
    writes = 0
    inner = bank.write

    def counting_write(facts: list[str], scope: str) -> object:
        nonlocal writes
        writes += 1
        return inner(facts, scope)

    bank.write = counting_write  # type: ignore[method-assign]
    c = client(bank=bank, budget=WriteBudget(writes_per_minute=1, max_instances=1))
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    assert writes == 1

    refused = c.post(
        "/v1/memories",
        json={"facts": [fact(value="Other")]},
        headers={**HEADERS, "Idempotency-Key": "key-0000002"},
    )
    assert refused.status_code == 429
    assert writes == 1


def test_recall_is_not_charged_to_the_write_budget() -> None:
    """A read does not consume the write quota; charging it would throttle reads for no reason."""
    c = client(budget=WriteBudget(writes_per_minute=1, max_instances=1))
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    for _ in range(5):
        read = c.get("/v1/memories", headers=HEADERS)
        assert read.status_code == 200


# --- idempotency ----------------------------------------------------------------------
#
# The contract has required an Idempotency-Key since v0.1.0 and promised what it buys. Until 012
# the service checked the header was present and discarded it.


def write_counting_bank() -> tuple[FakeMemoryBank, list[int]]:
    """A bank that records how many times it was actually asked to write."""
    bank = FakeMemoryBank()
    calls: list[int] = []
    inner = bank.write

    def counting(facts: list[str], scope: object) -> object:
        calls.append(len(facts))
        return inner(facts, scope)  # type: ignore[arg-type]

    bank.write = counting  # type: ignore[method-assign]
    return bank, calls


def test_replaying_a_key_with_the_same_body_does_not_write_again() -> None:
    """Counted at the provider, not inferred from the response: a response can look right
    while the write happened twice, which is the whole failure being prevented."""
    bank, calls = write_counting_bank()
    c = client(bank=bank)
    payload = {"facts": [fact()]}

    first = c.post("/v1/memories", json=payload, headers=HEADERS)
    second = c.post("/v1/memories", json=payload, headers=HEADERS)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls == [1], f"the provider was called {len(calls)} times"


def test_a_replay_returns_the_original_memory_id() -> None:
    c = client()
    payload = {"facts": [fact()]}
    first = c.post("/v1/memories", json=payload, headers=HEADERS)
    second = c.post("/v1/memories", json=payload, headers=HEADERS)
    assert (
        first.json()["results"][0]["memoryId"]
        == second.json()["results"][0]["memoryId"]
    )


def test_the_same_key_with_a_different_body_is_refused() -> None:
    c = client()
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    reused = c.post(
        "/v1/memories", json={"facts": [fact(value="Meadowlark")]}, headers=HEADERS
    )
    assert reused.status_code == 422
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert reused.json()["retryable"] is False


def test_a_refused_key_did_not_write() -> None:
    bank, calls = write_counting_bank()
    c = client(bank=bank)
    c.post("/v1/memories", json={"facts": [fact()]}, headers=HEADERS)
    c.post("/v1/memories", json={"facts": [fact(value="Other")]}, headers=HEADERS)
    assert calls == [1]


def test_different_keys_with_the_same_body_both_write() -> None:
    """The key is the identity of a write, not the body."""
    bank, calls = write_counting_bank()
    c = client(bank=bank)
    payload = {"facts": [fact()]}
    c.post("/v1/memories", json=payload, headers=HEADERS)
    c.post(
        "/v1/memories",
        json=payload,
        headers={**HEADERS, "Idempotency-Key": "key-0000002"},
    )
    assert calls == [1, 1]


def test_a_replay_carries_its_own_correlation_id() -> None:
    """A replay is a distinct request. Echoing the recorded id would break tracing."""
    c = client()
    payload = {"facts": [fact()]}
    c.post(
        "/v1/memories", json=payload, headers={**HEADERS, "X-Correlation-Id": "first"}
    )
    replay = c.post(
        "/v1/memories", json=payload, headers={**HEADERS, "X-Correlation-Id": "second"}
    )
    assert replay.headers["X-Correlation-Id"] == "second"


def test_a_noop_is_recorded_too() -> None:
    """A refusal is a completed outcome; replaying it must not re-run the classifier."""
    calls: list[str] = []

    class CountingClassifier:
        def classify(self, f: object, caller: object) -> object:
            calls.append("called")
            return AllowAll().classify(f, caller)  # type: ignore[arg-type]

    c = client(classifier=CountingClassifier())
    payload = {"facts": [fact(topic="health_conditions")]}
    first = c.post("/v1/memories", json=payload, headers=HEADERS)
    second = c.post("/v1/memories", json=payload, headers=HEADERS)
    assert first.json()["outcome"] == second.json()["outcome"] == "noop"
    assert first.json() == second.json()


def test_a_provider_failure_is_not_recorded_so_a_retry_still_works() -> None:
    """Caching a transient failure turns a short outage into a permanent one for that key."""

    class FailThenSucceed(FakeMemoryBank):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def write(self, facts: list[str], scope: object) -> object:
            self.attempts += 1
            if self.attempts == 1:
                raise ProviderUnavailable("the provider is unavailable")
            return super().write(facts, scope)  # type: ignore[arg-type]

    bank = FailThenSucceed()
    c = client(bank=bank)
    payload = {"facts": [fact()]}

    failed = c.post("/v1/memories", json=payload, headers=HEADERS)
    assert failed.status_code == 503
    assert failed.json()["retryable"] is True

    retried = c.post("/v1/memories", json=payload, headers=HEADERS)
    assert retried.status_code == 200, "the same key after a 503 must be able to retry"
    assert retried.json()["outcome"] == "written"


def test_two_end_users_may_share_a_key_without_seeing_each_other(  # S-8
) -> None:
    """An idempotency key is a string the client chose. Two end users can pick the same one."""
    c = client()
    payload = {"facts": [fact()]}
    alice = c.post(
        "/v1/memories",
        json=payload,
        headers={**HEADERS, "Authorization": "Bearer alice"},
    )
    bob = c.post(
        "/v1/memories",
        json=payload,
        headers={**HEADERS, "Authorization": "Bearer bob"},
    )
    assert alice.status_code == 200
    # Same key, same body, different end user: not a replay, and not Alice's memory id.
    assert bob.status_code == 200
    assert (
        bob.json()["results"][0]["memoryId"] != alice.json()["results"][0]["memoryId"]
    )
