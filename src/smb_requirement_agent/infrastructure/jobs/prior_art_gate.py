"""Hold prior-art jobs back while they are off or this hour's judge calls are spent."""

from __future__ import annotations

from datetime import datetime

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.ai_jobs import AiJobQueuePort, AiJobRecord
from smb_requirement_agent.application.ports.prior_art import PriorArtBudgetPort
from smb_requirement_agent.domain.jobs.entities import AiJobId, AiJobOperation


class PriorArtGatedQueue:
    """Prior-art jobs stay queued, never failed, until a judge call is free (ADR-0102)."""

    def __init__(
        self,
        queue: AiJobQueuePort,
        budget: PriorArtBudgetPort,
        clock: ClockPort,
        *,
        enabled: bool,
        hourly: int,
    ) -> None:
        self._queue = queue
        self._budget = budget
        self._clock = clock
        self._enabled = enabled
        self._hourly = hourly

    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_until: datetime,
        blocked_operations: tuple[AiJobOperation, ...] = (),
    ) -> AiJobRecord | None:
        blocked = blocked_operations
        if not self._enabled or self._budget.remaining(self._clock.now(), self._hourly) <= 0:
            blocked = (*blocked, AiJobOperation.SCREEN_PRIOR_ART)
        return self._queue.claim_next(worker_id, now, lease_until, blocked)

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
