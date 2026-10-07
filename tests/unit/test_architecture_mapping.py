"""Mapping a Requirement's backlog to systems: domain, application, persistence and API.

Matching runs in the knowledge service (ADR-0099). Requirement work asks it
through `ArchitectureKnowledgePort` and learns which catalogue release is active
from its local copy, fed by the service's events. Here `Catalogue` stands in for
the service's matching and `PublishedLibrary` for its event feed. Catalogue
editing, publishing and the matcher itself are tested in knowledge-portal.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
    MapFeatureArchitecture,
    MapStoryArchitecture,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureDependency,
    ArchitectureImpact,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.errors import InvalidArchitectureContentError
from smb_requirement_agent.identity.application.ports.identity import Actor
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.knowledge_client import OFFLINE_RELEASE_ID
from smb_requirement_agent.infrastructure.persistence.backlog_payloads import (
    feature_from_payload,
    feature_to_payload,
    story_from_payload,
    story_to_payload,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.conftest import FAKE_PROVIDER_SETTINGS, make_event_publisher
from tests.knowledge_doubles import PublishedLibrary, service_for, sync
from tests.unit.workflow_helpers import (
    confirm_fake_analysis,
    post_analysis,
    post_epic,
    post_epic_approval,
    post_feature_approval,
    post_features,
    post_stories,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class RecordingKnowledge:
    def __init__(self) -> None:
        self.queries: list[ArchitectureQuery] = []

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        self.queries.append(query)
        return ArchitectureKnowledgeMatch("test-v1", (), ())


BCRM = SystemReference(
    "bcrm", "BCRM", True, (SystemCapability("assisted-sales", "Assisted sales"),)
)


class Catalogue:
    """The knowledge service's matching, as requirement work sees it.

    Declared systems it knows are catalogued, others are not; BCRM orders through
    any other declared system. It answers for the release a query pins, or for
    the release it has active, as the service does.
    """

    def __init__(self) -> None:
        self.active = OFFLINE_RELEASE_ID
        self.queries: list[ArchitectureQuery] = []

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        self.queries.append(query)
        systems = tuple(
            BCRM if name == BCRM.name else SystemReference(name.lower(), name, False)
            for name in query.declared_systems
        )
        dependencies = tuple(
            ArchitectureDependency(BCRM.id, item.id, f"BCRM orders through {item.name}.")
            for item in systems
            if BCRM in systems and item != BCRM
        )
        return ArchitectureKnowledgeMatch(
            query.release_id or self.active,
            systems,
            dependencies,
        )


@pytest.fixture
def catalogue() -> Catalogue:
    return Catalogue()


@pytest.fixture
def library() -> PublishedLibrary:
    return PublishedLibrary()


@pytest.fixture
def container(catalogue: Catalogue, library: PublishedLibrary) -> Container:
    """The conftest client serves this graph: matching by `catalogue`, events by `library`."""
    return build_container(
        FAKE_PROVIDER_SETTINGS,
        architecture_knowledge=catalogue,
        knowledge_service=service_for(library),
    )


def _activate(
    container: Container, catalogue: Catalogue, library: PublishedLibrary, release_id: str
) -> None:
    """The knowledge service activates a release; requirement work's copy follows its event."""
    catalogue.active = release_id
    library.activate_release(release_id, f"Release {release_id}")
    sync(container)
    assert container.current_release.active_release_id() == release_id


def _tree(client: TestClient) -> tuple[str, list[dict[str, object]], list[dict[str, object]]]:
    requirement_id = client.post(
        "/requirements",
        json={
            "title": "Channel ordering",
            "description": "Allow assisted ordering and activation.",
            "systems": ["BCRM", "CPP"],
        },
    ).json()["id"]
    assert post_analysis(client, requirement_id).status_code == 200
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id).status_code == 201
    assert post_epic_approval(client, requirement_id).status_code == 200
    features = post_features(client, requirement_id).json()["features"]
    feature_id = features[0]["id"]
    assert post_feature_approval(client, requirement_id, feature_id).status_code == 200
    stories = post_stories(client, requirement_id, feature_id).json()["stories"]
    return str(requirement_id), features, stories


