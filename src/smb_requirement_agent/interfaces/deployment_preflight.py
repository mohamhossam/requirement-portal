"""Explicit configuration preflight for opening a shared workspace to public traffic."""

import sys

from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    IdentityProvider,
    LLMProvider,
)
from smb_requirement_agent.infrastructure.config.settings import Settings


def validate_public_deployment(settings: Settings) -> None:
    """Refuse what APP_ENV=production refuses, whatever APP_ENV this process runs with."""
    if settings.identity_provider is not IdentityProvider.OIDC:
        raise ConfigurationError(
            "Public deployment requires IDENTITY_PROVIDER=oidc and its issuer, audience, "
            "and client configuration."
        )
    if settings.llm_provider is LLMProvider.FAKE:
        raise ConfigurationError(
            "Public deployment refuses LLM_PROVIDER=fake: it returns sample output, not analysis."
        )
    if settings.debug_trace_enabled:
        raise ConfigurationError(
            "Public deployment refuses DEBUG_TRACE_ENABLED=true: the trace records prompts, "
            "model output and request paths."
        )


def main() -> int:
    try:
        validate_public_deployment(Settings.from_env())
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2
    print("Public deployment configuration is valid. Verify /ready before opening traffic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
