"""The polling loop both background ingestion workers run (ADR-0099)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event, Thread


class IngestionLoop:
    """Runs its steps until stopped, resting a second whenever none had work."""

    def __init__(self, name: str, steps: tuple[Callable[[], bool], ...]) -> None:
        self._name = name
        self._steps = steps
        self._stop = Event()
        self._thread: Thread | None = None

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
                # Top-level boundary: keep durable leases recoverable; never log document bodies.
                logging.getLogger(__name__).error(
                    "%s worker failed: %s", self._name, type(exc).__name__
                )
                worked = False
            if not worked:
                self._stop.wait(1)

    def stop(self) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        return not self.healthy

    def wait_until_stopped(self) -> None:
        if self._thread is not None:
            self._thread.join()