def test_architecture_impact_distinguishes_empty_mapping_and_cross_system() -> None:
    empty = ArchitectureImpact("v1", NOW, ())
    assert empty.systems == ()
    assert empty.cross_system is False

    systems = (
        SystemReference("one", "One", True),
        SystemReference("two", "Two", True),
    )
    mapped = ArchitectureImpact(
        "v1", NOW, systems, (ArchitectureDependency("one", "two", "One calls Two."),)
    )
    assert mapped.cross_system is True

    with pytest.raises(InvalidArchitectureContentError, match="connect systems"):
        ArchitectureImpact(
            "v1", NOW, systems[:1], (ArchitectureDependency("one", "two", "Missing target"),)
        )


def test_application_mappers_use_item_text_and_preserve_review_state(
    client: TestClient, container: Container
) -> None:
    _tree(client)
    requirement = container.requirement_repository.list_all()[0]
    epic = container.epic_repository.get_by_requirement_id(requirement.id)
    assert epic is not None
    feature = container.feature_repository.get_by_epic_id(epic.id)[0]
    story = container.story_repository.get_by_feature_id(feature.id)[0]
    knowledge = RecordingKnowledge()

    mapped_feature = MapFeatureArchitecture(knowledge).execute(requirement, feature, NOW).feature
    mapped_story = MapStoryArchitecture(knowledge).execute(requirement, feature, story, NOW).story

    assert mapped_feature.status is feature.status
    assert mapped_feature.provenance is feature.provenance
    assert mapped_story.status is story.status
    assert mapped_story.provenance is story.provenance
    assert knowledge.queries[0].declared_systems == ("BCRM", "CPP")
    assert feature.name.value in knowledge.queries[0].text
    assert story.voice in knowledge.queries[1].text
    assert all(
        "This is an assumption" not in text for query in knowledge.queries for text in query.text
    )


def test_whole_breakdown_mapping_accepts_empty_matches(
    client: TestClient, container: Container
) -> None:
    _tree(client)
    knowledge = RecordingKnowledge()
    mapper = MapBreakdownArchitecture(
        container.requirement_repository,
        container.analysis_repository,
        container.epic_repository,
        container.feature_repository,
        container.story_repository,
        container.transaction_manager,
        MapFeatureArchitecture(knowledge),
        MapStoryArchitecture(knowledge),
        container.clock,
        make_event_publisher(
            reviews=container.breakdown_review_repository,
            transactions=container.transaction_manager,
        ),
        authorization=container.requirement_access,
    )
    requirement = container.requirement_repository.list_all()[0]

    result = mapper.execute(FAKE_ACTORS[0], requirement.id)

    assert len(result.features) == 2
    assert all(mapping.impact.systems == () for mapping in result.features)
    assert all(
        story.impact.systems == () for mapping in result.features for story in mapping.stories
    )
    assert len(knowledge.queries) == 4


def test_snapshot_round_trip_preserves_architecture_and_accepts_legacy_payload(
    client: TestClient,
    container: Container,
) -> None:
    requirement_id, features, stories = _tree(client)
    assert client.post(f"/requirements/{requirement_id}/architecture-mapping").status_code == 200
    epic = container.epic_repository.get_by_requirement_id(
        container.requirement_repository.list_all()[0].id
    )
    assert epic is not None
    feature = container.feature_repository.get_by_epic_id(epic.id)[0]
    story = container.story_repository.get_by_feature_id(feature.id)[0]

    assert feature_from_payload(feature_to_payload(feature)) == feature
    assert story_from_payload(story_to_payload(story)) == story

    legacy_feature = feature_to_payload(feature)
    legacy_feature.pop("architecture")
    legacy_story = story_to_payload(story)
    legacy_story.pop("architecture")
    assert feature_from_payload(legacy_feature).architecture is None
    assert story_from_payload(legacy_story).architecture is None
    assert features and stories


