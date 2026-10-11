"""External id mapping and safe republish (Slice 13)."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.governance.application.errors import (
    PublicationRetryNotAllowedError,
    PublicationTargetChangedError,
    PublicationTargetError,
)
from smb_requirement_agent.governance.application.publication import (
    PlannedWorkItem,
    PublicationTarget,
    PublishedWorkItem,
)
from smb_requirement_agent.governance.domain.publication.entities import (
    BacklogPublication,
    ExternalWorkItemMapping,
    ItemOutcome,
    ItemResult,
    PublicationOutcome,
    PublicationStatus,
)
from smb_requirement_agent.governance.domain.publication.errors import (
    InvalidPublicationError,
    PublicationInProgressError,
)
from smb_requirement_agent.governance.domain.revision.entities import RevisionNumber
from smb_requirement_agent.governance.infrastructure.publication.fake import FakeBacklogPublisher
from smb_requirement_agent.infrastructure.config.options import AdoPublisher, LLMProvider
from smb_requirement_agent.infrastructure.config.settings import (
    AdoPublicationSettings,
    Settings,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.governance.test_backlog_publication import (
    OWNER,
    RefusingPublisher,
    approved_fingerprint,
    use_cases,
)
from tests.unit.workflow_helpers import approve_fake_breakdown

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
def publishing_container() -> Container:
    return build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            ado_publication=AdoPublicationSettings(publisher=AdoPublisher.FAKE),
        )
    )


@pytest.fixture
def publishing_client(publishing_container: Container) -> Generator[TestClient, None, None]:
    with TestClient(create_app(lambda: publishing_container)) as client:
        yield client


def _publish(client: TestClient, requirement_id: str, revision: int) -> dict[str, Any]:
    path = f"/requirements/{requirement_id}/revisions/{revision}/publication"
    preview = client.get(path).json()
    response = client.post(path, json={"approval_fingerprint": preview["approval_fingerprint"]})
    assert response.status_code == 200, response.text
    report: dict[str, Any] = response.json()
    return report


def test_publishing_twice_creates_nothing_the_second_time(
    publishing_client: TestClient, publishing_container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(publishing_client)
    first = _publish(publishing_client, requirement_id, revision)
    publisher = publishing_container.backlog_publisher
    assert isinstance(publisher, FakeBacklogPublisher)
    created = len(publisher.created)

    preview = publishing_client.get(
        f"/requirements/{requirement_id}/revisions/{revision}/publication"
    ).json()
    second = _publish(publishing_client, requirement_id, revision)

    assert preview["status"] == "published"
    assert preview["published_revision"] == revision
    assert {item["action"] for item in preview["items"]} == {"unchanged"}
    assert all(item["external_id"] for item in preview["items"])
    assert second["outcome"] == "published"
    assert {step["status"] for step in second["steps"]} == {"unchanged"}
    assert [step["external_id"] for step in second["steps"]] == [
        step["external_id"] for step in first["steps"]
    ]
    assert len(publisher.created) == created
    assert publisher.updated == ()


def test_status_keeps_the_mappings_attempts_and_an_empty_product_verdict(
    publishing_client: TestClient,
) -> None:
    requirement_id, stories, revision = approve_fake_breakdown(publishing_client)
    before = publishing_client.get(f"/requirements/{requirement_id}/publication").json()
    _publish(publishing_client, requirement_id, revision)

    status = publishing_client.get(f"/requirements/{requirement_id}/publication").json()

    assert before["status"] == "not_published"
    assert before["latest_approved_revision"] == revision
    assert status["status"] == "published"
    assert status["published_revision"] == revision
    assert status["product_verdict"] is None
    assert status["product_impact_version"] is None
    assert len(status["mappings"]) == 1 + len({story["feature_id"] for story in stories}) + len(
        stories
    )
    (attempt,) = status["attempts"]
    assert attempt["outcome"] == "published"
    assert attempt["actor_name"]
    assert {item["result"] for item in attempt["items"]} == {"created"}


def test_a_retry_continues_where_the_refusal_stopped(
    client: TestClient, container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(client)
    publisher = RefusingPublisher(accepted=2)
    _, publish, retry, status = use_cases(container, publisher)
    fingerprint = approved_fingerprint(container, requirement_id, revision)
    first = publish.execute(
        RequirementId(requirement_id), RevisionNumber(revision), OWNER, fingerprint
    )
    assert first.outcome is PublicationOutcome.PARTIAL
    assert (
        status.execute(RequirementId(requirement_id), OWNER).status is PublicationStatus.INCOMPLETE
    )

    publisher.accepted = 1_000
    second = retry.execute(RequirementId(requirement_id), OWNER)

    assert second.outcome is PublicationOutcome.PUBLISHED
    results = [step.status for step in second.steps]
    assert results[:2] == [ItemResult.UNCHANGED, ItemResult.UNCHANGED]
    assert set(results[2:]) == {ItemResult.CREATED}
    keys = [item.key for item, _, _ in publisher.created]
    assert len(keys) == len(set(keys)) == len(second.steps)
    created_ids = {item.key: done.external_id for item, done, _ in publisher.created}
    for item, _, parent_id in publisher.created:
        assert parent_id == (created_ids[item.parent_key] if item.parent_key else None)
    with pytest.raises(PublicationRetryNotAllowedError):
        retry.execute(RequirementId(requirement_id), OWNER)


def test_nothing_to_retry_before_a_first_publication(
    client: TestClient, container: Container
) -> None:
    requirement_id, _, _ = approve_fake_breakdown(client)
    _, _, retry, _ = use_cases(container, FakeBacklogPublisher())

    with pytest.raises(PublicationRetryNotAllowedError, match="Nothing has been published"):
        retry.execute(RequirementId(requirement_id), OWNER)


def test_changed_content_is_sent_as_an_update_of_the_same_item(
    client: TestClient, container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(client)
    publisher = FakeBacklogPublisher()
    preview, publish, _, _ = use_cases(container, publisher)
    fingerprint = approved_fingerprint(container, requirement_id, revision)
    publish.execute(RequirementId(requirement_id), RevisionNumber(revision), OWNER, fingerprint)
    records = container.publication_records
    record = records.get(RequirementId(requirement_id))
    assert record is not None
    story = next(item for item in record.mappings if item.kind == "story")
    # As if the Story had been edited and approved again since it was published.
    records.save(
        replace(
            record,
            version=record.version + 1,
            mappings=tuple(
                replace(item, content_fingerprint="sha256:older")
                if item.local_key == story.local_key
                else item
                for item in record.mappings
            ),
        )
    )

    planned = preview.execute(RequirementId(requirement_id), RevisionNumber(revision), OWNER)
    report = publish.execute(
        RequirementId(requirement_id), RevisionNumber(revision), OWNER, fingerprint
    )

    assert planned.actions[story.local_key].value == "update"
    by_key = {step.item.key: step for step in report.steps}
    assert by_key[story.local_key].status is ItemResult.UPDATED
    sent = by_key[story.local_key].published
    assert sent is not None
    assert sent.external_id == story.external_id
    assert [external_id for external_id, _ in publisher.updated] == [story.external_id]
    others = {step.status for key, step in by_key.items() if key != story.local_key}
    assert others == {ItemResult.UNCHANGED}
    saved = records.get(RequirementId(requirement_id))
    assert saved is not None
    mapping = saved.mapping_for(story.local_key)
    assert mapping is not None and mapping.content_fingerprint != "sha256:older"


def test_an_interrupted_attempt_is_recovered_by_marker_not_created_twice(
    client: TestClient, container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(client)
    publisher = FakeBacklogPublisher()
    preview, publish, _, _ = use_cases(container, publisher)
    plan = preview.execute(RequirementId(requirement_id), RevisionNumber(revision), OWNER).plan
    epic = plan.items[0]
    # An earlier process created the Epic, then stopped before recording it.
    publisher.create(epic, None)
    past = datetime.now(UTC) - timedelta(hours=1)
    container.publication_records.save(
        BacklogPublication(RequirementId(requirement_id), "fake:local").start(
            revision, "fake-owner", "Fake Owner", past, past + timedelta(minutes=15)
        )
    )

    report = publish.execute(
        RequirementId(requirement_id),
        RevisionNumber(revision),
        OWNER,
        approved_fingerprint(container, requirement_id, revision),
    )

    assert report.steps[0].status is ItemResult.RECOVERED
    assert report.outcome is PublicationOutcome.PUBLISHED
    assert [item.key for item, _, _ in publisher.created].count(epic.key) == 1
    record = container.publication_records.get(RequirementId(requirement_id))
    assert record is not None
    assert record.results[0].outcome is PublicationOutcome.INTERRUPTED


class LostAnswerPublisher(FakeBacklogPublisher):
    """Creates the first item it is sent, then loses the answer, as a timeout would."""

    def __init__(self) -> None:
        super().__init__()
        self.lose_next = True

    def create(self, item: PlannedWorkItem, parent: PublishedWorkItem | None) -> PublishedWorkItem:
        created = super().create(item, parent)
        if self.lose_next:
            self.lose_next = False
            raise PublicationTargetError("Azure DevOps could not be reached (ReadTimeout).")
        return created


def test_a_create_whose_answer_was_lost_is_found_on_retry_not_created_twice(
    client: TestClient, container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(client)
    publisher = LostAnswerPublisher()
    _, publish, retry, _ = use_cases(container, publisher)
    first = publish.execute(
        RequirementId(requirement_id),
        RevisionNumber(revision),
        OWNER,
        approved_fingerprint(container, requirement_id, revision),
    )
    assert first.outcome is PublicationOutcome.FAILED

    second = retry.execute(RequirementId(requirement_id), OWNER)

    assert second.outcome is PublicationOutcome.PUBLISHED
    assert second.steps[0].status is ItemResult.RECOVERED
    keys = [item.key for item, _, _ in publisher.created]
    assert len(keys) == len(set(keys)) == len(second.steps)


def test_a_running_attempt_holds_off_another(
    publishing_client: TestClient, publishing_container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(publishing_client)
    now = datetime.now(UTC)
    publishing_container.publication_records.save(
        BacklogPublication(RequirementId(requirement_id), "fake:local").start(
            revision, "fake-owner", "Fake Owner", now, now + timedelta(minutes=15)
        )
    )
    path = f"/requirements/{requirement_id}/revisions/{revision}/publication"
    preview = publishing_client.get(path).json()

    response = publishing_client.post(
        path, json={"approval_fingerprint": preview["approval_fingerprint"]}
    )

    assert preview["status"] == "in_progress"
    assert response.status_code == 409
    assert response.json()["code"] == "publication_in_progress"


class OtherProjectPublisher(FakeBacklogPublisher):
    def target(self) -> PublicationTarget:
        return replace(super().target(), key="fake:another-project")


def test_a_backlog_published_elsewhere_is_not_duplicated_into_a_new_target(
    client: TestClient, container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(client)
    fingerprint = approved_fingerprint(container, requirement_id, revision)
    _, publish, _, _ = use_cases(container, FakeBacklogPublisher())
    publish.execute(RequirementId(requirement_id), RevisionNumber(revision), OWNER, fingerprint)
    preview, publish_elsewhere, _, _ = use_cases(container, OtherProjectPublisher())

    with pytest.raises(PublicationTargetChangedError):
        preview.execute(RequirementId(requirement_id), RevisionNumber(revision), OWNER)
    with pytest.raises(PublicationTargetChangedError):
        publish_elsewhere.execute(
            RequirementId(requirement_id), RevisionNumber(revision), OWNER, fingerprint
        )


def _mapping(key: str, external_id: str) -> ExternalWorkItemMapping:
    return ExternalWorkItemMapping(key, "story", external_id, "https://t", "sha256:1", 1, NOW)


def test_the_record_reports_status_through_an_attempts_life() -> None:
    record = BacklogPublication(RequirementId("REQ-1"), "fake:local")
    assert record.status(None, NOW) is PublicationStatus.NOT_PUBLISHED

    running = record.start(1, "owner", "Owner", NOW, NOW + timedelta(minutes=15))
    assert running.status(1, NOW) is PublicationStatus.IN_PROGRESS
    assert running.status(1, NOW + timedelta(hours=1)) is PublicationStatus.INCOMPLETE
    with pytest.raises(PublicationInProgressError):
        running.start(1, "owner", "Owner", NOW, NOW + timedelta(minutes=15))

    done = running.record(ItemOutcome("a", ItemResult.CREATED), _mapping("a", "1")).finish(NOW)
    assert done.version == record.version + 3
    assert done.status(1, NOW) is PublicationStatus.PUBLISHED
    assert done.status(2, NOW) is PublicationStatus.OUTDATED
    assert done.published_revision() == 1

    later = NOW + timedelta(hours=1)
    restarted = running.start(1, "owner", "Owner", later, later + timedelta(minutes=15))
    assert restarted.results[0].outcome is PublicationOutcome.INTERRUPTED
    assert restarted.may_hold_unrecorded_items()
    assert not done.start(2, "owner", "Owner", later, later).may_hold_unrecorded_items()


def test_the_record_refuses_duplicate_mappings_and_a_verdict_without_its_version() -> None:
    with pytest.raises(InvalidPublicationError):
        BacklogPublication(
            RequirementId("REQ-1"), "fake:local", mappings=(_mapping("a", "1"), _mapping("b", "1"))
        )
    with pytest.raises(InvalidPublicationError):
        BacklogPublication(
            RequirementId("REQ-1"), "fake:local", mappings=(_mapping("a", "1"), _mapping("a", "2"))
        )
    with pytest.raises(InvalidPublicationError):
        BacklogPublication(
            RequirementId("REQ-1"), "fake:local", product_verdict="existing_offering"
        )
    with pytest.raises(InvalidPublicationError):
        BacklogPublication(RequirementId("REQ-1"), "fake:local").record(
            ItemOutcome("a", ItemResult.CREATED)
        )
    kept = BacklogPublication(
        RequirementId("REQ-1"),
        "fake:local",
        product_verdict="existing_offering",
        product_impact_version="impact-3",
    )
    assert kept.product_impact_version == "impact-3"
