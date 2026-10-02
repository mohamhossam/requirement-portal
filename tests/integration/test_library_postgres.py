"""Real PostgreSQL/pgvector library round trip, publication and replacement contract."""

import os
import uuid
from datetime import UTC, datetime

import psycopg
import pytest
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.persistence.connector import (
    DirectPostgresConnector,
)
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.use_cases.document_library import (
    CHUNKING_POLICY,
    DocumentLibrary,
)
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.application.use_cases.reference_currency import ReferenceCurrency
from smb_requirement_agent.application.use_cases.reference_knowledge import (
    ReferenceKnowledge,
    StructureAwareChunks,
)
from smb_requirement_agent.domain.document.library import OwnershipTransfer, ReviewedPassage
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile
from smb_requirement_agent.infrastructure.documents.library_worker import OfflineDocumentScanner
from smb_requirement_agent.infrastructure.persistence.document_library import (
    PostgresDocumentLibrary,
    PublishingDocumentLibrary,
)
from smb_requirement_agent.infrastructure.persistence.knowledge_events import (
    PostgresKnowledgeEvents,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_document_repository import (
    PostgresDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.infrastructure.persistence.reference_index import (
    PostgresReferenceIndex,
    Utf8BudgetCounter,
)
from smb_requirement_agent.infrastructure.persistence.reference_publications import (
    PostgresReferencePublications,
)
from tests.delimited_fixtures import reviewed_delimited_table
from tests.presentation_fixtures import PPTX_MIME, reviewed_table_presentation
from tests.spreadsheet_fixtures import (
    XLSX_MIME,
    reviewed_spreadsheet_document,
    reviewed_worksheet_names_document,
)
from tests.word_table_fixtures import (
    DOCX_MIME,
    reviewed_word_prose_document,
    reviewed_word_table_document,
)


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured"
)
def test_postgres_owner_projection_history_and_uploader_keys() -> None:
    from smb_requirement_agent.application.errors import DocumentVersionConflictError

    store = PostgresStore(
        DirectPostgresConnector(os.environ["TEST_DATABASE_URL"]),
        lambda _id, _conn: None,
        lambda _conn, _ids: None,
    )
    repository = PostgresDocumentLibrary(store)
    clock = FixedClock(datetime(2026, 9, 22, tzinfo=UTC))
    service = DocumentLibrary(
        repository,
        PostgresDocumentStorage(store),
        SafeDocumentTextExtractor(),
        OfflineDocumentScanner(),
        store,
        clock,
        100000,
    )
    unique = str(uuid.uuid4())
    owner = ActorProfile(ActorId(f"owner-{unique}"), "Original owner")
    target = ActorProfile(ActorId(f"target-{unique}"), "New owner")
    original = service.submit(
        "Handover", UploadDocumentInput("policy.txt", "text/plain", b"Policy"), unique, owner
    )
    transfer = OwnershipTransfer(
        owner.snapshot(), target.snapshot(), owner.snapshot(), clock.now(), "Custodian changed"
    )
    with store.transaction():
        updated = original.transfer(transfer)
        repository.save(updated, original.version)
    restarted = PostgresDocumentLibrary(store)
    assert restarted.get(original.id) == updated
    assert restarted.list_visible(owner.id.value, 0, 100) == ()
    assert restarted.list_visible(target.id.value, 0, 100) == (updated,)
    assert restarted.find_submission(owner.id.value, unique) == updated
    assert restarted.find_submission(target.id.value, unique) is None
    with pytest.raises(DocumentVersionConflictError), store.transaction():
        repository.save(updated, original.version)
    replacement = service.submit(
        "Handover",
        UploadDocumentInput("new.txt", "text/plain", b"New policy"),
        unique,
        target,
        original.id,
        updated.version,
    )
    assert restarted.find_submission(target.id.value, unique) == replacement
    assert restarted.find_submission(owner.id.value, unique) == replacement
    assert replacement.ownership_history == (transfer,)
    assert replacement.versions[0] == original.versions[0]


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured"
)
def test_cross_owner_rollout_and_rollback_with_postgres_vectors() -> None:
    from tests.indexing_contracts import exercise_owner_rollout

    store = PostgresStore(
        DirectPostgresConnector(os.environ["TEST_DATABASE_URL"]),
        lambda _id, _conn: None,
        lambda _conn, _ids: None,
    )
    repository = PostgresDocumentLibrary(store)
    clock = FixedClock(datetime(2026, 9, 22, tzinfo=UTC))
    service = DocumentLibrary(
        repository,
        PostgresDocumentStorage(store),
        SafeDocumentTextExtractor(),
        OfflineDocumentScanner(),
        store,
        clock,
        100000,
    )
    models = tuple(
        ReferenceKnowledge(
            repository,
            PostgresReferenceIndex(store),
            ConstantEmbeddings(),
            StructureAwareChunks(Utf8BudgetCounter()),
            store,
            clock,
            identity,
        )
        for identity in ("A", "B")
    )
    exercise_owner_rollout(service, models[0], models[1])


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured"
)
@pytest.mark.parametrize(
    "kind", ["pptx", "docx", "csv", "tsv", "xlsx", "txt", "md", "docx-prose", "xlsx-names"]
)
def test_postgres_table_rows_and_exclusions_survive_ready_build_restart(kind: str) -> None:
    word = kind == "docx"
    content = reviewed_word_table_document() if word else reviewed_table_presentation()
    mime = DOCX_MIME if word else PPTX_MIME
    expected_location = "Table 1, row 3" if word else "Slide 1, table 1, row 2"
    extraction_version = "structured-docx-sections-v3" if word else f"structured-{kind}-tables-v2"
    if kind == "xlsx":
        mime, content = XLSX_MIME, reviewed_spreadsheet_document()
        expected_location = "Worksheet 1!3:3"
        extraction_version = "structured-xlsx-sections-v3"
    if kind == "xlsx-names":
        mime, content = XLSX_MIME, reviewed_worksheet_names_document()
        expected_location = "Worksheet 1!1:1"
        extraction_version = "structured-xlsx-sections-v3"
    if kind in {"csv", "tsv"}:
        mime, content = reviewed_delimited_table(kind)
        expected_location = "Row 2"
        extraction_version = "structured-delimited-rows-v1"
    if kind in {"txt", "md"}:
        mime = "text/plain" if kind == "txt" else "text/markdown"
        content = "# Private heading\nXGPON التغطية مطلوبة\n# Private appendix".encode()
        expected_location = "Line 2"
        extraction_version = "structured-text-sections-v1"
    if kind == "docx-prose":
        mime, content = DOCX_MIME, reviewed_word_prose_document()
        expected_location = "Paragraph 2"
        extraction_version = "structured-docx-sections-v3"
    url = os.environ["TEST_DATABASE_URL"]
    store = PostgresStore(
        DirectPostgresConnector(url), lambda _id, _conn: None, lambda _conn, _ids: None
    )
    repository = PostgresDocumentLibrary(store)
    clock = FixedClock(datetime(2026, 9, 21, tzinfo=UTC))
    service = DocumentLibrary(
        repository,
        PostgresDocumentStorage(store),
        SafeDocumentTextExtractor(),
        OfflineDocumentScanner(),
        store,
        clock,
        100000,
    )
    knowledge = ReferenceKnowledge(
        repository,
        PostgresReferenceIndex(store),
        ConstantEmbeddings(),
        StructureAwareChunks(Utf8BudgetCounter()),
        store,
        clock,
        f"{kind}-contract",
    )
    actor = ActorProfile(ActorId(str(uuid.uuid4())), "Slide owner")
    document = service.submit(
        "Slide policy",
        UploadDocumentInput(
            "policy.docx"
            if kind == "docx-prose"
            else "policy.xlsx"
            if kind == "xlsx-names"
            else f"policy.{kind}",
            mime,
            content,
        ),
        str(uuid.uuid4()),
        actor,
    )
    assert service.process_next()
    view = service.get(document.id, actor)
    source = view.versions[0]
    included = source.blocks[3 if kind in {"docx", "xlsx"} else 1]
    expected_text = (
        (included.text or "").replace("Private", "Reviewed")
        if kind == "docx-prose"
        else included.text or ""
    )
    service.review(
        document.id,
        source.id,
        view.version,
        actor,
        tuple(
            ReviewedPassage(
                b.id,
                expected_text if b.id == included.id else b.text or "",
                b.id == included.id,
                "Private" if b.id != included.id else "",
            )
            for b in source.blocks
        ),
        "Checked slide table",
    )
    preview = knowledge.preview_build(document.id, actor)
    knowledge.build_review(
        document.id, actor, preview.document_version, preview.fingerprint, preview.index_identity
    )
    assert knowledge.index_next()
    restarted_store = PostgresStore(
        DirectPostgresConnector(url), lambda _id, _conn: None, lambda _conn, _ids: None
    )
    restarted_repository = PostgresDocumentLibrary(restarted_store)
    restarted = ReferenceKnowledge(
        restarted_repository,
        PostgresReferenceIndex(restarted_store),
        ConstantEmbeddings(),
        StructureAwareChunks(Utf8BudgetCounter()),
        restarted_store,
        clock,
        f"{kind}-contract",
    )
    durable = restarted_repository.get(document.id)
    assert (
        durable is not None and durable.versions[0] == service.get(document.id, actor).versions[0]
    )
    assert durable.versions[0].extraction_version == extraction_version
    assert restarted.search("XGPON") == ()
    publication = durable.publications[-1]
    assert publication.built_at and publication.chunk_manifest
    restarted.activate_build(
        document.id, publication.id, actor, durable.version, publication.chunk_manifest
    )
    results = restarted.search("XGPON")
    assert results
    assert all(c.location == expected_location for c in results)
    assert all("Private" not in str(c) for c in results)
    assert all("private" not in (c.context_text + c.search_text).casefold() for c in results)
    assert all(c.original_text == expected_text[c.start_offset : c.end_offset] for c in results)