def test_mapping_endpoint_persists_hierarchy_and_uncatalogued_systems(
    client: TestClient, container: Container
) -> None:
    requirement_id, features, stories = _tree(client)

    response = client.post(f"/requirements/{requirement_id}/architecture-mapping")

    assert response.status_code == 200
    result = response.json()
    assert len(result["features"]) == 2
    first = result["features"][0]
    assert first["feature_id"] == features[0]["id"]
    assert len(first["stories"]) == len(stories)
    assert first["architecture"]["cross_system"] is True
    assert {item["name"] for item in first["architecture"]["systems"]} >= {"BCRM", "CPP"}
    assert (
        next(item for item in first["architecture"]["systems"] if item["name"] == "CPP")[
            "catalogued"
        ]
        is False
    )

    feature_set = client.get(f"/requirements/{requirement_id}/features").json()
    story_set = client.get(
        f"/requirements/{requirement_id}/features/{features[0]['id']}/stories"
    ).json()
    assert feature_set["features"][0]["architecture"] is not None
    assert story_set["stories"][0]["architecture"] is not None

    repeated = client.post(f"/requirements/{requirement_id}/architecture-mapping")
    assert repeated.status_code == 200

    revisions = container.breakdown_repository.list_breakdown_revisions(
        container.requirement_repository.list_all()[0].id
    )
    assert revisions[-1].features[0].architecture is not None


def test_mapping_requires_confirmed_current_breakdown(client: TestClient) -> None:
    requirement_id = client.post(
        "/requirements", json={"title": "Not ready", "description": "No analysis"}
    ).json()["id"]
    response = client.post(f"/requirements/{requirement_id}/architecture-mapping")
    assert response.status_code == 409
    assert "human-confirmed analysis" in response.json()["message"]

    missing = client.post("/requirements/missing/architecture-mapping")
    assert missing.status_code == 404


def test_story_edit_clears_mapping_and_stale_story_blocks_refresh(client: TestClient) -> None:
    requirement_id, features, stories = _tree(client)
    feature_id = str(features[0]["id"])
    story = stories[0]
    assert client.post(f"/requirements/{requirement_id}/architecture-mapping").status_code == 200
    story = client.get(f"/requirements/{requirement_id}/features/{feature_id}/stories").json()[
        "stories"
    ][0]

    edited = client.put(
        f"/requirements/{requirement_id}/features/{feature_id}/stories/{story['id']}",
        json={
            "role": story["role"],
            "action": story["action"],
            "value": "a human-owned outcome",
            "acceptance_criteria": story["acceptance_criteria"],
            "expected_version": story["version"],
        },
    )
    assert edited.status_code == 200
    assert edited.json()["architecture"] is None
    assert client.post(f"/requirements/{requirement_id}/architecture-mapping").status_code == 200

    feature = client.get(f"/requirements/{requirement_id}/features").json()["features"][0]
    changed = client.put(
        f"/requirements/{requirement_id}/features/{feature_id}",
        json={
            "name": feature["name"],
            "outcome": "A changed Feature outcome",
            "delivery_drop": feature["delivery_drop"],
            "splitting_pattern": feature["splitting_pattern"],
            "splitting_rationale": feature["splitting_rationale"],
            "expected_version": feature["version"],
        },
    )
    assert changed.status_code == 200
    assert changed.json()["architecture"] is None
    preserved_story = client.get(
        f"/requirements/{requirement_id}/features/{feature_id}/stories"
    ).json()["stories"][0]
    assert preserved_story["architecture"] is not None
    assert preserved_story["stale"] is not None
    blocked = client.post(f"/requirements/{requirement_id}/architecture-mapping")
    assert blocked.status_code == 409
    assert "stale" in blocked.json()["message"]


def test_mapping_pins_one_release_for_the_whole_breakdown(
    client: TestClient, catalogue: Catalogue
) -> None:
    requirement_id, _, _ = _tree(client)
    catalogue.queries.clear()

    mapped = client.post(f"/requirements/{requirement_id}/architecture-mapping")

    assert mapped.status_code == 200
    # The first query takes the service's active release; every later one pins it.
    assert catalogue.queries[0].release_id is None
    assert {query.release_id for query in catalogue.queries[1:]} == {OFFLINE_RELEASE_ID}
    features = mapped.json()["features"]
    versions = {item["architecture"]["knowledge_version"] for item in features} | {
        story["architecture"]["knowledge_version"] for item in features for story in item["stories"]
    }
    assert versions == {OFFLINE_RELEASE_ID}


