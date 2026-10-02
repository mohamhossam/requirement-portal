"""The polled lists' bounds hold in PostgreSQL, not only in memory.

`limit` is a bound `LIMIT` parameter; None becomes `LIMIT NULL`, which
PostgreSQL treats as no limit. That is how the activity feed keeps every job.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from smb_requirement_agent.application.ports.ai_jobs import AiJobCommand, AiJobRecord
from smb_requirement_agent.domain.identity.entities import ActorId, ActorSnapshot
from smb_requirement_agent.domain.jobs.entities import (
    ActorNotification,
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobStatus,
    NotificationId,
    NotificationKind,
)
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementId,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_ai_jobs import (
    PostgresAiJobStore,
    PostgresNotificationRepository,
)
from tests.integration.postgres_fixture_store import FixturePostgresStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
START = datetime(2099, 1, 1, tzinfo=UTC)


class _NoWorklistProjection:
    def refresh(self, requirement_id: RequirementId) -> None:
        return None


def test_job_and_notification_lists_are_newest_first_and_bounded() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    store = FixturePostgresStore(DATABASE_URL, _NoWorklistProjection())
    requirement_id = RequirementId(str(uuid.uuid4()))
    store.add(
        Requirement(
            requirement_id,
            RequirementTitle("Bounded lists"),
            RequirementDescription("Newest first, bounded."),
            RequirementStatus.DRAFT,
        )
    )
    jobs = PostgresAiJobStore(store)
    notifications = PostgresNotificationRepository(store)
    recipient = ActorId(f"bounded-{uuid.uuid4()}")
    ids = []
    for minute in range(5):
        at = START + timedelta(minutes=minute)
        job = AiJob(
            AiJobId(f"bounded-{uuid.uuid4()}"),
            requirement_id,
            AiJobOperation.ANALYSE_REQUIREMENT,
            AiJobStatus.QUEUED,
            ActorSnapshot(recipient, "Owner"),
            at,
            at,
            f"bounded-{uuid.uuid4()}",
            f"bounded-{uuid.uuid4()}",
        )
        jobs.add(AiJobRecord(job, AiJobCommand({})))
        notifications.add(
            ActorNotification(
                NotificationId(f"bounded-{uuid.uuid4()}"),
                recipient,
                job.id,
                NotificationKind.AI_JOB_SUCCEEDED,
                "Done.",
                at,
            )
        )
        ids.append(job.id)

    newest = jobs.list_for_requirement(requirement_id, limit=2)
    assert [record.job.id for record in newest] == [ids[4], ids[3]]
    assert len(jobs.list_for_requirement(requirement_id)) == 5
    notes = notifications.list_for_actor(recipient, limit=3)
    assert [item.job_id for item in notes] == [ids[4], ids[3], ids[2]]
    assert len(notifications.list_for_actor(recipient)) == 5

    # Retention deletes only what was read before the cutoff.
    for item in notifications.list_for_actor(recipient)[:2]:
        notifications.save(item.mark_read(START + timedelta(days=1)))
    assert notifications.delete_read_before(START + timedelta(days=2)) == 2
    assert len(notifications.list_for_actor(recipient)) == 3
