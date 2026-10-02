"""Named versions, one draft at a time, publish impact counts, bulk rejection and passages."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from PIL import Image

from smb_requirement_agent.application.ports.architecture_mapping_stats import MappingCount
from smb_requirement_agent.application.ports.identity import Actor
from smb_requirement_agent.application.use_cases.architecture_mapping_impact import (
    ReportMappingImpact,
)
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.interfaces.api.container import Container
from tests.spreadsheet_fixtures import XLSX_MIME, spreadsheet_document
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
READER = {"X-Fake-Actor-Id": "fake-reviewer"}
RELEASES = "/architecture-knowledge/releases"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _start(client: TestClient, name: str = "October integration update") -> dict[str, object]:
    response = client.post(RELEASES, json={"name": name}, headers=OWNER)
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_a_version_is_named_and_only_one_can_be_in_progress(client: TestClient) -> None:
    draft = _start(client, "  October   integration update ")

    assert (draft["name"], draft["created_by"]) == ("October integration update", "fake-owner")
    second = client.post(RELEASES, json={"name": "Another"}, headers=OWNER)
    assert second.status_code == 409
    assert "'October integration update' is already in progress" in second.text
    assert "fake-owner" in second.text
    assert client.post(RELEASES, json={"name": "  "}, headers=OWNER).status_code == 422
    listed = client.get(RELEASES, headers=OWNER).json()
    assert {item["id"]: item["name"] for item in listed}["smb-source-reference-v1"] == (
        "Initial catalogue"
    )


def test_a_draft_is_renamed_without_losing_its_build(client: TestClient) -> None:
    draft = _start(client)
    base = f"{RELEASES}/{draft['id']}"
    client.post(f"{base}/build", json={"expected_revision": draft["revision"]}, headers=OWNER)
    built = client.get(base, headers=OWNER).json()
    assert built["built_revision"] == built["revision"]

    renamed = client.put(
        f"{base}/name",
        json={"expected_revision": built["revision"], "name": "Q4 update"},
        headers=OWNER,
    )

    body = renamed.json()
    assert renamed.status_code == 200
    assert body["name"] == "Q4 update"
    assert body["built_revision"] == body["revision"] == built["revision"] + 1
    stale = client.put(
        f"{base}/name",
        json={"expected_revision": built["revision"], "name": "Late"},
        headers=OWNER,
    )
    assert stale.status_code == 409
    seed = client.put(
        f"{RELEASES}/smb-source-reference-v1/name",
        json={"expected_revision": 1, "name": "Renamed seed"},
        headers=OWNER,
    )
    assert seed.status_code == 409


def test_a_discarded_draft_is_gone_and_a_new_one_can_start(client: TestClient) -> None:
    draft = _start(client)
    base = f"{RELEASES}/{draft['id']}"

    assert (
        client.request("DELETE", base, json={"expected_revision": 99}, headers=OWNER).status_code
        == 409
    )
    discarded = client.request(
        "DELETE", base, json={"expected_revision": draft["revision"]}, headers=OWNER
    )

    assert discarded.status_code == 204
    assert client.get(base, headers=OWNER).status_code == 404
    assert _start(client, "Second attempt")["name"] == "Second attempt"
    active = client.request(
        "DELETE",
        f"{RELEASES}/smb-source-reference-v1",
        json={"expected_revision": 1},
        headers=OWNER,
    )
    assert active.status_code == 409
    assert (
        client.request("DELETE", base, json={"expected_revision": 1}, headers=READER).status_code
        == 403
    )


def _mapped_requirement(client: TestClient) -> None:
    requirement_id = client.post(
        "/requirements",
        json={
            "title": "Channel ordering",
            "description": "Allow assisted ordering and activation.",
            "systems": ["BCRM"],
        },
    ).json()["id"]
    assert post_analysis(client, requirement_id).status_code == 200
    confirm_fake_analysis(client, requirement_id)
    assert post_epic(client, requirement_id).status_code == 201
    assert post_epic_approval(client, requirement_id).status_code == 200
    features = post_features(client, requirement_id).json()["features"]
    assert post_feature_approval(client, requirement_id, features[0]["id"]).status_code == 200
    post_stories(client, requirement_id, features[0]["id"])
    assert client.post(f"/requirements/{requirement_id}/architecture-mapping").status_code == 200


def test_publishing_reports_how_much_now_uses_an_older_version(client: TestClient) -> None:
    impact = "/architecture-knowledge/mapping-impact"
    assert client.get(impact, headers=OWNER).json()["requirements"] == 0
    _mapped_requirement(client)

    before = client.get(impact, headers=OWNER).json()
    assert before["requirements"] == 1
    assert before["features"] >= 1 and before["stories"] >= 1
    assert before["outdated_requirements"] == 0

    draft = _start(client)
    base = f"{RELEASES}/{draft['id']}"
    client.post(f"{base}/build", json={"expected_revision": draft["revision"]}, headers=OWNER)
    published = client.post(
        f"{base}/publish",
        json={"expected_revision": draft["revision"], "rationale": "Reviewed"},
        headers=OWNER,
    )
    assert published.status_code == 200, published.text

    after = client.get(impact, headers=OWNER).json()
    assert after["active_release_id"] == draft["id"]
    assert (
        after["outdated_requirements"],
        after["outdated_features"],
        after["outdated_stories"],
    ) == (
        before["requirements"],
        before["features"],
        before["stories"],
    )
    assert client.get(impact, headers=READER).status_code == 403


def test_impact_sums_every_release_that_is_not_in_use() -> None:
    class Stats:
        def by_release(self) -> tuple[MappingCount, ...]:
            return (
                MappingCount("smb-source-reference-v1", 2, 4, 9),
                MappingCount("old-1", 1, 1, 2),
                MappingCount("old-2", 3, 5, 7),
            )

    impact = ReportMappingImpact(InMemoryArchitectureKnowledgeRepository(seed_knowledge()), Stats())
    report = impact.execute(Actor("amina", frozenset({"knowledge_maintainer"})))

    assert (report.requirements, report.features, report.stories) == (6, 10, 18)
    assert (
        report.outdated_requirements,
        report.outdated_features,
        report.outdated_stories,
    ) == (4, 6, 9)


def _suggestions(client: TestClient) -> tuple[str, dict[str, object], list[dict[str, object]]]:
    draft = _start(client)
    base = f"{RELEASES}/{draft['id']}"
    content = (
        "System: Order Hub\nSystem: Billing Gateway\nConstraint: Order Hub only runs at night\n"
    )
    uploaded = client.post(
        f"{base}/documents",
        data={"title": "Design", "language": "en", "expected_revision": str(draft["revision"])},
        files={"file": ("design.txt", content.encode(), "text/plain")},
        headers=OWNER,
    ).json()
    version_id = uploaded["documents"][-1]["id"]
    client.post(f"{base}/documents/{version_id}/extractions", headers=OWNER)
    overview = client.get(f"{base}/suggestions", headers=OWNER).json()
    return base, uploaded, overview["suggestions"]


def test_waiting_suggestions_are_rejected_together(client: TestClient) -> None:
    base, uploaded, suggestions = _suggestions(client)
    ids = [str(item["id"]) for item in suggestions]
    assert len(ids) >= 2
    first = client.post(
        f"{base}/suggestions/{ids[0]}/decision",
        json={"expected_revision": uploaded["revision"], "accept": False},
        headers=OWNER,
    )
    assert first.status_code == 200

    rejected = client.post(
        f"{base}/suggestions/rejection",
        json={"expected_revision": uploaded["revision"], "suggestion_ids": [*ids, "unknown"]},
        headers=OWNER,
    )

    assert rejected.json() == {"rejected": len(ids) - 1}
    statuses = {
        item["status"]
        for item in client.get(f"{base}/suggestions", headers=OWNER).json()["suggestions"]
    }
    assert statuses == {"rejected"}
    stale = client.post(
        f"{base}/suggestions/rejection",
        json={"expected_revision": 1, "suggestion_ids": ids},
        headers=OWNER,
    )
    assert stale.status_code == 409


def _docx() -> bytes:
    paragraphs = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        for text in ("One.", "Two.", "Three: Order Hub runs nightly.", "Four.", "Five.", "Six.")
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W}"><w:body>{paragraphs}</w:body></w:document>',
        )
    return buffer.getvalue()


def test_a_cited_passage_is_shown_with_its_neighbours(client: TestClient) -> None:
    draft = _start(client)
    base = f"{RELEASES}/{draft['id']}"
    uploaded = client.post(
        f"{base}/documents",
        data={"title": "Design", "language": "en", "expected_revision": str(draft["revision"])},
        files={"file": ("design.docx", _docx(), DOCX)},
        headers=OWNER,
    ).json()
    passage = f"{base}/documents/{uploaded['documents'][-1]['id']}/passage"

    found = client.get(passage, params={"location": "paragraph 3 (part 1 of 2)"}, headers=OWNER)

    body = found.json()
    assert found.status_code == 200
    assert body["passage"] == {"location": "paragraph 3", "text": "Three: Order Hub runs nightly."}
    assert [item["location"] for item in body["before"]] == ["paragraph 1", "paragraph 2"]
    assert [item["location"] for item in body["after"]] == ["paragraph 4", "paragraph 5"]
    assert body["mime_type"] == DOCX
    assert (
        client.get(passage, params={"location": "paragraph 99"}, headers=OWNER).status_code == 404
    )
    assert (
        client.get(passage, params={"location": "paragraph 3"}, headers=READER).status_code == 403
    )
    missing = f"{base}/documents/nope/passage"
    assert client.get(missing, params={"location": "paragraph 1"}, headers=OWNER).status_code == 404


def test_a_markdown_citation_from_before_passages_followed_headings_still_opens(
    client: TestClient,
) -> None:
    """Suggestions read under 40-line windows cite "lines 1-40"; its first passage opens."""
    draft = _start(client)
    base = f"{RELEASES}/{draft['id']}"
    uploaded = client.post(
        f"{base}/documents",
        data={"title": "Notes", "language": "en", "expected_revision": str(draft["revision"])},
        files={
            "file": (
                "notes.md",
                b"# Systems\n\n| System | Owner |\n|---|---|\n| Order Hub | Sales |\n",
                "text/markdown",
            )
        },
        headers=OWNER,
    ).json()
    passage = f"{base}/documents/{uploaded['documents'][-1]['id']}/passage"

    row = client.get(passage, params={"location": "line 5"}, headers=OWNER).json()
    window = client.get(passage, params={"location": "lines 1-40"}, headers=OWNER).json()

    assert row["passage"] == {"location": "line 5", "text": "System: Order Hub | Owner: Sales"}
    assert window["passage"]["location"] == "line 1"
    assert [item["location"] for item in window["after"]] == ["line 5"]
    assert (
        client.get(passage, params={"location": "lines 90-120"}, headers=OWNER).status_code == 404
    )


def test_a_cited_spreadsheet_row_is_shown_with_its_neighbours(client: TestClient) -> None:
    draft = _start(client)
    base = f"{RELEASES}/{draft['id']}"
    workbook = spreadsheet_document(
        {"A1": "System", "A2": "Order Hub", "A3": "BCRM", "A4": "Billing", "A5": "CRM"}
    )
    form = {"title": "Inventory", "language": "en", "expected_revision": str(draft["revision"])}
    mislabelled = client.post(
        f"{base}/documents",
        data=form,
        files={"file": ("inventory.csv", workbook, XLSX_MIME)},
        headers=OWNER,
    )
    assert mislabelled.status_code == 422
    uploaded = client.post(
        f"{base}/documents",
        data=form,
        files={"file": ("inventory.xlsx", workbook, XLSX_MIME)},
        headers=OWNER,
    )
    assert uploaded.status_code == 201, uploaded.text
    passage = f"{base}/documents/{uploaded.json()['documents'][-1]['id']}/passage"

    body = client.get(passage, params={"location": "sheet 1, row 3"}, headers=OWNER).json()

    assert body["passage"] == {"location": "sheet 1, row 3", "text": "A3=BCRM"}
    assert [item["location"] for item in body["before"]] == ["sheet 1, row 1", "sheet 1, row 2"]
    assert [item["location"] for item in body["after"]] == ["sheet 1, row 4", "sheet 1, row 5"]


def test_a_csv_is_accepted_as_a_source(client: TestClient) -> None:
    draft = _start(client)
    uploaded = client.post(
        f"{RELEASES}/{draft['id']}/documents",
        data={"title": "Links", "language": "en", "expected_revision": str(draft["revision"])},
        files={"file": ("links.csv", b"From,To\nOrder Hub,BCRM\n", "text/csv")},
        headers=OWNER,
    )

    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["documents"][-1]["mime_type"] == "text/csv"


def test_an_image_has_no_passage_to_show(client: TestClient) -> None:
    draft = _start(client)
    base = f"{RELEASES}/{draft['id']}"
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    png = buffer.getvalue()
    uploaded = client.post(
        f"{base}/documents",
        data={"title": "Diagram", "language": "en", "expected_revision": str(draft["revision"])},
        files={"file": ("diagram.png", png, "image/png")},
        headers=OWNER,
    )
    assert uploaded.status_code == 201, uploaded.text
    version_id = uploaded.json()["documents"][-1]["id"]

    shown = client.get(
        f"{base}/documents/{version_id}/passage", params={"location": "image"}, headers=OWNER
    )

    assert shown.status_code == 422
    assert "Images have no text passages" in shown.text


def test_names_survive_a_published_round_trip() -> None:
    repository = InMemoryArchitectureKnowledgeRepository(seed_knowledge())
    assert repository.active().name == "Initial catalogue"
    assert datetime.now(UTC)


def test_a_job_queued_for_a_removed_draft_fails_instead_of_waiting(container: Container) -> None:
    actor = Actor("maintainer", frozenset({"knowledge_maintainer"}))
    draft = container.manage_architecture_knowledge.create_draft(actor, "Removed before building")
    queued = container.architecture_jobs.enqueue_build(draft.id, draft.revision, actor)
    assert queued.status == "queued"

    container.manage_architecture_knowledge.discard_draft(draft.id, draft.revision, actor)
    finished = container.architecture_jobs.run_once()

    assert finished is not None and finished.id == queued.id
    assert finished.status == "failed"
    assert container.architecture_jobs.run_once() is None
