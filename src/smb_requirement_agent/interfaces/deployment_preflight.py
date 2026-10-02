"""Explicit configuration preflight for opening a shared workspace to public traffic."""

import sys

from smb_requirement_agent.infrastructure.config.options import ConfigurationError, IdentityProvider
from smb_requirement_agent.infrastructure.config.settings import Settings


def validate_public_deployment(settings: Settings) -> None:
    if settings.identity_provider is not IdentityProvider.OIDC:
        raise ConfigurationError(
            "Public deployment requires IDENTITY_PROVIDER=oidc and its issuer, audience, "
            "and client configuration."
        )


def main() -> int:
    try:
        validate_public_deployment(Settings.from_env())
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2
    print("Public identity configuration is valid. Verify /ready before opening traffic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
