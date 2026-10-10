"""Queued AI jobs wait, never fail, while the day's token budget is spent (ADR-0106)."""

from __future__ import annotations

from datetime import datetime

from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobQueuePort, AiJobRecord
from smb_requirement_agent.jobs.application.use_cases.provider_call_rate import (
    ProviderSpendBudget,
)
from smb_requirement_agent.jobs.domain.entities import AiJobId, AiJobOperation


class SpendGatedQueue:
    """Claims nothing while the budget is spent; the jobs run after the UTC day turns."""

    def __init__(self, queue: AiJobQueuePort, budget: ProviderSpendBudget) -> None:
        self._queue = queue
        self._budget = budget

    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_until: datetime,
        blocked_operations: tuple[AiJobOperation, ...] = (),
    ) -> AiJobRecord | None:
        if not self._budget.admits_claim():
            return None
        return self._queue.claim_next(worker_id, now, lease_until, blocked_operations)

    def heartbeat(
        self,
        job_id: AiJobId,
        worker_id: str,
        attempt_token: str,
        now: datetime,
        lease_until: datetime,
    ) -> bool:
        return self._queue.heartbeat(job_id, worker_id, attempt_token, now, lease_until)

    def release(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> None:
        self._queue.release(job_id, worker_id, attempt_token)

    def fence_attempt(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> bool:
        return self._queue.fence_attempt(job_id, worker_id, attempt_token)
