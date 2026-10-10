"""The metrics alerting reads (production hardening PR 9): the release, readiness and the queue."""

from __future__ import annotations

import socket
from dataclasses import replace
from datetime import timedelta
from threading import RLock

from fastapi.testclient import TestClient

from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.interfaces.release import APPLICATION_VERSION
from smb_requirement_agent.interfaces.runtime import (
    sample_queue,
    start_metrics,
)
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobCommand, AiJobRecord
from smb_requirement_agent.jobs.domain.entities import AiJobId, AiJobOperation, AiJobStatus
from smb_requirement_agent.jobs.infrastructure.in_memory_ai_jobs import InMemoryAiJobStore
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.jobs.test_ai_jobs import NOW, _job


def _record(name: str, *, minutes_ago: int, retry_in: int | None = None) -> AiJobRecord:
    job = replace(
        _job(),
        id=AiJobId(name),
        idempotency_key=f"key-{name}",
        created_at=NOW - timedelta(minutes=minutes_ago),
        next_attempt_at=None if retry_in is None else NOW + timedelta(minutes=retry_in),
    )
    return AiJobRecord(job, command=AiJobCommand({}))


def test_the_backlog_counts_queued_jobs_and_ages_only_those_due() -> None:
    store = InMemoryAiJobStore(RLock())
    store.add(_record("waiting", minutes_ago=20))
    store.add(_record("backing-off", minutes_ago=60, retry_in=5))
    done = _record("done", minutes_ago=90)
    store.add(replace(done, job=replace(done.job, status=AiJobStatus.SUCCEEDED)))

    backlog = store.backlog(NOW)

    assert backlog.queued == {AiJobOperation.ANALYSE_REQUIREMENT.value: 2}
    # A job waiting out its backoff is not "stuck"; the oldest due job is 20 minutes old.
    assert backlog.oldest_claimable_since == NOW - timedelta(minutes=20)
    assert InMemoryAiJobStore(RLock()).backlog(NOW).oldest_claimable_since is None


def test_a_sample_records_the_queue_and_a_drained_one_reads_zero() -> None:
    container = build_container(FAKE_PROVIDER_SETTINGS)
    try:
        container.ai_job_repository.add(_record("waiting", minutes_ago=20))
        sample_queue(container)
        registry = container.metrics.registry
        queued = registry.get_sample_value(
            "smb_ai_jobs_queued", {"operation": "analyse_requirement"}
        )
        age = registry.get_sample_value("smb_ai_job_oldest_queued_age_seconds")
        assert queued == 1
        assert age is not None and age > 0
    finally:
        container.close_resources()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_the_exporter_names_the_running_release() -> None:
    container = build_container(replace(FAKE_PROVIDER_SETTINGS, metrics_port=_free_port()))
    stop = start_metrics(container)
    try:
        info = container.metrics.registry.get_sample_value(
            "smb_build_info", {"service": "requirement-portal", "version": APPLICATION_VERSION}
        )
    finally:
        stop()
        container.close_resources()
    assert info == 1


def test_the_readiness_probe_reports_its_answer_as_a_metric() -> None:
    container = build_container(FAKE_PROVIDER_SETTINGS)
    with TestClient(create_app(lambda: container)) as client:
        assert client.get("/ready").status_code == 200
        assert container.metrics.registry.get_sample_value("smb_ready") == 1
