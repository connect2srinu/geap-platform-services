"""Does this deployment still honour the pattern's contract?

Black box. Nothing here imports the pattern; it is the same suite whether it runs against the
reference implementation or against a domain's own customised build.

A domain configures policy *behind* the contract — which topics exist, what counts as sensitive,
who may write. It does not change the contract's shape, and that is what makes an agent written
against one domain work against another. These tests are what tells a domain they have not.

**The platform cannot see this run.** A domain that deletes the job is not stopped by anything
outside their team. That is the model, and it is why the suite is worth having rather than a
formality — see `standards/security.md`.
"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import ALLOWED_FIELD, ALLOWED_TOPIC, SENSITIVE_TOPIC

PER_FACT_CODES = {
    "ACCEPTED",
    "TOPIC_UNKNOWN",
    "TOPIC_DISABLED",
    "TOPIC_NOT_APPROVED",
    "TOPIC_SENSITIVE",
    "TOPIC_RESTRICTED",
    "FIELD_UNKNOWN",
    "VALUE_TYPE_INVALID",
    "VALUE_PROHIBITED",
    "INFERENCE_NOT_PERMITTED",
    "CLASSIFIER_ERROR",
}
ERROR_CODES = {
    "MALFORMED_REQUEST",
    "TOO_MANY_FACTS",
    "IDEMPOTENCY_KEY_MISSING",
    "IDEMPOTENCY_KEY_REUSED",
    "UNAUTHENTICATED",
    "TOKEN_INVALID",
    "CALLER_NOT_REGISTERED",
    "CALLER_NOT_PERMITTED",
    "SCOPE_NOT_RESOLVABLE",
    "SCOPE_IN_BODY_REFUSED",
    "RATE_LIMITED",
    "CONFIGURATION_INVALID",
    "PROVIDER_UNAVAILABLE",
}


def a_fact(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "topic": ALLOWED_TOPIC,
        "field": ALLOWED_FIELD,
        "value": "ConformanceBrand",
        "fact": "Prefers ConformanceBrand.",
    }
    base.update(kw)
    return base


def remember(client: Any, headers: dict[str, str], key: str, **kw: Any) -> Any:
    return client.post(
        "/v1/memories",
        json={"facts": [a_fact(**kw)]},
        headers={**headers, "Idempotency-Key": key},
    )


# --- health -------------------------------------------------------------------------


def test_healthz_is_reachable_without_credentials(client: Any) -> None:
    assert client.get("/healthz").status_code == 200


def test_readyz_reports_the_memory_store(client: Any) -> None:
    """A 503 here on a first deployment usually means the platform-owned IAM binding does not
    exist yet, not that the build is wrong."""
    assert client.get("/readyz").status_code in (200, 503)


# --- the write path -------------------------------------------------------------------


def test_an_allowed_fact_is_accepted(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    r = remember(client, writer, idempotency_key)
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] in {"written", "written_unverified"}
    assert body["stored"] == 1
    assert body["results"][0]["reasonCode"] == "ACCEPTED"


def test_a_sensitive_topic_is_a_noop_not_an_error(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    """The agent did nothing wrong by offering a fact the domain does not accept. A 4xx would
    teach agents to retry, or to read governance as an outage."""
    r = remember(
        client,
        writer,
        idempotency_key,
        topic=SENSITIVE_TOPIC,
        field=None,
        value="something",
        fact="Something sensitive.",
    )
    assert r.status_code == 200
    assert r.json()["outcome"] == "noop"
    assert r.json()["stored"] == 0
    assert r.json()["results"][0]["reasonCode"] in {
        "TOPIC_SENSITIVE",
        "TOPIC_RESTRICTED",
        "TOPIC_DISABLED",
        "TOPIC_NOT_APPROVED",
    }


def test_an_unknown_topic_is_refused(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    r = remember(
        client, writer, idempotency_key, topic="no_such_topic_at_all", field=None
    )
    assert r.status_code == 200
    assert r.json()["results"][0]["reasonCode"] == "TOPIC_UNKNOWN"
    assert r.json()["stored"] == 0


def test_every_reason_code_is_one_the_contract_publishes(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    """A code outside the catalogue is one an integrating agent cannot handle."""
    r = remember(
        client, writer, idempotency_key, topic="no_such_topic_at_all", field=None
    )
    for result in r.json()["results"]:
        assert result["reasonCode"] in PER_FACT_CODES


def test_a_result_is_returned_for_every_submitted_fact(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    r = client.post(
        "/v1/memories",
        json={"facts": [a_fact(), a_fact(topic="no_such_topic_at_all", field=None)]},
        headers={**writer, "Idempotency-Key": idempotency_key},
    )
    assert r.status_code == 200
    assert {x["index"] for x in r.json()["results"]} == {0, 1}


# --- the provider's limit is enforced by the contract --------------------------------------


def test_more_than_five_facts_is_refused(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    """A hard provider limit. A build that accepts six has changed the contract."""
    r = client.post(
        "/v1/memories",
        json={"facts": [a_fact() for _ in range(6)]},
        headers={**writer, "Idempotency-Key": idempotency_key},
    )
    assert r.status_code in (400, 422)


def test_five_facts_are_accepted(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    r = client.post(
        "/v1/memories",
        json={
            "facts": [
                a_fact(value=f"Brand{i}", fact=f"Prefers Brand{i}.") for i in range(5)
            ]
        },
        headers={**writer, "Idempotency-Key": idempotency_key},
    )
    assert r.status_code == 200


# --- idempotency ------------------------------------------------------------------------------


def test_the_idempotency_key_is_required(client: Any, writer: dict[str, str]) -> None:
    r = client.post("/v1/memories", json={"facts": [a_fact()]}, headers=writer)
    assert r.status_code == 400
    assert r.json()["code"] == "IDEMPOTENCY_KEY_MISSING"


def test_the_same_key_and_payload_does_not_double_store(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    first = remember(
        client,
        writer,
        idempotency_key,
        value="IdempotentBrand",
        fact="Prefers IdempotentBrand.",
    )
    second = remember(
        client,
        writer,
        idempotency_key,
        value="IdempotentBrand",
        fact="Prefers IdempotentBrand.",
    )
    assert first.status_code == 200
    assert second.status_code == 200

    read = client.get(f"/v1/memories?topic={ALLOWED_TOPIC}", headers=writer)
    matching = [v for v in read.json()["values"] if "IdempotentBrand" in v["fact"]]
    assert len(matching) == 1


def test_the_same_key_and_payload_returns_the_original_result(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    """The contract promises the *original result*, not merely that one memory ends up stored.

    Honest limit: a build with no idempotency at all can pass this. Provider consolidation
    collapses the second identical write onto the same memory and returns the same id, so the
    two responses match anyway — confirmed by removing the replay lookup and watching this test
    still pass. A conformance suite is black box and cannot count provider calls.

    What it does catch is a build that returns something *different* on replay: a new id, a
    changed outcome, a reordered result set. The discriminating test lives in the pattern's own
    suite, where the provider calls can be counted.
    """
    body = {"value": "ReplayBrand", "fact": "Prefers ReplayBrand."}
    first = remember(client, writer, idempotency_key, **body)
    second = remember(client, writer, idempotency_key, **body)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_the_same_key_with_a_different_payload_is_refused(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    """A key identifies one logical write. Reusing it for another must not silently apply."""
    remember(
        client, writer, idempotency_key, value="FirstBrand", fact="Prefers FirstBrand."
    )
    reused = remember(
        client,
        writer,
        idempotency_key,
        value="SecondBrand",
        fact="Prefers SecondBrand.",
    )
    assert reused.status_code == 422
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert reused.json()["retryable"] is False


def test_a_different_key_with_the_same_payload_is_a_new_request(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    """The key is the identity of a write, not the body. A build that deduplicates on the body
    would silently drop a legitimate repeat."""
    body = {"value": "RepeatBrand", "fact": "Prefers RepeatBrand."}
    first = remember(client, writer, idempotency_key, **body)
    second = remember(client, writer, f"{idempotency_key}-two", **body)
    assert first.status_code == second.status_code == 200
    assert second.json()["outcome"] in {"written", "written_unverified", "noop"}


# --- scope is never supplied by the caller -----------------------------------------------------------


def test_a_scope_in_the_request_body_is_refused(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    """Scope is derived from the authenticated caller. A build that accepts one here lets a
    caller reach another person's memory."""
    r = client.post(
        "/v1/memories",
        json={"facts": [a_fact()], "scope": "someone-else"},
        headers={**writer, "Idempotency-Key": idempotency_key},
    )
    assert r.status_code in (400, 403, 422)


