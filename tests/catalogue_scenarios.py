"""Paged drafts and documents (production hardening PR 13), as every store must serve them.

The unit tests run these against the in-memory store, and the integration tests against
PostgreSQL, so both answer the same way.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
OTHER = {"X-Fake-Actor-Id": "fake-observer"}


def _draft(client: TestClient, title: str, headers: dict[str, str]) -> str:
    response = client.post("/requirements/drafts", json={"title": title}, headers=headers)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _attach(client: TestClient, path: str, filename: str, headers: dict[str, str]) -> str:
    response = client.post(
        f"{path}/attachments",
        data={"include_in_analysis": "false"},
        files={"file": (filename, b"Policy text", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _drafts(client: TestClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    response = client.get("/requirements/drafts", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return dict(response.json())


def _documents(client: TestClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    response = client.get("/documents", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return dict(response.json())


def drafts_page_by_owner_search_and_title(client: TestClient) -> None:
    for title in ("Gamma", "beta offer", "Alpha bundle"):
        _draft(client, title, OWNER)
    theirs = _draft(client, "Observer idea", OTHER)

    first = _drafts(client, OWNER, sort="title_asc", limit=2)
    rest = _drafts(client, OWNER, sort="title_asc", limit=2, offset=2)

    assert [item["title"] for item in first["drafts"]] == ["Alpha bundle", "beta offer"]
    assert (first["total"], first["offset"], first["limit"], first["has_more"]) == (3, 0, 2, True)
    assert [item["title"] for item in rest["drafts"]] == ["Gamma"]
    assert rest["has_more"] is False
    assert [item["title"] for item in _drafts(client, OWNER, sort="title_desc")["drafts"]] == [
        "Gamma",
        "beta offer",
        "Alpha bundle",
    ]
    # Case-insensitive, and LIKE's wildcards are literal.
    assert [item["title"] for item in _drafts(client, OWNER, q="BUNDLE")["drafts"]] == [
        "Alpha bundle"
    ]
    assert _drafts(client, OWNER, q="%")["total"] == 0
    # Every draft carries its eligibility, read for the whole page at once.
    assert all("analysis_eligibility" in item for item in first["drafts"])
    # Drafts stay private to their owner.
    assert [item["id"] for item in _drafts(client, OTHER)["drafts"]] == [theirs]
    assert theirs not in str(_drafts(client, OWNER))
    for limit in (0, 101):
        refused = client.get("/requirements/drafts", params={"limit": limit}, headers=OWNER)
        assert refused.status_code == 422


def documents_page_with_owners_counts_and_privacy(client: TestClient) -> None:
    requirement = client.post(
        "/requirements",
        json={"title": "Fibre rollout", "description": "Fibre for SMB sites"},
        headers=OWNER,
    ).json()["id"]
    first = _attach(client, f"/requirements/{requirement}", "a-policy.txt", OWNER)
    second = _attach(client, f"/requirements/{requirement}", "b-pricing.txt", OWNER)
    draft = _draft(client, "Alpha bundle", OWNER)
    drafted = _attach(client, f"/requirement-drafts/{draft}", "c-notes.txt", OWNER)
    other_draft = _draft(client, "Observer idea", OTHER)
    hidden = _attach(client, f"/requirement-drafts/{other_draft}", "d-private.txt", OTHER)

    everything = _documents(client, OWNER, sort="name_asc")

    assert [item["id"] for item in everything["documents"]] == [first, second, drafted]
    assert everything["total"] == 3
    assert {item["id"]: item["owner"] for item in everything["documents"]}[drafted] == {
        "kind": "draft",
        "id": draft,
        "title": "Alpha bundle",
    }
    assert sorted((owner["kind"], owner["title"]) for owner in everything["owners"]) == [
        ("draft", "Alpha bundle"),
        ("requirement", "Fibre rollout"),
    ]
    counts = everything["counts"]
    assert counts["attention"] + counts["included"] + counts["excluded"] == 3
    assert _documents(client, OWNER, filter="excluded")["total"] == counts["excluded"]
    # Another actor's draft documents never appear, in rows, counts or owners.
    assert hidden not in str(everything)
    assert {item["id"] for item in _documents(client, OTHER)["documents"]} == {
        first,
        second,
        hidden,
    }

    descending = _documents(client, OWNER, sort="name_desc")["documents"]
    assert [item["id"] for item in descending] == [drafted, second, first]
    # Search matches the filename or the owner's title.
    assert {item["id"] for item in _documents(client, OWNER, q="FIBRE")["documents"]} == {
        first,
        second,
    }
    assert [item["id"] for item in _documents(client, OWNER, q="notes")["documents"]] == [drafted]
    assert [item["id"] for item in _documents(client, OWNER, owner=draft)["documents"]] == [drafted]
    # The counts and owners cover everything visible, whatever the search.
    assert _documents(client, OWNER, q="notes")["counts"] == counts

    page = _documents(client, OWNER, sort="name_asc", limit=1, offset=1)
    assert [item["id"] for item in page["documents"]] == [second]
    assert (page["total"], page["has_more"]) == (3, True)
    for limit in (0, 101):
        assert client.get("/documents", params={"limit": limit}, headers=OWNER).status_code == 422

    detail = client.get(f"/documents/{drafted}", headers=OWNER).json()
    assert detail["owner"] == {"kind": "draft", "id": draft, "title": "Alpha bundle"}
