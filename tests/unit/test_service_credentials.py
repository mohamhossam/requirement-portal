"""Each portal proves itself with its own credential (ADR-0099, ADR-0104).

Requirement work asks the OIDC issuer for its tokens to the knowledge service
with its own client, and admits the knowledge service's granted tokens on its
internal API, so neither side holds a secret of the other's. Shared tokens keep
working, alone or alongside.
"""

from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from smb_kernel.errors import ServiceAuthenticationError
from smb_kernel.http.client_credentials import ClientCredentialsTokenSource
from smb_kernel.http.service_auth import ServiceTokenVerifier, ServiceVerifierChain

from smb_requirement_agent.infrastructure.config.options import ConfigurationError, LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition import identity
from smb_requirement_agent.interfaces.api.composition.identity import (
    INTERNAL_AUDIENCE,
    build_internal_verifier,
)
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app

ISSUER = "https://identity.example.test/realms/requirement-ai"
TOKEN = "k" * 40
SECRET = "client-secret"
_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _settings(**changes: Any) -> Settings:
    return Settings(llm_provider=LLMProvider.FAKE, **changes)


def _granted(**overrides: object) -> str:
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": INTERNAL_AUDIENCE,
        "azp": "knowledge-service",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, _PRIVATE, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture
def issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The issuer's discovery and keys, served to the verifier's HTTP client."""
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


class TestSettings:
    @pytest.mark.parametrize(
        ("changes", "message"),
        [
            ({"requirement_service_client_id": "requirement-service"}, "set together"),
            ({"requirement_service_client_secret": SECRET}, "set together"),
            (
                {
                    "knowledge_api_base_url": "http://knowledge",
                    "requirement_service_client_id": "requirement-service",
                    "requirement_service_client_secret": SECRET,
                },
                "REQUIREMENT_SERVICE_CLIENT_ID needs OIDC_ISSUER_URL",
            ),
            (
                {"knowledge_service_client_id": "knowledge-service"},
                "KNOWLEDGE_SERVICE_CLIENT_ID needs OIDC_ISSUER_URL",
            ),
            (
                {
                    "knowledge_service_client_id": "knowledge-service",
                    "oidc_issuer_url": "http://identity.example.test",
                },
                "KNOWLEDGE_SERVICE_CLIENT_ID needs OIDC_ISSUER_URL",
            ),
        ],
    )
    def test_incomplete_client_settings_fail_the_boot(
        self, changes: dict[str, str], message: str
    ) -> None:
        with pytest.raises(ConfigurationError, match=message):
            _settings(**changes)

    def test_client_credentials_connect_the_knowledge_portal_without_a_shared_token(
        self,
    ) -> None:
        settings = _settings(
            oidc_issuer_url=ISSUER,
            knowledge_api_base_url="http://knowledge",
            requirement_service_client_id="requirement-service",
            requirement_service_client_secret=SECRET,
        )
        assert settings.knowledge_service_url == "http://knowledge"
        assert settings.uses_service_client
        assert SECRET not in repr(settings)

    def test_they_are_read_from_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        monkeypatch.setenv("OIDC_ISSUER_URL", ISSUER)
        monkeypatch.setenv("KNOWLEDGE_API_BASE_URL", "http://knowledge-api:8000")
        monkeypatch.setenv("REQUIREMENT_SERVICE_CLIENT_ID", "requirement-service")
        monkeypatch.setenv("REQUIREMENT_SERVICE_CLIENT_SECRET", SECRET)
        monkeypatch.setenv("KNOWLEDGE_SERVICE_CLIENT_ID", "knowledge-service")
        settings = Settings.from_env()
        assert settings.requirement_service_client_id == "requirement-service"
        assert settings.requirement_service_client_secret == SECRET
        assert settings.knowledge_service_client_id == "knowledge-service"
        assert settings.knowledge_service_url == "http://knowledge-api:8000"


def test_with_client_credentials_the_issuer_grants_the_outgoing_tokens() -> None:
    container = build_container(
        _settings(
            oidc_issuer_url=ISSUER,
            knowledge_api_base_url="http://knowledge",
            requirement_service_client_id="requirement-service",
            requirement_service_client_secret=SECRET,
        )
    )
    try:
        client = container.knowledge_views._views._client  # type: ignore[attr-defined]
        assert isinstance(client._token, ClientCredentialsTokenSource)
    finally:
        container.close_resources()


class TestIncoming:
    def test_with_neither_credential_nothing_is_admitted(self) -> None:
        with ExitStack() as resources:
            assert build_internal_verifier(_settings(), resources) is None

    def test_a_shared_token_alone_is_checked_in_memory(self) -> None:
        with ExitStack() as resources:
            verifier = build_internal_verifier(_settings(knowledge_service_token=TOKEN), resources)
        assert isinstance(verifier, ServiceTokenVerifier)

    @pytest.mark.usefixtures("issuer")
    def test_a_granted_token_names_the_knowledge_service(self) -> None:
        settings = _settings(
            oidc_issuer_url=ISSUER, knowledge_service_client_id="knowledge-service"
        )
        with ExitStack() as resources:
            verifier = build_internal_verifier(settings, resources)
            assert verifier is not None
            assert verifier.caller(f"Bearer {_granted()}") == "knowledge"
            for refused in (
                _granted(azp="requirement-spa"),
                _granted(aud="requirement-api"),
                _granted(azp="requirement-service"),
            ):
                with pytest.raises(ServiceAuthenticationError):
                    verifier.caller(f"Bearer {refused}")

    @pytest.mark.usefixtures("issuer")
    def test_both_are_admitted_while_a_deployment_moves_over(self) -> None:
        settings = _settings(
            oidc_issuer_url=ISSUER,
            knowledge_service_client_id="knowledge-service",
            knowledge_service_token=TOKEN,
        )
        with ExitStack() as resources:
            verifier = build_internal_verifier(settings, resources)
            assert isinstance(verifier, ServiceVerifierChain)
            assert verifier.caller(f"Bearer {TOKEN}") == "knowledge"
            assert verifier.caller(f"Bearer {_granted()}") == "knowledge"

    def test_the_internal_api_is_served_with_only_the_client_configured(self) -> None:
        container = build_container(
            _settings(oidc_issuer_url=ISSUER, knowledge_service_client_id="knowledge-service")
        )
        with TestClient(create_app(lambda: container)) as client:
            response = client.get("/internal/architecture-mapping/stats")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
