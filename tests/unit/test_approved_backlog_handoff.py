"""Handing approved backlogs to the knowledge service (ADR-0101 Amendment 2)."""

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.errors import (
    PersistenceError,
    ServiceResponseError,
    ServiceUnavailableError,
)
from smb_requirement_agent.application.exports import ExportFormat
from smb_requirement_agent.application.ports.backlog_export import BacklogExportPort
from smb_requirement_agent.application.ports.knowledge_handoff import (
    BacklogHandoff,
    HandoffStatus,
)
from smb_requirement_agent.application.use_cases.knowledge_handoff import (
    MAX_ATTEMPTS,
    DeliverApprovedBacklogs,
)
from smb_requirement_agent.domain.revision.entities import (
    BreakdownRevision,
    RequirementRevision,
    RevisionNumber,
)
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.infrastructure.knowledge_client import (
    FakeArchitectureKnowledge,
    FakeKnowledgeEvents,
    FakeKnowledgeViews,
    FakeReferenceKnowledge,
)
from smb_requirement_agent.infrastructure.persistence.backlog_handoffs import (
    InMemoryBacklogHandoffs,
)
from smb_requirement_agent.interfaces.api.composition.knowledge_service import KnowledgeService
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.workflow_helpers import approve_fake_breakdown

Answer = str | Exception


class RecordingInbox:
    """The knowledge service's inbox: answers in turn, then "CR-1"; keeps every body sent."""

    def __init__(self, *answers: Answer) -> None:
        self.answers = list(answers)
        self.sent: list[str] = []

    def deliver(self, export: dict[str, Any]) -> str:
        self.sent.append(json.dumps(export, sort_keys=True))
        answer = self.answers.pop(0) if self.answers else "CR-1"
        if isinstance(answer, Exception):
            raise answer
        return answer


class Clock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def _service(inbox: RecordingInbox | None) -> KnowledgeService:
    return KnowledgeService(
        FakeReferenceKnowledge(),
        FakeArchitectureKnowledge(),
        FakeKnowledgeEvents(),
        FakeKnowledgeViews(),
        remote=False,
        change_requests=inbox,
    )


@pytest.fixture
def inbox() -> RecordingInbox:
    return RecordingInbox()


@pytest.fixture
def handing_over(inbox: RecordingInbox) -> Container:
    """A container configured with a knowledge service inbox."""
    return build_container(FAKE_PROVIDER_SETTINGS, knowledge_service=_service(inbox))


@pytest.fixture
def approving(handing_over: Container) -> Generator[TestClient, None, None]:
    # The API runs every other worker, but not its own handoff worker: that would race
    # each test's worker for the same handoff, which would then find nothing due.
    workers = {
        name: worker
        for name, worker in handing_over.background_workers.items()
        if name != "approved_backlog_worker"
    }
    application = create_app(lambda: replace(handing_over, background_workers=workers))
    with TestClient(application) as client:
        yield client


def _json(container: Container) -> BacklogExportPort:
    return next(item for item in container.backlog_exporters if item.format is ExportFormat.JSON)


def _worker(
    container: Container, inbox: RecordingInbox, clock: Clock, outcomes: list[str] | None = None
) -> DeliverApprovedBacklogs:
    return DeliverApprovedBacklogs(
        container.backlog_handoffs,
        container.breakdown_repository,
        _json(container),
        inbox,
        clock,
        record=(lambda outcome, _seconds: outcomes.append(outcome))
        if outcomes is not None
        else None,
    )


def _later() -> Clock:
    return Clock(datetime.now(UTC) + timedelta(seconds=5))


