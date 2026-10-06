"""A Requirement's included attachments in its knowledge source (Knowledge Center B1).

An included attachment's passages reach exactly where typed text does: screening for
duplicates and contradictions, knowledge search, and answer suggestions. Each passage cites
its document and block, and the index follows inclusion, new versions, hidden worksheets
and removal.
"""

from __future__ import annotations

import io
from dataclasses import replace
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import Workbook

from smb_requirement_agent.application.ports.requirement_knowledge import KnowledgeReview
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
)
from smb_requirement_agent.domain.document.value_objects import DocumentId
from smb_requirement_agent.domain.knowledge.entities import (
    KnowledgeChunk,
    KnowledgeRelationshipKind,
    KnowledgeSourceKind,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.llm.fake_requirement_knowledge import (
    FakeKnowledgeEmbedding,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentRepository,
)
from smb_requirement_agent.infrastructure.persistence.requirement_knowledge_repository import (
    InMemoryRequirementKnowledgeStore,
)
from smb_requirement_agent.interfaces.api.container import Container
from tests.unit.workflow_helpers import drain_requirement_index

BRD = (
    b"# Business need\n\n"
    b"Business customers order XGPON fibre bundles through the BCRM and CPP channels.\n\n"
    b"# Rules\n\n"
    b"Each XGPON bundle includes a static IP address and a managed router.\n"
)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _document_only(client: TestClient, title: str, content: bytes = BRD) -> tuple[str, str]:
    """A Requirement written as an attachment alone: an empty business need, promoted."""
    draft = client.post("/requirements/drafts", json={"title": title, "description": ""})
    assert draft.status_code == 201, draft.text
    uploaded = client.post(
        f"/requirement-drafts/{draft.json()['id']}/attachments",
        data={"include_in_analysis": "true"},
        files={"file": ("brd.md", content, "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    resumed = client.get(f"/requirements/drafts/{draft.json()['id']}").json()
    promoted = client.post(
        f"/requirements/drafts/{draft.json()['id']}/promote",
        json={"expected_version": resumed["version"]},
    )
    assert promoted.status_code == 201, promoted.text
    return str(promoted.json()["id"]), str(uploaded.json()["id"])


def _corpus(container: Container) -> RequirementKnowledgeCorpus:
    return RequirementKnowledgeCorpus(
        container.requirement_repository,
        container.analysis_repository,
        container.analysis_audit_repository,
        container.access_repository,
        container.knowledge_repository,
        container.document_repository,
    )


def _attachments(container: Container, requirement_id: str) -> list[KnowledgeChunk]:
    """The Requirement's attachment passages as the index holds them, not as it would."""
    (query,) = FakeKnowledgeEmbedding().embed(("",))
    return [
        match.chunk
        for match in container.knowledge_index.search("", query, None, 10_000)
        if match.chunk.requirement_id.value == requirement_id
        and match.chunk.source_kind is KnowledgeSourceKind.ATTACHMENT
    ]


def _screen(container: Container, requirement_id: str) -> KnowledgeReview:
    subject = RequirementId(requirement_id)
    fingerprint = container.get_knowledge_review.execute(subject).current_fingerprint
    drain_requirement_index(container)
    return container.screen_requirement_knowledge.execute(FAKE_ACTORS[0], subject, fingerprint)


def _document(client: TestClient, requirement_id: str, document_id: str) -> dict[str, Any]:
    found = client.get(f"/requirements/{requirement_id}/attachments").json()
    return next(item for item in found if item["id"] == document_id)


def test_two_document_only_requirements_are_screened_as_duplicates_from_their_attachments(
    client: TestClient, container: Container
) -> None:
    canonical, document_id = _document_only(client, "Fibre for small offices")
    candidate, _ = _document_only(client, "Q3 connectivity launch")

    review = _screen(container, candidate)

    finding = next(
        item for item in review.findings if item.related_requirement_id.value == canonical
    )
    assert finding.kind is KnowledgeRelationshipKind.POSSIBLE_DUPLICATE
    cited = [item for item in finding.evidence if item.field.startswith("attachment:")]
    assert cited, [item.field for item in finding.evidence]
    assert all(item.field.startswith(f"attachment:{document_id}:") for item in cited)
    assert {item.evidence_path for item in cited} == {f"/documents/{document_id}"}
    assert any("XGPON" in item.excerpt for item in cited)


def test_each_included_block_is_a_passage_that_names_its_document_and_block(
    client: TestClient, container: Container
) -> None:
    requirement_id, document_id = _document_only(client, "Fibre for small offices")
    drain_requirement_index(container)
    blocks = client.get(f"/documents/{document_id}").json()["versions"][0]["evidence_blocks"]

    passages = _attachments(container, requirement_id)

    assert {item.field for item in passages} == {
        f"attachment:{document_id}:{block['id']}" for block in blocks if block["text"]
    }
    assert all(not item.source_lineage for item in passages)
    assert all(item.evidence_path == f"/documents/{document_id}" for item in passages)


def test_excluding_an_attachment_takes_its_passages_out_and_staleness_follows(
    client: TestClient, container: Container
) -> None:
    canonical, document_id = _document_only(client, "Fibre for small offices")
    candidate, _ = _document_only(client, "Q3 connectivity launch")
    finding = _screen(container, candidate).findings[0]
    store = container.knowledge_index
    assert isinstance(store, InMemoryRequirementKnowledgeStore)
    before = dict(store.source_versions())[RequirementId(canonical)]

    document = _document(client, canonical, document_id)
    excluded = client.put(
        f"/requirements/{canonical}/attachments/{document_id}/analysis-inclusion",
        json={"included": False, "expected_version": document["version"]},
    )

    assert excluded.status_code == 200, excluded.text
    # The exclusion marked the Requirement for re-indexing, as an edit to a typed field does.
    # The change number only grows; the TestClient's own indexer may already have run.
    assert dict(store.source_versions())[RequirementId(canonical)] > before
    drain_requirement_index(container)
    assert _attachments(container, canonical) == []
    assert not _corpus(container).citations_current(finding.evidence)


def test_a_new_version_replaces_the_old_passages(client: TestClient, container: Container) -> None:
    requirement_id, document_id = _document_only(client, "Fibre for small offices")
    drain_requirement_index(container)
    before = {item.text for item in _attachments(container, requirement_id)}

    document = _document(client, requirement_id, document_id)
    replaced = client.post(
        f"/requirements/{requirement_id}/attachments/{document_id}/versions",
        data={"expected_version": str(document["version"]), "include_in_analysis": "true"},
        files={"file": ("brd.md", b"# Need\n\nResidential copper retirement.\n", "text/markdown")},
    )

    assert replaced.status_code == 201, replaced.text
    drain_requirement_index(container)
    after = {item.text for item in _attachments(container, requirement_id)}
    assert after and after.isdisjoint(before)
    assert any("copper" in text for text in after)


def test_removing_an_attachment_removes_its_passages(
    client: TestClient, container: Container
) -> None:
    requirement_id, document_id = _document_only(client, "Fibre for small offices")
    drain_requirement_index(container)
    assert _attachments(container, requirement_id)
    document = _document(client, requirement_id, document_id)

    removed = client.delete(
        f"/requirements/{requirement_id}/attachments/{document_id}",
        params={"expected_version": document["version"]},
    )

    assert removed.status_code == 204, removed.text
    drain_requirement_index(container)
    assert _attachments(container, requirement_id) == []


def test_a_hidden_worksheet_is_indexed_only_once_someone_includes_it(
    client: TestClient, container: Container
) -> None:
    created = client.post(
        "/requirements", json={"title": "Order workflow", "description": "Order a bundle."}
    )
    requirement_id = str(created.json()["id"])
    workbook = Workbook()
    visible = workbook.active
    assert visible is not None
    visible["A1"] = "Validate the customer before activation"
    hidden = workbook.create_sheet("Internal")
    hidden.sheet_state = "hidden"
    hidden["A1"] = "Unconfirmed discount rule"
    stream = io.BytesIO()
    workbook.save(stream)
    uploaded = client.post(
        f"/requirements/{requirement_id}/attachments",
        data={"include_in_analysis": "true"},
        files={"file": ("workflow.xlsx", stream.getvalue(), XLSX)},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    drain_requirement_index(container)

    texts = " ".join(item.text for item in _attachments(container, requirement_id))
    assert "Validate the customer" in texts
    assert "Unconfirmed discount rule" not in texts

    selected = client.put(
        f"/requirements/{requirement_id}/attachments/{document['id']}/hidden-worksheets",
        json={"worksheet_names": document["hidden_worksheets"], "expected_version": 2},
    )
    assert selected.status_code == 200, selected.text
    drain_requirement_index(container)
    texts = " ".join(item.text for item in _attachments(container, requirement_id))
    assert "Unconfirmed discount rule" in texts


def test_knowledge_search_finds_an_attachment_passage(
    client: TestClient, container: Container
) -> None:
    requirement_id, document_id = _document_only(client, "Fibre for small offices")
    drain_requirement_index(container)

    found = client.post("/knowledge/search/unified", json={"query": "static IP managed router"})

    assert found.status_code == 200, found.text
    hit = next(
        item
        for item in found.json()
        if item["source_type"] == "requirement" and item["source_id"] == requirement_id
    )
    assert hit["evidence_path"] == f"/documents/{document_id}"
    assert hit["requirement_evidence"]["field"].startswith(f"attachment:{document_id}:")


def test_answer_suggestions_can_cite_an_attachment_passage(
    client: TestClient, container: Container
) -> None:
    _document_only(client, "Archive")
    subject = client.post(
        "/requirements",
        json={"title": "XGPON bundles", "description": "Prepare the XGPON bundle launch."},
    ).json()
    subject_id = RequirementId(subject["id"])
    container.analyze_requirement.execute(FAKE_ACTORS[0], subject_id)
    question = container.analysis_audit_repository.list_questions(subject_id)[0]
    drain_requirement_index(container)

    result = container.suggest_clarification_answers.execute(
        subject_id, question.id, question.version, FAKE_ACTORS[0]
    )

    cited = [e for item in result.suggestions for e in item.evidence]
    assert any(e.field.startswith("attachment:") for e in cited), [e.field for e in cited]


def test_the_memory_repository_marks_a_requirement_on_every_document_write(
    client: TestClient, container: Container
) -> None:
    """The memory twin of PostgreSQL's trigger on source_documents."""
    requirement_id, document_id = _document_only(client, "Fibre for small offices")
    stored = container.document_repository.get(DocumentId(document_id))
    assert stored is not None
    marked: list[RequirementId] = []
    repository = InMemoryDocumentRepository(marked.append)

    repository.add(stored)
    repository.save(stored.set_included(False))
    repository.add(
        replace(
            stored, id=DocumentId("draft-doc"), requirement_id=None, draft_id=stored.requirement_id
        )
    )

    assert marked == [RequirementId(requirement_id)] * 2
