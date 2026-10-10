"""Ingestion loops count every failure, report one a minute, and never log its message."""

from __future__ import annotations

import logging
import threading
import time

import pytest

from smb_requirement_agent.infrastructure.documents.ingestion_loop import IngestionLoop


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


# Built at run time: the logged frames show source lines, which must not contain it either.
_MARK = "".join(("SEC", "RET"))


def _raised() -> ValueError:
    try:
        try:
            raise KeyError(f"{_MARK} cause")
        except KeyError as cause:
            raise ValueError(f"{_MARK} requirement text") from cause
    except ValueError as exc:
        return exc


def test_failures_are_counted_each_time_and_reported_once_a_minute(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failures: list[int] = []
    clock = _Clock()
    loop = IngestionLoop(
        "test",
        (lambda: False,),
        failed=lambda: failures.append(1),
        shutdown_grace_seconds=1,
        monotonic_seconds=clock,
    )
    with caplog.at_level(logging.ERROR):
        for second in (0, 1, 2, 59, 60):
            clock.now = second
            loop._report(_raised())

    assert len(failures) == 5
    reports = [record.getMessage() for record in caplog.records]
    assert len(reports) == 2
    assert "test worker failed with ValueError <- KeyError (1 failures" in reports[0]
    assert "(4 failures since the last report)" in reports[1]
    # Where it failed, never what the message said.
    assert "test_ingestion_loop.py" in reports[0]
    assert all(_MARK not in report for report in reports)


def test_a_failing_step_is_reported_from_the_running_loop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failed = threading.Event()

    def step() -> bool:
        raise _raised()

    loop = IngestionLoop(
        "running",
        (step,),
        failed=failed.set,
        shutdown_grace_seconds=1,
        monotonic_seconds=time.monotonic,
    )
    with caplog.at_level(logging.ERROR):
        loop.start()
        assert failed.wait(1)
        loop.stop()
    assert any("running worker failed with ValueError" in r.getMessage() for r in caplog.records)


def test_stopping_waits_for_the_step_under_way() -> None:
    started = threading.Event()
    finished = threading.Event()

    def slow_step() -> bool:
        started.set()
        time.sleep(0.3)
        finished.set()
        return False

    loop = IngestionLoop(
        "slow",
        (slow_step,),
        failed=lambda: None,
        shutdown_grace_seconds=2,
        monotonic_seconds=time.monotonic,
    )
    loop.start()
    assert started.wait(1)
    assert loop.stop() is True
    assert finished.is_set()
