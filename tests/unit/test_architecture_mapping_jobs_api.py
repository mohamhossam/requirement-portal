"""Mapping a Requirement's backlog as a queued job: keys, access and its routes (ADR-0099).

Mapping jobs are requirement work with their own queue; the catalogue's jobs and
their `/jobs/{id}` routes left with the catalogue.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.architecture_jobs import MappingJobInput

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
READER = {"X-Fake-Actor-Id": "fake-reviewer"}


def test_mapping_job_keys_round_trip_and_match_previously_queued_jobs() -> None:
    mapping = MappingJobInput("release-7", "abc123", "embedding-profile", "model|impact-v1")

    assert MappingJobInput.from_key(mapping.key) == mapping
    # Keys are the durable idempotency value, so the stored format must not drift.
    assert mapping.key == "release-7|abc123|embedding-profile|model|impact-v1"


@pytest.mark.parametrize(
    "key", ["", "release|fingerprint|embedding", "release||embedding|reasoning"]
)
def test_malformed_mapping_job_input_is_a_persistence_failure(key: str) -> None:
    with pytest.raises(PersistenceError, match="mapping job input"):
        MappingJobInput.from_key(key)


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


def test_a_mapping_job_is_read_under_its_own_requirement(client: TestClient) -> None:
    requirement_id = _requirement(client)
    other_id = _requirement(client)
    job = client.post(
        f"/requirements/{requirement_id}/architecture-mapping/jobs", headers=OWNER
    ).json()
    base = f"/requirements/{requirement_id}/architecture-mapping/jobs/{job['id']}"

    found = client.get(base, headers=OWNER)
    elsewhere = client.get(
        f"/requirements/{other_id}/architecture-mapping/jobs/{job['id']}", headers=OWNER
    )

    assert found.status_code == 200 and found.json()["id"] == job["id"]
    assert found.json()["subject_id"] == requirement_id
    assert elsewhere.status_code == 404
    assert elsewhere.json()["code"] == "architecture_job_not_found"
    assert client.post(f"{base}/cancel", headers=OWNER).status_code in {200, 409}
    assert client.post(f"{base}/retry", headers=OWNER).status_code in {200, 409}
