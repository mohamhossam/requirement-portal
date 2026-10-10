"""Shutdown and lease-heartbeat behavior for in-process AI workers.

A heartbeat rides out a brief database failure while the lease lasts, then stops renewing
without restarting the process under the attempt (production hardening PR 10)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import timedelta
from typing import cast

from smb_kernel.observability.metrics import Metrics
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.jobs.application.ports.ai_jobs import (
    AiJobCommand,
    AiJobQueuePort,
    AiJobRecord,
)
from smb_requirement_agent.workflows.application.use_cases.ai_job_execution import ExecuteAiJob
from smb_requirement_agent.workflows.infrastructure.polling_worker import (
    AiJobWorkerGroup,
    PollingAiJobWorker,
)
from tests.unit.jobs.test_ai_jobs import NOW, _job


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


class FlakyQueue(RecordingQueue):
    """Renewals fail with `failures` errors first, then answer `renewed`."""

    def __init__(self, record: AiJobRecord, *, failures: int, renewed: bool = True) -> None:
        super().__init__(record)
        self.failures = failures
        self.renewed = renewed

    def heartbeat(self, *args: object) -> bool:
        del args
        self.heartbeats += 1
        if self.heartbeats <= self.failures:
            raise ConnectionError("database restarting")
        return self.renewed


def _running(lease: timedelta) -> AiJobRecord:
    return AiJobRecord(
        _job().claim(NOW),
        command=AiJobCommand({}),
        worker_id="claimed-by-store",
        attempt_token="attempt-1",
        lease_until=NOW + lease,
    )


def _worker(queue: RecordingQueue, executor: BlockingExecutor) -> PollingAiJobWorker:
    return PollingAiJobWorker(
        cast(AiJobQueuePort, queue),
        cast(ExecuteAiJob, executor),
        FixedClock(NOW),
        Metrics(),
        poll_interval_seconds=0.01,
        lease_seconds=30,
        heartbeat_seconds=0.01,
        shutdown_grace_seconds=1,
    )


def _until(condition: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + 2
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return condition()


def test_a_heartbeat_that_fails_while_the_lease_lasts_is_tried_again() -> None:
    queue = FlakyQueue(_running(timedelta(seconds=30)), failures=3)
    executor = BlockingExecutor()
    worker = _worker(queue, executor)
    worker.start()
    try:
        assert executor.started.wait(timeout=1)
        assert _until(lambda: queue.heartbeats > 5)
        assert not worker.lease_lost
        assert worker.healthy
    finally:
        executor.finish.set()
        worker.stop()


def test_a_lease_about_to_lapse_stops_renewing_but_lets_the_attempt_finish() -> None:
    queue = FlakyQueue(_running(timedelta(milliseconds=5)), failures=1_000)
    executor = BlockingExecutor()
    worker = _worker(queue, executor)
    worker.start()
    try:
        assert executor.started.wait(timeout=1)
        assert _until(lambda: worker.lease_lost)
        attempts = queue.heartbeats
        time.sleep(0.05)
        # Renewing has stopped, and the process is not restarted under the running attempt.
        assert queue.heartbeats == attempts
        assert worker.healthy
    finally:
        executor.finish.set()
        worker.stop()
    assert queue.released == 1


def test_a_lease_another_worker_took_back_stops_renewing_at_once() -> None:
    queue = FlakyQueue(_running(timedelta(seconds=30)), failures=0, renewed=False)
    executor = BlockingExecutor()
    worker = _worker(queue, executor)
    worker.start()
    try:
        assert executor.started.wait(timeout=1)
        assert _until(lambda: worker.lease_lost)
        time.sleep(0.05)
        assert queue.heartbeats == 1
    finally:
        executor.finish.set()
        worker.stop()