def test_two_end_users_do_not_share_memory(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    remember(
        client,
        writer,
        idempotency_key,
        value="UserOneBrand",
        fact="Prefers UserOneBrand.",
    )
    other = client.get(
        "/v1/memories",
        headers={**writer, "Authorization": "Bearer a-different-end-user"},
    )
    assert other.status_code == 200
    assert all("UserOneBrand" not in v["fact"] for v in other.json()["values"])


# --- authentication ----------------------------------------------------------------------------------


def test_no_credentials_is_401(client: Any, idempotency_key: str) -> None:
    r = client.post(
        "/v1/memories",
        json={"facts": [a_fact()]},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert r.status_code == 401


def test_an_unknown_agent_is_refused(client: Any, idempotency_key: str) -> None:
    r = client.post(
        "/v1/memories",
        json={"facts": [a_fact()]},
        headers={
            "X-Agent-ID": "no-such-agent",
            "Authorization": "Bearer someone",
            "Idempotency-Key": idempotency_key,
        },
    )
    assert r.status_code in (401, 403)


def test_a_read_only_agent_cannot_write(
    client: Any, reader: dict[str, str], idempotency_key: str
) -> None:
    """A read-only grant that can write is the clearest possible authorization defect."""
    r = remember(client, reader, idempotency_key)
    assert r.status_code == 403
    assert r.json()["code"] == "CALLER_NOT_PERMITTED"


def test_every_error_code_is_one_the_contract_publishes(client: Any) -> None:
    r = client.post("/v1/memories", json={"facts": [a_fact()]}, headers={})
    assert r.json()["code"] in ERROR_CODES


# --- the error shape ------------------------------------------------------------------------------------


def test_an_error_carries_only_the_published_fields(client: Any) -> None:
    r = client.post("/v1/memories", json={"facts": [a_fact()]}, headers={})
    assert set(r.json()) <= {"code", "message", "correlationId", "retryable"}


def test_an_error_does_not_echo_the_payload(
    client: Any, writer: dict[str, str]
) -> None:
    """Security rule S-4. A build that puts the request into its error message leaks memory
    content into every client's logs."""
    secret = "ZZTopSecretBrandValue"
    r = client.post(
        "/v1/memories",
        json={"facts": [a_fact(value=secret, fact=f"Prefers {secret}.")]},
        headers=writer,  # no idempotency key, so this is an error
    )
    assert r.status_code >= 400
    assert secret not in r.text


def test_every_response_carries_a_correlation_id(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    r = remember(client, writer, idempotency_key)
    assert r.headers.get("X-Correlation-Id")


# --- recall ------------------------------------------------------------------------------------------------


def test_recall_returns_what_was_written(
    client: Any, writer: dict[str, str], idempotency_key: str
) -> None:
    remember(
        client,
        writer,
        idempotency_key,
        value="RecallableBrand",
        fact="Prefers RecallableBrand.",
    )
    read = client.get(f"/v1/memories?topic={ALLOWED_TOPIC}", headers=writer)
    assert read.status_code == 200
    assert any("RecallableBrand" in v["fact"] for v in read.json()["values"])


def test_recall_reports_how_many_values_it_withheld(
    client: Any, writer: dict[str, str]
) -> None:
    """`withheld` is how a domain learns that stored content failed re-classification. A build
    that drops the field hides its own remediation signal.

    **Limit of this check:** it verifies the field is present and is a count, not that the count is
    accurate. Forcing a withhold from outside would need content this suite knows the domain's
    classifier will reject, and the suite deliberately knows nothing about a domain's vocabulary —
    so a build that hardcodes zero passes here. Removing the field is caught; faking it is not.
    """
    read = client.get("/v1/memories", headers=writer)
    assert "withheld" in read.json()
    assert isinstance(read.json()["withheld"], int)


def test_recall_never_returns_a_sensitive_topic(
    client: Any, writer: dict[str, str]
) -> None:
    read = client.get("/v1/memories", headers=writer)
    assert all(v["topic"] != SENSITIVE_TOPIC for v in read.json()["values"])


def test_recall_requires_credentials(client: Any) -> None:
    assert client.get("/v1/memories").status_code == 401


@pytest.mark.parametrize("field", ["topic", "fact"])
def test_every_recalled_value_has_the_published_shape(
    client: Any, writer: dict[str, str], idempotency_key: str, field: str
) -> None:
    remember(client, writer, idempotency_key)
    for value in client.get("/v1/memories", headers=writer).json()["values"]:
        assert field in value