def test_activating_a_release_makes_the_review_stale_until_the_breakdown_is_remapped(
    client: TestClient,
    container: Container,
    catalogue: Catalogue,
    library: PublishedLibrary,
) -> None:
    requirement_id, _, _ = _tree(client)
    review_url = f"/requirements/{requirement_id}/breakdown-review"
    assert client.post(f"/requirements/{requirement_id}/architecture-mapping").status_code == 200
    reviewed = client.post(review_url)
    assert reviewed.status_code == 200 and reviewed.json()["fresh"] is True

    _activate(container, catalogue, library, "release-2")

    assert client.get(review_url).json()["fresh"] is False
    refused = client.post(review_url)
    assert refused.status_code == 409
    assert "inactive knowledge release" in refused.json()["message"]
    remapped = client.post(f"/requirements/{requirement_id}/architecture-mapping")
    assert remapped.status_code == 200
    assert remapped.json()["features"][0]["architecture"]["knowledge_version"] == "release-2"
    review = client.post(review_url)
    assert review.status_code == 200
    assert review.json()["fresh"] is True


def test_mapping_job_pins_release_and_review_rejects_outdated_architecture(
    client: TestClient,
    container: Container,
    catalogue: Catalogue,
    library: PublishedLibrary,
) -> None:
    requirement_id, _, _ = _tree(client)
    job = container.architecture_mapping_jobs.enqueue(
        RequirementId(requirement_id),
        Actor("fake-owner", frozenset({"knowledge_reader", "knowledge_maintainer"})),
    )
    _activate(container, catalogue, library, "release-2")
    catalogue.queries.clear()

    completed = container.architecture_mapping_jobs.run_once()
    assert completed is not None and completed.id == job.id and completed.status == "succeeded"
    # The job asks for the release that was active when it was queued.
    assert {query.release_id for query in catalogue.queries} == {OFFLINE_RELEASE_ID}
    features = client.get(f"/requirements/{requirement_id}/features").json()["features"]
    assert features[0]["architecture"]["knowledge_version"] == OFFLINE_RELEASE_ID
    stale_review = client.post(f"/requirements/{requirement_id}/breakdown-review")
    assert stale_review.status_code == 409

    refreshed = client.post(f"/requirements/{requirement_id}/architecture-mapping")
    assert refreshed.status_code == 200
    assert refreshed.json()["features"][0]["architecture"]["knowledge_version"] == "release-2"
    review = client.post(f"/requirements/{requirement_id}/breakdown-review")
    assert review.status_code == 200
    assert review.json()["fresh"] is True


def test_mapping_jobs_run_in_the_requirement_queue_under_the_requirement_url(
    client: TestClient,
    container: Container,
) -> None:
    """Mapping is requirement work with its own queue (ADR-0099)."""
    requirement_id, _, _ = _tree(client)
    started = client.post(f"/requirements/{requirement_id}/architecture-mapping/jobs")
    assert started.status_code == 202
    job = started.json()
    # Fake models finish the job inside the request.
    assert job["status"] == "succeeded"

    assert container.architecture_mapping_jobs.owns(job["id"])
    base = f"/requirements/{requirement_id}/architecture-mapping/jobs"
    assert client.get(f"{base}/{job['id']}").json()["id"] == job["id"]
    assert client.get(f"{base}/no-such-job").status_code == 404
    features = client.get(f"/requirements/{requirement_id}/features").json()["features"]
    assert all(item["architecture"] is not None for item in features)


def test_a_mapping_queued_under_other_models_records_a_knowledge_conflict(
    client: TestClient,
    container: Container,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requirement_id, _, _ = _tree(client)
    actor = Actor("fake-owner", frozenset({"knowledge_reader", "knowledge_maintainer"}))
    queued = container.architecture_mapping_jobs.enqueue(RequirementId(requirement_id), actor)
    # The configured reasoning model changes between asking and running.
    monkeypatch.setattr(
        container.architecture_mapping_jobs, "_reasoning_profile", "other:architecture-impact-v1"
    )

    finished = container.architecture_mapping_jobs.run_once()

    assert finished is not None and finished.id == queued.id
    assert finished.status == "failed"
    assert finished.error_category == "architecture_knowledge_conflict"
