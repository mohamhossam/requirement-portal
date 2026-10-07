"""The per-actor provider call ceiling, in isolation and through the API."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.errors import ProviderRateLimitExceededError
from smb_requirement_agent.application.use_cases.provider_call_rate import ProviderCallRateLimit
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from tests.conftest import FAKE_PROVIDER_SETTINGS

START = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
ALICE = ActorProfile(ActorId("alice"), "Alice")
BOB = ActorProfile(ActorId("bob"), "Bob")


class SteppingClock:
    def __init__(self) -> None:
        self.current = START

    def now(self) -> datetime:
        return self.current


def test_refuses_the_call_after_the_limit_with_a_retry_delay() -> None:
    clock = SteppingClock()
    limit = ProviderCallRateLimit(2, clock)
    limit.acquire(ALICE)
    clock.current += timedelta(seconds=20)
    limit.acquire(ALICE)

    with pytest.raises(ProviderRateLimitExceededError) as refused:
        limit.acquire(ALICE)

    # The oldest call leaves the window 40 seconds from now.
    assert refused.value.retry_after_seconds == 40
    assert "at most 2 per minute" in str(refused.value)


def test_the_window_slides_so_old_calls_stop_counting() -> None:
    clock = SteppingClock()
    limit = ProviderCallRateLimit(1, clock)
    limit.acquire(ALICE)

    clock.current += timedelta(seconds=60)

    limit.acquire(ALICE)


def test_each_actor_has_their_own_budget() -> None:
    limit = ProviderCallRateLimit(1, SteppingClock())
    limit.acquire(ALICE)

    limit.acquire(BOB)
    with pytest.raises(ProviderRateLimitExceededError):
        limit.acquire(ALICE)


def test_zero_disables_the_limit() -> None:
    limit = ProviderCallRateLimit(0, SteppingClock())

    for _ in range(1000):
        limit.acquire(ALICE)


def test_a_negative_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        ProviderCallRateLimit(-1, SteppingClock())


def test_the_api_answers_429_with_retry_after_once_an_actor_is_over_budget() -> None:
    container = build_container(replace(FAKE_PROVIDER_SETTINGS, provider_rate_limit_per_minute=2))
    owner = {"X-Fake-Actor-Id": "fake-owner"}
    reviewer = {"X-Fake-Actor-Id": "fake-reviewer"}
    with TestClient(create_app(lambda: container)) as client:
        query = {"query": "eligibility"}
        for _ in range(2):
            assert (
                client.post("/knowledge/search/unified", json=query, headers=owner).status_code
                == 200
            )

        refused = client.post("/knowledge/search/unified", json=query, headers=owner)

        assert refused.status_code == 429
        assert refused.json()["code"] == "provider_rate_limited"
        assert 1 <= int(refused.headers["Retry-After"]) <= 60
        # Another actor is unaffected, and reads that call no provider are never counted.
        assert (
            client.post("/knowledge/search/unified", json=query, headers=reviewer).status_code
            == 200
        )
        assert client.get("/requirements", headers=owner).status_code == 200


def test_creating_a_requirement_is_charged_because_it_queues_automatic_screening() -> None:
    container = build_container(replace(FAKE_PROVIDER_SETTINGS, provider_rate_limit_per_minute=1))
    owner = {"X-Fake-Actor-Id": "fake-owner"}
    body = {"title": "Coverage", "description": "Coverage required."}
    with TestClient(create_app(lambda: container)) as client:
        assert client.post("/requirements", json=body, headers=owner).status_code == 201

        refused = client.post("/requirements", json=body, headers=owner)

        assert refused.status_code == 429
        assert refused.json()["code"] == "provider_rate_limited"
        # Refused before the use case ran: no Requirement, so no screen was queued.
        assert len(container.requirement_repository.list_all()) == 1


def test_a_refunded_call_no_longer_counts() -> None:
    limit = ProviderCallRateLimit(1, SteppingClock())
    ticket = limit.acquire(ALICE)
    assert ticket is not None

    limit.refund(ticket)

    limit.acquire(ALICE)


def test_refunding_twice_returns_only_one_call() -> None:
    clock = SteppingClock()
    limit = ProviderCallRateLimit(2, clock)
    first = limit.acquire(ALICE)
    assert first is not None
    limit.acquire(ALICE)

    limit.refund(first)
    limit.refund(first)

    limit.acquire(ALICE)
    with pytest.raises(ProviderRateLimitExceededError):
        limit.acquire(ALICE)


def test_requests_refused_before_any_provider_call_are_refunded() -> None:
    container = build_container(replace(FAKE_PROVIDER_SETTINGS, provider_rate_limit_per_minute=1))
    owner = {"X-Fake-Actor-Id": "fake-owner"}
    with TestClient(create_app(lambda: container)) as client:
        # 422: the body fails validation. 404: the Requirement does not exist.
        assert client.post("/knowledge/search/unified", json={}, headers=owner).status_code == 422
        missing = client.post(
            "/requirements/no-such-id/analysis", json={"context_token": "x"}, headers=owner
        )
        assert missing.status_code == 404

        # Neither consumed the single call per minute.
        search = client.post("/knowledge/search/unified", json={"query": "q"}, headers=owner)
        assert search.status_code == 200
        refused = client.post("/knowledge/search/unified", json={"query": "q"}, headers=owner)
        assert refused.status_code == 429


def test_an_actor_emptied_by_a_refund_does_not_break_other_callers() -> None:
    limit = ProviderCallRateLimit(1, SteppingClock())
    ticket = limit.acquire(ALICE)
    assert ticket is not None
    limit.refund(ticket)

    limit.acquire(BOB)
    limit.acquire(ALICE)
