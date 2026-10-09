"""A person's token, as the composition root checks it (ADR-0018, amendment 2026-10-09).

It must be an access token, issued to this app's sign-in client or a client the
deployment adds, and a minute of clock difference with the issuer is tolerated.
"""

from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from smb_kernel.errors import AuthenticationRequiredError
from smb_kernel.identity.ports import IdentityCredential

from smb_requirement_agent.identity.infrastructure.in_memory_identity import (
    InMemoryActorDirectory,
)
from smb_requirement_agent.infrastructure.config.options import IdentityProvider, LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition import identity
from smb_requirement_agent.interfaces.api.composition.identity import build_identity

ISSUER = "https://identity.example.test/realms/requirement-ai"
AUDIENCE = "requirement-api"
_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The issuer's discovery and keys, served to the provider's HTTP client."""
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_PRIVATE.public_key(), as_dict=True)
    jwk.update({"kid": "k1", "use": "sig"})

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": f"{ISSUER}/certs"})
        return httpx.Response(200, json={"keys": [jwk]})

    real = httpx.Client

    def client(**options: Any) -> httpx.Client:
        return real(transport=httpx.MockTransport(handle), **options)

    monkeypatch.setattr(identity.httpx, "Client", client)


def _token(**overrides: object) -> IdentityCredential:
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "person-1",
        "azp": "requirement-spa",
        "typ": "Bearer",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    return IdentityCredential(
        jwt.encode(claims, _PRIVATE, algorithm="RS256", headers={"kid": "k1"})
    )


def _authenticate(credential: IdentityCredential, **changes: Any) -> str:
    settings = Settings(
        llm_provider=LLMProvider.FAKE,
        identity_provider=IdentityProvider.OIDC,
        oidc_issuer_url=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_client_id="requirement-spa",
        **changes,
    )
    with ExitStack() as resources:
        directory = InMemoryActorDirectory(lock=RLock())
        provider = build_identity(settings, resources, directory, override=None)
        return provider.authenticate(credential).display_name


def test_an_access_token_from_the_sign_in_client_is_accepted() -> None:
    assert _authenticate(_token()) == "person-1"


@pytest.mark.parametrize(
    "credential",
    [
        _token(azp="requirement-service"),
        _token(azp=None),
        _token(typ="ID"),
        _token(typ="Refresh"),
        _token(exp=datetime.now(UTC) - timedelta(minutes=5)),
    ],
    ids=["another client", "no client", "an ID token", "a refresh token", "expired"],
)
def test_other_tokens_are_refused(credential: IdentityCredential) -> None:
    with pytest.raises(AuthenticationRequiredError):
        _authenticate(credential)


def test_a_client_the_deployment_adds_is_accepted_beside_the_sign_in_client() -> None:
    added = {"oidc_authorized_parties": ("release-cli",)}

    assert _authenticate(_token(azp="release-cli"), **added) == "person-1"
    assert _authenticate(_token(), **added) == "person-1"


def test_a_minute_of_clock_difference_is_tolerated_unless_configured_away() -> None:
    just_expired = _token(exp=datetime.now(UTC) - timedelta(seconds=30))

    assert _authenticate(just_expired) == "person-1"
    with pytest.raises(AuthenticationRequiredError):
        _authenticate(just_expired, oidc_leeway_seconds=0)
