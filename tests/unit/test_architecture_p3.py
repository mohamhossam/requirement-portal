"""How much of the backlog is mapped against each catalogue release (ADR-0099).

When a new release is published, the knowledge service reports how many
Requirements, Features and Stories still use an older one. It reads those
counts from requirement work, which owns the mappings. Naming versions, drafts,
suggestions, cited passages and the impact report itself are knowledge-service
work, tested in knowledge-portal.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.architecture_mapping_stats import MappingCount
from smb_requirement_agent.domain.architecture.entities import SystemReference
from smb_requirement_agent.infrastructure.knowledge_client import OFFLINE_RELEASE_ID
from smb_requirement_agent.interfaces.api.container import Container, build_container
from tests.conftest import FAKE_PROVIDER_SETTINGS
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

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
TOKEN = "s" * 40
SERVICE = {"Authorization": f"Bearer {TOKEN}"}


class Catalogue:
    """The knowledge service's matching: BCRM, for the pinned or the active release."""

    def __init__(self) -> None:
        self.active = OFFLINE_RELEASE_ID

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        return ArchitectureKnowledgeMatch(
            query.release_id or self.active, (SystemReference("bcrm", "BCRM", True),), ()
        )


@pytest.fixture
def catalogue() -> Catalogue:
    return Catalogue()


@pytest.fixture
def library() -> PublishedLibrary:
    return PublishedLibrary()


@pytest.fixture
def container(catalogue: Catalogue, library: PublishedLibrary) -> Container:
    built = build_container(
        FAKE_PROVIDER_SETTINGS,
        architecture_knowledge=catalogue,
        knowledge_service=service_for(library),
    )
    # The internal API is served only with the knowledge service's token.
    return replace(built, settings=replace(built.settings, knowledge_service_token=TOKEN))


def _mapped_requirement(client: TestClient) -> str:
    requirement_id = client.post(
        "/requirements",
        json={
            "title": "Channel ordering",
            "description": "Allow assisted ordering and activation.",
            "systems": ["BCRM"],
        },
        headers=OWNER,
    ).json()["id"]
    assert post_analysis(client, requirement_id, headers=OWNER).status_code == 200
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id, headers=OWNER).status_code == 201
    assert post_epic_approval(client, requirement_id).status_code == 200
    features = post_features(client, requirement_id).json()["features"]
    assert post_feature_approval(client, requirement_id, features[0]["id"]).status_code == 200
    post_stories(client, requirement_id, features[0]["id"])
    mapped = client.post(f"/requirements/{requirement_id}/architecture-mapping", headers=OWNER)
    assert mapped.status_code == 200
    return str(requirement_id)


def _counts(client: TestClient) -> dict[str, MappingCount]:
    response = client.get("/internal/architecture-mapping/stats", headers=SERVICE)
    assert response.status_code == 200
    return {row["release_id"]: MappingCount(**row) for row in response.json()}


def test_mappings_are_counted_by_the_release_they_pinned_until_remapped(
    client: TestClient,
    container: Container,
    catalogue: Catalogue,
    library: PublishedLibrary,
) -> None:
    assert _counts(client) == {}
    requirement_id = _mapped_requirement(client)

    before = _counts(client)
    assert set(before) == {OFFLINE_RELEASE_ID}
    counted = before[OFFLINE_RELEASE_ID]
    assert counted.requirements == 1
    assert counted.features >= 1 and counted.stories >= 1
    assert before == {item.release_id: item for item in container.internal_reads.mapping_counts()}

    # Publishing a release changes no mapping: the knowledge service reports
    # these as using an older release.
    catalogue.active = "release-2"
    library.activate_release("release-2", "October integration update")
    sync(container)
    assert _counts(client) == before

    remapped = client.post(f"/requirements/{requirement_id}/architecture-mapping", headers=OWNER)
    assert remapped.status_code == 200
    after = _counts(client)
    assert set(after) == {"release-2"}
    assert replace(after["release-2"], release_id=OFFLINE_RELEASE_ID) == counted
