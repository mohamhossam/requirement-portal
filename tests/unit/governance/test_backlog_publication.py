"""Previewing and publishing an approved backlog to a work-item tracker (Slice 12)."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.governance.application.errors import PublicationTargetError
from smb_requirement_agent.governance.application.exports import (
    ExportActor,
    ExportApproval,
    ExportArchitecture,
    ExportCounts,
    ExportEpic,
    ExportFeature,
    ExportManifest,
    ExportOrganisationReference,
    ExportProvenance,
    ExportStory,
    ExportSystem,
    NeutralBacklogExport,
)
from smb_requirement_agent.governance.application.publication import (
    TITLE_LIMIT,
    PlannedWorkItem,
    PublicationOutcome,
    PublicationStepStatus,
    PublicationTarget,
    PublishedWorkItem,
    SquadLocation,
    WorkItemKind,
    publication_plan,
)
from smb_requirement_agent.governance.application.use_cases.publish_breakdown import (
    PublishBreakdown,
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
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.workflow_helpers import approve_fake_breakdown

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
OWNER = ActorProfile(ActorId("fake-owner"), "Fake Owner")


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


def _path(requirement_id: str, revision: int) -> str:
    return f"/requirements/{requirement_id}/revisions/{revision}/publication"


def test_preview_shows_target_counts_and_hierarchy(publishing_client: TestClient) -> None:
    requirement_id, stories, revision = approve_fake_breakdown(publishing_client)

    response = publishing_client.get(_path(requirement_id, revision))

    assert response.status_code == 200
    preview = response.json()
    assert preview["revision"] == revision
    assert preview["target"]["system"] == "Offline stand-in"
    assert preview["counts"]["epics"] == 1
    assert preview["counts"]["stories"] == len(stories)
    items = preview["items"]
    assert items[0]["kind"] == "epic" and items[0]["parent_key"] is None
    keys = {item["key"] for item in items}
    seen: set[str] = set()
    for item in items:
        assert item["parent_key"] is None or item["parent_key"] in seen
        seen.add(item["key"])
    assert keys == seen
    assert all(item["location"] == "Local" for item in items)
    first_story = next(item for item in items if item["kind"] == "story")
    assert first_story["label"] == "Story 1.1"
    assert first_story["acceptance_criteria_count"] >= 1


def test_owner_publishes_every_item_under_its_parent(
    publishing_client: TestClient, publishing_container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(publishing_client)
    preview = publishing_client.get(_path(requirement_id, revision)).json()

    response = publishing_client.post(
        _path(requirement_id, revision),
        json={"approval_fingerprint": preview["approval_fingerprint"]},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["outcome"] == "published"
    assert [step["key"] for step in report["steps"]] == [item["key"] for item in preview["items"]]
    assert all(step["status"] == "published" and step["url"] for step in report["steps"])
    publisher = publishing_container.backlog_publisher
    assert isinstance(publisher, FakeBacklogPublisher)
    ids = {item.key: created.external_id for item, created, _ in publisher.created}
    for item, _, parent_id in publisher.created:
        assert parent_id == (ids[item.parent_key] if item.parent_key else None)


def test_publication_needs_the_previewed_approval_and_the_owner(
    publishing_client: TestClient, publishing_container: Container
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(publishing_client)
    preview = publishing_client.get(_path(requirement_id, revision)).json()
    access = publishing_client.get(f"/requirements/{requirement_id}/assignments").json()
    assert (
        publishing_client.put(
            f"/requirements/{requirement_id}/reviewers/fake-reviewer",
            json={"expected_version": access["version"]},
        ).status_code
        == 200
    )
    reviewer = {"X-Fake-Actor-Id": "fake-reviewer"}

    stale = publishing_client.post(
        _path(requirement_id, revision), json={"approval_fingerprint": "an-older-approval"}
    )
    by_reviewer = publishing_client.post(
        _path(requirement_id, revision),
        json={"approval_fingerprint": preview["approval_fingerprint"]},
        headers=reviewer,
    )

    assert stale.status_code == 409
    assert stale.json()["code"] == "publication_confirmation_mismatch"
    assert (
        publishing_client.get(_path(requirement_id, revision), headers=reviewer).status_code == 200
    )
    assert by_reviewer.status_code == 403
    publisher = publishing_container.backlog_publisher
    assert isinstance(publisher, FakeBacklogPublisher)
    assert publisher.created == ()


def test_an_unapproved_revision_is_not_publishable(publishing_client: TestClient) -> None:
    requirement_id = publishing_client.post(
        "/requirements", json={"title": "Draft only", "description": "Nothing approved yet."}
    ).json()["id"]

    missing = publishing_client.get(_path(requirement_id, 1))

    assert missing.status_code == 404


def test_without_a_publisher_the_preview_says_it_is_not_set_up(client: TestClient) -> None:
    requirement_id, _, revision = approve_fake_breakdown(client)

    response = client.get(_path(requirement_id, revision))

    assert response.status_code == 503
    assert response.json()["code"] == "publication_unavailable"


class FailingPublisher:
    """Accepts the first `accepted` items, then refuses."""

    def __init__(self, accepted: int) -> None:
        self._accepted = accepted
        self.calls: list[str] = []

    def target(self) -> PublicationTarget:
        return PublicationTarget("Tracker", "Project", "Project", ())

    def create(self, item: PlannedWorkItem, parent: PublishedWorkItem | None) -> PublishedWorkItem:
        self.calls.append(item.key)
        if len(self.calls) > self._accepted:
            raise PublicationTargetError("The tracker refused the item (400).")
        return PublishedWorkItem(item.key, str(len(self.calls)), f"https://t/{len(self.calls)}")


@pytest.mark.parametrize(
    ("accepted", "outcome"),
    [(0, PublicationOutcome.FAILED), (2, PublicationOutcome.PARTIAL)],
)
def test_a_refused_item_stops_publication_and_reports_what_was_created(
    client: TestClient, container: Container, accepted: int, outcome: PublicationOutcome
) -> None:
    requirement_id, _, revision = approve_fake_breakdown(client)
    publisher = FailingPublisher(accepted)
    use_case = PublishBreakdown(
        container.requirement_repository,
        container.requirement_access,
        container.breakdown_repository,
        publisher,
    )
    saved = container.breakdown_repository.get_breakdown_revision(
        RequirementId(requirement_id), RevisionNumber(revision)
    )
    assert saved is not None and saved.review is not None
    fingerprint = saved.review.submitted_fingerprint
    assert fingerprint is not None

    report = use_case.execute(
        RequirementId(requirement_id), RevisionNumber(revision), OWNER, fingerprint
    )

    assert report.outcome is outcome
    statuses = [step.status for step in report.steps]
    assert statuses[:accepted] == [PublicationStepStatus.PUBLISHED] * accepted
    assert statuses[accepted] is PublicationStepStatus.FAILED
    assert report.steps[accepted].error == "The tracker refused the item (400)."
    assert set(statuses[accepted + 1 :]) == {PublicationStepStatus.NOT_ATTEMPTED}
    assert len(publisher.calls) == accepted + 1


def _system(system_id: str, *squads: str) -> ExportSystem:
    return ExportSystem(
        id=system_id,
        name=system_id.upper(),
        catalogued=True,
        capabilities=(),
        squads=tuple(ExportOrganisationReference(squad, squad.title()) for squad in squads),
        value_streams=(),
        products=(),
    )


def _architecture(*systems: ExportSystem) -> ExportArchitecture:
    return ExportArchitecture(
        knowledge_version="v1",
        mapped_at=NOW,
        systems=systems,
        dependencies=(),
    )


def _feature(sequence: int, architecture: ExportArchitecture | None) -> ExportFeature:
    provenance = ExportProvenance(NOW, "fake", "v1")
    return ExportFeature(
        sequence=sequence,
        id=f"feature-{sequence}",
        epic_id="epic-1",
        name=f"Feature {sequence}",
        outcome="Customers can order online.",
        delivery_drop="MVP",
        splitting_pattern="channel",
        splitting_rationale="Online first.",
        status="approved",
        provenance=provenance,
        architecture=architecture,
        stories=(
            ExportStory(
                sequence=1,
                id=f"story-{sequence}-1",
                feature_id=f"feature-{sequence}",
                role="customer",
                action="order " + "a line " * 60,
                value="I get service",
                voice="As a customer, I want to order a line, so that I get service.",
                status="approved",
                provenance=provenance,
                acceptance_criteria=(),
                architecture=None,
            ),
        ),
    )


def _document(*features: ExportFeature) -> NeutralBacklogExport:
    return NeutralBacklogExport(
        schema_version="1.5",
        manifest=ExportManifest(
            requirement_id="req-1",
            breakdown_revision=3,
            revision_created_at=NOW,
            final_approval=ExportApproval(
                "approval-1", "fingerprint-1", ExportActor("owner", "Owner", None), NOW, None
            ),
            counts=ExportCounts(1, len(features), len(features), 0),
        ),
        epic=ExportEpic(
            id="epic-1",
            requirement_id="req-1",
            name="Online ordering",
            outcome="Orders move online.",
            business_case="Fewer calls.",
            status="approved",
            provenance=ExportProvenance(NOW, "fake", "v1"),
            features=features,
        ),
    )


def test_a_feature_belongs_to_a_squad_only_when_one_squad_owns_its_systems() -> None:
    plan = publication_plan(
        _document(
            _feature(1, _architecture(_system("crm", "billing"), _system("bss", "billing"))),
            _feature(2, _architecture(_system("crm", "billing"), _system("bss", "network"))),
            _feature(3, None),
        )
    )

    by_key = {item.key: item for item in plan.items}
    assert by_key["feature-1"].owning_squad_id == "billing"
    assert by_key["story-1-1"].owning_squad_id == "billing"
    assert by_key["feature-2"].owning_squad_id is None
    assert by_key["feature-3"].owning_squad_id is None
    assert plan.approval_fingerprint == "fingerprint-1"
    assert [item.kind for item in plan.items][:3] == [
        WorkItemKind.EPIC,
        WorkItemKind.FEATURE,
        WorkItemKind.STORY,
    ]
    target = PublicationTarget(
        "Tracker", "SMB", "SMB", (), (SquadLocation("billing", "SMB\\Billing"),)
    )
    assert target.location_for("billing") == "SMB\\Billing"
    assert target.location_for("network") == "SMB"
    assert target.location_for(None) == "SMB"


def test_long_story_titles_are_cut_to_one_tracker_line() -> None:
    plan = publication_plan(_document(_feature(1, None)))

    story = next(item for item in plan.items if item.kind is WorkItemKind.STORY)
    assert len(story.title) <= TITLE_LIMIT
    assert story.title.endswith("…")
    assert "\n" not in story.title
    assert story.description == (
        ("Story", "As a customer, I want to order a line, so that I get service."),
    )
