"""Worker process: ``python -m smb_requirement_agent.interfaces.worker``.

Runs every background worker without serving HTTP, so API replicas can be
deployed with ``API_BACKGROUND_WORKERS=false`` and scaled independently.

The process exits non-zero when a worker stops being healthy (for example its
job lease heartbeat fails), leaving restart policy to the process supervisor.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from collections.abc import Sequence

from smb_kernel.observability.logging import configure_logging

from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.runtime import (
    start_metrics,
    start_workers,
    stop_workers_and_close,
)

HEALTH_CHECK_INTERVAL_SECONDS = 10.0

_LOGGER = logging.getLogger("smb_requirement_agent.worker")


def main(argv: Sequence[str] | None = None) -> int:
    del argv  # No options yet; accepted for a uniform entrypoint signature.
    try:
        settings = Settings.from_env()
        configure_logging(settings.log_level, settings.log_format)
        if settings.persistence_provider is not PersistenceProvider.POSTGRES:
            raise ConfigurationError(
                "The worker process requires PERSISTENCE_PROVIDER=postgres: it cannot see "
                "an API process's in-memory queues."
            )
        container = build_container(settings)
    except ConfigurationError as exc:
        print(f"[worker] {exc}", file=sys.stderr)
        return 2

    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())

    workers = container.background_workers
    exit_code = 0
    stop_metrics = start_metrics(container)
    try:
        start_workers(workers)
        _LOGGER.info("Worker process started: %s", ", ".join(workers))
        container.metrics.set_ready(True)
        while not stop.wait(HEALTH_CHECK_INTERVAL_SECONDS):
            unhealthy = [name for name, worker in workers.items() if not worker.healthy]
            container.metrics.set_ready(not unhealthy)
            if unhealthy:
                _LOGGER.error("Unhealthy background workers %s; exiting for restart", unhealthy)
                exit_code = 1
                break
    finally:
        stop_metrics()
        stop_workers_and_close(container, workers)
    _LOGGER.info("Worker process stopped")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
