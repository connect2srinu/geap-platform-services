"""The contract must stay valid, and must keep agreeing with the catalogue and the design.

These are the tests that stop the three drifting apart. No implementation exists yet; they check
the artifacts, which is what there is to check.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

PATTERN = Path(__file__).resolve().parent.parent
SPEC_PATH = PATTERN / "contracts" / "openapi.yaml"
ERRORS_PATH = PATTERN / "contracts" / "errors.md"
DESIGN_PATH = PATTERN.parent.parent / "design" / "001-memory-manager" / "design.md"


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def errors_doc() -> str:
    return ERRORS_PATH.read_text(encoding="utf-8")


def _codes(spec: dict[str, Any], name: str) -> set[str]:
    return set(spec["components"]["schemas"][name]["enum"])


# --- the spec itself -------------------------------------------------------------------


def test_spec_parses_and_declares_openapi_31(spec: dict[str, Any]) -> None:
    assert spec["openapi"].startswith("3.1")


def test_both_operations_are_present(spec: dict[str, Any]) -> None:
    operations = {
        op["operationId"]
        for path in spec["paths"].values()
        for verb, op in path.items()
        if verb in {"get", "post"}
    }
    assert {"remember", "recall"} <= operations


def test_every_schema_ref_resolves(spec: dict[str, Any]) -> None:
    defined = set(spec["components"]["schemas"])
    referenced = {
        m
        for m in re.findall(
            r"#/components/schemas/([A-Za-z0-9_]+)", SPEC_PATH.read_text()
        )
    }
    assert referenced <= defined, f"dangling: {referenced - defined}"


def test_health_endpoints_are_unauthenticated(spec: dict[str, Any]) -> None:
    for path in ("/healthz", "/readyz"):
        assert spec["paths"][path]["get"]["security"] == []


# --- the provider limit the design found -----------------------------------------------


def test_remember_caps_facts_at_five(spec: dict[str, Any]) -> None:
    """Verified live 2026-10-22: GenerateMemories accepts at most five facts per request."""
    facts = spec["components"]["schemas"]["RememberRequest"]["properties"]["facts"]
    assert facts["maxItems"] == 5
    assert facts["minItems"] == 1


def test_stored_count_cannot_exceed_the_cap(spec: dict[str, Any]) -> None:
    assert (
        spec["components"]["schemas"]["RememberResponse"]["properties"]["stored"][
            "maximum"
        ]
        == 5
    )


# --- idempotency -----------------------------------------------------------------------


def test_idempotency_key_is_required_on_remember(spec: dict[str, Any]) -> None:
    param = spec["components"]["parameters"]["IdempotencyKey"]
    assert param["required"] is True
    assert param["in"] == "header"

    refs = [p["$ref"] for p in spec["paths"]["/memories"]["post"]["parameters"]]
    assert "#/components/parameters/IdempotencyKey" in refs


def test_reused_key_with_a_different_payload_is_422(
    spec: dict[str, Any], errors_doc: str
) -> None:
    assert "422" in spec["paths"]["/memories"]["post"]["responses"]
    assert re.search(r"`422`\s*\|\s*`IDEMPOTENCY_KEY_REUSED`", errors_doc)


# --- a filtered request is a no-op, not an error ----------------------------------------


def test_remember_outcomes_include_noop_and_unverified(spec: dict[str, Any]) -> None:
    outcomes = set(
        spec["components"]["schemas"]["RememberResponse"]["properties"]["outcome"][
            "enum"
        ]
    )
    assert outcomes == {"written", "written_unverified", "noop"}


def test_noop_is_a_200_not_a_4xx(spec: dict[str, Any]) -> None:
    examples = spec["paths"]["/memories"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["examples"]
    assert examples["noop"]["value"]["outcome"] == "noop"
    assert examples["noop"]["value"]["stored"] == 0


# --- spec, catalogue and design must agree ----------------------------------------------


def test_every_fact_reason_code_is_documented(
    spec: dict[str, Any], errors_doc: str
) -> None:
    for code in _codes(spec, "FactReasonCode"):
        assert re.search(rf"`{code}`", errors_doc), f"{code} is not in errors.md"


def test_every_error_code_is_documented(spec: dict[str, Any], errors_doc: str) -> None:
    for code in _codes(spec, "ErrorCode"):
        assert re.search(rf"`{code}`", errors_doc), f"{code} is not in errors.md"


def test_fact_reason_codes_match_the_approved_design(spec: dict[str, Any]) -> None:
    """The design lists them explicitly; the spec must not quietly add or drop one."""
    design = DESIGN_PATH.read_text(encoding="utf-8")
    section = design[design.index("Per-fact reason codes:") :]
    section = section[: section.index("\n\n")]
    in_design = set(re.findall(r"`([A-Z_]+)`", section))
    assert _codes(spec, "FactReasonCode") == in_design


def test_provider_429_maps_to_503_never_to_the_callers_429(
    spec: dict[str, Any], errors_doc: str
) -> None:
    """A provider throttle is not the caller's fault; shaping their behaviour would be wrong."""
    assert "PROVIDER_UNAVAILABLE" in _codes(spec, "ErrorCode")
    rate_limited = spec["components"]["responses"]["RateLimited"]["description"]
    assert "never surfaced as this" in rate_limited
    assert re.search(r"`429` is never the provider", errors_doc)


# --- security rule S-4: nothing in an error carries payload -------------------------------


def test_error_schema_carries_no_payload_field(spec: dict[str, Any]) -> None:
    error = spec["components"]["schemas"]["Error"]
    assert error["additionalProperties"] is False
    assert set(error["properties"]) <= {"code", "message", "correlationId", "retryable"}
    for forbidden in ("fact", "value", "topic", "subject", "userId", "provider"):
        assert forbidden not in error["properties"]


def test_errors_doc_states_what_is_never_included(errors_doc: str) -> None:
    assert "S-4" in errors_doc
    assert "correlation ID" in errors_doc


# --- scope is server-side ------------------------------------------------------------------


def test_scope_cannot_be_set_in_the_request_body(spec: dict[str, Any]) -> None:
    body = spec["components"]["schemas"]["RememberRequest"]
    assert body["additionalProperties"] is False
    assert set(body["properties"]) == {"facts"}
    assert "SCOPE_IN_BODY_REFUSED" in _codes(spec, "ErrorCode")


def test_fact_rejects_unknown_properties(spec: dict[str, Any]) -> None:
    assert spec["components"]["schemas"]["Fact"]["additionalProperties"] is False


# --- inference defaults to not permitted -----------------------------------------------------


def test_basis_defaults_to_stated(spec: dict[str, Any]) -> None:
    basis = spec["components"]["schemas"]["Fact"]["properties"]["basis"]
    assert basis["default"] == "stated"
    assert set(basis["enum"]) == {"stated", "inferred"}
    assert "INFERENCE_NOT_PERMITTED" in _codes(spec, "FactReasonCode")
