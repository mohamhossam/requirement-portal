"""Identity selection: who is calling, and which actors the directory knows up front."""

from __future__ import annotations

from contextlib import ExitStack
from time import monotonic

import httpx as httpx
from smb_kernel.identity.oidc import OidcIdentityProvider
from smb_kernel.identity.ports import IdentityProviderPort

from smb_requirement_agent.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.infrastructure.config.options import IdentityProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.identity.fake_identity import (
    FAKE_ACTORS,
    FakeIdentityProvider,
)


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
    )
