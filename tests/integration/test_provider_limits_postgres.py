"""The provider call limit and token budget hold across processes, in PostgreSQL (ADR-0106).

Two limiters over one database stand in for two API replicas: together they admit
no more calls per minute than one would. The in-memory log has the same tests in
`tests/unit/jobs/test_provider_call_rate.py`.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from smb_kernel.persistence.connector import DirectPostgresConnector

from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.jobs.application.errors import ProviderRateLimitExceededError
from smb_requirement_agent.jobs.application.use_cases.provider_call_rate import (
    ProviderCallRateLimit,
)
from smb_requirement_agent.jobs.infrastructure.postgres_provider_calls import (
    PostgresProviderCallLog,
    PostgresProviderSpend,
)
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorProfile

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NOW = datetime.now(UTC)


class Clock:
    def __init__(self) -> None:
        self.current = NOW

    def now(self) -> datetime:
        return self.current


def _connector() -> DirectPostgresConnector:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    return DirectPostgresConnector(DATABASE_URL)


def _actor() -> ActorProfile:
    return ActorProfile(ActorId(f"limit-{uuid.uuid4()}"), "Replica tester")


def test_two_replicas_share_one_per_actor_window() -> None:
    connector = _connector()
    clock = Clock()
    first = ProviderCallRateLimit(2, clock, PostgresProviderCallLog(connector))
    second = ProviderCallRateLimit(2, clock, PostgresProviderCallLog(connector))
    actor = _actor()

    first.acquire(actor)
    clock.current += timedelta(seconds=20)
    second.acquire(actor)

    with pytest.raises(ProviderRateLimitExceededError) as refused:
        first.acquire(actor)
    assert refused.value.retry_after_seconds == 40
    # Another actor has their own window.
    second.acquire(_actor())

    clock.current += timedelta(seconds=40)
    first.acquire(actor)


def test_a_refund_on_one_replica_frees_the_call_for_another() -> None:
    connector = _connector()
    clock = Clock()
    first = ProviderCallRateLimit(1, clock, PostgresProviderCallLog(connector))
    second = ProviderCallRateLimit(1, clock, PostgresProviderCallLog(connector))
    actor = _actor()
    ticket = first.acquire(actor)
    assert ticket is not None

    first.refund(ticket)
    first.refund(ticket)

    second.acquire(actor)
    with pytest.raises(ProviderRateLimitExceededError):
        first.acquire(actor)


def test_token_spend_adds_up_per_day_across_writers() -> None:
    connector = _connector()
    day = date(1999, 1, 1) + timedelta(days=uuid.uuid4().int % 300)
    with connector.connection() as connection:
        connection.execute("DELETE FROM provider_token_spend WHERE day = %s", (day,))

    PostgresProviderSpend(connector).add(day, 120)
    PostgresProviderSpend(connector).add(day, 30)

    assert PostgresProviderSpend(connector).spent(day) == 150
    assert PostgresProviderSpend(connector).spent(day + timedelta(days=1)) == 0
