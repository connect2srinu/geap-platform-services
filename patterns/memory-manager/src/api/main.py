"""The service.

`remember` and `recall`, wiring the validation pipeline, the provider and read-back verification
together. This module translates between HTTP and those three; it decides nothing itself.

Identity is deliberately minimal here. v0.1.0 resolves a caller from a header in local mode and
**refuses to start** with that enabled outside a local environment — the full token verification is
the next task. The refusal is tested, because a development shortcut that merely defaults off is
one deployment away from being on.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Annotated

from extensions import CallerContext, Fact, PiiClassifier, PolicyProvider, Topic
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from ..policy import ReasonCode, validate_facts
from ..providers import MemoryBank, ProviderUnavailable, encode_fact_text
from ..providers.encoding import decode_fact_text
from ..worker import VerificationOutcome, verify_write
from .errors import ErrorCode, error_response
from .models import (
    FactResultOut,
    RecalledValueOut,
    RecallResponse,
    RememberRequest,
    RememberResponse,
)


class ConfigurationError(RuntimeError):
    """The service cannot run as configured. Raised at startup, never swallowed."""


@dataclass(frozen=True, slots=True)
class Caller:
    """A registered caller, from configuration."""

    caller_id: str
    operations: frozenset[str]
    granted_topics: frozenset[str]


@dataclass(frozen=True, slots=True)
class Deployment:
    """Everything the service needs, assembled once at startup."""

    domain: str
    topics: dict[str, Topic]
    callers: dict[str, Caller]
    bank: MemoryBank
    classifier: PiiClassifier
    policy: PolicyProvider
    auth_enabled: bool = True


def _is_local(environment: str | None) -> bool:
    return (environment or "").lower() in {"local", "dev-local"}


def create_app(deployment: Deployment, *, environment: str | None = None) -> FastAPI:
    """Build the service.

    Refuses to start when authentication is disabled outside a local environment. Not defaulted
    off — refused, so a misconfigured deployment fails loudly at boot rather than quietly serving
    unauthenticated traffic.
    """
    if not deployment.auth_enabled and not _is_local(
        environment or os.environ.get("ENVIRONMENT")
    ):
        raise ConfigurationError(
            "auth_enabled=false is permitted only in a local environment; "
            "set ENVIRONMENT=local or enable authentication"
        )

    app = FastAPI(title="Memory Manager", version="0.1.0")
    app.state.deployment = deployment

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        """Readiness includes the provider. Fails until the platform-owned IAM binding exists."""
        try:
            deployment.bank.retrieve((("user_id", "__readiness__"),))
        except ProviderUnavailable:
            return JSONResponse(
                status_code=503, content={"status": "memory store unreachable"}
            )
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.post("/v1/memories")
    def remember(
        body: RememberRequest,
        request: Request,
        x_agent_id: Annotated[str | None, Header()] = None,
        idempotency_key: Annotated[str | None, Header()] = None,
        x_correlation_id: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        correlation_id = x_correlation_id or str(uuid.uuid4())

        if idempotency_key is None:
            return error_response(ErrorCode.IDEMPOTENCY_KEY_MISSING, correlation_id)

        caller = _resolve(deployment, x_agent_id, correlation_id)
        if isinstance(caller, JSONResponse):
            return caller
        if "remember" not in caller.operations:
            return error_response(ErrorCode.CALLER_NOT_PERMITTED, correlation_id)

        context = _context(deployment, caller, correlation_id)
        facts = [
            _to_fact(f.topic, f.field_name, f.value, f.fact, f.basis)
            for f in body.facts
        ]
        outcomes = validate_facts(
            facts,
            context,
            topics=deployment.topics,
            classifier=deployment.classifier,
            policy=deployment.policy,
        )

        approved = [o for o in outcomes if o.accepted and o.fact is not None]
        results = [
            FactResultOut(index=o.index, topic=o.topic, reasonCode=o.reason.value)
            for o in outcomes
        ]

        if not approved:
            return _ok(
                RememberResponse(outcome="noop", stored=0, results=results),
                correlation_id,
            )

        texts = [
            encode_fact_text(o.fact.topic, o.fact.field_name, o.fact.text)
            for o in approved
            if o.fact is not None
        ]
        try:
            written = deployment.bank.write(texts, context.scope)
        except ProviderUnavailable:
            # The write was not accepted. Say so; a retry with the same key is correct.
            return error_response(
                ErrorCode.PROVIDER_UNAVAILABLE, correlation_id, retry_after=5
            )

        verification = verify_write(
            written.memory_names,
            context,
            bank=deployment.bank,
            classifier=deployment.classifier,
        )

        names = list(written.memory_names)
        for position, outcome in enumerate(o for o in outcomes if o.accepted):
            if position < len(names):
                results[outcome.index] = FactResultOut(
                    index=outcome.index,
                    topic=outcome.topic,
                    reasonCode=ReasonCode.ACCEPTED.value,
                    memoryId=names[position].rsplit("/", 1)[-1],
                )

        if verification.outcome is VerificationOutcome.WRITTEN_UNVERIFIED:
            api_outcome = "written_unverified"
        else:
            api_outcome = "written"

        return _ok(
            RememberResponse(
                outcome=api_outcome,  # type: ignore[arg-type]
                stored=len(approved),
                results=results,
            ),
            correlation_id,
        )

    @app.get("/v1/memories")
    def recall(
        request: Request,
        topic: str | None = None,
        x_agent_id: Annotated[str | None, Header()] = None,
        x_correlation_id: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        correlation_id = x_correlation_id or str(uuid.uuid4())

        caller = _resolve(deployment, x_agent_id, correlation_id)
        if isinstance(caller, JSONResponse):
            return caller
        if "recall" not in caller.operations:
            return error_response(ErrorCode.CALLER_NOT_PERMITTED, correlation_id)

        context = _context(deployment, caller, correlation_id)
        try:
            stored = deployment.bank.retrieve(context.scope)
        except ProviderUnavailable:
            return error_response(
                ErrorCode.PROVIDER_UNAVAILABLE, correlation_id, retry_after=5
            )

        values: list[RecalledValueOut] = []
        withheld = 0
        for memory in stored:
            decoded = decode_fact_text(memory.text)
            if decoded is None:
                # Unattributable: no topic, so no rules to judge it by. Withhold it.
                withheld += 1
                continue
            if topic is not None and decoded.topic != topic:
                continue
            if decoded.topic not in caller.granted_topics:
                continue
            topic_config = deployment.topics.get(decoded.topic)
            if topic_config is None or not topic_config.is_eligible:
                withheld += 1
                continue
            # Re-classify before returning, as a backstop against a consolidation that rewrote
            # a stored fact into prohibited content after it was written.
            probe = _to_fact(
                decoded.topic, decoded.field, decoded.text, decoded.text, "stated"
            )
            try:
                if not deployment.classifier.classify(probe, context).allowed:
                    withheld += 1
                    continue
            except Exception:  # noqa: BLE001 - an undecided classifier withholds, never returns
                withheld += 1
                continue
            values.append(
                RecalledValueOut(
                    topic=decoded.topic,
                    field=decoded.field,
                    value=decoded.text,
                    fact=decoded.text,
                )
            )

        return _ok(RecallResponse(values=values, withheld=withheld), correlation_id)

    return app


# -- helpers ---------------------------------------------------------------------------


def _to_fact(
    topic: str, field: str | None, value: str | float | bool, text: str, basis: str
) -> Fact:
    return Fact(
        topic=topic,
        value=value,
        text=text,
        field_name=field,
        basis="inferred" if basis == "inferred" else "stated",
    )


def _resolve(
    deployment: Deployment, agent_id: str | None, correlation_id: str
) -> Caller | JSONResponse:
    if agent_id is None:
        return error_response(ErrorCode.UNAUTHENTICATED, correlation_id)
    caller = deployment.callers.get(agent_id)
    if caller is None:
        return error_response(ErrorCode.CALLER_NOT_REGISTERED, correlation_id)
    return caller


def _context(
    deployment: Deployment, caller: Caller, correlation_id: str
) -> CallerContext:
    """Scope is derived here, from the caller — never from a request body."""
    return CallerContext(
        caller_id=caller.caller_id,
        domain=deployment.domain,
        scope=(("user_id", f"{deployment.domain}:{caller.caller_id}"),),
        subject_pseudonym=f"hmac-{caller.caller_id}",
        operations=caller.operations,
        granted_topics=caller.granted_topics,
        correlation_id=correlation_id,
    )


def _ok(model: RememberResponse | RecallResponse, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=model.model_dump(exclude_none=True),
        headers={"X-Correlation-Id": correlation_id},
    )
