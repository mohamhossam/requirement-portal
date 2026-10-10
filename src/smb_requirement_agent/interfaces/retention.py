"""Online retention command (ADR-0079).

Deletes read notifications past their period, clears the stored inputs of
finished AI jobs past theirs, and reports document blob usage, orphans
included, without deleting any. Unlike `maintenance`, this is safe to run while
the API and workers serve traffic. Schedule it, for example daily from cron, or
with the `retention` compose profile.
"""

import argparse
from datetime import timedelta

from smb_requirement_agent.infrastructure.config.options import PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import RetentionSettings
from smb_requirement_agent.interfaces.api.composition.operations import build_retention


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Delete notifications read longer ago than NOTIFICATION_RETENTION_DAYS, clear the "
            "inputs of AI jobs finished longer ago than AI_JOB_PAYLOAD_RETENTION_DAYS, and "
            "report document blob usage."
        )
    )
    parser.parse_args()
    settings = RetentionSettings.from_env()
    persistence = settings.persistence
    if persistence.provider is not PersistenceProvider.POSTGRES or persistence.database_url is None:
        parser.error("Retention requires PostgreSQL persistence and DATABASE_URL.")
    retention = build_retention(persistence.database_url)
    days = settings.notification_retention_days
    count = retention.notifications.execute(timedelta(days=days))
    print(f"Deleted {count} notifications read more than {days} days ago.")
    days = settings.ai_job_payload_retention_days
    count = retention.job_payloads.execute(timedelta(days=days))
    print(f"Cleared the inputs of {count} AI jobs finished more than {days} days ago.")
    blobs = retention.blobs.usage()
    print(
        f"Document blobs: {blobs.count} ({blobs.size_bytes} bytes); "
        f"{blobs.orphan_count} referenced by no document or upload "
        f"({blobs.orphan_size_bytes} bytes). Nothing was deleted."
    )


if __name__ == "__main__":
    main()
