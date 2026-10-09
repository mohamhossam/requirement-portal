"""Workspace-wide read, members-only write, private drafts (ADR-0075).

This pins the visibility policy so it cannot change as a side effect of an
authorization refactor. Changing it is a product decision and needs a new ADR.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.workflow_helpers import confirm_fake_analysis, post_analysis, post_epic

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
# Signed in, but neither the owner nor a reviewer of anything created here.
NON_MEMBER = {"X-Fake-Actor-Id": "fake-observer"}


def _submitted_requirement_with_an_epic(client: TestClient) -> str:
    requirement_id: str = client.post(
        "/requirements", json={"title": "Bundle", "description": "SMB bundle"}, headers=OWNER
    ).json()["id"]
    assert post_analysis(client, requirement_id, headers=OWNER).succeeded
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id, headers=OWNER).succeeded
    return requirement_id


def test_any_signed_in_user_can_read_a_submitted_requirement_and_its_artifacts(
    client: TestClient,
) -> None:
    requirement_id = _submitted_requirement_with_an_epic(client)

    for path in ("", "/analysis", "/epic", "/revisions", "/attachments"):
        response = client.get(f"/requirements/{requirement_id}{path}", headers=NON_MEMBER)
        assert response.status_code == 200, path
    listed = client.get("/requirements", headers=NON_MEMBER).json()
    assert requirement_id in str(listed)


def test_only_members_can_change_it(client: TestClient) -> None:
    requirement_id = _submitted_requirement_with_an_epic(client)
    epic = client.get(f"/requirements/{requirement_id}/epic", headers=OWNER).json()

    edit = client.put(
        f"/requirements/{requirement_id}/epic",
        json={
            "name": "n",
            "outcome": "o",
            "business_case": "b",
            "expected_version": epic["version"],
        },
        headers=NON_MEMBER,
    )
    approve = client.post(
        f"/requirements/{requirement_id}/epic/approval",
        json={
            "expected_version": epic["version"],
            "expected_content_fingerprint": epic["content_fingerprint"],
        },
        headers=NON_MEMBER,
    )

    assert (edit.status_code, approve.status_code) == (403, 403)


def test_drafts_stay_private_to_their_author(client: TestClient) -> None:
    draft_id = client.post(
        "/requirements/drafts", json={"title": "Unsubmitted idea"}, headers=OWNER
    ).json()["id"]

    assert client.get(f"/requirements/drafts/{draft_id}", headers=NON_MEMBER).status_code == 403
    assert draft_id not in str(client.get("/requirements/drafts", headers=NON_MEMBER).json())
