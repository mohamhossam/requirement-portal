"""Lease-based in-process worker safe across PostgreSQL-backed API replicas."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import timedelta
from time import monotonic, perf_counter

from smb_kernel.observability.correlation import correlation_scope
from smb_kernel.observability.metrics import Metrics
from smb_kernel.observability.tracing_setup import Tracing
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.infrastructure.log_safety import exception_types
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobQueuePort, AiJobRecord
from smb_requirement_agent.jobs.domain.entities import AiJob, AiJobStatus
from smb_requirement_agent.workflows.application.use_cases.ai_job_execution import ExecuteAiJob

logger = logging.getLogger("smb_requirement_agent.ai_jobs.worker")


class PollingAiJobWorker:
    def __init__(
        self,
        queue: AiJobQueuePort,
        executor: ExecuteAiJob,
        clock: ClockPort,
        metrics: Metrics,
        tracing: Tracing,
        *,
        poll_interval_seconds: float,
        lease_seconds: float,
        heartbeat_seconds: float,
        shutdown_grace_seconds: float,
    ) -> None:
        self._queue = queue
        self._executor = executor
        self._clock = clock
        self._metrics = metrics
        self._tracing = tracing
        self._poll_interval = poll_interval_seconds
        self._lease_seconds = lease_seconds
        self._heartbeat_seconds = heartbeat_seconds
        self._shutdown_grace_seconds = shutdown_grace_seconds
        self._worker_id = str(uuid.uuid4())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_lock = threading.Lock()
        self._active: AiJobRecord | None = None
        self._last_healthy = monotonic()
        self._lease_lost = threading.Event()

    @property
    def healthy(self) -> bool:
        """Alive, and either running an attempt or claiming within a lease's time.

        An attempt under way keeps the worker healthy even while its heartbeat fails,
        so the process is not restarted under a provider call: provider and database
        calls are bounded by their own timeouts, so the attempt always returns.
        """
        if not (self._thread and self._thread.is_alive() and not self._stop.is_set()):
            return False
        with self._active_lock:
            busy = self._active is not None
        return busy or monotonic() - self._last_healthy < self._lease_seconds

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        thread = threading.Thread(
            target=self._run,
            name=f"ai-job-worker-{self._worker_id[:8]}",
            daemon=True,
        )
        thread.start()
        self._thread = thread

    @property
    def shutdown_grace_seconds(self) -> float:
        return self._shutdown_grace_seconds

    def stop(self) -> bool:
        self.request_stop()
        drained = self.join(self._shutdown_grace_seconds)
        if not drained:
            self.fence_active()
        return drained

    def request_stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> bool:
        if self._thread is None:
            return True
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    def fence_active(self) -> None:
        with self._active_lock:
            active = self._active
        if active is not None and active.attempt_token is not None:
            self._queue.fence_attempt(active.job.id, self._worker_id, active.attempt_token)

    def wait_until_stopped(self) -> None:
        self.join()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                now = self._clock.now()
                record = self._queue.claim_next(
                    self._worker_id,
                    now,
                    now + timedelta(seconds=self._lease_seconds),
                )
                self._last_healthy = monotonic()
                if record is None:
                    self._stop.wait(self._poll_interval)
                    continue
                self._execute(record)
            except Exception:
                logger.exception("AI job worker polling failed")
                self._stop.wait(self._poll_interval)

    @property
    def lease_lost(self) -> bool:
        """Whether the attempt under way, or the last one, stopped holding its lease."""
        return self._lease_lost.is_set()

    def _execute(self, record: AiJobRecord) -> None:
        self._lease_lost.clear()
        with self._active_lock:
            self._active = record
        heartbeat_stop = threading.Event()

        def heartbeat() -> None:
            # A renewal that fails is tried again while the lease still has time; once
            # the next try would come too late, or the lease was taken back, renewing
            # stops. The attempt runs on: a provider call under way finishes, and the
            # fenced writes refuse its result if another worker has claimed the job.
            held_until = record.lease_until
            while not heartbeat_stop.wait(self._heartbeat_seconds):
                now = self._clock.now()
                until = now + timedelta(seconds=self._lease_seconds)
                try:
                    renewed = self._queue.heartbeat(
                        record.job.id, self._worker_id, record.attempt_token or "", now, until
                    )
                except Exception as exc:
                    next_try = now + timedelta(seconds=self._heartbeat_seconds)
                    if held_until is not None and next_try < held_until:
                        logger.warning(
                            "AI job heartbeat failed with %s; trying again while the lease "
                            "lasts [job_id=%s]",
                            exception_types(exc),
                            record.job.id.value,
                        )
                        continue
                    self._lose_lease(record, f"its renewal failed with {exception_types(exc)}")
                    return
                if not renewed:
                    self._lose_lease(record, "another worker holds it now")
                    return
                held_until = until
                self._last_healthy = monotonic()

        heartbeat_thread = threading.Thread(
            target=heartbeat,
            name=f"ai-job-heartbeat-{record.job.id.value[:8]}",
            daemon=True,
        )
        heartbeat_thread.start()
        operation = record.job.operation.value
        started = perf_counter()
        status = "error"
        try:
            # One trace per attempt, holding its SQL and provider calls (ADR-0110).
            with (
                correlation_scope(f"job:{record.job.id.value}"),
                self._tracing.span(
                    f"ai_job {operation}",
                    {
                        "ai_job.id": record.job.id.value,
                        "ai_job.operation": operation,
                        "ai_job.attempt": record.job.attempt_count,
                    },
                ),
            ):
                status = metric_status(self._executor.execute(record))
        finally:
            elapsed = perf_counter() - started
            self._metrics.record_job(operation, status, elapsed)
            logger.info(
                "AI job attempt finished",
                extra={
                    "job_id": record.job.id.value,
                    "operation": operation,
                    "status": status,
                    "duration_ms": round(elapsed * 1000, 1),
                },
            )
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=max(1.0, self._heartbeat_seconds))
            self._queue.release(
                record.job.id,
                self._worker_id,
                record.attempt_token or "",
            )
            with self._active_lock:
                self._active = None

    def _lose_lease(self, record: AiJobRecord, reason: str) -> None:
        self._lease_lost.set()
        logger.error(
            "AI job lease lost: %s; the attempt finishes, and its result is kept only if "
            "no other worker claimed the job [job_id=%s]",
            reason,
            record.job.id.value,
        )


class AiJobWorkerGroup:
    def __init__(self, workers: tuple[PollingAiJobWorker, ...]) -> None:
        self._workers = workers

    def start(self) -> None:
        for worker in self._workers:
            worker.start()

    @property
    def healthy(self) -> bool:
        return all(worker.healthy for worker in self._workers)

    def stop(self) -> bool:
        for worker in self._workers:
            worker.request_stop()
        deadline = monotonic() + max(
            (worker.shutdown_grace_seconds for worker in self._workers), default=0.0
        )
        unfinished: list[PollingAiJobWorker] = []
        for worker in self._workers:
            if not worker.join(max(0.0, deadline - monotonic())):
                unfinished.append(worker)
        for worker in unfinished:
            worker.fence_active()
        return not unfinished

    def wait_until_stopped(self) -> None:
        for worker in self._workers:
            worker.wait_until_stopped()


def metric_status(job: AiJob) -> str:
    """The attempt's outcome as `smb_ai_jobs_total` labels it.

    A requeued attempt is `retrying`, and a job failed at the attempt cap is
    `attempts_exhausted`, so alerts can tell them from an ordinary failure.
    """
    if job.status is AiJobStatus.QUEUED and job.next_attempt_at is not None:
        return "retrying"
    if job.failure is not None and job.failure.code == "attempts_exhausted":
        return "attempts_exhausted"
    return job.status.value
