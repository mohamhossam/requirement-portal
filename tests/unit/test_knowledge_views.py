"""The read-only viewers: what they read from the knowledge service, and how (ADR-0099).

The adapter is held to the pinned `contracts/knowledge-internal.openapi.json`;
knowledge-portal serves and tests those routes against the same file.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from smb_kernel.errors import ServiceResponseError, ServiceUnavailableError
from smb_kernel.http.client import InternalHttpClient

from smb_requirement_agent.application.ports.architecture_knowledge import ActiveRelease
from smb_requirement_agent.application.ports.knowledge_views import (
    ArchitectureEvidence,
    CitedPassage,
    KnowledgeViewsPort,
    PassageCitation,
)
from smb_requirement_agent.application.use_cases.knowledge_views import KnowledgeViews
from smb_requirement_agent.infrastructure.knowledge_client import (
    FakeKnowledgeViews,
    HttpKnowledgeViews,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.main import create_app

CONTRACT = json.loads(
    (Path(__file__).parents[2] / "contracts" / "knowledge-internal.openapi.json").read_text(
        encoding="utf-8"
    )
)
TOKEN = "q" * 40
CITATION = PassageCitation("doc/1", "pub-1", "ver-1", "rev-1", "block-1")
PASSAGE = {
    "document_id": "doc/1",
    "title": "Eligibility policy",
    "publication_id": "pub-1",
    "version_id": "ver-1",
    "version_number": 2,
    "revision_id": "rev-1",
    "block_id": "block-1",
    "section_path": ["Eligibility", "Coverage"],
    "label": "Paragraph 3",
    "text": "XGPON coverage is required.",
}
EVIDENCE = {
    "id": "chunk-1",
    "source_label": "Landscape",
    "location": "Section 2",
    "text": "BCRM orders bundles.",
    "document_version_id": None,
}

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler, seen: list[httpx.Request] | None = None) -> InternalHttpClient:
    def record(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return handler(request)

    return InternalHttpClient(
        "http://knowledge",
        TOKEN,
        service="knowledge",
        http=httpx.Client(transport=httpx.MockTransport(record)),
        retries=0,
    )


def _answering(body: Any, status: int = 200) -> Handler:
    return lambda _request: httpx.Response(status, json=body)


def _assert_in_contract(request: httpx.Request) -> None:
    # The raw path: an escaped slash inside an id must stay one path segment.
    path = request.url.raw_path.split(b"?")[0].decode()
    for template, item in CONTRACT["paths"].items():
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$"
        if re.match(pattern, path) and request.method.lower() in item:
            parameters = item[request.method.lower()].get("parameters", ())
            query = {p["name"] for p in parameters if p["in"] == "query"}
            required = {p["name"] for p in parameters if p["in"] == "query" and p["required"]}
            sent = set(request.url.params.keys())
            assert sent <= query and required <= sent, (sent, query, required)
            assert request.headers["authorization"] == f"Bearer {TOKEN}"
            return
    raise AssertionError(f"{request.method} {path} is not in the contract.")


def test_a_cited_passage_is_read_by_its_exact_citation() -> None:
    seen: list[httpx.Request] = []

    passage = HttpKnowledgeViews(_client(_answering(PASSAGE), seen)).passage(CITATION)

    (request,) = seen
    _assert_in_contract(request)
    assert dict(request.url.params) == {
        "document_id": "doc/1",
        "publication_id": "pub-1",
        "version_id": "ver-1",
        "revision_id": "rev-1",
        "block_id": "block-1",
    }
    assert passage is not None and passage.section_path == ("Eligibility", "Coverage")
    assert passage.text == "XGPON coverage is required."
    assert passage.review_due_on is None


def test_the_knowledge_service_says_when_a_cited_document_or_system_falls_due() -> None:
    """Knowledge Center D: additive fields, decoded where the contract has them."""
    passage = HttpKnowledgeViews(
        _client(_answering({**PASSAGE, "review_due_on": "2026-10-01"}))
    ).passage(CITATION)
    assert passage is not None and passage.review_due_on == date(2026, 10, 1)
    record = {**EVIDENCE, "location": "system bcrm", "system_review_due_on": "2026-06-30"}
    evidence = HttpKnowledgeViews(_client(_answering(record))).evidence("rel-1", "chunk-1")
    assert evidence is not None and evidence.system_review_due_on == date(2026, 6, 30)


def test_evidence_is_read_from_its_release() -> None:
    seen: list[httpx.Request] = []

    evidence = HttpKnowledgeViews(_client(_answering(EVIDENCE), seen)).evidence("rel/1", "c 1")

    (request,) = seen
    _assert_in_contract(request)
    assert request.url.raw_path == b"/internal/architecture/releases/rel%2F1/evidence/c%201"
    assert evidence == ArchitectureEvidence(
        "chunk-1", "Landscape", "Section 2", "BCRM orders bundles."
    )


@pytest.mark.parametrize("status", [404, 409])
def test_a_view_the_knowledge_service_no_longer_has_is_absent(status: int) -> None:
    views = HttpKnowledgeViews(_client(_answering({"detail": "gone"}, status)))

    assert views.passage(CITATION) is None
    assert views.evidence("r", "c") is None


def test_a_refusal_is_not_mistaken_for_absence() -> None:
    views = HttpKnowledgeViews(_client(_answering({"detail": "no"}, 401)))

    with pytest.raises(ServiceResponseError):
        views.passage(CITATION)


@pytest.mark.parametrize("call", [lambda v: v.passage(CITATION), lambda v: v.evidence("r", "c")])
@pytest.mark.parametrize("body", [{"unexpected": True}, [], {**PASSAGE, "version_number": "two"}])
def test_an_unusable_answer_is_an_explicit_failure(call: Any, body: Any) -> None:
    with pytest.raises(ServiceUnavailableError):
        call(HttpKnowledgeViews(_client(_answering(body))))


def test_offline_there_is_nothing_to_show() -> None:
    views: KnowledgeViewsPort = FakeKnowledgeViews()

    assert views.passage(CITATION) is None
    assert views.evidence("r", "c") is None


class OnePassageAndOneEvidence:
    def passage(self, citation: PassageCitation) -> CitedPassage | None:
        if citation != CITATION:
            return None
        return TypeAdapter(CitedPassage).validate_python(PASSAGE)

    def evidence(self, release_id: str, chunk_id: str) -> ArchitectureEvidence | None:
        found = (release_id, chunk_id) == ("rel-1", "chunk-1")
        return TypeAdapter(ArchitectureEvidence).validate_python(EVIDENCE) if found else None


@pytest.fixture
def viewer(container: Container) -> Iterator[TestClient]:
    stubbed = replace(container, knowledge_views=KnowledgeViews(OnePassageAndOneEvidence()))
    with TestClient(create_app(lambda: stubbed)) as client:
        yield client


def test_a_member_opens_the_cited_passage(viewer: TestClient) -> None:
    params = {
        "document_id": "doc/1",
        "publication_id": "pub-1",
        "version_id": "ver-1",
        "revision_id": "rev-1",
        "block_id": "block-1",
    }

    found = viewer.get("/references/passage", params=params)
    gone = viewer.get("/references/passage", params={**params, "revision_id": "older"})

    assert found.status_code == 200, found.text
    assert found.headers["Cache-Control"] == "private, no-store"
    assert found.json()["text"] == "XGPON coverage is required."
    assert gone.status_code == 404
    assert gone.json()["code"] == "knowledge_view_unavailable"
    assert viewer.get("/references/passage", params={"document_id": "doc/1"}).status_code == 422


def test_a_member_opens_impact_evidence(viewer: TestClient) -> None:
    found = viewer.get("/architecture-evidence/rel-1/chunk-1")

    assert found.status_code == 200
    assert found.json()["text"] == "BCRM orders bundles."
    assert viewer.get("/architecture-evidence/draft/chunk-1").status_code == 404


def test_someone_who_is_not_a_knowledge_admin_still_reads_citations_and_evidence(
    viewer: TestClient,
) -> None:
    # fake-observer holds no knowledge role: the views are read-only, open to every member.
    observer = {"X-Fake-Actor-Id": "fake-observer"}
    params = {
        "document_id": "doc/1",
        "publication_id": "pub-1",
        "version_id": "ver-1",
        "revision_id": "rev-1",
        "block_id": "block-1",
    }

    assert viewer.get("/references/passage", params=params, headers=observer).status_code == 200
    assert viewer.get("/architecture-evidence/rel-1/chunk-1", headers=observer).status_code == 200
    # Read-only: nothing here writes.
    assert viewer.post("/references/passage", params=params, headers=observer).status_code == 405


def test_the_version_in_use_is_named_from_the_local_copy(
    container: Container, viewer: TestClient
) -> None:
    container.current_release._releases.apply(10**9, ActiveRelease("rel-9", "Q4 catalogue"))

    assert viewer.get("/architecture/active-release").json() == {
        "id": "rel-9",
        "name": "Q4 catalogue",
    }
