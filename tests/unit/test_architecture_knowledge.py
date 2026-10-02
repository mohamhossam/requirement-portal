"""Human publication and evidence indexing through the Slice 14 boundaries."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.llm.local_structured_output import (
    LocalStructuredOutputClient,
)

from smb_requirement_agent.application.ports.architecture_knowledge import ArchitectureQuery
from smb_requirement_agent.application.ports.architecture_rag import (
    ArchitectureEvidenceError,
    EvidenceChunk,
)
from smb_requirement_agent.application.ports.identity import Actor, AuthorizationError
from smb_requirement_agent.application.use_cases.architecture_documents import (
    UploadKnowledgeDocument,
)
from smb_requirement_agent.application.use_cases.architecture_index import BuildArchitectureIndex
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    KnowledgeConflictError,
    KnowledgeDocumentVersion,
    KnowledgeReleaseStatus,
    SystemDefinition,
    SystemRelationship,
)
from smb_requirement_agent.domain.document.value_objects import DocumentVersionId
from smb_requirement_agent.infrastructure.architecture.catalogue_files import (
    CatalogueFileAdapter,
)
from smb_requirement_agent.infrastructure.architecture.embeddings import (
    DIMENSIONS,
    ArchitectureEmbeddings,
    FakeEmbeddings,
)
from smb_requirement_agent.infrastructure.architecture.evidence_index import InMemoryEvidenceIndex
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.located_extractor import (
    LocatedDocumentExtractor,
)
from smb_requirement_agent.infrastructure.architecture.reasoning import (
    FakeArchitectureReasoner,
    StructuredArchitectureReasoner,
)
from smb_requirement_agent.infrastructure.architecture.tokenizer import (
    ApproximateTokenizer,
    FakeWordTokenizer,
)
from smb_requirement_agent.infrastructure.config.options import (
    ConfigurationError,
    IdentityProvider,
    LLMProvider,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentStorage,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.main import create_app


def test_catalogue_rejects_duplicate_aliases_and_dangling_relationships() -> None:
    with pytest.raises(InvalidKnowledgeError, match="Each name or alias must identify one system"):
        ArchitectureKnowledge(
            "draft",
            1,
            (
                SystemDefinition("one", "One", aliases=("shared",)),
                SystemDefinition("two", "Two", aliases=("shared",)),
            ),
            (),
        )
    with pytest.raises(InvalidKnowledgeError, match="catalogued systems"):
        ArchitectureKnowledge(
            "draft",
            1,
            (SystemDefinition("one", "One"),),
            (SystemRelationship("one", "missing", "Calls"),),
        )


def test_stale_build_cannot_replace_newly_published_evidence() -> None:
    actor = Actor("maintainer", frozenset({"knowledge_maintainer"}))
    repository = InMemoryArchitectureKnowledgeRepository(seed_knowledge())
    replacement: ArchitectureKnowledge | None = None

    class InterleavedEmbeddings(FakeEmbeddings):
        fired = False

        def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
            nonlocal replacement
            if not self.fired:
                self.fired = True
                changed = knowledge.upsert_system(
                    draft.id, draft.revision, SystemDefinition("unique", "Newest evidence"), actor
                )
                builder.execute(changed.id, changed.revision, actor.id, fence=lambda: None)
                replacement = knowledge.publish(
                    changed.id, changed.revision, actor, datetime.now(UTC), "Reviewed"
                )
            return super().embed(texts)

    index = InMemoryEvidenceIndex(InterleavedEmbeddings(), FakeWordTokenizer())
    knowledge = ManageArchitectureKnowledge(repository, CatalogueFileAdapter(), index, 10_000_000)
    draft = knowledge.create_draft(actor, "Next version")
    builder = BuildArchitectureIndex(
        knowledge,
        index,
        InMemoryDocumentStorage(),
        LocatedDocumentExtractor(SafeDocumentTextExtractor()),
        FakeWordTokenizer(),
    )
    with pytest.raises(KnowledgeConflictError):
        builder.execute(draft.id, draft.revision, actor.id, fence=lambda: None)
    assert replacement is not None and replacement.index_id is not None
    evidence = index.retrieve(replacement.index_id, "Newest evidence", 8)
    assert any(item.text == "Newest evidence" for item in evidence)
    assert all(index.get(replacement.index_id, item.id) == item for item in evidence)


def test_deselected_upload_remains_available_without_becoming_reader_visible(
    client: TestClient,
    container: Container,
) -> None:
    draft = client.post("/architecture-knowledge/releases", json={"name": "Next version"}).json()
    root = f"/architecture-knowledge/releases/{draft['id']}"
    uploaded = client.post(
        f"{root}/documents",
        data={"title": "Preserved", "language": "en", "expected_revision": draft["revision"]},
        files={"file": ("notes.txt", b"Preserve this document version", "text/plain")},
    ).json()
    version = uploaded["documents"][0]
    deselected = client.put(
        f"{root}/documents",
        json={
            "expected_revision": uploaded["revision"],
            "version_ids": [],
        },
    ).json()
    assert (
        client.get(f"/architecture-knowledge/documents/versions/{version['id']}").status_code == 200
    )
    reader = Actor("reader", frozenset({"knowledge_reader"}))
    assert not container.manage_architecture_knowledge.document_versions(reader)
    restored = client.put(
        f"{root}/documents",
        json={
            "expected_revision": deselected["revision"],
            "version_ids": [version["id"]],
        },
    )
    assert restored.status_code == 200
    assert restored.json()["documents"] == [version]


def test_draft_is_version_checked_and_published_release_is_immutable() -> None:
    repo = InMemoryArchitectureKnowledgeRepository(seed_knowledge())
    from smb_requirement_agent.application.use_cases.architecture_knowledge import (
        ManageArchitectureKnowledge,
    )

    use_case = ManageArchitectureKnowledge(
        repo,
        CatalogueFileAdapter(),
        InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer()),
        10_000_000,
    )
    actor = Actor("maintainer", frozenset({"knowledge_maintainer"}))
    with pytest.raises(AuthorizationError):
        use_case.create_draft(Actor("reader", frozenset({"knowledge_reader"})), "Next version")
    draft = use_case.create_draft(actor, "Next version")
    changed = use_case.upsert_system(
        draft.id, draft.revision, SystemDefinition("new-system", "New system"), actor
    )
    with pytest.raises(KnowledgeConflictError):
        use_case.update(draft.id, draft.revision, actor)
    built = use_case.mark_built(
        changed.id,
        changed.revision,
        "fake-architecture-embedding-v2:offline-word-v1:section-v2",
        "hash",
        actor.id,
        "index-fixture",
    )
    assert built.built_revision == changed.revision
    from datetime import UTC, datetime

    published = use_case.publish(
        built.id, built.revision, actor, datetime(2026, 1, 1, tzinfo=UTC), "Reviewed"
    )
    assert repo.active().id == published.id
    with pytest.raises(KnowledgeConflictError):
        use_case.upsert_system(
            published.id, published.revision, SystemDefinition("another", "Another"), actor
        )
    with pytest.raises(KnowledgeConflictError, match="immutable"):
        repo.save(
            replace(published, status=KnowledgeReleaseStatus.DRAFT),
            published.revision,
            actor.id,
            "late_build",
        )


def test_upload_build_preview_and_publish(client: TestClient, container: Container) -> None:
    created = client.post("/architecture-knowledge/releases", json={"name": "Next version"})
    assert created.status_code == 201
    draft = created.json()
    content = "نظام BCRM يدعم المبيعات. BCRM supports assisted sales."
    uploaded = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data={
            "title": "SMB architecture",
            "language": "mixed",
            "expected_revision": draft["revision"],
        },
        files={"file": ("knowledge.txt", content.encode(), "text/plain")},
    )
    assert uploaded.status_code == 201
    draft = uploaded.json()
    assert draft["documents"][0]["checksum"]
    job_response = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/build",
        json={"expected_revision": draft["revision"]},
    )
    assert job_response.status_code == 202
    assert job_response.json()["status"] == "succeeded"
    preview = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/preview", json={"query": "BCRM المبيعات"}
    )
    assert preview.status_code == 200
    assert any(item["source_label"] == "SMB architecture" for item in preview.json())
    candidates = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/preview-impact",
        json={"query": "BCRM assisted sales"},
    )
    assert candidates.status_code == 200
    assert "bcrm" in candidates.json()["system_ids"]
    assert candidates.json()["citation_ids"]
    published = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/publish",
        json={"expected_revision": draft["revision"], "rationale": "Verified source"},
    )
    assert published.status_code == 200
    assert client.get("/architecture-knowledge/releases/active").json()["id"] == draft["id"]
    audit = client.get(f"/architecture-knowledge/releases/{draft['id']}/audit")
    assert [event["action"] for event in audit.json()] == [
        "create_draft",
        "upload_document",
        "build_index",
        "publish",
    ]


def test_catalogue_file_import_export_and_document_selection_are_revision_checked(
    client: TestClient,
) -> None:
    draft = client.post("/architecture-knowledge/releases", json={"name": "Next version"}).json()
    base = f"/architecture-knowledge/releases/{draft['id']}"
    exported = client.get(f"{base}/catalogue-file", params={"format": "yaml"})
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/yaml")
    yaml_file = {"file": ("catalogue.yaml", exported.content, "application/yaml")}
    preview = client.post(f"{base}/catalogue-file/preview", files=yaml_file)
    assert preview.status_code == 200
    assert preview.json()["changes"] == []
    imported = client.post(
        f"{base}/catalogue-file", data={"expected_revision": draft["revision"]}, files=yaml_file
    )
    assert imported.status_code == 200
    assert imported.json()["revision"] == draft["revision"] + 1
    stale = client.post(
        f"{base}/catalogue-file", data={"expected_revision": draft["revision"]}, files=yaml_file
    )
    assert stale.status_code == 409
    unknown = client.post(
        f"{base}/catalogue-file/preview", files={"file": ("catalogue.csv", b"a,b", "text/csv")}
    )
    assert unknown.status_code == 422
    selected = client.put(
        f"{base}/documents",
        json={"expected_revision": imported.json()["revision"], "version_ids": []},
    )
    assert selected.status_code == 200


def test_architecture_upload_rejects_mismatched_extension(client: TestClient) -> None:
    draft = client.post("/architecture-knowledge/releases", json={"name": "Next version"}).json()
    response = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data={"title": "Bad upload", "language": "en", "expected_revision": draft["revision"]},
        files={"file": ("not-pdf.txt", b"hello", "application/pdf")},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("filename", "declared"),
    [
        ("landscape.md", "text/markdown"),
        ("landscape.md", "application/octet-stream"),
        ("landscape.md", "text/plain"),
        ("landscape.markdown", "text/x-markdown"),
    ],
)
def test_architecture_upload_accepts_markdown_however_the_browser_types_it(
    client: TestClient, filename: str, declared: str
) -> None:
    draft = client.post("/architecture-knowledge/releases", json={"name": "Next version"}).json()
    response = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data={"title": "Landscape", "language": "en", "expected_revision": draft["revision"]},
        files={"file": (filename, b"# Systems\n\n- Order Hub", declared)},
    )
    assert response.status_code == 201, response.text
    (document,) = response.json()["documents"]
    assert (document["filename"], document["mime_type"]) == (filename, "text/markdown")


def test_architecture_upload_rejects_markdown_declared_as_another_type(
    client: TestClient,
) -> None:
    draft = client.post("/architecture-knowledge/releases", json={"name": "Next version"}).json()
    response = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data={"title": "Bad upload", "language": "en", "expected_revision": draft["revision"]},
        files={"file": ("landscape.md", b"# Systems", "application/pdf")},
    )
    assert response.status_code == 422


def test_architecture_upload_reads_at_most_one_byte_past_the_limit(container: Container) -> None:
    received: list[int] = []

    class RecordingUpload:
        max_bytes = 8

        def execute(self, *args: object) -> object:
            content = args[6]
            assert isinstance(content, bytes)
            received.append(len(content))
            raise InvalidKnowledgeError("Oversized upload rejected by the use case.")

    bounded = replace(
        container, upload_knowledge_document=cast(UploadKnowledgeDocument, RecordingUpload())
    )
    with TestClient(create_app(lambda: bounded)) as client:
        draft = client.post(
            "/architecture-knowledge/releases", json={"name": "Next version"}
        ).json()
        response = client.post(
            f"/architecture-knowledge/releases/{draft['id']}/documents",
            data={"title": "Huge", "language": "en", "expected_revision": draft["revision"]},
            files={"file": ("huge.txt", b"x" * 1_000_000, "text/plain")},
        )

    assert response.status_code == 422
    assert received == [9]


def test_architecture_upload_rejects_duplicate_bytes(client: TestClient) -> None:
    draft = client.post("/architecture-knowledge/releases", json={"name": "Next version"}).json()
    data = {"title": "Knowledge", "language": "en", "expected_revision": draft["revision"]}
    first = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data=data,
        files={"file": ("knowledge.txt", b"BCRM supports sales", "text/plain")},
    )
    assert first.status_code == 201
    data["expected_revision"] = first.json()["revision"]
    duplicate = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data=data,
        files={"file": ("renamed.txt", b"BCRM supports sales", "text/plain")},
    )
    assert duplicate.status_code == 422


def test_reader_cannot_see_drafts_or_publish(container: Container) -> None:
    draft = container.manage_architecture_knowledge.create_draft(
        Actor("maintainer", frozenset({"knowledge_maintainer"})), "Next version"
    )
    headers = {"X-Fake-Actor-Id": "fake-reviewer"}
    with TestClient(create_app(lambda: container)) as client:
        assert client.get("/architecture-knowledge/releases", headers=headers).status_code == 403
        assert (
            client.post(
                "/architecture-knowledge/releases", json={"name": "Next version"}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.get("/architecture-knowledge/releases/active", headers=headers).status_code
            == 200
        )
        assert (
            client.get(f"/architecture-knowledge/releases/{draft.id}", headers=headers).status_code
            == 403
        )
        assert (
            client.get(
                f"/architecture-knowledge/releases/{draft.id}/audit", headers=headers
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/architecture-knowledge/releases/{draft.id}/preview",
                json={"query": "BCRM"},
                headers=headers,
            ).status_code
            == 403
        )


def test_architecture_embeddings_reject_a_well_formed_wrong_dimension() -> None:
    class Short:
        model = "short"

        def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
            return tuple((1.0,) * (DIMENSIONS - 1) for _ in texts)

    from smb_requirement_agent.application.ports.architecture_rag import ArchitectureEvidenceError

    with pytest.raises(ArchitectureEvidenceError):
        ArchitectureEmbeddings(Short()).embed(("query",))


def test_production_requires_real_model_evaluation_approval() -> None:
    with pytest.raises(ConfigurationError, match="KNOWLEDGE_EVALUATION_APPROVED"):
        Settings(
            llm_provider=LLMProvider.FAKE,
            app_environment="production",
            identity_provider=IdentityProvider.OIDC,
            oidc_issuer_url="https://identity.example/tenant",
            oidc_audience="api://smb",
            oidc_client_id="browser",
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url="postgresql://example/test",
        )


def test_production_requires_durable_persistence() -> None:
    with pytest.raises(ConfigurationError, match="PERSISTENCE_PROVIDER=postgres"):
        Settings(
            llm_provider=LLMProvider.FAKE,
            app_environment="production",
            identity_provider=IdentityProvider.OIDC,
            oidc_issuer_url="https://identity.example/tenant",
            oidc_audience="api://smb",
            oidc_client_id="browser",
            knowledge_evaluation_approved=True,
        )


def test_chunk_windows_preserve_exact_text_and_75_token_overlap() -> None:
    builder = BuildArchitectureIndex.__new__(BuildArchitectureIndex)
    builder._tokenizer = FakeWordTokenizer()
    content = " ".join(f"word-{index}" for index in range(600))
    windows = builder._windows(content, "TXT lines 1-10")
    assert len(windows) == 2
    assert windows[0][0].endswith("tokens 1-500")
    assert windows[1][0].endswith("tokens 426-600")
    assert windows[0][1] in content
    assert windows[1][1] in content
    assert windows[0][1].split()[-75:] == windows[1][1].split()[:75]


def test_docx_evidence_retains_table_cell_location() -> None:
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Overview</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Owner unknown</w:t></w:r></w:p>"
        "</w:tc></w:tr></w:tbl></w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", xml)
    located = LocatedDocumentExtractor(SafeDocumentTextExtractor()).extract(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer.getvalue(),
    )
    assert [(item.location, item.text) for item in located] == [
        ("paragraph 1", "Overview"),
        ("table 1, row 1, cell 1, paragraph 2", "Owner unknown"),
    ]


def test_reviewed_retrieval_fixture_reaches_top_eight_and_resolves_citations() -> None:
    cases = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "architecture_retrieval_cases.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(cases) >= 30
    arabic = {
        "bcrm": "نظام إدارة علاقات العملاء",
        "cwom": "تنسيق الطلبات الثابتة",
        "gis": "التحقق من تغطية الشبكة",
        "service-now": "تذاكر إدارة الخدمة",
    }
    seed = seed_knowledge()
    documents = (
        ("conflict-one", "GIS coverage availability is always authoritative."),
        ("conflict-two", "GIS coverage availability can be outdated; verify before use."),
    )
    now = datetime(2026, 9, 23, tzinfo=UTC)
    release = ArchitectureKnowledge(
        "retrieval-evaluation-v1",
        1,
        tuple(replace(item, name_ar=arabic.get(item.id)) for item in seed.systems),
        seed.relationships,
        tuple(
            KnowledgeDocumentVersion(
                doc_id,
                doc_id,
                f"{doc_id}.txt",
                "text/plain",
                "en",
                "checksum",
                doc_id,
                "reviewer",
                now,
            )
            for doc_id, _ in documents
        ),
        capability_domains=seed.capability_domains,
    )
    repository = InMemoryArchitectureKnowledgeRepository(seed)
    repository.save(release, None, "reviewer", "create_draft")
    index = InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer())
    knowledge = ManageArchitectureKnowledge(repository, CatalogueFileAdapter(), index, 10_000_000)
    storage = InMemoryDocumentStorage()
    for doc_id, content in documents:
        storage.put(DocumentVersionId(doc_id), content.encode("utf-8"))
    built = BuildArchitectureIndex(
        knowledge,
        index,
        storage,
        LocatedDocumentExtractor(SafeDocumentTextExtractor()),
        FakeWordTokenizer(),
    ).execute(release.id, release.revision, "reviewer", fence=lambda: None)
    assert built.index_id is not None
    answerable = [case for case in cases if case["system"] is not None]
    found = 0
    for case in answerable:
        results = index.retrieve(built.index_id, case["query"], 8)
        if any(chunk.location == f"system {case['system']}" for chunk in results):
            found += 1
        assert all(index.get(built.index_id, chunk.id) == chunk for chunk in results)
    assert found / len(answerable) >= 0.9
    conflict = index.retrieve(built.index_id, cases[-2]["query"], 8)
    assert {"conflict-one", "conflict-two"} <= {chunk.document_version_id for chunk in conflict}
    empty = cases[-1]
    assert (
        FakeArchitectureReasoner()
        .select(
            ArchitectureQuery((empty["query"],)),
            release,
            index.retrieve(built.index_id, empty["query"], 8),
        )
        .system_ids
        == ()
    )


@pytest.mark.parametrize(
    "citation_id,quote",
    [
        ("invented", "GIS coverage"),
        ("evidence-1", "fabricated passage"),
    ],
)
def test_local_reasoner_rejects_invented_citation_or_quote(
    monkeypatch: pytest.MonkeyPatch,
    citation_id: str,
    quote: str,
) -> None:
    client = LocalStructuredOutputClient(
        base_url="http://localhost:1234/v1",
        http_client=httpx.Client(),
        model="test",
        timeout_seconds=1,
        reasoning_effort=None,
    )
    monkeypatch.setattr(
        client,
        "parse",
        lambda **kwargs: SimpleNamespace(
            impacts=[
                SimpleNamespace(
                    system_id="gis", citations=[SimpleNamespace(id=citation_id, quote=quote)]
                )
            ],
            uncertainty=None,
            conflicts=[],
        ),
    )
    reasoner = StructuredArchitectureReasoner(client, max_input_tokens=4096)
    with pytest.raises(ArchitectureEvidenceError):
        reasoner.select(
            ArchitectureQuery(("GIS coverage",)),
            seed_knowledge(),
            (EvidenceChunk("evidence-1", "GIS", "system gis", "GIS coverage evidence"),),
        )


def test_profile_change_creates_new_build_job(
    container: Container,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = Actor("maintainer", frozenset({"knowledge_maintainer"}))
    draft = container.manage_architecture_knowledge.create_draft(actor, "Next version")
    first = container.architecture_jobs.start_build(draft.id, draft.revision, actor)
    assert first.status == "succeeded"
    monkeypatch.setattr(ApproximateTokenizer, "profile", property(lambda self: "new-tokenizer-v2"))
    second = container.architecture_jobs.enqueue_build(draft.id, draft.revision, actor)
    assert second.id != first.id and second.status == "queued"
    completed = container.architecture_jobs.run_once()
    assert completed is not None and completed.status == "succeeded"


def test_local_reasoner_preserves_each_system_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LocalStructuredOutputClient(
        base_url="http://localhost:1234/v1",
        http_client=httpx.Client(),
        model="test",
        timeout_seconds=1,
        reasoning_effort=None,
    )
    monkeypatch.setattr(
        client,
        "parse",
        lambda **kwargs: SimpleNamespace(
            impacts=[
                SimpleNamespace(
                    system_id=system, citations=[SimpleNamespace(id="shared", quote=quote)]
                )
                for system, quote in (("gis", "GIS coverage"), ("bcrm", "BCRM sales"))
            ],
            uncertainty=None,
            conflicts=[],
        ),
    )
    selected = StructuredArchitectureReasoner(client, max_input_tokens=4096).select(
        ArchitectureQuery(("sales coverage",)),
        seed_knowledge(),
        (EvidenceChunk("shared", "Document", "line 1", "GIS coverage enables BCRM sales"),),
    )
    assert [(item.system_id, item.chunk_id, item.quote) for item in selected.citations] == [
        ("gis", "shared", "GIS coverage"),
        ("bcrm", "shared", "BCRM sales"),
    ]