class ConstantEmbeddings:
    model = "postgres-contract-test"

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0,) + (0.0,) * 767 for _ in texts)


@pytest.fixture(autouse=True)
def isolated_library_tables() -> None:
    """TEST_DATABASE_URL must name a disposable database, as in the existing PG suite."""
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        run_migrations(url)
        with psycopg.connect(url) as connection:
            connection.execute(
                "TRUNCATE library_chunks, library_embedding_cache, "
                "library_submissions, library_documents CASCADE"
            )


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured"
)
def test_postgres_library_publication_survives_restart_and_replacement() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    run_migrations(url)
    store = PostgresStore(
        DirectPostgresConnector(url), lambda _id, _connection: None, lambda _connection, _ids: None
    )
    repository = _publishing(store)
    currency = ReferenceCurrency(PostgresReferencePublications(store), store)
    storage = PostgresDocumentStorage(store)
    clock = FixedClock(datetime(2026, 9, 21, tzinfo=UTC))
    service = DocumentLibrary(
        repository,
        storage,
        SafeDocumentTextExtractor(),
        OfflineDocumentScanner(),
        store,
        clock,
        10000,
    )
    knowledge = ReferenceKnowledge(
        repository,
        PostgresReferenceIndex(store),
        ConstantEmbeddings(),
        StructureAwareChunks(Utf8BudgetCounter()),
        store,
        clock,
        "contract-test",
    )
    actor = ActorProfile(ActorId(str(uuid.uuid4())), "Policy owner")
    document = service.submit(
        "Coverage",
        UploadDocumentInput("policy.txt", "text/plain", b"XGPON coverage required."),
        str(uuid.uuid4()),
        actor,
    )
    assert service.process_next()
    view = service.get(document.id, actor)
    version = view.versions[0]
    reviewed = service.review(
        document.id,
        version.id,
        view.version,
        actor,
        tuple(ReviewedPassage(b.id, b.text or "", True) for b in version.blocks),
        "Checked",
    )
    revision = reviewed.versions[0].revisions[-1]
    approved = service.approve(
        document.id,
        version.id,
        revision.id,
        revision.fingerprint(version.id, CHUNKING_POLICY),
        reviewed.version,
        actor,
    )
    assert approved.published_id is None
    assert knowledge.index_next()
    assert any(c.document_id == document.id for c in knowledge.search("XGPON"))
    restarted = PostgresDocumentLibrary(
        PostgresStore(
            DirectPostgresConnector(url), lambda _id, _conn: None, lambda _conn, _ids: None
        )
    )
    durable = restarted.get(document.id)
    assert durable is not None and durable.published_id is not None
    old_publication = durable.published_id
    contract = knowledge.preview_build(document.id, actor)
    build = knowledge.build_review(
        document.id, actor, contract.document_version, contract.fingerprint, contract.index_identity
    )
    assert knowledge.index_next()
    ready = restarted.get(document.id)
    assert ready is not None and ready.published_id == old_publication
    generation = ready.publications[-1]
    assert (
        generation.built_at is not None
        and generation.chunk_manifest
        and generation.chunk_count == 1
    )
    assert not knowledge.index_next()
    assert all(c.publication_id != generation.id for c in knowledge.search("XGPON"))
    restarted_store = PostgresStore(
        DirectPostgresConnector(url), lambda _id, _conn: None, lambda _conn, _ids: None
    )
    restarted_knowledge = ReferenceKnowledge(
        _publishing(restarted_store),
        PostgresReferenceIndex(restarted_store),
        ConstantEmbeddings(),
        StructureAwareChunks(Utf8BudgetCounter()),
        restarted_store,
        clock,
        "contract-test",
    )
    durable = restarted_knowledge.activate_build(
        build.id, generation.id, actor, ready.version, generation.chunk_manifest
    )
    assert restarted.get(build.id) == durable
    assert knowledge.search("XGPON")[0].publication_id == generation.id
    from smb_requirement_agent.application.use_cases.analysis_mapping import build_analysis
    from smb_requirement_agent.application.use_cases.create_requirement import (
        CreateRequirement,
        CreateRequirementInput,
    )
    from smb_requirement_agent.domain.analysis.value_objects import (
        IntentProposalKind,
        IntentProposalStatus,
    )
    from smb_requirement_agent.domain.shared.generation import Provenance
    from smb_requirement_agent.infrastructure.llm.fake_requirement_analyzer import (
        FakeRequirementAnalyzer,
    )
    from smb_requirement_agent.infrastructure.persistence.postgres_repositories import (
        PostgresAnalysisRepository,
        PostgresRequirementRepository,
    )

    requirement = CreateRequirement(PostgresRequirementRepository(store)).execute(
        CreateRequirementInput("XGPON", "Coverage ordering")
    )
    candidate = FakeRequirementAnalyzer().analyze(requirement, ())
    citation = knowledge.citation(knowledge.search("XGPON")[0])
    candidate["intent_proposals"] = [
        {
            "kind": IntentProposalKind.BUSINESS_RULE,
            "statement": citation.excerpt,
            "rationale": "Review applicability",
            "success_measures": [],
            "reference_evidence": (citation,),
            "reference_provenance": Provenance(clock.now(), "fake", "test-v1"),
        }
    ]
    analysis = build_analysis(requirement.id, candidate, (), ())
    analysis = analysis.decide_intent_proposal(
        analysis.intent_proposals[0].id,
        IntentProposalStatus.ACCEPTED,
        actor,
        clock.now(),
        1,
        rationale="Covered offer",
    )
    PostgresAnalysisRepository(store).save(analysis)
    reloaded = PostgresAnalysisRepository(
        PostgresStore(
            DirectPostgresConnector(url), lambda _id, _conn: None, lambda _conn, _ids: None
        )
    ).get_by_requirement_id(requirement.id)
    assert reloaded == analysis
    knowledge.require_current(reloaded.intent_proposals[0].reference_evidence)
    # Requirement work answers the same question from its local copy (ADR-0099).
    currency.require_current(reloaded.intent_proposals[0].reference_evidence)
    from smb_requirement_agent.domain.analysis.value_objects import QuestionId
    from smb_requirement_agent.domain.knowledge.entities import (
        AnswerSuggestion,
        AnswerSuggestionId,
        AnswerSuggestionSet,
        AnswerSuggestionSetId,
    )
    from smb_requirement_agent.infrastructure.persistence.postgres_requirement_knowledge import (
        PostgresRequirementKnowledgeStore,
    )

    suggestions = AnswerSuggestionSet(
        AnswerSuggestionSetId(str(uuid.uuid4())),
        requirement.id,
        QuestionId(str(uuid.uuid4())),
        "question-fingerprint",
        (
            AnswerSuggestion(
                AnswerSuggestionId(str(uuid.uuid4())),
                citation.excerpt,
                "Published reference; owner decides applicability",
                (),
                (citation,),
            ),
        ),
        Provenance(clock.now(), "fake", "clarification-suggestions-v4"),
    )
    PostgresRequirementKnowledgeStore(store).append_suggestion_set(suggestions)
    restored = PostgresRequirementKnowledgeStore(restarted_store).latest_suggestion_set(
        requirement.id, suggestions.question_id.value
    )
    assert restored == suggestions
    replacement = service.submit(
        "Coverage",
        UploadDocumentInput("policy.txt", "text/plain", b"Private replacement."),
        str(uuid.uuid4()),
        actor,
        document.id,
        durable.version,
    )
    assert replacement.published_id == durable.published_id
    assert any(c.document_id == document.id for c in knowledge.search("XGPON"))
    service.withdraw(document.id, replacement.version, actor, "Unsafe policy")
    assert not any(c.document_id == document.id for c in knowledge.search("XGPON"))
    assert currency.stale_proposals(reloaded.intent_proposals) == (
        analysis.intent_proposals[0].id.value,
    )
    assert PostgresAnalysisRepository(store).get_by_requirement_id(requirement.id) == analysis


def _publishing(store: PostgresStore) -> PublishingDocumentLibrary:
    """A library repository that keeps requirement work's local copy current, as wired."""
    return PublishingDocumentLibrary(
        PostgresDocumentLibrary(store),
        PostgresKnowledgeEvents(store),
        PostgresReferencePublications(store).apply,
    )
