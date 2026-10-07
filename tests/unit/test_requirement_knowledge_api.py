"""Public knowledge-review and answer-suggestion contracts."""

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.workflow_helpers import (
    drain_requirement_index,
    post_analysis,
    screen_current_knowledge,
)


def _requirement(client: TestClient, title: str, description: str) -> str:
    response = client.post("/requirements", json={"title": title, "description": description})
    assert response.status_code == 201
    return str(response.json()["id"])


def _legacy_requirement(container: Container) -> str:
    requirement = Requirement(
        RequirementId(str(uuid.uuid4())),
        RequirementTitle("Legacy requirement"),
        RequirementDescription("This row predates automatic knowledge screening."),
        RequirementStatus.DRAFT,
    )
    container.requirement_repository.add(requirement)
    container.requirement_access.create_requirement_owner(requirement.id, FAKE_ACTORS[0])
    return requirement.id.value


def test_ensure_knowledge_screen_is_lazy_authorized_and_idempotent(
    client: TestClient,
    container: Container,
) -> None:
    requirement_id = _legacy_requirement(container)
    path = f"/requirements/{requirement_id}/knowledge-screen/ensure"

    denied = client.post(path, headers={"X-Fake-Actor-Id": "fake-observer"})
    assert denied.status_code == 403
    unauthenticated = client.post(path, headers={"X-Fake-Actor-Id": "unknown"})
    assert unauthenticated.status_code == 401

    first = client.post(path)
    second = client.post(path)

    assert first.status_code == 200
    assert first.json()["outcome"] == "scheduled"
    assert second.json() == {
        "outcome": "already_scheduled",
        "job_id": first.json()["job_id"],
    }


def test_ensure_reports_a_current_screen_without_creating_a_job(
    client: TestClient,
    container: Container,
) -> None:
    requirement_id = _legacy_requirement(container)
    typed_id = RequirementId(requirement_id)
    fingerprint = container.get_knowledge_review.execute(typed_id).current_fingerprint
    drain_requirement_index(container)
    container.screen_requirement_knowledge.execute(FAKE_ACTORS[0], typed_id, fingerprint)

    response = client.post(f"/requirements/{requirement_id}/knowledge-screen/ensure")

    assert response.json() == {"outcome": "current", "job_id": None}
    assert container.ai_job_repository.list_for_requirement(typed_id) == []


def test_source_update_and_draft_promotion_keep_change_driven_screening(
    client: TestClient,
    container: Container,
) -> None:
    requirement_id = _requirement(client, "Initial source", "Initial knowledge evidence.")
    updated = client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": "Changed source",
            "description": "Changed knowledge evidence.",
            "expected_version": 1,
        },
    )
    assert updated.status_code == 200
    changed_jobs = [
        item.job
        for item in container.ai_job_repository.list_for_requirement(RequirementId(requirement_id))
        if item.job.operation.value == "screen_requirement_knowledge"
    ]
    assert len(changed_jobs) == 2
    assert len({item.command_fingerprint for item in changed_jobs}) == 2

    draft = client.post(
        "/requirements/drafts",
        json={"title": "Promoted source", "description": "Promoted knowledge evidence."},
    ).json()
    promoted = client.post(
        f"/requirements/drafts/{draft['id']}/promote",
        json={"expected_version": draft["version"]},
    )
    assert promoted.status_code == 201
    promoted_jobs = container.ai_job_repository.list_for_requirement(
        RequirementId(str(promoted.json()["id"]))
    )
    assert (
        len(
            [
                item
                for item in promoted_jobs
                if item.job.operation.value == "screen_requirement_knowledge"
            ]
        )
        == 1
    )


def test_concurrent_ensure_requests_create_one_automatic_job(
    client: TestClient,
    container: Container,
) -> None:
    requirement_id = _legacy_requirement(container)
    path = f"/requirements/{requirement_id}/knowledge-screen/ensure"

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: client.post(path), range(2)))

    assert {response.status_code for response in responses} == {200}
    assert {response.json()["outcome"] for response in responses} == {
        "scheduled",
        "already_scheduled",
    }
    jobs = [
        item
        for item in container.ai_job_repository.list_for_requirement(RequirementId(requirement_id))
        if item.job.operation.value == "screen_requirement_knowledge"
    ]
    assert len(jobs) == 1


def test_cancelled_automatic_screen_requires_explicit_user_retry(
    client: TestClient,
    container: Container,
) -> None:
    requirement_id = _requirement(
        client, "Retry screening", "A cancelled automatic attempt must remain stopped."
    )
    typed_id = RequirementId(requirement_id)
    original = next(
        item.job
        for item in container.ai_job_repository.list_for_requirement(typed_id)
        if item.job.operation.value == "screen_requirement_knowledge"
    )
    container.ai_job_repository.save(original.request_cancellation(container.clock.now()))
    access = container.access_repository.get_requirement(typed_id)
    assert access is not None
    container.requirement_access.assign_reviewer(
        typed_id, FAKE_ACTORS[0], FAKE_ACTORS[1].id, access.version
    )

    ensured = client.post(
        f"/requirements/{requirement_id}/knowledge-screen/ensure",
        headers={"X-Fake-Actor-Id": "fake-reviewer"},
    )
    assert ensured.json() == {
        "outcome": "manual_retry_required",
        "job_id": original.id.value,
    }

    retried = client.post(
        f"/requirements/{requirement_id}/ai-jobs/{original.id.value}/retry",
        json={"expected_version": original.version + 1},
        headers={
            "X-Fake-Actor-Id": "fake-owner",
            "Idempotency-Key": "reviewer-knowledge-retry",
        },
    )
    assert retried.status_code == 202
    assert retried.json()["origin"] == "user"
    assert retried.json()["retry_of_job_id"] == original.id.value
    active = client.post(
        f"/requirements/{requirement_id}/knowledge-screen/ensure",
        headers={"X-Fake-Actor-Id": "fake-reviewer"},
    )
    assert active.json() == {
        "outcome": "already_scheduled",
        "job_id": retried.json()["id"],
    }


