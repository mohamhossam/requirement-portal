"""The knowledge API's own schemas keep the wire format the browser already relies on.

Before these schemas existed the routes serialised domain dataclasses directly;
each response model must produce exactly that JSON, so moving the contract into
the API layer changed ownership, not shape.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeAuditEvent,
    KnowledgeDocumentVersion,
    KnowledgeReleaseStatus,
    SystemDefinition,
)
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.interfaces.api.schemas.architecture_knowledge import (
    ArchitectureJobResponse,
    KnowledgeAuditEventResponse,
    KnowledgeReleaseResponse,
    SystemDefinitionSchema,
)

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
READER = {"X-Fake-Actor-Id": "fake-reviewer"}
AT = datetime(2026, 9, 24, 9, 30, tzinfo=UTC)


def _published_release_with_document() -> ArchitectureKnowledge:
    document = KnowledgeDocumentVersion(
        "version-1", "Runbook", "runbook.txt", "text/plain", "ar", "abc", "version-1", "amina", AT
    )
    return replace(
        seed_knowledge(),
        documents=(document,),
        status=KnowledgeReleaseStatus.PUBLISHED,
        built_revision=1,
        published_at=AT,
        published_by="amina",
        index_profile="profile",
        index_hash="hash",
        index_id="index-1",
    )


def test_release_response_matches_the_previous_domain_serialisation() -> None:
    previous = TypeAdapter(ArchitectureKnowledge)
    for release in (seed_knowledge(), _published_release_with_document()):
        assert KnowledgeReleaseResponse.from_domain(release).model_dump(
            mode="json"
        ) == previous.dump_python(release, mode="json")


def test_job_and_audit_responses_match_the_previous_domain_serialisation() -> None:
    job = ArchitectureJob(
        "job-1",
        ArchitectureJobKind.MAPPING,
        "requirement-1",
        "release|fingerprint|embedding|reasoning",
        "fake-owner",
        ArchitectureJobStatus.RUNNING,
        attempts=2,
        error_category=None,
        lease_until=AT,
    )
    event = KnowledgeAuditEvent("release-1", "amina", "publish", 3, "Reviewed", AT)

    assert ArchitectureJobResponse.from_domain(job).model_dump(mode="json") == TypeAdapter(
        ArchitectureJob
    ).dump_python(job, mode="json")
    assert KnowledgeAuditEventResponse.from_domain(event).model_dump(mode="json") == TypeAdapter(
        KnowledgeAuditEvent
    ).dump_python(event, mode="json")


def test_system_request_round_trips_to_the_domain_value() -> None:
    for system in seed_knowledge().systems:
        payload = TypeAdapter(SystemDefinition).dump_python(system, mode="json")
        assert SystemDefinitionSchema.model_validate(payload).to_domain() == system


def _requirement(client: TestClient) -> str:
    response = client.post(
        "/requirements",
        json={
            "title": "Bulk SIM activation",
            "description": "Let SMB admins activate many SIMs at once.",
        },
        headers=OWNER,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_mapping_jobs_require_requirement_membership_not_only_the_reader_role(
    client: TestClient,
) -> None:
    requirement_id = _requirement(client)

    outsider = client.post(
        f"/requirements/{requirement_id}/architecture-mapping/jobs", headers=READER
    )
    missing = client.post("/requirements/does-not-exist/architecture-mapping/jobs", headers=OWNER)
    member = client.post(f"/requirements/{requirement_id}/architecture-mapping/jobs", headers=OWNER)

    assert outsider.status_code == 403
    assert missing.status_code == 404
    assert member.status_code == 202
    assert member.json()["kind"] == "mapping"


def test_readers_see_published_knowledge_but_not_drafts(client: TestClient) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    )
    assert draft.status_code == 201
    draft_id = draft.json()["id"]

    assert client.get("/architecture-knowledge/releases/active", headers=READER).status_code == 200
    assert (
        client.get(f"/architecture-knowledge/releases/{draft_id}", headers=READER).status_code
        == 403
    )
    assert (
        client.get(
            f"/architecture-knowledge/releases/{draft_id}/catalogue-file", headers=READER
        ).status_code
        == 403
    )
    assert client.get("/architecture-knowledge/releases", headers=READER).status_code == 403
    assert (
        client.get(f"/architecture-knowledge/releases/{draft_id}", headers=OWNER).status_code == 200
    )
