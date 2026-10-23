"""Authentication, scope resolution and pseudonymisation.

Security rule S-1 lives here, and S-7's "the raw subject never leaves this layer".

Tokens are signed with a throwaway RSA key generated per test run, so the verifier is exercised
against real signatures rather than a stubbed-out decode.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))

from memory_manager.api.auth import (  # noqa: E402
    AuthError,
    IdentityConfig,
    JwtSubjectVerifier,
    LocalHeaderVerifier,
    pseudonymise,
    resolve_scope,
)

ISSUER = "https://issuer.example-domain.invalid"
AUDIENCE = "memory-manager"
HMAC_KEY = "a-test-only-hmac-key"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def config(**kw: Any) -> IdentityConfig:
    base: dict[str, Any] = {
        "issuer": ISSUER,
        "jwks_uri": f"{ISSUER}/.well-known/jwks.json",
        "audience": AUDIENCE,
        "subject_hmac_key": HMAC_KEY,
    }
    base.update(kw)
    return IdentityConfig(**base)


class StubJwkClient:
    """Stands in for the JWKS endpoint. The signature itself is real."""

    def __init__(self, key: Any = None) -> None:
        self._key = key if key is not None else _KEY.public_key()

    def get_signing_key_from_jwt(self, token: str) -> Any:
        class Signing:
            def __init__(self, k: Any) -> None:
                self.key = k

        return Signing(self._key)


def token(**claims: Any) -> str:
    payload: dict[str, Any] = {
        "sub": "user-1234",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 300,
    }
    payload.update(claims)
    return jwt.encode(payload, _KEY, algorithm="RS256")


def verifier(**kw: Any) -> JwtSubjectVerifier:
    return JwtSubjectVerifier(
        config(**kw.pop("config", {})), jwk_client=StubJwkClient(**kw)
    )


# --- configuration must be complete ---------------------------------------------------


@pytest.mark.parametrize(
    "missing", ["issuer", "jwks_uri", "audience", "subject_hmac_key"]
)
def test_incomplete_identity_configuration_is_refused(missing: str) -> None:
    """The service cannot start half-configured. A missing HMAC key would otherwise produce a
    constant pseudonym for every user."""
    with pytest.raises(ValueError, match=missing):
        config(**{missing: ""})


# --- a valid token ----------------------------------------------------------------------


def test_a_valid_token_yields_its_subject() -> None:
    assert verifier().verify(token()) == "user-1234"


# --- every way a token can be wrong ---------------------------------------------------------


def test_an_expired_token_is_refused() -> None:
    with pytest.raises(AuthError) as caught:
        verifier().verify(token(exp=int(time.time()) - 10))
    assert caught.value.code == "TOKEN_INVALID"


def test_a_token_from_another_issuer_is_refused() -> None:
    with pytest.raises(AuthError):
        verifier().verify(token(iss="https://attacker.invalid"))


def test_a_token_for_another_audience_is_refused() -> None:
    with pytest.raises(AuthError):
        verifier().verify(token(aud="some-other-service"))


def test_a_token_signed_by_another_key_is_refused() -> None:
    """The signature is actually checked, not merely decoded."""
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        {
            "sub": "user-1234",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": int(time.time()) + 300,
        },
        other,
        algorithm="RS256",
    )
    with pytest.raises(AuthError):
        verifier().verify(forged)


def test_an_unsigned_token_is_refused() -> None:
    """alg=none must never be accepted."""
    unsigned = jwt.encode(
        {
            "sub": "user-1234",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": int(time.time()) + 300,
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(AuthError):
        verifier().verify(unsigned)


@pytest.mark.parametrize("algorithm", ["none", "NONE", "None", ""])
def test_none_cannot_even_be_configured(algorithm: str) -> None:
    """The test above passed because PyJWT rejected the KEY, not because the allowlist excluded
    'none' - so it would have kept passing had someone added 'none' to the list. This refuses it at
    configuration time, where a refactor cannot quietly undo it."""
    with pytest.raises(ValueError, match="not an acceptable signing algorithm"):
        config(algorithms=("RS256", algorithm))


def test_an_empty_algorithm_list_is_refused() -> None:
    with pytest.raises(ValueError, match="algorithms"):
        config(algorithms=())


@pytest.mark.parametrize("claim", ["sub", "exp", "iss", "aud"])
def test_a_token_missing_a_required_claim_is_refused(claim: str) -> None:
    payload = {
        "sub": "u",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 300,
    }
    del payload[claim]
    with pytest.raises(AuthError):
        verifier().verify(jwt.encode(payload, _KEY, algorithm="RS256"))


def test_an_empty_subject_is_refused() -> None:
    with pytest.raises(AuthError):
        verifier().verify(token(sub=""))


def test_garbage_is_refused() -> None:
    with pytest.raises(AuthError):
        verifier().verify("not-a-token")


def test_a_jwks_failure_is_not_an_authentication() -> None:
    class Broken:
        def get_signing_key_from_jwt(self, token: str) -> Any:
            raise RuntimeError("jwks unreachable")

    v = JwtSubjectVerifier(config(), jwk_client=Broken())
    with pytest.raises(AuthError):
        v.verify(token())


def test_an_auth_error_carries_no_token_or_subject() -> None:
    """S-4: the code is all a caller or a log gets."""
    with pytest.raises(AuthError) as caught:
        verifier().verify(token(sub="alice@example.invalid", exp=int(time.time()) - 10))
    assert "alice" not in str(caught.value)
    assert caught.value.code == "TOKEN_INVALID"


# --- the development shortcut is refused outside local -------------------------------------------


@pytest.mark.parametrize("environment", ["production", "staging", "prod", "", None])
def test_the_local_verifier_refuses_to_exist_outside_local(
    environment: str | None,
) -> None:
    """Blocked at construction as well as in create_app - two independent points, not one."""
    with pytest.raises(ValueError, match="only in a local environment"):
        LocalHeaderVerifier(environment=environment)


@pytest.mark.parametrize("environment", ["local", "LOCAL", "dev-local"])
def test_the_local_verifier_is_permitted_locally(environment: str) -> None:
    assert LocalHeaderVerifier(environment=environment).verify("user-1") == "user-1"


def test_the_local_verifier_still_requires_something() -> None:
    with pytest.raises(AuthError) as caught:
        LocalHeaderVerifier(environment="local").verify("")
    assert caught.value.code == "UNAUTHENTICATED"


# --- pseudonymisation ------------------------------------------------------------------------------


def test_the_pseudonym_is_stable() -> None:
    assert pseudonymise("user-1", HMAC_KEY) == pseudonymise("user-1", HMAC_KEY)


def test_different_subjects_get_different_pseudonyms() -> None:
    assert pseudonymise("user-1", HMAC_KEY) != pseudonymise("user-2", HMAC_KEY)


def test_a_different_key_gives_a_different_pseudonym() -> None:
    """HMAC, not a bare hash: the mapping cannot be rebuilt by hashing a guessed subject list."""
    assert pseudonymise("user-1", HMAC_KEY) != pseudonymise("user-1", "another-key")


def test_the_pseudonym_does_not_contain_the_subject() -> None:
    assert "alice@example.invalid" not in pseudonymise(
        "alice@example.invalid", HMAC_KEY
    )


def test_a_plain_sha256_of_the_subject_is_not_the_pseudonym() -> None:
    """Guards against someone 'simplifying' the HMAC into a hash, which a dictionary reverses."""
    import hashlib

    plain = hashlib.sha256(b"user-1").hexdigest()[:32]
    assert pseudonymise("user-1", HMAC_KEY) != plain


# --- scope is derived, never supplied ------------------------------------------------------------------


def test_the_scope_is_built_from_the_domain_and_pseudonym() -> None:
    scope = resolve_scope("example-domain", "pseudo-1")
    assert scope == (("organization_id", "example-domain"), ("user_id", "pseudo-1"))


def test_two_subjects_never_share_a_scope() -> None:
    a = resolve_scope("example-domain", pseudonymise("user-1", HMAC_KEY))
    b = resolve_scope("example-domain", pseudonymise("user-2", HMAC_KEY))
    assert a != b


def test_two_domains_never_share_a_scope() -> None:
    """S-8 at the scope level: one domain cannot reach another's memory."""
    pseudonym = pseudonymise("user-1", HMAC_KEY)
    assert resolve_scope("domain-a", pseudonym) != resolve_scope("domain-b", pseudonym)


def test_the_scope_never_contains_the_raw_subject() -> None:
    scope = resolve_scope(
        "example-domain", pseudonymise("alice@example.invalid", HMAC_KEY)
    )
    assert "alice" not in str(scope)
