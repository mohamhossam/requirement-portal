"""Read notifications are pruned after the retention period; nothing else is.

AI jobs are never pruned (they are the activity feed's record), and unread
notifications are kept until they are read (ADR-0079). The PostgreSQL delete
runs in `tests/integration/test_postgres_bounded_lists.py`.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from threading import RLock

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.use_cases.retention import PruneReadNotifications
from smb_requirement_agent.domain.jobs.entities import (
    ActorNotification,
    AiJobId,
    NotificationId,
    NotificationKind,
)
from smb_requirement_agent.infrastructure.config.options import (
    DEFAULT_NOTIFICATION_RETENTION_DAYS,
    ConfigurationError,
)
from smb_requirement_agent.infrastructure.config.settings import RetentionSettings
from smb_requirement_agent.infrastructure.persistence.in_memory_ai_jobs import (
    InMemoryAiJobStore,
    InMemoryNotificationRepository,
)
from smb_requirement_agent.interfaces import retention
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


def test_retention_settings_default_and_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "memory")
    monkeypatch.setenv("NOTIFICATION_RETENTION_DAYS", "")
    assert RetentionSettings.from_env().notification_retention_days == (
        DEFAULT_NOTIFICATION_RETENTION_DAYS
    )
    for raw in ("0", "-5", "soon"):
        monkeypatch.setenv("NOTIFICATION_RETENTION_DAYS", raw)
        with pytest.raises(ConfigurationError, match="NOTIFICATION_RETENTION_DAYS"):
            RetentionSettings.from_env()


def test_the_command_refuses_memory_persistence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["retention"])
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "memory")
    monkeypatch.setattr(retention, "build_notification_retention", _unexpected)

    with pytest.raises(SystemExit) as exited:
        retention.main()

    assert exited.value.code == 2
    assert "requires PostgreSQL" in capsys.readouterr().err


def test_the_command_prunes_with_the_configured_period(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["retention"])
    monkeypatch.setenv("PERSISTENCE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://retention@db/app")
    monkeypatch.setenv("NOTIFICATION_RETENTION_DAYS", "30")
    periods: list[timedelta] = []

    class _Prune:
        def execute(self, period: timedelta) -> int:
            periods.append(period)
            return 4

    def build(database_url: str) -> _Prune:
        assert database_url == "postgresql://retention@db/app"
        return _Prune()

    monkeypatch.setattr(retention, "build_notification_retention", build)

    retention.main()

    assert periods == [timedelta(days=30)]
    assert capsys.readouterr().out.strip() == (
        "Deleted 4 notifications read more than 30 days ago."
    )


def _unexpected(database_url: str) -> object:
    raise AssertionError("A refused run must not build the retention path.")
