"""Assemble a :class:`~.api.main.Deployment` from validated configuration and the environment.

The pattern's components take their collaborators as arguments, which keeps them testable but
leaves someone to do the wiring. Without this module every domain writes that wiring itself, and
each one is a chance to pass a deny-all default where a real classifier was meant, or to skip the
write budget entirely. So the wiring is part of the pattern.

Three rules shape it:

* **Validate before building.** The configuration is checked against the pattern's own schema,
  so a typo is a startup error naming the field, not an attribute error on the request path.
* **Fail closed, loudly.** An extension the domain *named* and that cannot be loaded is a startup
  failure. Silently falling back to the deny-all default would be safe but indistinguishable from
  a working deployment that stores nothing, and that is discovered weeks later.
* **Secrets from the environment only.** Never from the configuration file, which is versioned.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .extensions import (
    DenyAllClassifier,
    DenyAllPolicyProvider,
    PiiClassifier,
    PolicyProvider,
    YamlTopicProvider,
)

from .api.auth import IdentityConfig, JwtSubjectVerifier, LocalHeaderVerifier
from .api.main import Caller, ConfigurationError, Deployment
from .api.replay import ReplayCache
from .observability import LoggingMetrics, WriteBudget
from .providers import FakeMemoryBank, MemoryBank

#: Package data, not a repository path. The schema is the *pattern's* artifact — the domain's
#: config/ holds only their own values — so it has to travel inside the wheel. Keeping it outside
#: the package meant an installed pattern could not find it, which only a container would notice.
SCHEMA_PATH = Path(__file__).resolve().parent / "config.schema.json"


def load_config(path: str | Path) -> dict[str, Any]:
    """Read and validate a domain configuration file."""
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"configuration not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"configuration is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError("configuration must be a mapping")

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(raw, schema, format_checker=jsonschema.FormatChecker())
    except jsonschema.ValidationError as exc:
        where = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ConfigurationError(
            f"configuration invalid at {where}: {exc.message}"
        ) from exc
    return raw


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigurationError(f"environment variable {name} is required")
    return value


def _load_extension(path: str, what: str) -> Any:
    """Import a dotted ``module.Attribute`` path — or ``module:Attribute`` — and instantiate it.

    Both forms are accepted because both are in circulation; the colon only matters when a module
    and an attribute share a name. A named-but-unloadable extension stops startup, always: see the
    module docstring.
    """
    if ":" in path:
        module_name, _, attribute = path.partition(":")
    elif "." in path:
        module_name, _, attribute = path.rpartition(".")
    else:
        raise ConfigurationError(
            f"{what} must be a dotted path to a class, such as "
            f"'mydomain.classifier.DomainClassifier', not '{path}'"
        )
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigurationError(
            f"{what} '{path}' could not be imported: {exc}"
        ) from exc
    try:
        target = getattr(module, attribute)
    except AttributeError as exc:
        raise ConfigurationError(
            f"{what} '{path}': module has no attribute '{attribute}'"
        ) from exc
    try:
        return target()
    except Exception as exc:
        raise ConfigurationError(
            f"{what} '{path}' could not be constructed: {exc}"
        ) from exc


def _callers(config: dict[str, Any], topics: dict[str, Any]) -> dict[str, Caller]:
    callers: dict[str, Caller] = {}
    for entry in config["callers"]:
        unknown = sorted(set(entry["topics"]) - set(topics))
        if unknown:
            raise ConfigurationError(
                f"caller '{entry['id']}' is granted topics that do not exist: {unknown}"
            )
        callers[entry["id"]] = Caller(
            caller_id=entry["id"],
            operations=frozenset(entry["operations"]),
            granted_topics=frozenset(entry["topics"]),
        )
    return callers


def _bank(domain: str, metrics: LoggingMetrics, *, local: bool) -> MemoryBank:
    if local:
        # The fake is the reference behaviour, not a stub: it models consolidation, dedup and
        # rollback as verified against the provider. It is never reachable outside local.
        return FakeMemoryBank()

    from .providers.vertex import VertexMemoryBank  # noqa: PLC0415 - optional extra

    return VertexMemoryBank(
        project=_require_env("GOOGLE_CLOUD_PROJECT"),
        location=_require_env("GOOGLE_CLOUD_LOCATION"),
        bank=_require_env("MEMORY_BANK_ID"),
        metrics=metrics,
    )


def build_deployment(
    config: dict[str, Any], *, environment: str | None = None
) -> Deployment:
    """Wire a deployment from validated configuration plus environment and secrets."""
    env = environment or os.environ.get("ENVIRONMENT") or "production"
    local = env.lower() in {"local", "dev-local"}
    domain = config["domain"]["name"]
    metrics = LoggingMetrics(domain=domain)

    extensions = config.get("extensions") or {}
    topic_provider: Any = (
        _load_extension(extensions["topicProvider"], "extensions.topicProvider")
        if "topicProvider" in extensions
        else YamlTopicProvider(config["topics"])
    )
    topics = topic_provider.topics()

    # Omitting these is legitimate and fails closed: the defaults deny everything, so the domain
    # stores nothing until it supplies a real classifier and policy.
    classifier: PiiClassifier = (
        _load_extension(extensions["piiClassifier"], "extensions.piiClassifier")
        if "piiClassifier" in extensions
        else DenyAllClassifier()
    )
    policy: PolicyProvider = (
        _load_extension(extensions["policyProvider"], "extensions.policyProvider")
        if "policyProvider" in extensions
        else DenyAllPolicyProvider()
    )

    quota = config.get("quota")
    if not quota:
        raise ConfigurationError(
            "quota.maxWritesPerMinute is required: the Memory Bank quota is shared across every "
            "domain in the project, and an unbounded domain can starve the others"
        )
    try:
        max_instances = int(os.environ.get("MAX_INSTANCES", "1"))
    except ValueError as exc:
        raise ConfigurationError("MAX_INSTANCES must be an integer") from exc
    budget = WriteBudget(
        writes_per_minute=quota["maxWritesPerMinute"], max_instances=max_instances
    )

    idempotency = config.get("idempotency") or {}
    replay = ReplayCache(
        retention_seconds=int(idempotency.get("retentionSeconds", 900)),
        max_entries=int(idempotency.get("maxEntries", 10000)),
    )

    identity = IdentityConfig(
        issuer=config["identity"]["issuer"],
        jwks_uri=config["identity"]["jwksUri"],
        audience=config["identity"]["audience"],
        subject_hmac_key=_require_env("SUBJECT_HMAC_KEY"),
    )
    verifier = (
        LocalHeaderVerifier(environment=env) if local else JwtSubjectVerifier(identity)
    )

    return Deployment(
        domain=domain,
        topics=topics,
        callers=_callers(config, topics),
        bank=_bank(domain, metrics, local=local),
        classifier=classifier,
        policy=policy,
        identity=identity,
        verifier=verifier,
        metrics=metrics,
        budget=budget,
        replay=replay,
    )
