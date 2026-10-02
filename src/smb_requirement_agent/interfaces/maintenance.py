"""Explicit offline maintenance entry point; never starts workers or provider clients."""

import argparse

from smb_requirement_agent.infrastructure.config.options import PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import PersistenceSettings
from smb_requirement_agent.interfaces.api.composition.operations import build_projection_rebuild


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild derived activity and worklist projections."
    )
    parser.parse_args()
    settings = PersistenceSettings.from_env()
    if settings.provider is not PersistenceProvider.POSTGRES or settings.database_url is None:
        parser.error("Projection maintenance requires PostgreSQL persistence and DATABASE_URL.")
    count = build_projection_rebuild(settings.database_url)()
    print(f"Rebuilt activity and worklist projections for {count} Requirements.")


if __name__ == "__main__":
    main()
