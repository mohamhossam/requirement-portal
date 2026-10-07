"""Polled lists stay bounded as a workspace ages.

The browser polls a Requirement's jobs while work runs and every open tab polls
notifications, and both only ever grow. They are bounded, newest first. An
active job is never cut off, because the browser is watching it. The activity
feed still reads every job, since the job rows are its audit record.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.ai_jobs import AiJobCommand, AiJobRecord, JsonValue
from smb_requirement_agent.application.use_cases.ai_jobs import MAX_LIST_LIMIT
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.domain.jobs.entities import (
    ActorNotification,
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobStatus,
    NotificationId,
    NotificationKind,
)
from smb_requirement_agent.domain.shared.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.conftest import FAKE_PROVIDER_SETTINGS

# After any real clock, so the automatic screen (real-clock timestamped) is always oldest.
START = datetime(2099, 1, 1, tzinfo=UTC)
OWNER = {"X-Fake-Actor-Id": "fake-owner"}


@pytest.fixture
def container() -> Container:
    return build_container(FAKE_PROVIDER_SETTINGS)


def _job(requirement_id: RequirementId, minute: int, status: AiJobStatus) -> AiJob:
    at = START + timedelta(minutes=minute)
    job = AiJob(
        AiJobId(f"job-{minute:03d}"),
        requirement_id,
        AiJobOperation.ANALYSE_REQUIREMENT,
        AiJobStatus.QUEUED,
        ActorSnapshot(ActorId("fake-owner"), "Owner"),
        at,
        at,
        f"key-{uuid.uuid4()}",
        f"fingerprint-{minute}",
    )
    if status is AiJobStatus.QUEUED:
        return job
    running = job.claim(at)
    return running if status is AiJobStatus.RUNNING else running.succeed((), at)


def _requirement_with_jobs(container: Container, statuses: dict[int, AiJobStatus]) -> RequirementId:
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Bounded", "Bounded job history."), FAKE_ACTORS[0]
    )
    # Creating it queued an automatic screen; finish it so the counts below are exact.
    now = container.clock.now()
    for record in container.ai_job_repository.list_for_requirement(requirement.id):
        # Each transition is its own optimistic save.
        running = record.job.claim(now)
        container.ai_job_repository.save(running)
        container.ai_job_repository.save(running.succeed((), now))
    for minute, status in statuses.items():
        container.ai_job_repository.add(
            AiJobRecord(_job(requirement.id, minute, status), AiJobCommand({}))
        )
    return requirement.id


def test_the_list_keeps_every_active_job_and_fills_with_the_newest_finished(
    container: Container,
) -> None:
    # An old job still running, and newer finished ones.
    requirement_id = _requirement_with_jobs(
        container,
        {1: AiJobStatus.RUNNING, **{m: AiJobStatus.SUCCEEDED for m in range(10, 20)}},
    )

    listed = container.ai_jobs.list(requirement_id, limit=4)

    assert [item.job.id.value for item in listed] == ["job-019", "job-018", "job-017", "job-001"]


def test_active_jobs_are_never_cut_off_even_beyond_the_limit(container: Container) -> None:
    requirement_id = _requirement_with_jobs(
        container,
        {**{m: AiJobStatus.QUEUED for m in range(1, 4)}, 10: AiJobStatus.SUCCEEDED},
    )

    listed = container.ai_jobs.list(requirement_id, limit=2)

    assert {item.job.id.value for item in listed} == {"job-001", "job-002", "job-003"}


def test_the_activity_feed_still_sees_every_job(container: Container) -> None:
    requirement_id = _requirement_with_jobs(
        container, {m: AiJobStatus.SUCCEEDED for m in range(1, 8)}
    )

    everything = container.ai_job_repository.list_for_requirement(requirement_id)

    assert len(everything) == 8  # seven, plus the finished automatic screen


@pytest.fixture
def client(container: Container) -> Iterator[TestClient]:
    with TestClient(create_app(lambda: container), headers=OWNER) as test_client:
        yield test_client


def test_the_job_list_route_applies_and_bounds_the_limit(
    client: TestClient, container: Container
) -> None:
    requirement_id = _requirement_with_jobs(
        container, {m: AiJobStatus.SUCCEEDED for m in range(1, 6)}
    )
    path = f"/requirements/{requirement_id.value}/ai-jobs"

    assert len(client.get(path, params={"limit": 2}).json()) == 2
    assert len(client.get(path).json()) == 6
    assert client.get(path, params={"limit": 0}).status_code == 422
    assert client.get(path, params={"limit": MAX_LIST_LIMIT + 1}).status_code == 422


def test_the_job_list_reads_each_command_with_its_job_not_one_by_one(
    client: TestClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: the route re-read every job's command, one query per row, on every poll."""
    requirement_id = _requirement_with_jobs(
        container, {m: AiJobStatus.SUCCEEDED for m in range(1, 6)}
    )
    batch = replace(
        _job(requirement_id, 30, AiJobStatus.SUCCEEDED),
        id=AiJobId("job-batch"),
        operation=AiJobOperation.RESOLVE_CLARIFICATION_QUESTIONS,
    )
    answers: list[JsonValue] = [
        {"question_id": f"q-{n}", "answer": "Yes.", "expected_version": 1} for n in range(3)
    ]
    container.ai_job_repository.add(AiJobRecord(batch, AiJobCommand({"answers": answers})))
    lookups: list[AiJobId] = []
    read_one = container.ai_job_repository.get

    def counting_get(job_id: AiJobId) -> AiJobRecord | None:
        lookups.append(job_id)
        return read_one(job_id)

    monkeypatch.setattr(container.ai_job_repository, "get", counting_get)

    listed = client.get(f"/requirements/{requirement_id.value}/ai-jobs").json()

    assert len(listed) == 7
    assert lookups == []
    # The command is still read: a batch resolution reports how many answers it carries.
    assert next(item for item in listed if item["id"] == "job-batch")["item_count"] == 3


def test_notifications_are_newest_first_and_bounded(
    client: TestClient, container: Container
) -> None:
    requirement_id = _requirement_with_jobs(container, {1: AiJobStatus.SUCCEEDED})
    for minute in range(5):
        container.notification_repository.add(
            ActorNotification(
                NotificationId(f"note-{minute}"),
                ActorId("fake-owner"),
                AiJobId("job-001"),
                NotificationKind.AI_JOB_SUCCEEDED,
                "Done.",
                START + timedelta(minutes=minute),
            )
        )

    newest = client.get("/notifications", params={"limit": 2, "unread_only": True}).json()

    assert [item["id"] for item in newest] == ["note-4", "note-3"]
    assert client.get("/notifications", params={"limit": 0}).status_code == 422
    assert requirement_id.value
