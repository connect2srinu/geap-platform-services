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
import time
import uuid
from dataclasses import dataclass, field
from typing import Annotated

from ..extensions import CallerContext, Fact, PiiClassifier, PolicyProvider, Topic
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from ..observability import (
    AuditSink,
    BudgetExhausted,
    MetricSink,
    NullAudit,
    NullMetrics,
    WriteBudget,
)
from ..policy import ReasonCode, validate_facts
from ..providers import MemoryBank, ProviderUnavailable, encode_fact_text
from ..providers.encoding import decode_fact_text
from ..worker import VerificationOutcome, verify_write
from .auth import (
    AuthError,
    IdentityConfig,
    SubjectVerifier,
    pseudonymise,
    resolve_scope,
)
from .errors import ErrorCode, error_response
from .replay import KeyReused, ReplayCache, fingerprint, scoped_key
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
    identity: IdentityConfig
    verifier: SubjectVerifier
    metrics: MetricSink = field(default_factory=NullMetrics)
    #: Where this deployment records what it did. `bootstrap` always supplies a real sink; the
    #: null default exists so a directly constructed Deployment still runs in a test.
    audit: AuditSink = field(default_factory=NullAudit)
    #: One instance's share of the domain's write budget. Required: a deployment with no budget
    #: cannot bound its consumption of the shared project quota.
    budget: WriteBudget | None = None
    #: What each idempotency key did on this instance. Per instance by design — see replay.py.
    replay: ReplayCache = field(default_factory=ReplayCache)
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

    if deployment.budget is None:
        raise ConfigurationError(
            "a write budget is required: the project's Memory Bank quota is shared across every "
            "domain, and a deployment that cannot bound its own consumption can starve another"
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
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        correlation_id = x_correlation_id or str(uuid.uuid4())
        started = time.monotonic()

        def done(decision: str) -> None:
            deployment.metrics.increment(
                "tool_invocations", operation="remember", decision=decision
            )
            deployment.metrics.increment(
                "tool_latency",
                operation="remember",
                ms=str(int((time.monotonic() - started) * 1000)),
            )

        if idempotency_key is None:
            done("refused")
            return error_response(ErrorCode.IDEMPOTENCY_KEY_MISSING, correlation_id)

        resolved = _resolve(deployment, x_agent_id, authorization, correlation_id)
        if isinstance(resolved, JSONResponse):
            return resolved
        caller, subject = resolved
        if "remember" not in caller.operations:
            # No scope yet, so no pseudonym to name. The caller and the reason are what an
            # investigator needs here, and the raw subject is never emitted (S-4).
            deployment.audit.emit(
                "policy_denial",
                correlation_id=correlation_id,
                caller_id=caller.caller_id,
                domain=deployment.domain,
                operation="remember",
                reason="CALLER_NOT_PERMITTED",
            )
            done("refused")
            return error_response(ErrorCode.CALLER_NOT_PERMITTED, correlation_id)

        context = _context(deployment, caller, subject, correlation_id)

        # After the caller and scope are resolved, because both are part of a request's identity;
        # before validation, the budget and the write, because a replay must consume none of them.
        replay_key = scoped_key(caller.caller_id, context.scope, idempotency_key)
        request_fingerprint = fingerprint(body.model_dump(mode="json"))
        try:
            recorded = deployment.replay.lookup(replay_key, request_fingerprint)
        except KeyReused:
            deployment.metrics.increment(
                "tool_invocations", operation="remember", decision="key_reused"
            )
            deployment.audit.emit(
                "policy_denial",
                correlation_id=correlation_id,
                caller_id=caller.caller_id,
                domain=deployment.domain,
                subject_pseudonym=context.subject_pseudonym,
                operation="remember",
                reason="IDEMPOTENCY_KEY_REUSED",
            )
            done("refused")
            return error_response(ErrorCode.IDEMPOTENCY_KEY_REUSED, correlation_id)
        if recorded is not None:
            # The recorded body, but this request's correlation id: a replay is a distinct
            # request and has to be traceable as one.
            deployment.audit.emit(
                "idempotency_replay",
                correlation_id=correlation_id,
                caller_id=caller.caller_id,
                domain=deployment.domain,
                subject_pseudonym=context.subject_pseudonym,
            )
            done("replayed")
            return JSONResponse(
                status_code=200,
                content=recorded,
                headers={"X-Correlation-Id": correlation_id},
            )

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
            metrics=deployment.metrics,
            audit=deployment.audit,
        )

        approved = [o for o in outcomes if o.accepted and o.fact is not None]
        results = [
            FactResultOut(index=o.index, topic=o.topic, reasonCode=o.reason.value)
            for o in outcomes
        ]

        if not approved:
            deployment.audit.emit(
                "policy_denial",
                correlation_id=correlation_id,
                caller_id=caller.caller_id,
                domain=deployment.domain,
                subject_pseudonym=context.subject_pseudonym,
                operation="remember",
                reason=",".join(sorted({o.reason.value for o in outcomes})),
            )
            done("noop")
            return _recorded(
                deployment,
                replay_key,
                request_fingerprint,
                RememberResponse(outcome="noop", stored=0, results=results),
                correlation_id,
            )

        texts = [
            encode_fact_text(o.fact.topic, o.fact.field_name, o.fact.text)
            for o in approved
            if o.fact is not None
        ]
        try:
            assert deployment.budget is not None  # guaranteed by create_app
            deployment.budget.take(len(texts))
        except BudgetExhausted as exhausted:
            deployment.metrics.increment("quota_budget_exhausted", operation="remember")
            deployment.audit.emit(
                "policy_denial",
                correlation_id=correlation_id,
                caller_id=caller.caller_id,
                domain=deployment.domain,
                subject_pseudonym=context.subject_pseudonym,
                operation="remember",
                reason="RATE_LIMITED",
            )
            done("rate_limited")
            return error_response(
                ErrorCode.RATE_LIMITED,
                correlation_id,
                retry_after=exhausted.retry_after_seconds,
            )

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
            metrics=deployment.metrics,
            audit=deployment.audit,
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

        deployment.audit.emit(
            "memory_write",
            correlation_id=correlation_id,
            caller_id=caller.caller_id,
            domain=deployment.domain,
            subject_pseudonym=context.subject_pseudonym,
            stored=str(len(approved)),
            outcome=api_outcome,
        )
        done(api_outcome)
        return _recorded(
            deployment,
            replay_key,
            request_fingerprint,
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
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        correlation_id = x_correlation_id or str(uuid.uuid4())
        started = time.monotonic()

        def done(decision: str) -> None:
            deployment.metrics.increment(
                "tool_invocations", operation="recall", decision=decision
            )
            deployment.metrics.increment(
                "tool_latency",
                operation="recall",
                ms=str(int((time.monotonic() - started) * 1000)),
            )

        resolved = _resolve(deployment, x_agent_id, authorization, correlation_id)
        if isinstance(resolved, JSONResponse):
            return resolved
        caller, subject = resolved
        if "recall" not in caller.operations:
            deployment.audit.emit(
                "policy_denial",
                correlation_id=correlation_id,
                caller_id=caller.caller_id,
                domain=deployment.domain,
                operation="recall",
                reason="CALLER_NOT_PERMITTED",
            )
            done("refused")
            return error_response(ErrorCode.CALLER_NOT_PERMITTED, correlation_id)

        context = _context(deployment, caller, subject, correlation_id)
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

        if withheld:
            deployment.metrics.increment("recall_withheld", count=str(withheld))
        # Beyond what S-7 names. A read of someone's memory is what an investigator would want a
        # trail of, and the counts say how much was served without saying what.
        deployment.audit.emit(
            "memory_recall",
            correlation_id=correlation_id,
            caller_id=caller.caller_id,
            domain=deployment.domain,
            subject_pseudonym=context.subject_pseudonym,
            served=str(len(values)),
            withheld=str(withheld),
            topic=topic or "",
        )
        done("served")
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
    deployment: Deployment,
    agent_id: str | None,
    authorization: str | None,
    correlation_id: str,
) -> tuple[Caller, str] | JSONResponse:
    """Identify the calling agent, then verify the end user whose memory it is acting on.

    Both are required. The agent says who is asking; the token says whose memory it is. A valid
    agent with no end-user token has not told us the second, and the scope cannot be guessed.
    """
    if agent_id is None:
        return error_response(ErrorCode.UNAUTHENTICATED, correlation_id)
    caller = deployment.callers.get(agent_id)
    if caller is None:
        return error_response(ErrorCode.CALLER_NOT_REGISTERED, correlation_id)

    token = _bearer(authorization)
    if token is None:
        return error_response(ErrorCode.UNAUTHENTICATED, correlation_id)
    try:
        subject = deployment.verifier.verify(token)
    except AuthError as exc:
        code = (
            ErrorCode.UNAUTHENTICATED
            if exc.code == "UNAUTHENTICATED"
            else ErrorCode.TOKEN_INVALID
        )
        return error_response(code, correlation_id)
    if not subject:
        return error_response(ErrorCode.SCOPE_NOT_RESOLVABLE, correlation_id)
    return caller, subject


