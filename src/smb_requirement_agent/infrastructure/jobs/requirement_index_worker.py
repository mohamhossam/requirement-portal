"""Dedicated index worker plus non-blocking knowledge-job prerequisite gate."""

import logging
from datetime import datetime
from threading import Event, Thread

from smb_requirement_agent.application.ports.ai_jobs import AiJobQueuePort, AiJobRecord
from smb_requirement_agent.application.use_cases.requirement_indexing import (
    IndexRequirementKnowledge,
)
from smb_requirement_agent.domain.jobs.entities import AiJobId, AiJobOperation


class RequirementIndexWorker:
    def __init__(self, indexer: IndexRequirementKnowledge) -> None:
        self._indexer = indexer
        self._stop = Event()
        self._thread: Thread | None = None

    @property
    def healthy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self._stop.clear()
        self._thread = Thread(target=self._run, name="requirement-index", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._indexer.process_next():
                    continue
            except Exception as exc:
                logging.getLogger(__name__).error(
                    "Requirement index worker failed: %s", type(exc).__name__
                )
            self._stop.wait(0.25)

    def stop(self) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        return not self.healthy

    def wait_until_stopped(self) -> None:
        if self._thread is not None:
            self._thread.join()


class IndexReadyJobQueue:
    """Leave knowledge jobs queued while the independent index catches up."""

    def __init__(self, queue: AiJobQueuePort, indexer: IndexRequirementKnowledge) -> None:
        self._queue, self._indexer = queue, indexer

    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_until: datetime,
        blocked_operations: tuple[AiJobOperation, ...] = (),
    ) -> AiJobRecord | None:
        # Readiness is a point-in-time hint: a source can change after this check.
        # ExecuteAiJob defers, never fails, a gated job that then finds the index pending.
        blocked = blocked_operations
        if not self._indexer.ready():
            blocked = (
                *blocked,
                *(operation for operation in AiJobOperation if operation.requires_current_index),
            )
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
