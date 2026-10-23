"""Caller authentication and server-side scope resolution.

Three things, in order:

1. **Verify the forwarded end-user token** against the domain's configured issuer and JWKS. Signature,
   issuer, audience and expiry are all checked — not just decoded.
2. **Resolve the scope from the verified subject**, never from the request. A caller cannot name
   whose memory it is reading or writing.
3. **Pseudonymise the subject** with an HMAC before it goes anywhere else. The raw subject never
   reaches a log, a metric, an audit event or an extension (security rules S-4 and S-7).

The development shortcut — identifying a caller from a header — exists because a conformance suite
has no Google-signed token to present. It is **refused** outside a local environment, not merely
defaulted off, and the refusal is tested.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient


class AuthError(Exception):
    """The caller could not be authenticated. Carries a code, never a token or a subject."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class IdentityConfig:
    """How to verify a token. Values come from configuration; the HMAC key from Secret Manager."""

    issuer: str
    jwks_uri: str
    audience: str
    subject_hmac_key: str
    algorithms: tuple[str, ...] = ("RS256", "ES256")

    def __post_init__(self) -> None:
        for name in ("issuer", "jwks_uri", "audience", "subject_hmac_key"):
            if not getattr(self, name):
                # Refusing here means the service cannot start half-configured. A missing HMAC key
                # would otherwise silently produce a constant pseudonym for every user.
                raise ValueError(f"identity configuration is missing '{name}'")
        if not self.algorithms:
            raise ValueError("identity configuration is missing 'algorithms'")
        # "none" means an unsigned token, which is the classic JWT forgery. Refusing it here makes
        # it impossible to configure, rather than relying on the library's key handling to reject
        # it incidentally -- which is what it does, and which a later refactor could undo.
        for algorithm in self.algorithms:
            if algorithm.lower() in {"none", ""}:
                raise ValueError("'none' is not an acceptable signing algorithm")


class SubjectVerifier(Protocol):
    """Turns a bearer token into a verified subject."""

    def verify(self, token: str) -> str: ...


class JwtSubjectVerifier:
    """Verifies a JWT against the configured issuer's JWKS.

    `PyJWKClient` caches the key set, so the JWKS endpoint is not fetched per request.
    """

    def __init__(
        self, config: IdentityConfig, *, jwk_client: Any | None = None
    ) -> None:
        self._config = config
        self._keys = jwk_client or PyJWKClient(config.jwks_uri, cache_keys=True)

    def verify(self, token: str) -> str:
        try:
            key = self._keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=list(self._config.algorithms),
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("TOKEN_INVALID") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthError("TOKEN_INVALID") from exc
        except Exception as exc:  # noqa: BLE001 - a JWKS fetch failure is not an authentication
            raise AuthError("TOKEN_INVALID") from exc

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthError("TOKEN_INVALID")
        return subject


class LocalHeaderVerifier:
    """The development shortcut: the subject is whatever the header says.

    Constructing this outside a local environment raises. `create_app` also refuses, so the
    shortcut is blocked at two independent points rather than one.
    """

    def __init__(self, *, environment: str | None) -> None:
        if (environment or "").lower() not in {"local", "dev-local"}:
            raise ValueError(
                "the local header verifier is permitted only in a local environment; "
                f"ENVIRONMENT={environment!r}"
            )

    def verify(self, token: str) -> str:
        if not token:
            raise AuthError("UNAUTHENTICATED")
        return token


def pseudonymise(subject: str, key: str) -> str:
    """A stable, non-reversible handle for an end user.

    HMAC rather than a bare hash, so the mapping cannot be rebuilt by hashing a guessed list of
    subjects — a plain SHA-256 of an email address is trivially reversible by dictionary.
    """
    digest = hmac.new(key.encode("utf-8"), subject.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:32]


def resolve_scope(domain: str, pseudonym: str) -> tuple[tuple[str, str], ...]:
    """The memory scope for a verified subject.

    Derived here and nowhere else. The request body has no scope field, and this is the only place
    one is constructed, so a caller cannot reach another user's memory however the request is shaped.
    """
    return (("organization_id", domain), ("user_id", pseudonym))
