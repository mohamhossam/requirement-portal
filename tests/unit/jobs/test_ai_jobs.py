"""Durable AI job lifecycle and HTTP contract."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobCommand, AiJobRecord
from smb_requirement_agent.jobs.domain.entities import (
    AiJob,
    AiJobFailure,
    AiJobId,
    AiJobOperation,
    AiJobOrigin,
    AiJobStatus,
)
from smb_requirement_agent.jobs.domain.errors import AiJobConflictError
from smb_requirement_agent.jobs.infrastructure.in_memory_ai_jobs import InMemoryAiJobStore
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.job_driver import JobRun
from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    post_analysis,
    post_epic,
    post_epic_approval,
    post_feature_approval,
    post_features,
    post_stories,
)

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
NOW = datetime(2026, 9, 3, 12, tzinfo=UTC)


def _job() -> AiJob:
    return AiJob(
        AiJobId("job-1"),
        RequirementId("requirement-1"),
        AiJobOperation.ANALYSE_REQUIREMENT,
        AiJobStatus.QUEUED,
        ActorSnapshot(ActorId("actor-1"), "Owner"),
        NOW,
        NOW,
        "key-1",
        "fingerprint-1",
    )


def _requirement(client: TestClient) -> str:
    response = client.post(
        "/requirements",
        json={"title": "Async analysis", "description": "Continue after navigation"},
        headers=OWNER,
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _analysis_body(
    client: TestClient, requirement_id: str, *, force: bool = False
) -> dict[str, object]:
    requirement = client.get(f"/requirements/{requirement_id}", headers=OWNER).json()
    return {
        "operation": "analyse_requirement",
        "context_token": requirement["analysis_context_token"],
        "force": force,
    }


def test_job_lifecycle_supports_claim_and_cooperative_cancellation() -> None:
    running = _job().claim(NOW)
    requested = running.request_cancellation(NOW)
    cancelled = requested.cancel(NOW)

    assert running.status is AiJobStatus.RUNNING
    assert running.attempt_count == 1
    assert requested.status is AiJobStatus.CANCELLATION_REQUESTED
    assert cancelled.status is AiJobStatus.CANCELLED
    assert cancelled.completed_at == NOW


def test_job_start_is_idempotent_and_cancel_is_visible(client: TestClient) -> None:
    requirement_id = _requirement(client)
    path = f"/requirements/{requirement_id}/ai-jobs"
    body = _analysis_body(client, requirement_id)

    first = client.post(path, json=body, headers={**OWNER, "Idempotency-Key": "analyse-1"})
    repeated = client.post(path, json=body, headers={**OWNER, "Idempotency-Key": "analyse-1"})
    equivalent = client.post(
        path, json=body, headers={**OWNER, "Idempotency-Key": "analyse-equivalent"}
    )

    assert first.status_code == 202
    assert repeated.status_code == 202
    assert repeated.json()["id"] == first.json()["id"]
    assert equivalent.json()["id"] == first.json()["id"]
    assert first.json()["status"] == "queued"

    listed = client.get(f"{path}?active_only=true", headers=OWNER)
    assert [item["id"] for item in listed.json() if item["operation"] == "analyse_requirement"] == [
        first.json()["id"]
    ]

    cancelled = client.post(
        f"{path}/{first.json()['id']}/cancellation",
        json={"expected_version": first.json()["version"]},
        headers=OWNER,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    repeated_alias = client.post(
        path, json=body, headers={**OWNER, "Idempotency-Key": "analyse-equivalent"}
    )
    assert repeated_alias.status_code == 200
    assert repeated_alias.json()["id"] == first.json()["id"]

    retried = client.post(
        f"{path}/{first.json()['id']}/retry",
        json={"expected_version": cancelled.json()["version"]},
        headers={**OWNER, "Idempotency-Key": "analyse-retry-1"},
    )
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    assert retried.json()["retry_of_job_id"] == first.json()["id"]


def test_anomalous_succeeded_knowledge_job_supports_explicit_user_retry(
    client: TestClient,
    container: Container,
) -> None:
    requirement_id = _requirement(client)
    typed_id = RequirementId(requirement_id)
    automatic = next(
        item.job
        for item in container.ai_job_repository.list_for_requirement(typed_id)
        if item.job.operation is AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE
    )
    running = automatic.claim(NOW)
    container.ai_job_repository.save(running)
    container.ai_job_repository.save(running.succeed((), NOW))
    current = container.ai_job_repository.get(automatic.id)
    assert current is not None

    retried = client.post(
        f"/requirements/{requirement_id}/ai-jobs/{automatic.id.value}/retry",
        json={"expected_version": current.job.version},
        headers={**OWNER, "Idempotency-Key": "anomalous-screen-retry"},
    )

    assert retried.status_code == 202
    assert retried.json()["origin"] == "user"
    assert retried.json()["retry_of_job_id"] == automatic.id.value


def test_idempotency_key_cannot_be_reused_for_different_input(client: TestClient) -> None:
    requirement_id = _requirement(client)
    path = f"/requirements/{requirement_id}/ai-jobs"
    headers = {**OWNER, "Idempotency-Key": "same-key"}
    assert (
        client.post(path, json=_analysis_body(client, requirement_id), headers=headers).status_code
        == 202
    )

    conflict = client.post(
        path, json=_analysis_body(client, requirement_id, force=True), headers=headers
    )

    assert conflict.status_code == 409
    assert "different AI job input" in conflict.json()["message"]


def test_stale_generation_context_is_rejected_before_enqueue(client: TestClient) -> None:
    requirement_id = _requirement(client)
    stale_body = _analysis_body(client, requirement_id)
    requirement = client.get(f"/requirements/{requirement_id}", headers=OWNER).json()
    changed = client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": "Changed before enqueue",
            "description": "The displayed generation context is now stale.",
            "expected_version": requirement["version"],
            "impact_acknowledged": True,
        },
        headers=OWNER,
    )
    assert changed.status_code == 200

    rejected = client.post(
        f"/requirements/{requirement_id}/ai-jobs",
        json=stale_body,
        headers={**OWNER, "Idempotency-Key": "stale-before-enqueue"},
    )

    assert rejected.status_code == 409
    jobs = client.get(f"/requirements/{requirement_id}/ai-jobs", headers=OWNER).json()
    assert all(item["operation"] != "analyse_requirement" for item in jobs)


def test_batch_resolution_job_preserves_answer_count_in_status(client: TestClient) -> None:
    requirement_id = _requirement(client)
    path = f"/requirements/{requirement_id}/ai-jobs"
    answers = [
        {"question_id": "question-1", "answer": "Product", "expected_version": 1},
        {"question_id": "question-2", "answer": "Operations", "expected_version": 2},
    ]
    body = {
        "operation": "resolve_clarification_questions",
        "answers": answers,
    }

    started = client.post(
        path,
        json=body,
        headers={**OWNER, "Idempotency-Key": "resolve-batch-1"},
    )

    assert started.status_code == 202
    assert started.json()["operation"] == "resolve_clarification_questions"
    assert started.json()["item_count"] == 2
    detail = client.get(f"{path}/{started.json()['id']}", headers=OWNER)
    assert detail.json()["item_count"] == 2
    listed = client.get(path, headers=OWNER)
    assert listed.json()[0]["item_count"] == 2

    duplicate = client.post(
        path,
        json={"operation": "resolve_clarification_questions", "answers": [answers[0]] * 2},
        headers={**OWNER, "Idempotency-Key": "resolve-batch-duplicate"},
    )
    assert duplicate.status_code == 422


def test_notification_preferences_are_actor_scoped(client: TestClient) -> None:
    initial = client.get("/notifications/preferences/current", headers=OWNER)
    enabled = client.put(
        "/notifications/preferences/current",
        json={"browser_enabled": True},
        headers=OWNER,
    )

    assert initial.json() == {"browser_enabled": False}
    assert enabled.json() == {"browser_enabled": True}


def test_only_creator_or_requirement_owner_can_control_job(client: TestClient) -> None:
    requirement_id = _requirement(client)
    path = f"/requirements/{requirement_id}/ai-jobs"
    created = client.post(
        path,
        json=_analysis_body(client, requirement_id),
        headers={**OWNER, "Idempotency-Key": "owned-job"},
    )

    denied = client.post(
        f"{path}/{created.json()['id']}/cancellation",
        json={"expected_version": created.json()["version"]},
        headers={"X-Fake-Actor-Id": "fake-reviewer"},
    )

    assert denied.status_code == 403


def test_idempotency_key_reuse_for_another_requirement_is_a_conflict(
    client: TestClient,
) -> None:
    first_id = _requirement(client)
    second_id = _requirement(client)
    headers = {**OWNER, "Idempotency-Key": "actor-key-across-requirements"}
    first = client.post(
        f"/requirements/{first_id}/ai-jobs",
        json=_analysis_body(client, first_id),
        headers=headers,
    )

    conflict = client.post(
        f"/requirements/{second_id}/ai-jobs",
        json=_analysis_body(client, second_id),
        headers=headers,
    )

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "ai_job_conflict"


def test_queue_serializes_jobs_per_requirement_and_recovers_expired_lease() -> None:
    store = InMemoryAiJobStore(RLock())
    first = AiJobRecord(_job(), AiJobCommand({"force": False}))
    second_job = AiJob(
        AiJobId("job-2"),
        first.job.requirement_id,
        AiJobOperation.GENERATE_EPIC,
        AiJobStatus.QUEUED,
        first.job.created_by,
        NOW + timedelta(seconds=1),
        NOW + timedelta(seconds=1),
        "key-2",
        "fingerprint-2",
    )
    store.add(first)
    store.add(AiJobRecord(second_job, AiJobCommand({"force": False})))

    claimed = store.claim_next("worker-a", NOW, NOW + timedelta(seconds=30))
    blocked = store.claim_next("worker-b", NOW + timedelta(seconds=2), NOW + timedelta(seconds=32))
    recovered = store.claim_next(
        "worker-b", NOW + timedelta(seconds=31), NOW + timedelta(seconds=61)
    )

    assert claimed is not None and claimed.job.id == first.job.id
    assert blocked is None
    assert recovered is not None and recovered.job.id == first.job.id
    assert recovered.job.attempt_count == 2


def test_queue_prioritizes_user_work_over_older_automatic_work() -> None:
    store = InMemoryAiJobStore(RLock())
    automatic = replace(
        _job(),
        id=AiJobId("automatic-job"),
        requirement_id=RequirementId("automatic-requirement"),
        origin=AiJobOrigin.AUTOMATIC,
    )
    user = replace(
        _job(),
        id=AiJobId("user-job"),
        requirement_id=RequirementId("user-requirement"),
        created_at=NOW + timedelta(seconds=1),
        updated_at=NOW + timedelta(seconds=1),
        idempotency_key="user-key",
        command_fingerprint="user-fingerprint",
    )
    store.add(AiJobRecord(automatic, AiJobCommand({})))
    store.add(AiJobRecord(user, AiJobCommand({})))

    claimed = store.claim_next("worker", NOW + timedelta(seconds=2), NOW + timedelta(seconds=32))

    assert claimed is not None
    assert claimed.job.id == user.id


def test_queue_recovers_expired_cancellation_request_for_worker_cleanup() -> None:
    store = InMemoryAiJobStore(RLock())
    store.add(AiJobRecord(_job(), AiJobCommand({"force": False})))
    claimed = store.claim_next("worker-a", NOW, NOW + timedelta(seconds=30))
    assert claimed is not None
    store.save(claimed.job.request_cancellation(NOW + timedelta(seconds=1)))

    recovered = store.claim_next(
        "worker-b", NOW + timedelta(seconds=31), NOW + timedelta(seconds=61)
    )

    assert recovered is not None
    assert recovered.job.status is AiJobStatus.CANCELLATION_REQUESTED
    assert recovered.job.attempt_count == 1


def test_fenced_attempt_is_reclaimable_and_old_attempt_cannot_write() -> None:
    store = InMemoryAiJobStore(RLock())
    store.add(AiJobRecord(_job(), AiJobCommand({"force": False})))
    first = store.claim_next("worker-a", NOW, NOW + timedelta(seconds=30))
    assert first is not None and first.attempt_token is not None
    assert store.fence_attempt(first.job.id, "worker-a", first.attempt_token)

    reclaimed = store.claim_next(
        "worker-b", NOW + timedelta(seconds=1), NOW + timedelta(seconds=31)
    )
    assert reclaimed is not None and reclaimed.attempt_token is not None
    stale_progress = first.job.report_progress("provider", 1, 2, None, NOW)
    stale_completion = first.job.succeed((), NOW)

    assert not store.report_progress_fenced(stale_progress, "worker-a", first.attempt_token, NOW)
    assert not store.save_fenced(stale_completion, "worker-a", first.attempt_token, NOW)
    assert store.save_fenced(
        reclaimed.job.succeed((), NOW + timedelta(seconds=2)),
        "worker-b",
        reclaimed.attempt_token,
        NOW + timedelta(seconds=2),
    )


def test_deferred_attempt_is_not_consumed_and_only_a_running_job_defers() -> None:
    running = _job().claim(NOW)
    deferred = running.defer(NOW + timedelta(seconds=1))

    assert deferred.status is AiJobStatus.QUEUED
    assert deferred.attempt_count == 0
    assert deferred.started_at is None and deferred.phase is None
    assert deferred.version == running.version + 1
    recovered = replace(running, attempt_count=2)
    assert recovered.defer(NOW).attempt_count == 1
    assert recovered.defer(NOW).started_at == running.started_at
    for job in (
        _job(),
        running.request_cancellation(NOW),
        running.fail(AiJobFailure("code", "Failed.", True, "correlation"), NOW),
    ):
        with pytest.raises(AiJobConflictError):
            job.defer(NOW)


def test_fenced_deferral_releases_lease_and_stale_attempt_cannot_defer() -> None:
    store = InMemoryAiJobStore(RLock())
    store.add(AiJobRecord(_job(), AiJobCommand({"force": False})))
    first = store.claim_next("worker-a", NOW, NOW + timedelta(seconds=30))
    assert first is not None and first.attempt_token is not None

    assert not store.save_fenced(first.job.defer(NOW), "worker-a", "other-attempt", NOW)
    assert store.save_fenced(first.job.defer(NOW), "worker-a", first.attempt_token, NOW)
    queued = store.get(first.job.id)
    assert queued is not None and queued.job.status is AiJobStatus.QUEUED
    assert queued.worker_id is None and queued.attempt_token is None
    assert not store.heartbeat(
        first.job.id, "worker-a", first.attempt_token, NOW, NOW + timedelta(seconds=30)
    )

    reclaimed = store.claim_next("worker-b", NOW, NOW + timedelta(seconds=30))
    assert reclaimed is not None and reclaimed.job.id == first.job.id
    assert reclaimed.job.attempt_count == 1
    assert reclaimed.attempt_token != first.attempt_token


def test_stale_attempt_and_synchronous_analysis_cannot_report_new_attempt_progress() -> None:
    from datetime import timedelta

    from smb_kernel.time.fixed import FixedClock

    from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobCommand, AiJobRecord
    from smb_requirement_agent.jobs.application.use_cases.job_execution_context import bind_attempt
    from smb_requirement_agent.workflows.application.use_cases.ai_jobs import (
        AnalysisProgressReporter,
    )

    jobs = InMemoryAiJobStore(RLock())
    jobs.add(AiJobRecord(_job(), AiJobCommand({})))
    first = jobs.claim_next("worker-old", NOW, NOW + timedelta(seconds=1))
    assert first is not None
    later = NOW + timedelta(seconds=2)
    replacement = jobs.claim_next("worker-new", later, later + timedelta(seconds=30))
    assert replacement is not None
    reporter = AnalysisProgressReporter(jobs, FixedClock(later))
    with bind_attempt(first):
        reporter.report(first.job.requirement_id, "stale", 1, 2, None)
    reporter.report(first.job.requirement_id, "synchronous", 1, 2, None)
    assert jobs.get(first.job.id) == replacement
    with bind_attempt(replacement):
        reporter.report(first.job.requirement_id, "current", 1, 2, None)
    updated = jobs.get(first.job.id)
    assert updated is not None
    assert updated.job.phase == "current"


def _analysis_jobs(client: TestClient, requirement_id: str) -> list[str]:
    listed = client.get(f"/requirements/{requirement_id}/ai-jobs", headers=OWNER)
    assert listed.status_code == 200
    return [item["id"] for item in listed.json() if item["operation"] == "analyse_requirement"]


def test_re_analysis_is_refused_before_enqueue_unless_forced(client: TestClient) -> None:
    requirement_id = _requirement(client)
    path = f"/requirements/{requirement_id}/ai-jobs"
    before = _analysis_body(client, requirement_id)
    first = client.post(path, json=before, headers={**OWNER, "Idempotency-Key": "first"})
    assert first.status_code == 202
    cancelled = client.post(
        f"{path}/{first.json()['id']}/cancellation",
        json={"expected_version": first.json()["version"]},
        headers=OWNER,
    )
    assert cancelled.status_code == 200
    analysed = post_analysis(client, requirement_id, headers=OWNER)
    assert analysed.succeeded
    queued = sorted([first.json()["id"], analysed.start.json()["id"]])

    # The worker could only fail this: an analysis exists and force was not asked for.
    again = client.post(
        path,
        json=_analysis_body(client, requirement_id),
        headers={**OWNER, "Idempotency-Key": "again"},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "requirement_analysis_conflict"
    assert sorted(_analysis_jobs(client, requirement_id)) == queued

    # A replayed key still answers with the job it started, before any new check runs.
    replayed = client.post(path, json=before, headers={**OWNER, "Idempotency-Key": "first"})
    assert replayed.status_code == 200
    assert replayed.json()["id"] == first.json()["id"]

    forced = client.post(
        path,
        json=_analysis_body(client, requirement_id, force=True),
        headers={**OWNER, "Idempotency-Key": "forced"},
    )
    assert forced.status_code == 202
    assert forced.json()["status"] == "queued"


def test_analysis_of_an_ineligible_requirement_is_refused_before_enqueue(
    client: TestClient,
) -> None:
    source = client.post(
        "/requirements/drafts", json={"title": "Online bundles", "description": ""}
    ).json()
    document = client.post(
        f"/requirement-drafts/{source['id']}/attachments",
        data={"include_in_analysis": "true"},
        files={"file": ("need.md", b"Enable ordering.", "text/markdown")},
    ).json()
    promoted = client.post(
        f"/requirements/drafts/{source['id']}/promote", json={"expected_version": source["version"]}
    ).json()
    current = client.get(f"/documents/{document['id']}").json()
    excluded = client.put(
        f"/requirements/{promoted['id']}/attachments/{document['id']}/analysis-inclusion",
        json={"included": False, "expected_version": current["version"]},
    )
    assert excluded.status_code == 200

    response = client.post(
        f"/requirements/{promoted['id']}/ai-jobs",
        json=_analysis_body(client, promoted["id"]),
        headers={**OWNER, "Idempotency-Key": "ineligible"},
    )

    assert response.status_code == 422
    assert _analysis_jobs(client, promoted["id"]) == []


def _jobs_of(client: TestClient, requirement_id: str, operation: str) -> int:
    jobs = client.get(f"/requirements/{requirement_id}/ai-jobs", headers=OWNER).json()
    return sum(1 for item in jobs if item["operation"] == operation)


def _refused(run: JobRun, code: str) -> None:
    assert run.job is None, run.job
    assert run.start.status_code == 409, run.start.text
    assert run.start.json()["code"] == code


def test_breakdown_generation_that_can_only_fail_is_refused_before_enqueue(
    client: TestClient,
) -> None:
    """Epic, Features and first Stories refuse at start what the worker could only fail."""
    requirement_id = _requirement(client)
    assert post_analysis(client, requirement_id, headers=OWNER).succeeded

    _refused(post_epic(client, requirement_id, headers=OWNER), "analysis_confirmation_required")
    assert _jobs_of(client, requirement_id, "generate_epic") == 0

    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id, headers=OWNER).succeeded
    _refused(post_features(client, requirement_id, headers=OWNER), "epic_not_approved")
    assert _jobs_of(client, requirement_id, "generate_features") == 0

    assert post_epic_approval(client, requirement_id, headers=OWNER).status_code == 200
    _refused(post_epic(client, requirement_id, headers=OWNER), "epic_regeneration_conflict")
    assert _jobs_of(client, requirement_id, "generate_epic") == 1

    assert post_features(client, requirement_id, headers=OWNER).succeeded
    features = client.get(f"/requirements/{requirement_id}/features", headers=OWNER).json()
    feature_id = features["features"][0]["id"]
    assert (
        post_feature_approval(client, requirement_id, feature_id, headers=OWNER).status_code == 200
    )
    assert post_stories(client, requirement_id, feature_id, headers=OWNER).succeeded
    _refused(
        post_stories(client, requirement_id, feature_id, headers=OWNER), "stories_already_exist"
    )
    assert _jobs_of(client, requirement_id, "generate_stories") == 1
