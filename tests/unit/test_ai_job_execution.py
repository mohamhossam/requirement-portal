"""Every AI job operation runs end to end through the job executor.

The API tests call use cases directly, and the smoke suite drives the worker
through a browser. These start each job over HTTP as the browser does, claim it
as the worker does, and run it through `ExecuteAiJob`, covering the dispatch,
the result resources, notifications, and the cancellation, failure and
lease-loss paths.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import timedelta
from threading import RLock
from types import TracebackType
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.domain.entities import ClarificationQuestion
from smb_requirement_agent.analysis.domain.value_objects import QuestionId
from smb_requirement_agent.application.errors import (
    DocumentNotFoundError,
    KnowledgeIndexPendingError,
)
from smb_requirement_agent.application.ports.saved_views import SavedViewCriteria
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.identity.infrastructure.in_memory_identity import (
    InMemoryActorDirectory,
)
from smb_requirement_agent.infrastructure.jobs.requirement_index_worker import IndexReadyJobQueue
from smb_requirement_agent.infrastructure.persistence.in_memory_saved_views import (
    InMemorySavedViewRepository,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobCommand, AiJobRecord
from smb_requirement_agent.jobs.domain.entities import (
    AiJob,
    AiJobOperation,
    AiJobOrigin,
    AiJobStatus,
    NotificationKind,
)
from smb_requirement_agent.requirements.domain.document.value_objects import DocumentVersionId
from smb_requirement_agent.requirements.infrastructure.in_memory_document_repository import (
    InMemoryDocumentStorage,
)
from smb_requirement_agent.shared_kernel.actors import ActorId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    drain_requirement_index,
    generate_story_tree,
    post_analysis,
    post_epic_approval,
)

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
OWNER_ID = ActorId("fake-owner")
WORKER = "worker-1"


@pytest.fixture
def container() -> Container:
    # No background workers: the test is the only worker, so no other claim races it.
    return replace(build_container(FAKE_PROVIDER_SETTINGS), background_workers={})


@pytest.fixture
def client(container: Container) -> Iterator[TestClient]:
    with TestClient(create_app(lambda: container), headers=OWNER) as test_client:
        yield test_client


def _start(client: TestClient, requirement_id: str, body: dict[str, Any]) -> str:
    response = client.post(
        f"/requirements/{requirement_id}/ai-jobs",
        json=body,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 202, response.text
    return str(response.json()["id"])


def _claim(container: Container, job_id: str) -> AiJobRecord:
    """Claim as the worker does, running any automatic work queued ahead of the job."""
    queue = IndexReadyJobQueue(container.ai_job_queue, container.requirement_indexer)
    for _ in range(50):
        drain_requirement_index(container)
        now = container.clock.now()
        claimed = queue.claim_next(WORKER, now, now + timedelta(minutes=5))
        assert claimed is not None, "The job was never claimable."
        if claimed.job.id.value == job_id:
            return claimed
        container.execute_ai_job.execute(claimed)
    raise AssertionError("The job was never claimed.")


def _drain(container: Container) -> None:
    """Run every claimable job, as an idle worker would."""
    queue = IndexReadyJobQueue(container.ai_job_queue, container.requirement_indexer)
    for _ in range(50):
        drain_requirement_index(container)
        now = container.clock.now()
        claimed = queue.claim_next(WORKER, now, now + timedelta(minutes=5))
        if claimed is None:
            return
        container.execute_ai_job.execute(claimed)
    raise AssertionError("The queue never drained.")


def _run(
    client: TestClient, container: Container, requirement_id: str, body: dict[str, Any]
) -> AiJob:
    # Finish automatic work first, so an equivalent automatic job cannot absorb this one.
    _drain(container)
    job_id = _start(client, requirement_id, body)
    claimed = _claim(container, job_id)
    assert claimed.job.origin is AiJobOrigin.USER
    return container.execute_ai_job.execute(claimed)


def _succeeded(job: AiJob, kind: str) -> None:
    assert job.status is AiJobStatus.SUCCEEDED, job.failure
    assert job.result_resources[0].kind == kind


def _requirement(client: TestClient) -> str:
    response = client.post("/requirements", json={"title": "Jobs", "description": "Run jobs."})
    assert response.status_code == 201
    return str(response.json()["id"])


def _analysed(client: TestClient) -> str:
    requirement_id = _requirement(client)
    assert post_analysis(client, requirement_id).status_code == 200
    return requirement_id


def _open_questions(client: TestClient, requirement_id: str) -> list[dict[str, Any]]:
    analysis = client.get(f"/requirements/{requirement_id}/analysis").json()
    return [item for item in analysis["questions"] if item["status"] == "open"]


def _notifications(container: Container, kind: NotificationKind) -> list[str]:
    return [
        item.job_id.value
        for item in container.notification_repository.list_for_actor(OWNER_ID)
        if item.kind is kind and item.job_id is not None
    ]


def test_analysis_and_question_jobs_run_and_notify_their_creator(
    client: TestClient, container: Container
) -> None:
    requirement_id = _requirement(client)
    requirement = client.get(f"/requirements/{requirement_id}").json()

    analysed = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "analyse_requirement",
            "context_token": requirement["analysis_context_token"],
        },
    )
    _succeeded(analysed, "analysis")
    assert _notifications(container, NotificationKind.AI_JOB_SUCCEEDED) == [analysed.id.value]

    first, second, third, fourth = _open_questions(client, requirement_id)
    suggested = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "suggest_clarification_answers",
            "question_id": fourth["id"],
            "expected_version": fourth["version"],
        },
    )
    _succeeded(suggested, "answer_suggestions")

    resolved = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "resolve_clarification_question",
            "question_id": first["id"],
            "answer": "Confirmed.",
            "expected_version": first["version"],
        },
    )
    _succeeded(resolved, "analysis")

    batch = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "resolve_clarification_questions",
            "answers": [
                {"question_id": item["id"], "answer": "Yes.", "expected_version": item["version"]}
                for item in (second, third)
            ],
        },
    )
    _succeeded(batch, "analysis")
    assert {item["id"] for item in _open_questions(client, requirement_id)} == {fourth["id"]}


def test_legacy_clarification_job_runs(client: TestClient, container: Container) -> None:
    requirement_id = _analysed(client)
    analysis = client.get(f"/requirements/{requirement_id}/analysis").json()

    clarified = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "clarify_requirement_analysis",
            "answers": [
                {"kind": item["kind"], "subject": item["subject"], "answer": "Confirmed."}
                for item in _open_questions(client, requirement_id)
            ],
            "expected_analysis_version": analysis["version"],
        },
    )

    _succeeded(clarified, "analysis")


def test_epic_and_feature_jobs_run(client: TestClient, container: Container) -> None:
    requirement_id = _analysed(client)
    confirm_fake_analysis(client, requirement_id)
    analysis = client.get(f"/requirements/{requirement_id}/analysis").json()

    epic = _run(
        client,
        container,
        requirement_id,
        {"operation": "generate_epic", "context_token": analysis["epic_context_token"]},
    )
    _succeeded(epic, "epic")

    assert post_epic_approval(client, requirement_id).status_code == 200
    current = client.get(f"/requirements/{requirement_id}/epic").json()
    features = _run(
        client,
        container,
        requirement_id,
        {"operation": "generate_features", "context_token": current["feature_context_token"]},
    )
    _succeeded(features, "features")
    assert client.get(f"/requirements/{requirement_id}/features").json()["features"]


def test_story_jobs_run(client: TestClient, container: Container) -> None:
    requirement_id, feature_id, stories = generate_story_tree(client)
    path = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    story = client.get(path).json()["stories"][0]

    one = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "regenerate_story",
            "context_token": story["story_context_token"],
            "feature_id": feature_id,
            "story_id": story["id"],
            "force": True,
        },
    )
    _succeeded(one, "stories")

    story_set = client.get(path).json()
    every = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "regenerate_story_set",
            "context_token": story_set["generation_context_token"],
            "feature_id": feature_id,
            "force": True,
        },
    )
    _succeeded(every, "stories")

    story_set = client.get(path).json()
    proposed = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "propose_story_change",
            "context_token": story_set["generation_context_token"],
            "feature_id": feature_id,
            "change_operation": "split",
            "source_story_ids": [story_set["stories"][0]["id"]],
        },
    )
    _succeeded(proposed, "story_proposals")

    story_set = client.get(path).json()
    evaluated = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "evaluate_feature_quality",
            "context_token": story_set["generation_context_token"],
            "feature_id": feature_id,
        },
    )
    _succeeded(evaluated, "story_quality")

    reviewed = _run(client, container, requirement_id, {"operation": "generate_breakdown_review"})
    _succeeded(reviewed, "breakdown_review")


def test_story_generation_job_runs_for_a_newly_approved_feature(
    client: TestClient, container: Container
) -> None:
    requirement_id, _, _ = generate_story_tree(client)
    features = client.get(f"/requirements/{requirement_id}/features").json()["features"]
    pending = next(item for item in features if item["status"] != "approved")
    approved = client.post(
        f"/requirements/{requirement_id}/features/{pending['id']}/approval",
        json={
            "expected_version": pending["version"],
            "expected_content_fingerprint": pending["content_fingerprint"],
        },
    )
    assert approved.status_code == 200
    feature = next(
        item
        for item in client.get(f"/requirements/{requirement_id}/features").json()["features"]
        if item["id"] == pending["id"]
    )

    generated = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "generate_stories",
            "context_token": feature["story_context_token"],
            "feature_id": feature["id"],
        },
    )

    _succeeded(generated, "stories")


def test_a_user_knowledge_screen_job_runs(client: TestClient, container: Container) -> None:
    requirement_id = _requirement(client)
    drain_requirement_index(container)
    review = container.get_knowledge_review.execute(RequirementId(requirement_id))

    screened = _run(
        client,
        container,
        requirement_id,
        {
            "operation": "screen_requirement_knowledge",
            "knowledge_fingerprint": review.current_fingerprint,
        },
    )

    _succeeded(screened, "knowledge_review")


def test_a_screen_finding_a_contradiction_notifies_both_owners(
    client: TestClient, container: Container
) -> None:
    rule = "Customers {} receive refunds within five business days of cancellation."
    first = client.post(
        "/requirements", json={"title": "Refunds", "description": rule.format("must")}
    )
    assert first.status_code == 201
    _drain(container)
    second = client.post(
        "/requirements", json={"title": "No refunds", "description": rule.format("must not")}
    )
    assert second.status_code == 201

    _drain(container)

    review = container.get_knowledge_review.execute(RequirementId(second.json()["id"]))
    assert any(item.kind.value == "possible_contradiction" for item in review.findings)
    assert _notifications(container, NotificationKind.KNOWLEDGE_CONFLICT_ACTION_REQUIRED)


def test_a_failing_job_is_recorded_with_a_public_error_and_notified(
    client: TestClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirement_id = _requirement(client)
    requirement = client.get(f"/requirements/{requirement_id}").json()
    job_id = _start(
        client,
        requirement_id,
        {
            "operation": "analyse_requirement",
            "context_token": requirement["analysis_context_token"],
        },
    )
    claimed = _claim(container, job_id)

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Synthetic provider outage")

    monkeypatch.setattr(container.execute_ai_job._analyze, "execute_workspace", fail)
    failed = container.execute_ai_job.execute(claimed)

    assert failed.status is AiJobStatus.FAILED
    assert failed.failure is not None and failed.failure.correlation_id
    assert "Synthetic" not in failed.failure.message
    assert _notifications(container, NotificationKind.AI_JOB_FAILED) == [job_id]


def test_an_index_wait_fails_a_job_that_does_not_need_the_index(
    client: TestClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirement_id = _requirement(client)
    requirement = client.get(f"/requirements/{requirement_id}").json()
    job_id = _start(
        client,
        requirement_id,
        {
            "operation": "analyse_requirement",
            "context_token": requirement["analysis_context_token"],
        },
    )
    claimed = _claim(container, job_id)
    assert not claimed.job.operation.requires_current_index

    def pending(*args: object, **kwargs: object) -> None:
        raise KnowledgeIndexPendingError("Index is catching up.")

    monkeypatch.setattr(container.execute_ai_job._analyze, "execute_workspace", pending)

    assert container.execute_ai_job.execute(claimed).status is AiJobStatus.FAILED


def test_a_failing_automatic_job_notifies_the_requirement_owner(
    client: TestClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirement_id = _requirement(client)
    drain_requirement_index(container)
    queue = IndexReadyJobQueue(container.ai_job_queue, container.requirement_indexer)
    now = container.clock.now()
    claimed = queue.claim_next(WORKER, now, now + timedelta(minutes=5))
    assert claimed is not None and claimed.job.origin is AiJobOrigin.AUTOMATIC
    assert claimed.job.requirement_id.value == requirement_id

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Synthetic classifier outage")

    monkeypatch.setattr(container.execute_ai_job._screen_knowledge, "execute_automatic", fail)

    failed = container.execute_ai_job.execute(claimed)

    assert failed.status is AiJobStatus.FAILED
    assert _notifications(container, NotificationKind.AI_JOB_FAILED) == [claimed.job.id.value]


class _AnnouncedLock:
    """The shared graph lock, announcing each attempt to take it."""

    def __init__(self, lock: RLock, attempted: threading.Event) -> None:
        self._lock = lock
        self._attempted = attempted

    def __enter__(self) -> bool:
        self._attempted.set()
        return self._lock.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._lock.__exit__(exc_type, exc, traceback)


@dataclass(frozen=True)
class _RequestWrite:
    """A write a request makes outside any unit of work, and how to see it landed."""

    store: InMemoryActorDirectory | InMemorySavedViewRepository | InMemoryDocumentStorage
    write: Callable[[], object]
    landed: Callable[[], bool]


def _saves_a_view(container: Container) -> _RequestWrite:
    reviewer = FAKE_ACTORS[1]
    store = container.saved_view_repository
    assert isinstance(store, InMemorySavedViewRepository)
    return _RequestWrite(
        store,
        lambda: container.saved_views.create(reviewer, "Review queue", SavedViewCriteria()),
        lambda: bool(container.saved_views.list(reviewer)),
    )


def _records_a_changed_profile(container: Container) -> _RequestWrite:
    renamed = replace(FAKE_ACTORS[1], display_name="Ravi R. Reviewer")
    store = container.actor_directory
    assert isinstance(store, InMemoryActorDirectory)
    return _RequestWrite(
        store,
        lambda: container.actor_directory.record(renamed),
        lambda: container.actor_directory.get(renamed.id) == renamed,
    )


def _stores_an_upload_blob(container: Container) -> _RequestWrite:
    # An architecture upload stores its blob before, and outside, its own save.
    blob = DocumentVersionId("architecture-upload")
    store = container.document_storage
    assert isinstance(store, InMemoryDocumentStorage)

    def landed() -> bool:
        try:
            return container.document_storage.get(blob) == b"context"
        except DocumentNotFoundError:
            return False

    return _RequestWrite(store, lambda: container.document_storage.put(blob, b"context"), landed)


@pytest.mark.parametrize(
    "request_write", [_saves_a_view, _records_a_changed_profile, _stores_an_upload_blob]
)
def test_a_concurrent_request_write_is_not_the_automatic_suggestions_write(
    client: TestClient,
    container: Container,
    monkeypatch: pytest.MonkeyPatch,
    request_write: Callable[[Container], _RequestWrite],
) -> None:
    """Regression: a saved worklist view failed a concurrent suggestion job.

    Saving a view, like recording a changed profile or storing an upload blob,
    writes an in-memory store outside any unit of work. When that write landed
    inside the job's transaction, the transaction counted it as its own,
    refused the provider call ("External providers cannot run after a
    transaction has written.") and rolled the write back. The request here
    starts while the job holds its transaction, and the job resumes once the
    request is waiting for the graph lock, so no timing decides the outcome.
    """
    requirement_id = _analysed(client)
    queue = IndexReadyJobQueue(container.ai_job_queue, container.requirement_indexer)
    claimed = None
    for _ in range(50):
        drain_requirement_index(container)
        now = container.clock.now()
        claimed = queue.claim_next(WORKER, now, now + timedelta(minutes=5))
        assert claimed is not None, "No automatic suggestion job was queued."
        if claimed.job.operation is AiJobOperation.SUGGEST_CLARIFICATION_ANSWERS:
            break
        container.execute_ai_job.execute(claimed)
    assert claimed is not None and claimed.job.origin is AiJobOrigin.AUTOMATIC
    assert claimed.job.requirement_id.value == requirement_id

    concurrent = request_write(container)
    assert not concurrent.landed()
    attempted = threading.Event()
    monkeypatch.setattr(
        concurrent.store, "_lock", _AnnouncedLock(concurrent.store._lock, attempted)
    )
    request = threading.Thread(target=concurrent.write)
    audits = container.analysis_audit_repository
    get_question = audits.get_question

    def question_then_request(
        requirement: RequirementId, question: QuestionId
    ) -> ClarificationQuestion | None:
        # The suggestion reads its question inside the job's transaction, just
        # before it hands over to the provider.
        if request.ident is None:
            request.start()
            assert attempted.wait(timeout=10), "The request never reached the store."
        return get_question(requirement, question)

    monkeypatch.setattr(audits, "get_question", question_then_request)

    job = container.execute_ai_job.execute(claimed)
    request.join()

    assert job.status is AiJobStatus.SUCCEEDED, job.failure
    assert job.result_resources[0].kind == "answer_suggestions"
    assert concurrent.landed()


def test_a_cancellation_requested_before_the_attempt_cancels_without_running(
    client: TestClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirement_id = _requirement(client)
    requirement = client.get(f"/requirements/{requirement_id}").json()
    job_id = _start(
        client,
        requirement_id,
        {
            "operation": "analyse_requirement",
            "context_token": requirement["analysis_context_token"],
        },
    )
    claimed = _claim(container, job_id)
    current = client.get(f"/requirements/{requirement_id}/ai-jobs/{job_id}").json()
    cancel = client.post(
        f"/requirements/{requirement_id}/ai-jobs/{job_id}/cancellation",
        json={"expected_version": current["version"]},
    )
    assert cancel.status_code == 200, cancel.text

    def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("A cancelled job must not run.")

    monkeypatch.setattr(container.execute_ai_job._analyze, "execute_workspace", unexpected)

    assert container.execute_ai_job.execute(claimed).status is AiJobStatus.CANCELLED


def test_a_cancellation_requested_while_running_is_honoured_at_commit(
    client: TestClient, container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirement_id = _requirement(client)
    requirement = client.get(f"/requirements/{requirement_id}").json()
    job_id = _start(
        client,
        requirement_id,
        {
            "operation": "analyse_requirement",
            "context_token": requirement["analysis_context_token"],
        },
    )
    claimed = _claim(container, job_id)
    analyze = container.execute_ai_job._analyze
    original = analyze.execute_workspace

    def cancel_midway(*args: Any, **kwargs: Any) -> object:
        # The provider work finishes; the user cancels before the result commits.
        result = original(*args, **kwargs)
        running = container.ai_job_repository.get(claimed.job.id)
        assert running is not None
        container.ai_job_repository.save(running.job.request_cancellation(container.clock.now()))
        return result

    monkeypatch.setattr(analyze, "execute_workspace", cancel_midway)

    assert container.execute_ai_job.execute(claimed).status is AiJobStatus.CANCELLED


def test_an_unclaimed_or_superseded_attempt_cannot_write(
    client: TestClient, container: Container
) -> None:
    requirement_id = _requirement(client)
    requirement = client.get(f"/requirements/{requirement_id}").json()
    job_id = _start(
        client,
        requirement_id,
        {
            "operation": "analyse_requirement",
            "context_token": requirement["analysis_context_token"],
        },
    )
    claimed = _claim(container, job_id)

    with pytest.raises(Exception, match="claimed attempt token"):
        container.execute_ai_job.execute(replace(claimed, attempt_token=None))
    with pytest.raises(Exception, match="attempt changed|lease was lost"):
        container.execute_ai_job.execute(replace(claimed, attempt_token="superseded"))

    stored = container.ai_job_repository.get(claimed.job.id)
    assert stored is not None and stored.job.status is AiJobStatus.RUNNING


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param({"answers": "not a list"}, id="list"),
        pytest.param({"answers": ["not an object"]}, id="object"),
        pytest.param({"answers": [{"answer": "Yes.", "expected_version": 1}]}, id="string"),
        pytest.param(
            {"answers": [{"question_id": "q", "answer": "Yes.", "expected_version": True}]},
            id="integer",
        ),
        pytest.param(
            {
                "answers": [
                    {
                        "question_id": "q",
                        "answer": "Yes.",
                        "expected_version": 1,
                        "source_suggestion_id": 7,
                    }
                ]
            },
            id="optional string",
        ),
    ],
)
def test_a_malformed_stored_command_fails_as_a_conflict(
    client: TestClient, container: Container, arguments: dict[str, Any]
) -> None:
    requirement_id = _analysed(client)
    question = _open_questions(client, requirement_id)[0]
    job_id = _start(
        client,
        requirement_id,
        {
            "operation": "resolve_clarification_questions",
            "answers": [{"question_id": question["id"], "answer": "Yes.", "expected_version": 1}],
        },
    )
    claimed = _claim(container, job_id)

    failed = container.execute_ai_job.execute(replace(claimed, command=AiJobCommand(arguments)))

    assert failed.status is AiJobStatus.FAILED
    assert failed.failure is not None and failed.failure.code == "ai_job_conflict"


def test_a_malformed_force_flag_fails_as_a_conflict(
    client: TestClient, container: Container
) -> None:
    requirement_id = _requirement(client)
    requirement = client.get(f"/requirements/{requirement_id}").json()
    job_id = _start(
        client,
        requirement_id,
        {
            "operation": "analyse_requirement",
            "context_token": requirement["analysis_context_token"],
        },
    )
    claimed = _claim(container, job_id)
    command = AiJobCommand({**claimed.command.arguments, "force": "yes"})

    failed = container.execute_ai_job.execute(replace(claimed, command=command))

    assert failed.status is AiJobStatus.FAILED
    assert failed.failure is not None and failed.failure.code == "ai_job_conflict"
    assert claimed.job.operation is AiJobOperation.ANALYSE_REQUIREMENT
