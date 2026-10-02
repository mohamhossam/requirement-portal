"""Domain, adapter, application, persistence, and API coverage for Slice 7."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.identity import Actor
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
    MapFeatureArchitecture,
    MapStoryArchitecture,
)
from smb_requirement_agent.application.use_cases.invalidate_approval_workflow import (
    InvalidateApprovalWorkflow,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureDependency,
    ArchitectureImpact,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.errors import InvalidArchitectureContentError
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.infrastructure.architecture.yaml_knowledge import (
    YamlArchitectureKnowledge,
    default_knowledge_path,
)
from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.persistence.backlog_payloads import (
    feature_from_payload,
    feature_to_payload,
    story_from_payload,
    story_to_payload,
)
from smb_requirement_agent.interfaces.api.container import Container
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


def test_yaml_adapter_maps_catalogued_and_declared_unknown_systems() -> None:
    adapter = YamlArchitectureKnowledge(default_knowledge_path())

    result = adapter.match(
        ArchitectureQuery(
            text=("The assisted sales journey needs service activation.",),
            declared_systems=("BCRM", "CPP"),
        )
    )

    by_name = {item.name: item for item in result.systems}
    assert result.knowledge_version == "smb-source-reference-v1"
    assert by_name["BCRM"].catalogued is True
    assert by_name["CPP"].catalogued is False
    assert by_name["eVEDA / E2ESO / XaaS / IN"].capabilities[0].name == (
        "Network and service activation"
    )
    assert all(not item.squads for item in result.systems)


def test_yaml_adapter_matches_punctuation_and_selected_dependencies(
    tmp_path: Path,
) -> None:
    catalogue = tmp_path / "catalogue.yaml"
    catalogue.write_text(
        """version: test-v1
systems:
  - id: front-end
    name: Front End
    aliases: [customer portal]
    capabilities:
      - {id: quote, name: Quote capture, triggers: [quote capture]}
  - {id: crm, name: CRM, aliases: [customer records]}
dependencies:
  - {source_system_id: front-end, target_system_id: crm, description: Reads customers}
""",
        encoding="utf-8",
    )

    result = YamlArchitectureKnowledge(catalogue).match(
        ArchitectureQuery(
            text=("The customer-portal performs quote capture.",),
            declared_systems=("CRM",),
        )
    )

    assert [item.name for item in result.systems] == ["CRM", "Front End"]
    front_end = result.systems[1]
    assert front_end.capabilities[0].name == "Quote capture"
    assert result.dependencies == (ArchitectureDependency("front-end", "crm", "Reads customers"),)


def test_yaml_adapter_rejects_duplicate_aliases_and_dangling_dependencies(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        """version: v1
systems:
  - {id: one, name: One, aliases: [shared]}
  - {id: two, name: Two, aliases: [shared]}
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="multiple systems"):
        YamlArchitectureKnowledge(duplicate)

    dangling = tmp_path / "dangling.yaml"
    dangling.write_text(
        """version: v1
systems:
  - {id: one, name: One}
dependencies:
  - {source_system_id: one, target_system_id: missing, description: Missing}
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="absent"):
        YamlArchitectureKnowledge(dangling)

    duplicate_id = tmp_path / "duplicate-id.yaml"
    duplicate_id.write_text(
        """version: v1
systems:
  - {id: repeated, name: One}
  - {id: repeated, name: Two}
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="Duplicate architecture system id"):
        YamlArchitectureKnowledge(duplicate_id)

    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("version: [", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="could not be loaded"):
        YamlArchitectureKnowledge(malformed)


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
        InvalidateApprovalWorkflow(container.breakdown_review_repository),
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


def test_mapping_job_pins_release_and_review_rejects_outdated_architecture(
    client: TestClient,
    container: Container,
) -> None:
    requirement_id, _, _ = _tree(client)
    job = container.architecture_jobs.enqueue_mapping(
        RequirementId(requirement_id),
        Actor("fake-owner", frozenset({"knowledge_reader", "knowledge_maintainer"})),
    )
    draft = client.post("/architecture-knowledge/releases", json={"name": "Next version"}).json()
    container.build_architecture_index.execute(
        draft["id"], draft["revision"], "fake-owner", fence=lambda: None
    )
    published = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/publish",
        json={"expected_revision": draft["revision"], "rationale": "Reviewed"},
    )
    assert published.status_code == 200

    completed = container.architecture_jobs.run_once()
    assert completed is not None and completed.id == job.id and completed.status == "succeeded"
    features = client.get(f"/requirements/{requirement_id}/features").json()["features"]
    assert features[0]["architecture"]["knowledge_version"] == "smb-source-reference-v1"
    stale_review = client.post(f"/requirements/{requirement_id}/breakdown-review")
    assert stale_review.status_code == 409

    refreshed = client.post(f"/requirements/{requirement_id}/architecture-mapping")
    assert refreshed.status_code == 200
    assert refreshed.json()["features"][0]["architecture"]["knowledge_version"] == draft["id"]
    review = client.post(f"/requirements/{requirement_id}/breakdown-review")
    assert review.status_code == 200
    assert review.json()["fresh"] is True
