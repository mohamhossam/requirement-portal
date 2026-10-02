"""Shutdown and lease-heartbeat behavior for in-process AI workers."""

from __future__ import annotations

import threading
from datetime import timedelta
from typing import cast

from smb_kernel.observability.metrics import Metrics
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.ports.ai_jobs import (
    AiJobCommand,
    AiJobQueuePort,
    AiJobRecord,
)
from smb_requirement_agent.application.use_cases.ai_job_execution import ExecuteAiJob
from smb_requirement_agent.infrastructure.jobs.polling_worker import (
    AiJobWorkerGroup,
    PollingAiJobWorker,
)
from tests.unit.test_ai_jobs import NOW, _job


class BlockingExecutor:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.finish = threading.Event()

    def execute(self, record: AiJobRecord) -> object:
        del record
        self.started.set()
        self.finish.wait(timeout=2)
        return None


class RecordingQueue:
    def __init__(self, record: AiJobRecord) -> None:
        self.record = record
        self.claimed = False
        self.heartbeats = 0
        self.fenced = 0
        self.released = 0

    def claim_next(self, worker_id: str, now: object, lease_until: object) -> AiJobRecord | None:
        del worker_id, now, lease_until
        if self.claimed:
            return None
        self.claimed = True
        return self.record

    def heartbeat(self, *args: object) -> bool:
        del args
        self.heartbeats += 1
        return True

    def release(self, *args: object) -> None:
        del args
        self.released += 1

    def fence_attempt(self, *args: object) -> bool:
        del args
        self.fenced += 1
        return True


def test_shutdown_keeps_heartbeats_running_then_fences_at_grace_deadline() -> None:
    running = _job().claim(NOW)
    record = AiJobRecord(
        running,
        command=AiJobCommand({}),
        worker_id="claimed-by-store",
        attempt_token="attempt-1",
        lease_until=NOW + timedelta(seconds=30),
    )
    queue = RecordingQueue(record)
    executor = BlockingExecutor()
    worker = PollingAiJobWorker(
        cast(AiJobQueuePort, queue),
        cast(ExecuteAiJob, executor),
        FixedClock(NOW),
        Metrics(),
        poll_interval_seconds=0.01,
        lease_seconds=30,
        heartbeat_seconds=0.01,
        shutdown_grace_seconds=0.05,
    )
    worker.start()
    assert executor.started.wait(timeout=1)

    assert worker.stop() is False
    assert queue.heartbeats > 0
    assert queue.fenced == 1

    executor.finish.set()
    worker.wait_until_stopped()
    assert queue.released == 1


class GroupWorker:
    shutdown_grace_seconds = 0.05

    def __init__(self, *, drains: bool) -> None:
        self.drains = drains
        self.requested = False
        self.join_timeouts: list[float | None] = []
        self.fenced = 0

    def request_stop(self) -> None:
        self.requested = True

    def join(self, timeout: float | None = None) -> bool:
        self.join_timeouts.append(timeout)
        return self.drains

    def fence_active(self) -> None:
        self.fenced += 1

    def wait_until_stopped(self) -> None:
        return None


def test_worker_group_uses_one_shared_shutdown_deadline() -> None:
    first = GroupWorker(drains=False)
    second = GroupWorker(drains=True)
    group = AiJobWorkerGroup(cast(tuple[PollingAiJobWorker, ...], (first, second)))

    assert group.stop() is False
    assert first.requested and second.requested
    assert first.join_timeouts[0] is not None
    assert second.join_timeouts[0] is not None
    assert second.join_timeouts[0] <= first.join_timeouts[0]
    assert first.fenced == 1
    assert second.fenced == 0
