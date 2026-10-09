"""Run model-backed work the only way the API offers it: as a durable job (ADR-0105).

A test starts the job through the public route, then plays the worker with the
container's own queue and executor until the job reaches a terminal state. A
background worker started by the TestClient may claim the job first; the driver
then waits for it, so the outcome is the same either way.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response

from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.jobs.domain.entities import AiJobStatus
from smb_requirement_agent.knowledge.infrastructure.requirement_index_worker import (
    IndexReadyJobQueue,
)

DRIVER = "test-job-driver"
TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class JobRun:
    """What starting a job came to: the start response and, once queued, the finished job."""

    start: Response
    job: dict[str, Any] | None

    @property
    def succeeded(self) -> bool:
        return self.job is not None and self.job["status"] == AiJobStatus.SUCCEEDED

    @property
    def failure(self) -> dict[str, Any] | None:
        """The failure a queued job ended with, or None."""
        return None if self.job is None else cast(dict[str, Any] | None, self.job["failure"])


def start_job(
    client: TestClient,
    requirement_id: str,
    operation: str,
    *,
    headers: dict[str, str] | None = None,
    **arguments: object,
) -> Response:
    return client.post(
        f"/requirements/{requirement_id}/ai-jobs",
        json={"operation": operation, **arguments},
        headers={**(headers or {}), "Idempotency-Key": str(uuid.uuid4())},
    )


def run_job(
    client: TestClient,
    requirement_id: str,
    operation: str,
    *,
    headers: dict[str, str] | None = None,
    **arguments: object,
) -> JobRun:
    """Start a job and run it to the end; a refused start comes back without a job."""
    start = start_job(client, requirement_id, operation, headers=headers, **arguments)
    if start.status_code not in {200, 202}:
        return JobRun(start, None)
    return JobRun(start, finish_job(client, requirement_id, start.json()["id"], headers=headers))


def finish_job(
    client: TestClient,
    requirement_id: str,
    job_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run claimable jobs, in queue order, until this one is terminal; return it."""
    container = cast(Container, cast(FastAPI, client.app).state.container)
    queue = IndexReadyJobQueue(container.ai_job_queue, container.requirement_indexer)
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        response = client.get(f"/requirements/{requirement_id}/ai-jobs/{job_id}", headers=headers)
        assert response.status_code == 200, response.text
        job = cast(dict[str, Any], response.json())
        if AiJobStatus(job["status"]).terminal:
            return job
        assert time.monotonic() < deadline, f"AI job {job_id} never finished: {job}"
        container.requirement_indexer.process_next()
        now = container.clock.now()
        claimed = queue.claim_next(DRIVER, now, now + timedelta(minutes=5))
        if claimed is None:
            time.sleep(0.01)  # A TestClient worker holds the job, or the index is catching up.
        else:
            container.execute_ai_job.execute(claimed)
