"""Retention: read notifications are deleted, finished jobs' inputs are cleared.

AI job rows are never deleted (they are the activity feed's record), and unread
notifications are kept until they are read (ADR-0079). The PostgreSQL delete
runs in `tests/integration/test_postgres_bounded_lists.py`, the job pruning and
blob report in `tests/integration/test_postgres_retention.py`.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from threading import RLock
from types import SimpleNamespace
from typing import cast

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.infrastructure.config.options import (
    DEFAULT_AI_JOB_PAYLOAD_RETENTION_DAYS,
    DEFAULT_NOTIFICATION_RETENTION_DAYS,
    ConfigurationError,
)
from smb_requirement_agent.infrastructure.config.settings import RetentionSettings
from smb_requirement_agent.interfaces import retention
from smb_requirement_agent.interfaces.api.composition.operations import Retention
from smb_requirement_agent.jobs.application.use_cases.retention import (
    PAYLOAD_PRUNE_BATCH,
    PruneFinishedJobPayloads,
    PruneReadNotifications,
)
from smb_requirement_agent.jobs.domain.entities import (
    ActorNotification,
    AiJobId,
    NotificationId,
    NotificationKind,
)
from smb_requirement_agent.jobs.infrastructure.in_memory_ai_jobs import (
    InMemoryAiJobStore,
    InMemoryNotificationRepository,
)
from smb_requirement_agent.requirements.infrastructure.postgres_blob_report import (
    DocumentBlobUsage,
)
from smb_requirement_agent.shared_kernel.actors import ActorId

NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)
OWNER = ActorId("fake-owner")


def _note(name: str, read_days_ago: int | None) -> ActorNotification:
    read_at = None if read_days_ago is None else NOW - timedelta(days=read_days_ago)
    return ActorNotification(
        NotificationId(name),
        OWNER,
        AiJobId("job-1"),
        NotificationKind.AI_JOB_SUCCEEDED,
        "Done.",
        NOW - timedelta(days=400),
        read_at=read_at,
    )


def test_only_notifications_read_before_the_period_are_deleted() -> None:
    repository = InMemoryNotificationRepository(InMemoryAiJobStore(RLock()))
    for item in (
        _note("old-read", 91),
        _note("recent-read", 89),
        _note("old-unread", None),
    ):
        repository.add(item)

    deleted = PruneReadNotifications(repository, FixedClock(NOW)).execute(timedelta(days=90))

    assert deleted == 1
    assert {item.id.value for item in repository.list_for_actor(OWNER)} == {
        "recent-read",
        "old-unread",
    }


def test_a_non_positive_period_is_refused() -> None:
    repository = InMemoryNotificationRepository(InMemoryAiJobStore(RLock()))

    with pytest.raises(ValueError, match="positive"):
        PruneReadNotifications(repository, FixedClock(NOW)).execute(timedelta(0))


class _Jobs:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, int]] = []

    def prune_finished_inputs(self, completed_before: datetime, batch_size: int) -> int:
        self.calls.append((completed_before, batch_size))
        return 3


def test_job_inputs_are_cleared_for_jobs_finished_before_the_period() -> None:
    jobs = _Jobs()

    pruned = PruneFinishedJobPayloads(jobs, FixedClock(NOW)).execute(timedelta(days=90))

    assert pruned == 3
    assert jobs.calls == [(NOW - timedelta(days=90), PAYLOAD_PRUNE_BATCH)]
    with pytest.raises(ValueError, match="positive"):
        PruneFinishedJobPayloads(jobs, FixedClock(NOW)).execute(timedelta(0))


@pytest.mark.parametrize(
    ("name", "field", "default"),
    [
        (
            "NOTIFICATION_RETENTION_DAYS",
            "notification_retention_days",
            DEFAULT_NOTIFICATION_RETENTION_DAYS,
        ),
        (
            "AI_JOB_PAYLOAD_RETENTION_DAYS",
            "ai_job_payload_retention_days",
            DEFAULT_AI_JOB_PAYLOAD_RETENTION_DAYS,
        ),
    ],
)
def test_retention_settings_default_and_validate(
    monkeypatch: pytest.MonkeyPatch, name: str, field: str, default: int
) -> None:
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "memory")
    monkeypatch.setenv(name, "")
    assert getattr(RetentionSettings.from_env(), field) == default
    monkeypatch.setenv(name, "7")
    assert getattr(RetentionSettings.from_env(), field) == 7
    for raw in ("0", "-5", "soon"):
        monkeypatch.setenv(name, raw)
        with pytest.raises(ConfigurationError, match=name):
            RetentionSettings.from_env()


def test_the_command_refuses_memory_persistence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["retention"])
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "memory")
    monkeypatch.setattr(retention, "build_retention", _unexpected)

    with pytest.raises(SystemExit) as exited:
        retention.main()

    assert exited.value.code == 2
    assert "requires PostgreSQL" in capsys.readouterr().err


def test_the_command_prunes_with_the_configured_periods_and_reports_blobs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["retention"])
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://retention@db/app")
    monkeypatch.setenv("NOTIFICATION_RETENTION_DAYS", "30")
    monkeypatch.setenv("AI_JOB_PAYLOAD_RETENTION_DAYS", "60")
    periods: list[tuple[str, timedelta]] = []

    class _Prune:
        def __init__(self, name: str, count: int) -> None:
            self._name = name
            self._count = count

        def execute(self, period: timedelta) -> int:
            periods.append((self._name, period))
            return self._count

    class _Blobs:
        def usage(self) -> DocumentBlobUsage:
            return DocumentBlobUsage(10, 5000, 1, 200)

    def build(database_url: str) -> Retention:
        assert database_url == "postgresql://retention@db/app"
        return cast(
            Retention,
            SimpleNamespace(
                notifications=_Prune("notifications", 4),
                job_payloads=_Prune("jobs", 2),
                blobs=_Blobs(),
            ),
        )

    monkeypatch.setattr(retention, "build_retention", build)

    retention.main()

    assert periods == [("notifications", timedelta(days=30)), ("jobs", timedelta(days=60))]
    assert capsys.readouterr().out.strip().splitlines() == [
        "Deleted 4 notifications read more than 30 days ago.",
        "Cleared the inputs of 2 AI jobs finished more than 60 days ago.",
        "Document blobs: 10 (5000 bytes); 1 referenced by no document or upload (200 bytes). "
        "Nothing was deleted.",
    ]


def _unexpected(database_url: str) -> object:
    raise AssertionError("A refused run must not build the retention path.")
