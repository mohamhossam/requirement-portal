"""Identity selection: who is calling, and which actors the directory knows up front."""

from __future__ import annotations

from contextlib import ExitStack
from time import monotonic

import httpx as httpx
from smb_kernel.http.service_auth import (
    ServiceCallerVerifier,
    ServiceJwtVerifier,
    ServiceTokenVerifier,
    ServiceVerifierChain,
)
from smb_kernel.identity.oidc import OidcIdentityProvider, OidcSigningKeys
from smb_kernel.identity.ports import IdentityProviderPort

from smb_requirement_agent.identity.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.identity.infrastructure.fake_identity import (
    FAKE_ACTORS,
    FakeIdentityProvider,
)
from smb_requirement_agent.infrastructure.config.options import IdentityProvider
from smb_requirement_agent.infrastructure.config.settings import Settings

# The audience a token the OIDC issuer grants the knowledge service must carry to
# reach this service's internal API. The knowledge portal's service client adds it.
INTERNAL_AUDIENCE = "requirement-internal"


def build_identity(
    settings: Settings,
    resources: ExitStack,
    actor_directory: ActorDirectoryPort,
    override: IdentityProviderPort | None,
) -> IdentityProviderPort:
    """Select the identity provider; fake identity also seeds its known actors."""
    if settings.identity_provider is IdentityProvider.FAKE:
        for fake_actor in FAKE_ACTORS:
            actor_directory.record(fake_actor)
    if override is not None:
        return override
    if settings.identity_provider is IdentityProvider.FAKE:
        return FakeIdentityProvider()
    return OidcIdentityProvider(
        settings.oidc_issuer_url,
        settings.oidc_audience,
        settings.oidc_allowed_algorithms,
        resources.enter_context(httpx.Client(timeout=10)),
        monotonic,
        jwks_ttl_seconds=settings.oidc_jwks_ttl_seconds,
        unknown_key_ttl_seconds=settings.oidc_unknown_key_ttl_seconds,
        unknown_key_cache_size=settings.oidc_unknown_key_cache_size,
        roles_claim=settings.oidc_roles_claim,
        leeway_seconds=settings.oidc_leeway_seconds,
        # A person's token must come from this app's sign-in client, or one the
        # deployment adds; a service's token for the same audience is refused.
        authorized_parties=(settings.oidc_client_id, *settings.oidc_authorized_parties),
    )


def build_internal_verifier(
    settings: Settings, resources: ExitStack
) -> ServiceCallerVerifier | None:
    """Who may call /internal: the knowledge service, named "knowledge" (ADR-0099).

    It proves itself with the shared KNOWLEDGE_SERVICE_TOKEN, with a token the
    OIDC issuer granted its client KNOWLEDGE_SERVICE_CLIENT_ID (ADR-0104), or with
    either while a deployment moves over. With neither configured there is no
    caller, and the internal API is not served.
    """
    verifiers: list[ServiceCallerVerifier] = []
    if settings.knowledge_service_token is not None:
        verifiers.append(ServiceTokenVerifier({"knowledge": settings.knowledge_service_token}))
    if settings.knowledge_service_client_id is not None:
        keys = OidcSigningKeys(
            settings.oidc_issuer_url,
            resources.enter_context(httpx.Client(timeout=10)),
            monotonic,
            jwks_ttl_seconds=settings.oidc_jwks_ttl_seconds,
            unknown_key_ttl_seconds=settings.oidc_unknown_key_ttl_seconds,
            unknown_key_cache_size=settings.oidc_unknown_key_cache_size,
        )
        verifiers.append(
            ServiceJwtVerifier(
                keys,
                INTERNAL_AUDIENCE,
                {settings.knowledge_service_client_id: "knowledge"},
                allowed_algorithms=settings.oidc_allowed_algorithms,
                leeway_seconds=settings.oidc_leeway_seconds,
            )
        )
    if not verifiers:
        return None
    return verifiers[0] if len(verifiers) == 1 else ServiceVerifierChain(*verifiers)