def _bearer(authorization: str | None) -> str | None:
    """The token from an Authorization header, or None.

    A malformed header is treated as absent rather than as a distinct error. Telling a caller
    whether its header *shape* was wrong versus its token invalid is worth nothing to them and
    something to someone probing.
    """
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1].strip()


def _context(
    deployment: Deployment, caller: Caller, subject: str, correlation_id: str
) -> CallerContext:
    """Scope is derived here, from the verified subject - never from a request body.

    The raw subject is pseudonymised before it reaches anywhere another component can see it, so no
    extension, log, metric or audit event ever receives it (S-4, S-7).
    """
    pseudonym = pseudonymise(subject, deployment.identity.subject_hmac_key)
    return CallerContext(
        caller_id=caller.caller_id,
        domain=deployment.domain,
        scope=resolve_scope(deployment.domain, pseudonym),
        subject_pseudonym=pseudonym,
        operations=caller.operations,
        granted_topics=caller.granted_topics,
        correlation_id=correlation_id,
    )


def _recorded(
    deployment: Deployment,
    replay_key: str,
    request_fingerprint: str,
    model: RememberResponse,
    correlation_id: str,
) -> JSONResponse:
    """Return a **completed** outcome and record it against the key.

    Only completed outcomes pass through here. A retryable failure — RATE_LIMITED,
    PROVIDER_UNAVAILABLE — returns through `error_response` and is never recorded, because caching
    one would turn a transient outage into a permanent failure for that key and send the caller
    following our own Retry-After into a wall.
    """
    body = model.model_dump(exclude_none=True)
    deployment.replay.record(replay_key, request_fingerprint, body)
    return JSONResponse(
        status_code=200,
        content=body,
        headers={"X-Correlation-Id": correlation_id},
    )


def _ok(model: RememberResponse | RecallResponse, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=model.model_dump(exclude_none=True),
        headers={"X-Correlation-Id": correlation_id},
    )