def test_a_final_approval_hands_its_revision_over_once_without_the_approvers_email(
    approving: TestClient, handing_over: Container, inbox: RecordingInbox
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(approving)
    outcomes: list[str] = []
    worker = _worker(handing_over, inbox, _later(), outcomes)

    assert worker.deliver_next() is True
    assert worker.deliver_next() is False

    (sent,) = inbox.sent
    export = json.loads(sent)
    downloaded = json.loads(
        approving.get(
            f"/requirements/{requirement_id}/revisions/{revision}/export?format=json"
        ).content
    )
    approval = export["manifest"]["final_approval"]
    # The download's export, except that the knowledge service never receives an email.
    assert approval["recorded_by"]["email"] is None
    downloaded["manifest"]["final_approval"]["recorded_by"]["email"] = None
    assert export == downloaded
    assert (export["schema_version"], export["manifest"]["breakdown_revision"]) == ("1.5", revision)
    handoff = handing_over.backlog_handoffs.get(approval["id"])
    assert handoff is not None
    assert (handoff.status, handoff.change_request_id, handoff.requirement_id) == (
        HandoffStatus.DELIVERED,
        "CR-1",
        requirement_id,
    )
    assert outcomes == ["delivered"]


def test_without_a_knowledge_service_an_approval_queues_nothing(
    client: TestClient, container: Container
) -> None:
    approve_fake_breakdown(client)

    assert "approved_backlog_worker" not in container.background_workers
    assert _worker(container, RecordingInbox(), _later()).deliver_next() is False


def test_the_worker_runs_only_with_a_knowledge_service(handing_over: Container) -> None:
    assert "approved_backlog_worker" in handing_over.background_workers


def test_an_unreachable_or_absent_inbox_is_retried_with_the_same_body(
    approving: TestClient, handing_over: Container
) -> None:
    approve_fake_breakdown(approving)
    inbox = RecordingInbox(
        ServiceUnavailableError("down"), ServiceResponseError(404, "not deployed yet"), "CR-9"
    )
    clock = _later()
    outcomes: list[str] = []
    worker = _worker(handing_over, inbox, clock, outcomes)

    assert worker.deliver_next() is True
    # Not due again for a minute, then two.
    assert worker.deliver_next() is False
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is True
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is False
    clock.at += timedelta(minutes=1)
    assert worker.deliver_next() is True

    assert outcomes == ["retry", "retry", "delivered"]
    assert len(inbox.sent) == 3 and len(set(inbox.sent)) == 1
    approval_id = json.loads(inbox.sent[0])["manifest"]["final_approval"]["id"]
    handoff = handing_over.backlog_handoffs.get(approval_id)
    assert handoff is not None
    assert (handoff.status, handoff.attempts, handoff.change_request_id) == (
        HandoffStatus.DELIVERED,
        3,
        "CR-9",
    )


@pytest.mark.parametrize("status", [409, 413, 422])
def test_an_export_the_inbox_refuses_is_not_sent_again(
    approving: TestClient, handing_over: Container, status: int
) -> None:
    approve_fake_breakdown(approving)
    inbox = RecordingInbox(ServiceResponseError(status, "refused"))
    clock = _later()
    outcomes: list[str] = []
    worker = _worker(handing_over, inbox, clock, outcomes)

    assert worker.deliver_next() is True
    clock.at += timedelta(days=1)
    assert worker.deliver_next() is False

    assert outcomes == ["failed"]
    approval_id = json.loads(inbox.sent[0])["manifest"]["final_approval"]["id"]
    handoff = handing_over.backlog_handoffs.get(approval_id)
    assert handoff is not None
    assert handoff.status is HandoffStatus.FAILED
    assert handoff.last_error == f"The knowledge service refused it ({status})."


def test_replaying_an_approval_queues_nothing_new(
    approving: TestClient, handing_over: Container, inbox: RecordingInbox
) -> None:
    requirement_id, _, _ = approve_fake_breakdown(approving)
    workflow = approving.get(f"/requirements/{requirement_id}/approval-workflow").json()
    replay = approving.post(
        f"/requirements/{requirement_id}/breakdown-approval",
        json={
            "expected_fingerprint": workflow["subject_fingerprint"],
            "expected_version": workflow["review_version"],
        },
    )

    assert replay.status_code == 200, replay.text
    worker = _worker(handing_over, inbox, _later())
    assert worker.deliver_next() is True
    assert worker.deliver_next() is False
    assert len(inbox.sent) == 1


# The worker against an outbox alone.

AT = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)


