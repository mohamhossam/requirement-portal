"""The polling loop both background ingestion workers run (ADR-0099)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event, Thread

from smb_requirement_agent.infrastructure.log_safety import exception_frames, exception_types

logger = logging.getLogger(__name__)
# A connected portal that is down fails every step about once a second; one report a minute
# says so without flooding the log.
FAILURE_REPORT_SECONDS = 60.0


class IngestionLoop:
    """Runs its steps until stopped, resting a second whenever none had work.

    A failing step is counted through `failed` every time, and reported in the log at
    most once per `FAILURE_REPORT_SECONDS`, with where it failed but never its message,
    which may quote a document. Stopping waits up to `shutdown_grace_seconds` for the
    step under way to finish.
    """

    def __init__(
        self,
        name: str,
        steps: tuple[Callable[[], bool], ...],
        *,
        failed: Callable[[], None],
        shutdown_grace_seconds: float,
        monotonic_seconds: Callable[[], float],
    ) -> None:
        self._name = name
        self._steps = steps
        self._failed = failed
        self._grace = shutdown_grace_seconds
        self._monotonic = monotonic_seconds
        self._stop = Event()
        self._thread: Thread | None = None
        self._last_report = float("-inf")
        self._unreported = 0

    @property
    def healthy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self._stop.clear()
        self._thread = Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                worked = False
                for step in self._steps:
                    worked = step() or worked
            except Exception as exc:
                # Top-level boundary: keep durable leases recoverable.
                self._report(exc)
                worked = False
            if not worked:
                self._stop.wait(1)

    def _report(self, exc: Exception) -> None:
        self._failed()
        self._unreported += 1
        now = self._monotonic()
        if now - self._last_report < FAILURE_REPORT_SECONDS:
            return
        logger.error(
            "%s worker failed with %s (%d failures since the last report)\n%s",
            self._name,
            exception_types(exc),
            self._unreported,
            exception_frames(exc),
        )
        self._last_report = now
        self._unreported = 0

    def stop(self) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._grace)
        return not self.healthy

    def wait_until_stopped(self) -> None:
        if self._thread is not None:
            self._thread.join()
