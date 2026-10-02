"""Background-worker lifecycle shared by the API process and the worker process."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping

from smb_requirement_agent.infrastructure.observability.metrics import serve_metrics
from smb_requirement_agent.interfaces.api.container import BackgroundWorker, Container

_LOGGER = logging.getLogger(__name__)


def start_metrics(container: Container) -> Callable[[], None]:
    """Serve this process's metrics on METRICS_PORT; return how to stop serving them."""
    port = container.settings.metrics_port
    if port is None:
        return lambda: None
    stop = serve_metrics(container.metrics, container.settings.metrics_host, port)
    _LOGGER.info("Metrics exporter listening on %s:%s", container.settings.metrics_host, port)
    return stop


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
