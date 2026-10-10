"""Background-worker lifecycle shared by the API process and the worker process."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from importlib.metadata import version

from smb_kernel.observability.metrics import serve_metrics

from smb_requirement_agent.interfaces.api.container import BackgroundWorker, Container

_LOGGER = logging.getLogger(__name__)
# The installed package's version, which a release tag must match (ADR-0108).
APPLICATION_VERSION = version("smb-requirement-agent")
SERVICE_NAME = "requirement-portal"
# How often each exporting process samples the AI job queue. Every process reports the
# same queue, so the alerts take the largest value (docs/operations/alerts.md).
QUEUE_SAMPLE_SECONDS = 15.0


def start_metrics(container: Container) -> Callable[[], None]:
    """Serve this process's metrics on METRICS_PORT; return how to stop serving them.

    While serving, the process samples the AI job queue every `QUEUE_SAMPLE_SECONDS`.
    """
    port = container.settings.metrics_port
    if port is None:
        return lambda: None
    container.metrics.set_build_info(SERVICE_NAME, APPLICATION_VERSION)
    stop_serving = serve_metrics(container.metrics, container.settings.metrics_host, port)
    _LOGGER.info("Metrics exporter listening on %s:%s", container.settings.metrics_host, port)
    stopping = threading.Event()
    sampler = threading.Thread(
        target=_sample_queue_until,
        args=(container, stopping),
        name="ai-job-queue-sampler",
        daemon=True,
    )
    sampler.start()

    def stop() -> None:
        stopping.set()
        sampler.join(timeout=5)
        stop_serving()

    return stop


def sample_queue(container: Container) -> None:
    """Record the AI job backlog: waiting jobs by operation, and how long the oldest has waited."""
    now = container.clock.now()
    backlog = container.ai_job_backlog.backlog(now)
    oldest = backlog.oldest_claimable_since
    waited = 0.0 if oldest is None else (now - oldest).total_seconds()
    container.metrics.set_ai_job_queue(backlog.queued, waited)


def _sample_queue_until(container: Container, stopping: threading.Event) -> None:
    failing = False
    while True:
        try:
            sample_queue(container)
            failing = False
        except Exception:  # A failed sample keeps the last values; it never stops the process.
            if not failing:
                _LOGGER.warning("Sampling the AI job queue failed; trying again", exc_info=True)
            failing = True
        if stopping.wait(QUEUE_SAMPLE_SECONDS):
            return


def start_workers(workers: Mapping[str, BackgroundWorker]) -> None:
    for worker in workers.values():
        worker.start()


def stop_workers_and_close(container: Container, workers: Mapping[str, BackgroundWorker]) -> None:
    """Stop every worker, then release shared resources once none can use them.

    A worker still inside provider or database I/O after its grace period keeps
    the pool and clients open on a background thread until it actually returns.
    """
    drained = True
    try:
        # Reverse start order: producers such as the index worker stop last.
        for name, worker in reversed(tuple(workers.items())):
            try:
                drained = worker.stop() and drained
            except Exception:
                # Keep stopping the others; treat this one as still running so
                # shared resources stay open until it has really returned.
                _LOGGER.exception("Background worker %s failed to stop", name)
                drained = False
        container.debug_trace.record("application.stopped")
    finally:
        if drained:
            _close(container)
        else:
            threading.Thread(
                target=_close_after_workers,
                args=(container, workers),
                name="worker-resource-cleanup",
                daemon=True,
            ).start()


def _close_after_workers(container: Container, workers: Mapping[str, BackgroundWorker]) -> None:
    for worker in workers.values():
        worker.wait_until_stopped()
    container.debug_trace.record("application.workers_stopped_after_fence")
    _close(container)


def _close(container: Container) -> None:
    container.close_resources()
    container.debug_trace.close()
