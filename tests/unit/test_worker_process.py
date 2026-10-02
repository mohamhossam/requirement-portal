"""Background workers outside the HTTP lifecycle: architecture polling and the worker process."""

from __future__ import annotations

import signal
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from smb_kernel.observability.metrics import Metrics

from smb_requirement_agent.application.use_cases.architecture_jobs import ArchitectureJobs
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.jobs.architecture_job_worker import (
    ArchitectureJobWorker,
)
from smb_requirement_agent.interfaces import worker as worker_process


@dataclass(frozen=True)
class CompletedJob:
    id: str
    status: str


class QueuedJobs:
    """Hands out queued jobs, then reports an empty queue."""

    def __init__(self, count: int) -> None:
        self.remaining = count
        self.drained = threading.Event()
        self.failures = 0

    def claim_next(self) -> CompletedJob | None:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("database unavailable")
        if self.remaining == 0:
            self.drained.set()
            return None
        self.remaining -= 1
        return CompletedJob(f"job-{self.remaining}", "running")

    def renew_lease(self, job: CompletedJob) -> bool:
        return True

    def execute_claimed(self, job: CompletedJob) -> CompletedJob:
        return CompletedJob(job.id, "succeeded")


def _worker(jobs: QueuedJobs) -> ArchitectureJobWorker:
    return ArchitectureJobWorker(
        cast(ArchitectureJobs, jobs), poll_interval_seconds=0.01, shutdown_grace_seconds=1
    )


def test_architecture_worker_drains_the_queue_and_stops_cleanly() -> None:
    jobs = QueuedJobs(count=3)
    worker = _worker(jobs)
    assert worker.healthy is False

    worker.start()
    assert jobs.drained.wait(timeout=2)
    assert jobs.remaining == 0
    assert worker.healthy is True

    assert worker.stop() is True
    assert worker.healthy is False


def test_architecture_worker_survives_a_failed_poll() -> None:
    jobs = QueuedJobs(count=1)
    jobs.failures = 2
    worker = _worker(jobs)

    worker.start()
    try:
        assert jobs.drained.wait(timeout=2)
        assert worker.healthy is True
    finally:
        assert worker.stop() is True


def test_worker_process_refuses_memory_persistence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        Settings,
        "from_env",
        classmethod(lambda cls: Settings(llm_provider=LLMProvider.FAKE)),
    )
    monkeypatch.setattr(
        worker_process,
        "build_container",
        lambda settings: pytest.fail("No graph may be built for an unusable configuration."),
    )

    assert worker_process.main() == 2
    assert "PERSISTENCE_PROVIDER=postgres" in capsys.readouterr().err


class RecordingWorker:
    def __init__(self, events: list[str], name: str) -> None:
        self.events, self.name, self.healthy = events, name, True

    def start(self) -> None:
        self.events.append(f"start {self.name}")

    def stop(self) -> bool:
        self.events.append(f"stop {self.name}")
        return True

    def wait_until_stopped(self) -> None:
        return None


def _run_worker_process(
    monkeypatch: pytest.MonkeyPatch, workers: dict[str, RecordingWorker], events: list[str]
) -> int:
    postgres = Settings(
        llm_provider=LLMProvider.FAKE,
        persistence_provider=PersistenceProvider.POSTGRES,
        database_url="postgresql://example/test",
    )
    container = SimpleNamespace(
        background_workers=workers,
        settings=postgres,
        metrics=Metrics(),
        debug_trace=SimpleNamespace(record=lambda *args, **kwargs: None, close=lambda: None),
        close_resources=lambda: events.append("resources closed"),
    )
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: postgres))
    # Process-wide logging belongs to the real entrypoint, not to the test run.
    monkeypatch.setattr(worker_process, "configure_logging", lambda level, log_format: None)
    monkeypatch.setattr(worker_process, "build_container", lambda settings: cast(Any, container))
    monkeypatch.setattr(worker_process, "HEALTH_CHECK_INTERVAL_SECONDS", 0.01)
    return worker_process.main()


def test_worker_process_exits_for_restart_when_a_worker_turns_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    workers = {
        "workers": RecordingWorker(events, "ai"),
        "document_worker": RecordingWorker(events, "doc"),
    }
    workers["document_worker"].healthy = False

    assert _run_worker_process(monkeypatch, workers, events) == 1
    assert events == ["start ai", "start doc", "stop doc", "stop ai", "resources closed"]


def test_worker_process_stops_cleanly_on_termination_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    handlers: dict[int, Any] = {}
    monkeypatch.setattr(signal, "signal", lambda signum, h: handlers.setdefault(signum, h))

    class SignalledOnStart(RecordingWorker):
        def start(self) -> None:
            super().start()
            handlers[signal.SIGTERM](signal.SIGTERM, None)

    workers: dict[str, RecordingWorker] = {"workers": SignalledOnStart(events, "ai")}

    assert _run_worker_process(monkeypatch, workers, events) == 0
    assert set(handlers) == {signal.SIGINT, signal.SIGTERM}
    assert events == ["start ai", "stop ai", "resources closed"]
