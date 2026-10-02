"""Online retention command: prunes read notifications (ADR-0079).

Unlike `maintenance`, this is safe to run while the API and workers serve
traffic. Schedule it, for example daily from cron, or with the `retention`
compose profile.
"""

import argparse
from datetime import timedelta

from smb_requirement_agent.infrastructure.config.options import PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import RetentionSettings
from smb_requirement_agent.interfaces.api.composition.operations import (
    build_notification_retention,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete notifications read longer ago than NOTIFICATION_RETENTION_DAYS."
    )
    parser.parse_args()
    settings = RetentionSettings.from_env()
    persistence = settings.persistence
    if persistence.provider is not PersistenceProvider.POSTGRES or persistence.database_url is None:
        parser.error("Retention requires PostgreSQL persistence and DATABASE_URL.")
    days = settings.notification_retention_days
    count = build_notification_retention(persistence.database_url).execute(timedelta(days=days))
    print(f"Deleted {count} notifications read more than {days} days ago.")


if __name__ == "__main__":
    main()
