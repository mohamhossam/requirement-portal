"""The daily token budget: counted from responses, refusing new work, pausing the queue."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.infrastructure.llm.spend_transport import SpendCountingTransport
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.jobs.application.errors import ProviderBudgetExhaustedError
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobRecord
from smb_requirement_agent.jobs.application.use_cases.provider_call_rate import (
    ProviderSpendBudget,
)
from smb_requirement_agent.jobs.domain.entities import AiJobId, AiJobOperation
from smb_requirement_agent.jobs.infrastructure.in_memory_provider_calls import (
    InMemoryProviderSpend,
)
from smb_requirement_agent.jobs.infrastructure.spend_gate import SpendGatedQueue
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.job_driver import start_job

EVENING = datetime(2026, 10, 9, 22, 30, tzinfo=UTC)
OWNER = {"X-Fake-Actor-Id": "fake-owner"}


class Clock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


def test_the_budget_is_spent_by_reported_tokens_and_resets_with_the_utc_day() -> None:
    clock = Clock(EVENING)
    budget = ProviderSpendBudget(1_000, clock, InMemoryProviderSpend())

    budget.record(999)
    assert not budget.exhausted()
    budget.record(1)
    assert budget.exhausted()
    with pytest.raises(ProviderBudgetExhaustedError) as refused:
        budget.require_available()
    # 22:30 UTC: the next day starts in an hour and a half.
    assert refused.value.retry_after_seconds == 90 * 60
    assert "00:00 UTC" in str(refused.value)

    clock.current += timedelta(hours=2)
    assert not budget.exhausted()
    budget.require_available()


def test_a_zero_budget_records_spend_without_limiting_it() -> None:
    spend = InMemoryProviderSpend()
    budget = ProviderSpendBudget(0, Clock(EVENING), spend)

    budget.record(10_000_000)

    assert not budget.exhausted()
    assert spend.spent(EVENING.date()) == 10_000_000


def test_a_negative_budget_is_rejected() -> None:
    with pytest.raises(ValueError):
        ProviderSpendBudget(-1, Clock(EVENING), InMemoryProviderSpend())


def _response(status: int, body: object) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status, content=json.dumps(body)))


def test_every_successful_model_response_counts_its_reported_tokens() -> None:
    recorded: list[int] = []
    usage = {"model": "m", "usage": {"prompt_tokens": 120, "completion_tokens": 30}}
    with httpx.Client(
        transport=SpendCountingTransport(recorded.append, _response(200, usage))
    ) as client:
        response = client.post("https://models.example/v1/chat/completions")

    assert response.json() == usage
    assert recorded == [150]


def test_a_failed_or_unmetered_response_counts_nothing() -> None:
    recorded: list[int] = []
    for transport in (
        _response(429, {"usage": {"prompt_tokens": 5}}),
        _response(200, {"choices": []}),
    ):
        with httpx.Client(transport=SpendCountingTransport(recorded.append, transport)) as client:
            client.post("https://models.example/v1/chat/completions")

    assert recorded == []


def test_failing_to_record_spend_never_fails_the_model_call() -> None:
    def broken(tokens: int) -> None:
        raise RuntimeError("database down")

    usage = {"usage": {"prompt_tokens": 1}}
    with httpx.Client(transport=SpendCountingTransport(broken, _response(200, usage))) as client:
        assert client.post("https://models.example/v1/embeddings").status_code == 200


class _OneJobQueue:
    def __init__(self) -> None:
        self.claims = 0

    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_until: datetime,
        blocked_operations: tuple[AiJobOperation, ...] = (),
    ) -> AiJobRecord | None:
        self.claims += 1
        return None

    def heartbeat(
        self, job_id: AiJobId, worker_id: str, attempt_token: str, now: datetime, until: datetime
    ) -> bool:
        return True

    def release(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> None:
        return None

    def fence_attempt(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> bool:
        return True


def test_workers_claim_nothing_while_the_budget_is_spent() -> None:
    clock = Clock(EVENING)
    budget = ProviderSpendBudget(100, clock, InMemoryProviderSpend())
    queue = _OneJobQueue()
    gated = SpendGatedQueue(queue, budget)

    gated.claim_next("w", EVENING, EVENING)
    budget.record(100)
    gated.claim_next("w", EVENING, EVENING)

    assert queue.claims == 1
    clock.current += timedelta(hours=2)
    gated.claim_next("w", clock.current, clock.current)
    assert queue.claims == 2


def test_a_spent_budget_refuses_new_ai_work_but_not_editing() -> None:
    container = build_container(replace(FAKE_PROVIDER_SETTINGS, provider_daily_token_budget=500))
    with TestClient(create_app(lambda: container)) as client:
        created = client.post(
            "/requirements",
            json={"title": "Budget", "description": "Spend stops new AI work."},
            headers=OWNER,
        )
        assert created.status_code == 201
        requirement_id = created.json()["id"]
        token = client.get(f"/requirements/{requirement_id}", headers=OWNER).json()[
            "analysis_context_token"
        ]
        container.provider_spend_budget.record(500)

        refused = start_job(
            client, requirement_id, "analyse_requirement", headers=OWNER, context_token=token
        )

        assert refused.status_code == 429
        assert refused.json()["code"] == "provider_budget_exhausted"
        assert 1 <= int(refused.headers["Retry-After"]) <= 24 * 3600
        changed = client.put(
            f"/requirements/{requirement_id}",
            json={
                "title": "Budget, revised",
                "description": "Spend stops new AI work.",
                "expected_version": created.json()["version"],
                "impact_acknowledged": True,
            },
            headers=OWNER,
        )
        assert changed.status_code == 200, changed.text