def test_knowledge_review_decision_and_worklist_states_are_public(
    client: TestClient,
    container: Container,
) -> None:
    _requirement(client, "XGPON", "Customers order XGPON through BCRM and CPP.")
    candidate_id = _requirement(client, "XGPON", "Customers order XGPON through BCRM and CPP.")

    assert client.get(f"/requirements/{candidate_id}/knowledge-review").json()["status"] == (
        "required"
    )
    assert post_analysis(client, candidate_id).status_code == 200
    for question in container.analysis_audit_repository.list_questions(RequirementId(candidate_id)):
        container.analysis_audit_repository.save_question(question.supersede())
    screen_current_knowledge(client, candidate_id)
    review = client.get(f"/requirements/{candidate_id}/knowledge-review")
    assert review.status_code == 200
    assert review.json()["status"] == "action_required"
    worklist = client.get("/requirements").json()["requirements"]
    item = next(value for value in worklist if value["id"] == candidate_id)
    assert item["workflow_status"] == "knowledge_review"
    finding = review.json()["findings"][0]

    decided = client.post(
        f"/requirements/{candidate_id}/knowledge-findings/{finding['id']}/decisions",
        json={
            "decision": "distinct",
            "expected_version": finding["version"],
            "text": "This request is for a separate managed-service contract.",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "distinct"
    assert client.get(f"/requirements/{candidate_id}/knowledge-review").json()["ready"] is True


@pytest.fixture
def quiet_container() -> Container:
    """A container with no background workers: this test is the only thing running jobs.

    With the app's worker running, the queued suggestion job could finish between
    the test reading a suggestion and resolving with it. The newer suggestion
    set would then replace the one the test holds, and resolution would 404.
    """
    return replace(build_container(FAKE_PROVIDER_SETTINGS), background_workers={})


@pytest.fixture
def quiet_client(quiet_container: Container) -> Iterator[TestClient]:
    with TestClient(create_app(lambda: quiet_container)) as test_client:
        yield test_client


def test_suggestion_job_and_human_resolution_preserve_suggestion_origin(
    quiet_client: TestClient,
    quiet_container: Container,
) -> None:
    client, container = quiet_client, quiet_container
    _requirement(
        client,
        "Known ownership",
        "Customer Operations owns order fallout for business broadband.",
    )
    requirement_id = _requirement(
        client,
        "Launch ownership",
        "Prepare business broadband ordering for launch.",
    )
    assert post_analysis(client, requirement_id).status_code == 200
    typed_id = RequirementId(requirement_id)
    question = container.analysis_audit_repository.list_questions(typed_id)[0]

    queued = client.post(
        f"/requirements/{requirement_id}/ai-jobs",
        headers={"Idempotency-Key": "suggest-answers-1"},
        json={
            "operation": "suggest_clarification_answers",
            "question_id": question.id.value,
            "expected_version": question.version,
        },
    )
    assert queued.status_code == 202
    assert queued.json()["operation"] == "suggest_clarification_answers"

    drain_requirement_index(container)
    generated = container.suggest_clarification_answers.execute(
        typed_id, question.id, question.version, FAKE_ACTORS[0]
    )
    assert generated.suggestions
    response = client.get(
        f"/requirements/{requirement_id}/analysis/questions/{question.id.value}/answer-suggestions"
    )
    assert response.status_code == 200
    suggestion = response.json()["suggestions"][0]
    assert suggestion["evidence"][0]["fingerprint"]
    assert {item["source"] for item in response.json()["suggestions"]} == {
        "current_analysis",
        "trusted_knowledge",
        "combined",
    }

    resolved = client.post(
        f"/requirements/{requirement_id}/analysis/questions/{question.id.value}/resolution",
        json={
            "answer": f"{suggestion['answer']} Confirmed by the owner.",
            "expected_version": question.version,
            "source_suggestion_id": suggestion["id"],
        },
    )
    assert resolved.status_code == 200
    assert any(
        item["source_suggestion_id"] == suggestion["id"]
        for item in resolved.json()["clarifications"]
    )


def test_re_screening_the_same_input_keeps_an_undecided_finding() -> None:
    """Screening a second time must not discard the first screen's open finding.

    Screening records at most one finding per current pair, so a second screen of
    unchanged input records none. The review used to show only the latest
    screen's findings, which made the Requirement look ready with an undecided
    possible duplicate. The app is built without its lifespan, so no background
    worker screens concurrently: the two screens run in a fixed order.
    """
    container = build_container(FAKE_PROVIDER_SETTINGS)
    application = create_app(lambda: container)
    application.state.container = container
    client = TestClient(application)
    _requirement(client, "XGPON", "Customers order XGPON through BCRM and CPP.")
    candidate_id = _requirement(client, "XGPON", "Customers order XGPON through BCRM and CPP.")
    assert post_analysis(client, candidate_id).status_code == 200
    typed_id = RequirementId(candidate_id)
    for question in container.analysis_audit_repository.list_questions(typed_id):
        container.analysis_audit_repository.save_question(question.supersede())

    screen_current_knowledge(client, candidate_id)
    first = client.get(f"/requirements/{candidate_id}/knowledge-review").json()
    screen_current_knowledge(client, candidate_id)
    second = client.get(f"/requirements/{candidate_id}/knowledge-review").json()

    assert first["status"] == "action_required"
    assert second["status"] == "action_required"
    assert [item["id"] for item in second["findings"]] == [item["id"] for item in first["findings"]]