class NoRevisions:
    def create_current_revisions(self, requirement_id: RequirementId) -> None:
        raise AssertionError("The worker never captures revisions.")

    def list_requirement_revisions(
        self, requirement_id: RequirementId
    ) -> list[RequirementRevision]:
        return []

    def list_breakdown_revisions(self, requirement_id: RequirementId) -> list[BreakdownRevision]:
        return []

    def get_breakdown_revision(
        self, requirement_id: RequirementId, number: RevisionNumber
    ) -> BreakdownRevision | None:
        return None


def _queued(**changes: Any) -> BacklogHandoff:
    return replace(
        BacklogHandoff(
            approval_id="apr-1",
            requirement_id="REQ-1",
            subject_fingerprint="sha256:1",
            created_at=AT,
            next_attempt_at=AT,
        ),
        **changes,
    )


def _alone(outbox: InMemoryBacklogHandoffs, inbox: RecordingInbox) -> DeliverApprovedBacklogs:
    container = build_container(FAKE_PROVIDER_SETTINGS)
    return DeliverApprovedBacklogs(outbox, NoRevisions(), _json(container), inbox, Clock(AT))


def test_an_approval_no_exportable_revision_carries_is_skipped_unsent() -> None:
    outbox, inbox = InMemoryBacklogHandoffs(RLock()), RecordingInbox()
    outbox.enqueue(_queued())

    assert _alone(outbox, inbox).deliver_next() is True

    handoff = outbox.get("apr-1")
    assert handoff is not None and handoff.status is HandoffStatus.SKIPPED
    assert inbox.sent == []


def test_a_handoff_is_given_up_after_its_last_attempt() -> None:
    outbox, inbox = (
        InMemoryBacklogHandoffs(RLock()),
        RecordingInbox(ServiceUnavailableError("down")),
    )
    outbox.enqueue(_queued(payload={"schema_version": "1.5"}, attempts=MAX_ATTEMPTS - 1))

    assert _alone(outbox, inbox).deliver_next() is True

    handoff = outbox.get("apr-1")
    assert handoff is not None
    assert (handoff.status, handoff.attempts) == (HandoffStatus.FAILED, MAX_ATTEMPTS)
    assert handoff.last_error == (
        f"The knowledge service could not be reached. Gave up after {MAX_ATTEMPTS} attempts."
    )


def test_the_outbox_keeps_one_handoff_per_approval_and_leases_it_to_one_worker() -> None:
    outbox = InMemoryBacklogHandoffs(RLock())
    assert outbox.enqueue(_queued()) is True
    assert outbox.enqueue(_queued(requirement_id="REQ-2")) is False

    claimed = outbox.claim(AT, timedelta(minutes=5), "first")
    assert claimed is not None
    assert (claimed.lease_token, claimed.attempts, claimed.version) == ("first", 1, 2)
    # Leased: no one else takes it until the lease runs out.
    assert outbox.claim(AT + timedelta(minutes=4), timedelta(minutes=5), "second") is None
    again = outbox.claim(AT + timedelta(minutes=5), timedelta(minutes=5), "second")
    assert again is not None and again.lease_token == "second"
    # The first worker's write is refused: the handoff moved on without it.
    with pytest.raises(PersistenceError):
        outbox.save(claimed.retried("late", AT), claimed.version)


def test_a_rolled_back_approval_leaves_no_handoff() -> None:
    outbox = InMemoryBacklogHandoffs(RLock())
    before = outbox.snapshot_state()
    outbox.enqueue(_queued())

    outbox.restore_state(before)

    assert outbox.get("apr-1") is None
