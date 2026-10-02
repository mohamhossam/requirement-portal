"""Public library API: authenticated reads, owner review and exact content publication."""

import time

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.spreadsheet_fixtures import XLSX_MIME, spreadsheet_document, with_merge_ranges
from tests.word_table_fixtures import DOCX_MIME, word_cell, word_document, word_row, word_table


@pytest.mark.parametrize("kind", ["docx", "csv", "tsv", "xlsx"])
def test_malformed_table_has_visible_ingestion_failure_and_no_publication(kind: str) -> None:
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE, library_scan_mode="offline")
    )
    content = word_document(
        word_table(word_row(word_cell("Rule", '<w:gridSpan w:val="invalid"/>')))
    )
    mime = DOCX_MIME
    error = "DOCX table grid value is invalid."
    if kind == "xlsx":
        content = with_merge_ranges(spreadsheet_document({"A1": "Rule"}), ("A1:B2", "B2:C3"))
        mime = XLSX_MIME
        error = "XLSX merged ranges overlap."
    if kind in {"csv", "tsv"}:
        delimiter = "\t" if kind == "tsv" else ","
        content = f"Rule{delimiter}Channel\nBroken".encode()
        mime = "text/tab-separated-values" if kind == "tsv" else "text/csv"
        error = "Row 2 does not match the first record width. Check the delimiter."
    with TestClient(create_app(lambda: container)) as client:
        submitted = client.post(
            "/library/ingestions",
            data={"title": "Malformed table", "idempotency_key": "bad-word-grid"},
            files={"file": (f"bad.{kind}", content, mime)},
        )
        assert submitted.status_code == 202
        path = f"/library/documents/{submitted.json()['id']}"
        view = submitted.json()
        for _ in range(100):
            response = client.get(path)
            assert response.status_code == 200
            view = response.json()
            if view["versions"][0]["stage"] == "failed":
                break
            time.sleep(0.05)
        assert view["versions"][0]["stage"] == "failed"
        assert view["versions"][0]["error"] == error
        assert view["published_id"] is None and view["review_fingerprint"] is None
        assert client.get(f"{path}/builds/preview").status_code == 409
        assert client.post("/knowledge/search", json={"query": "Rule"}).json() == []


def test_library_owner_review_publication_and_authorization() -> None:
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE, library_scan_mode="offline")
    )
    with TestClient(create_app(lambda: container)) as client:
        uploaded = client.post(
            "/library/ingestions",
            data={"title": "Coverage", "idempotency_key": "api-upload"},
            files={"file": ("policy.txt", b"XGPON coverage is required.", "text/plain")},
        )
        assert uploaded.status_code == 202
        document_id = uploaded.json()["id"]
        path = f"/library/documents/{document_id}"
        reader = {"X-Fake-Actor-Id": "fake-observer"}
        # The fake identity header uses the actual seeded IDs, checked in identity tests.
        owner_view = uploaded.json()
        for _ in range(100):
            owner_view = client.get(path).json()
            if owner_view["versions"][0]["stage"] == "ready_for_review":
                break
            time.sleep(0.05)
        assert owner_view["versions"][0]["stage"] == "ready_for_review"
        source = owner_view["versions"][0]
        data = {
            "expected_version": owner_view["version"],
            "explanation": "Reviewed original",
            "passages": [
                {"block_id": b["id"], "text": b["text"], "included": True, "exclusion_reason": ""}
                for b in source["blocks"]
            ],
        }
        review = client.post(f"{path}/versions/{source['id']}/review", json=data)
        assert review.status_code == 200
        assert client.post(f"{path}/versions/{source['id']}/review", json=data).status_code == 409
        updated = review.json()
        approval = client.post(
            f"{path}/versions/{source['id']}/approval",
            json={
                "expected_version": updated["version"],
                "revision_id": updated["versions"][0]["revisions"][-1]["id"],
                "fingerprint": updated["review_fingerprint"],
            },
        )
        assert approval.status_code == 200
        for _ in range(100):
            if client.get(path).json()["published_id"]:
                break
            time.sleep(0.05)
        search = client.post("/knowledge/search", json={"query": "XGPON"})
        assert search.status_code == 200 and search.json()[0]["document_id"] == document_id
        assert search.json()[0]["context_text"]
        assert search.json()[0]["context_locations"] == ["Line 1"]
        assert search.json()[0]["context_token_count"] > 0
        assert client.get(path, headers=reader).status_code == 200
        assert (
            client.get(f"{path}/versions/{source['id']}/original", headers=reader).status_code
            == 403
        )
        current = client.get(path).json()
        assert (
            client.post(
                f"{path}/withdrawal",
                headers=reader,
                json={"expected_version": current["version"], "reason": "Unauthorized"},
            ).status_code
            == 403
        )
        assert client.post("/knowledge/search", json={"query": ""}).status_code == 422
        preview = client.get(f"{path}/builds/preview")
        assert preview.status_code == 200
        assert client.get(f"{path}/builds/preview", headers=reader).status_code == 403
        contract = preview.json()
        body = {
            "expected_version": contract["document_version"],
            "fingerprint": contract["fingerprint"],
            "index_identity": contract["index_identity"],
        }
        assert client.post(f"{path}/builds", json=body, headers=reader).status_code == 403
        assert (
            client.post(f"{path}/builds", json={**body, "fingerprint": "0" * 64}).status_code == 422
        )
        built = client.post(f"{path}/builds", json=body)
        assert built.status_code == 202
        assert client.post(f"{path}/builds", json=body).status_code == 409
        for _ in range(100):
            ready_view = client.get(path).json()
            if ready_view["publications"][-1]["built_at"]:
                break
            time.sleep(0.05)
        ready = ready_view["publications"][-1]
        assert ready["built_at"] and ready["activated_at"] is None
        assert ready_view["published_id"] == current["published_id"]
        activation_path = f"{path}/builds/{ready['id']}/activation"
        activation = {
            "expected_version": ready_view["version"],
            "manifest": ready["chunk_manifest"],
        }
        assert client.post(activation_path, json=activation, headers=reader).status_code == 403
        assert (
            client.post(activation_path, json={**activation, "manifest": "0" * 64}).status_code
            == 409
        )
        activated = client.post(activation_path, json=activation)
        assert activated.status_code == 200 and activated.json()["published_id"] == ready["id"]
        assert client.post(activation_path, json=activation).status_code == 409
        second_preview = client.get(f"{path}/builds/preview").json()
        second = client.post(
            f"{path}/builds",
            json={
                "expected_version": second_preview["document_version"],
                "fingerprint": second_preview["fingerprint"],
                "index_identity": second_preview["index_identity"],
            },
        ).json()
        second = client.get(path).json()
        discarded = client.post(
            f"{path}/builds/{second['publications'][-1]['id']}/discard",
            json={"expected_version": second["version"]},
        )
        assert discarded.status_code == 200
        assert discarded.json()["published_id"] == ready["id"]
