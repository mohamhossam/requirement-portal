"""Library trust-boundary and durable-attempt regression tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock

import pytest
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import (
    DocumentNotFoundError,
    DocumentVersionConflictError,
    KnowledgeGenerationError,
    RequirementAnalysisConflictError,
)
from smb_requirement_agent.application.use_cases.document_library import (
    CHUNKING_POLICY,
    TABLE_CHUNKING_POLICY,
    DocumentLibrary,
)
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.application.use_cases.reference_knowledge import (
    CONTEXT_MAX_BUDGET,
    ReferenceKnowledge,
    StructureAwareChunks,
)
from smb_requirement_agent.domain.document.library import (
    IngestionStage,
    LibraryDocument,
    ReviewedPassage,
)
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.infrastructure.documents.library_worker import OfflineDocumentScanner
from smb_requirement_agent.infrastructure.persistence.document_library import (
    InMemoryDocumentLibrary,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.infrastructure.persistence.reference_index import (
    InMemoryReferenceIndex,
    Utf8BudgetCounter,
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


class Embeddings:
    model = "deterministic-test-768"

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0,) + (0.0,) * 767 for _ in texts)


def test_cross_owner_model_rollout_and_rollback_preserve_review_authority() -> None:
    from tests.indexing_contracts import exercise_owner_rollout

    lock = RLock()
    repository = InMemoryDocumentLibrary(lock)
    storage = InMemoryDocumentStorage()
    index = InMemoryReferenceIndex(lock, repository)
    transactions = InMemoryTransactionManager(lambda _: None, lock)
    transactions.enroll(repository, storage, index)
    clock = FixedClock(datetime(2026, 9, 22, tzinfo=UTC))
    service = DocumentLibrary(
        repository,
        storage,
        SafeDocumentTextExtractor(),
        OfflineDocumentScanner(),
        transactions,
        clock,
        100000,
    )
    models = tuple(
        ReferenceKnowledge(
            repository,
            index,
            Embeddings(),
            StructureAwareChunks(Utf8BudgetCounter()),
            transactions,
            clock,
            identity,
        )
        for identity in ("model-A", "model-B")
    )
    exercise_owner_rollout(service, *models)


@pytest.fixture
def library() -> tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary]:
    lock = RLock()
    repository = InMemoryDocumentLibrary(lock)
    storage = InMemoryDocumentStorage()
    index = InMemoryReferenceIndex(lock, repository)
    transactions = InMemoryTransactionManager(lambda _: None, lock)
    transactions.enroll(repository, storage, index)
    clock = FixedClock(datetime(2026, 9, 21, tzinfo=UTC))
    service = DocumentLibrary(
        repository,
        storage,
        SafeDocumentTextExtractor(),
        OfflineDocumentScanner(),
        transactions,
        clock,
        100000,
    )
    knowledge = ReferenceKnowledge(
        repository,
        index,
        Embeddings(),
        StructureAwareChunks(Utf8BudgetCounter()),
        transactions,
        clock,
        "test-model",
    )
    return service, knowledge, repository


def owner() -> ActorProfile:
    return ActorProfile(ActorId("library-owner"), "Owner")


def other() -> ActorProfile:
    return ActorProfile(ActorId("library-reader"), "Reader")


def test_upload_review_publish_withdraw_and_exact_citation(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
) -> None:
    service, knowledge, _ = library
    data = UploadDocumentInput(
        "policy.txt", "text/plain", b"XGPON coverage is required.\nPrivate appendix."
    )
    document = service.submit("Eligibility", data, "upload-1", owner())
    assert service.submit("Eligibility", data, "upload-1", owner()).id == document.id
    assert service.list(other()) == ()
    with pytest.raises(DocumentNotFoundError):
        service.get(document.id, other())
    assert knowledge.search("XGPON") == ()
    assert service.process_next()
    view = service.get(document.id, owner())
    source = view.versions[0]
    assert source.stage is IngestionStage.READY
    passages = tuple(
        ReviewedPassage(b.id, b.text or "", i == 0, "Private material" if i else "")
        for i, b in enumerate(source.blocks)
    )
    document = service.review(
        document.id, source.id, view.version, owner(), passages, "Checked against original"
    )
    revision = document.versions[0].revisions[-1]
    document = service.approve(
        document.id,
        source.id,
        revision.id,
        revision.fingerprint(source.id, CHUNKING_POLICY),
        document.version,
        owner(),
    )
    assert document.published_id is None
    assert service.list(other()) == ()
    assert knowledge.index_next()
    found = knowledge.search("XGPON")
    assert len(found) == 1
    assert found[0].original_text == "XGPON coverage is required."
    assert found[0].location == "Line 1"
    public = service.get(document.id, other())
    assert not public.can_edit
    assert "Private appendix" not in str(public)
    with pytest.raises(AuthorizationDeniedError):
        service.original(document.id, source.id, other())
    service.withdraw(document.id, public.version, owner(), "Policy no longer applicable")
    assert knowledge.search("XGPON") == ()


def test_owner_concurrency_cancel_and_submission_binding(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
) -> None:
    service, _, _ = library
    data = UploadDocumentInput("a.txt", "text/plain", b"Safe policy")
    document = service.submit("Policy", data, "key", owner())
    with pytest.raises(DocumentVersionConflictError):
        service.submit("Policy", replace(data, content=b"different"), "key", owner())
    with pytest.raises(AuthorizationDeniedError):
        service.control(
            document.id, document.versions[0].id, document.version, other(), retry=False
        )
    cancelled = service.control(
        document.id, document.versions[0].id, document.version, owner(), retry=False
    )
    assert not service.process_next()
    with pytest.raises(DocumentVersionConflictError):
        service.control(document.id, document.versions[0].id, document.version, owner(), retry=True)
    service.control(document.id, document.versions[0].id, cancelled.version, owner(), retry=True)
    assert service.process_next()


def test_quarantine_is_not_retryable_or_publishable(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
) -> None:
    service, _, _ = library
    document = service.submit(
        "Unsafe",
        UploadDocumentInput("a.txt", "text/plain", b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"),
        "bad",
        owner(),
    )
    service.process_next()
    view = service.get(document.id, owner())
    assert view.versions[0].stage is IngestionStage.QUARANTINED
    with pytest.raises(DocumentVersionConflictError):
        service.control(document.id, view.versions[0].id, view.version, owner(), retry=True)


def test_expired_attempt_is_recovered_and_old_writer_is_fenced(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
) -> None:
    service, _, repository = library
    document = service.submit(
        "Policy", UploadDocumentInput("a.txt", "text/plain", b"Rule"), "key", owner()
    )
    now = datetime(2026, 9, 21, tzinfo=UTC)
    first = repository.claim(now, now + timedelta(seconds=1), "attempt-1")
    assert first is not None
    second = repository.claim(now + timedelta(seconds=2), now + timedelta(seconds=10), "attempt-2")
    assert second is not None and second.versions[0].attempt == 2
    with pytest.raises(DocumentVersionConflictError):
        repository.save(replace(first, version=first.version + 1), first.version)
    assert repository.get(document.id) == second


def test_csv_values_inert_and_row_citations() -> None:
    result = SafeDocumentTextExtractor().extract_structured(
        "text/csv", b'Channel,Rule\nBCRM,"Coverage, required"\nCPP,=HYPERLINK("bad")'
    )
    assert len(result.evidence_blocks) == 3
    assert result.evidence_blocks[1].label == "Row 2"
    assert "R2C1: BCRM" in result.text
    assert '=HYPERLINK("bad")' in result.text


def test_chunk_budget_preserves_all_arabic_text(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
) -> None:
    service, knowledge, _ = library
    text = "التغطية مطلوبة للاشتراك. " * 100
    document = service.submit(
        "Policy", UploadDocumentInput("a.txt", "text/plain", text.encode()), "ar", owner()
    )
    service.process_next()
    view = service.get(document.id, owner())
    source = view.versions[0]
    document = service.review(
        document.id,
        source.id,
        view.version,
        owner(),
        tuple(ReviewedPassage(b.id, b.text or "", True) for b in source.blocks),
        "Checked Arabic",
    )
    revision = document.versions[0].revisions[-1]
    document = service.approve(
        document.id,
        source.id,
        revision.id,
        revision.fingerprint(source.id, CHUNKING_POLICY),
        document.version,
        owner(),
    )
    chunks = knowledge.preview(document, document.publications[0])
    assert len(chunks) > 1
    assert all(c.token_count <= 768 and c.language == "ar" for c in chunks)
    assert all(c.context_token_count <= CONTEXT_MAX_BUDGET for c in chunks)
    assert "".join(c.original_text for c in chunks) == text.strip()


def test_surrounding_context_is_bounded_to_selected_passages_in_one_section(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
) -> None:
    service, knowledge, _ = library
    content = (
        b"# Eligibility\n"
        b"XGPON coverage is required.\n"
        b"Private operational note.\n"
        b"BCRM and CPP are supported channels.\n"
        b"# Billing\n"
        b"Monthly billing applies.\n"
    )
    document = service.submit(
        "Bundle policy",
        UploadDocumentInput("policy.md", "text/markdown", content),
        "context",
        owner(),
    )
    assert service.process_next()
    view = service.get(document.id, owner())
    source = view.versions[0]
    reviewed = service.review(
        document.id,
        source.id,
        view.version,
        owner(),
        tuple(
            ReviewedPassage(
                block.id,
                block.text or "",
                block.label != "Line 3",
                "Internal operations" if block.label == "Line 3" else "",
            )
            for block in source.blocks
        ),
        "Checked section context",
    )
    revision = reviewed.versions[0].revisions[-1]
    approved = service.approve(
        reviewed.id,
        source.id,
        revision.id,
        revision.fingerprint(source.id, CHUNKING_POLICY),
        reviewed.version,
        owner(),
    )

    chunks = knowledge.preview(approved, approved.publications[-1])
    target = next(chunk for chunk in chunks if chunk.original_text == "XGPON coverage is required.")
    assert target.context_locations == ("Line 1", "Line 2", "Line 4")
    assert "BCRM and CPP" in target.context_text
    assert "Private operational note" not in target.context_text
    assert "Monthly billing" not in target.context_text
    assert target.context_token_count <= CONTEXT_MAX_BUDGET
    assert knowledge.citation(target).excerpt == "XGPON coverage is required."

    assert knowledge.index_next()
    found = next(
        chunk
        for chunk in knowledge.search("XGPON")
        if chunk.original_text == "XGPON coverage is required."
    )
    assert found.context_text == target.context_text


def approve_fixture(
    service: DocumentLibrary, content: bytes = b"Coverage required."
) -> LibraryDocument:
    document = service.submit(
        "Policy",
        UploadDocumentInput("p.txt", "text/plain", content),
        "approved-fixture",
        owner(),
    )
    service.process_next()
    view = service.get(document.id, owner())
    version = view.versions[0]
    reviewed = service.review(
        document.id,
        version.id,
        view.version,
        owner(),
        tuple(ReviewedPassage(b.id, b.text or "", True) for b in version.blocks),
        "Checked",
    )
    revision = reviewed.versions[0].revisions[-1]
    return service.approve(
        document.id,
        version.id,
        revision.id,
        revision.fingerprint(version.id, CHUNKING_POLICY),
        reviewed.version,
        owner(),
    )


def test_index_outage_backs_off_and_requires_explicit_retry_after_three_attempts(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, knowledge, repository = library
    document = approve_fixture(service)
    instant = datetime(2026, 9, 21, tzinfo=UTC)
    monkeypatch.setattr(FixedClock, "now", lambda _self: instant)

    def unavailable(_self: Embeddings, _texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        raise KnowledgeGenerationError("Provider unavailable")

    monkeypatch.setattr(Embeddings, "embed", unavailable)
    for attempt in range(1, 4):
        with pytest.raises(KnowledgeGenerationError):
            knowledge.index_next()
        current = repository.get(document.id)
        assert current is not None and current.published_id is None
        assert current.publications[-1].indexing_attempts == attempt
        assert not knowledge.index_next()  # No hot-loop provider retry.
        instant += timedelta(seconds=30 * attempt)
    assert not knowledge.index_next()
    current_view = service.get(document.id, owner())
    retried = service.retry_index(document.id, current_view.version, owner())
    assert retried.publications[-1].indexing_attempts == 0


def test_withdrawal_during_embedding_cannot_activate_a_stale_publication(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, knowledge, repository = library
    document = approve_fixture(service)

    def withdraw_during_embedding(
        _self: Embeddings, texts: tuple[str, ...]
    ) -> tuple[tuple[float, ...], ...]:
        current = service.get(document.id, owner())
        service.withdraw(document.id, current.version, owner(), "Withdrawn during external call")
        return tuple((1.0,) + (0.0,) * 767 for _ in texts)

    monkeypatch.setattr(Embeddings, "embed", withdraw_during_embedding)
    with pytest.raises(DocumentVersionConflictError, match="changed while indexing"):
        knowledge.index_next()
    current = repository.get(document.id)
    assert current is not None and current.published_id is None
    assert current.publications[-1].withdrawn_at is not None


def test_index_lease_prevents_claim_and_fences_expired_completion(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, knowledge, repository = library
    document = approve_fixture(service)
    instant = datetime(2026, 9, 21, tzinfo=UTC)
    monkeypatch.setattr(FixedClock, "now", lambda _self: instant)

    def delayed_embedding(
        _self: Embeddings, texts: tuple[str, ...]
    ) -> tuple[tuple[float, ...], ...]:
        nonlocal instant
        assert repository.pending_publication(instant) is None
        instant += timedelta(seconds=661)
        return tuple((1.0,) + (0.0,) * 767 for _ in texts)

    monkeypatch.setattr(Embeddings, "embed", delayed_embedding)
    with pytest.raises(DocumentVersionConflictError, match="lease expired"):
        knowledge.index_next()
    current = repository.get(document.id)
    assert current is not None and current.published_id is None
    assert repository.pending_publication(instant) is not None


def test_text_line_locations_count_original_blank_lines() -> None:
    result = SafeDocumentTextExtractor().extract_structured("text/plain", b"\n\nRule.\n")
    assert result.evidence_blocks[0].label == "Line 3"


def test_partial_index_batches_are_invisible_and_reused_after_retry(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, knowledge, repository = library
    content = "\n".join(f"Coverage rule {i}." for i in range(17)).encode()
    document = approve_fixture(service, content)
    instant = datetime(2026, 9, 21, tzinfo=UTC)
    monkeypatch.setattr(FixedClock, "now", lambda _self: instant)
    batches: list[int] = []
    fail_once = True

    def outage_on_last_batch(
        _self: Embeddings, texts: tuple[str, ...]
    ) -> tuple[tuple[float, ...], ...]:
        nonlocal fail_once
        batches.append(len(texts))
        if len(texts) == 1 and fail_once:
            fail_once = False
            raise KnowledgeGenerationError("Temporary outage")
        return tuple((1.0,) + (0.0,) * 767 for _ in texts)

    monkeypatch.setattr(Embeddings, "embed", outage_on_last_batch)
    with pytest.raises(KnowledgeGenerationError):
        knowledge.index_next()
    assert batches == [16, 1]
    current = repository.get(document.id)
    assert current is not None and current.published_id is None
    assert knowledge.search("Coverage") == ()
    batches.clear()
    instant += timedelta(seconds=30)
    assert knowledge.index_next()
    assert batches == [1]  # Completed first batch was reused, not embedded again.
    assert knowledge.search("Coverage")


@pytest.mark.parametrize(
    "value",
    ["rule " * 280, "التغطية مطلوبة " * 120, "value | embedded: delimiter " * 70],
    ids=["long-english", "long-arabic", "literal-delimiters"],
)
def test_table_children_preserve_fields_offsets_and_budgets(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    value: str,
) -> None:
    service, knowledge, _ = library
    content = f'Channel,Rule,Region\nBCRM,"{value}",Dubai\nCPP,Private appendix,Secret'
    document = service.submit(
        "Eligibility", UploadDocumentInput("p.csv", "text/csv", content.encode()), "table", owner()
    )
    service.process_next()
    view = service.get(document.id, owner())
    source = view.versions[0]
    service.review(
        document.id,
        source.id,
        view.version,
        owner(),
        tuple(
            ReviewedPassage(b.id, b.text or "", i == 1, "Private" if i != 1 else "")
            for i, b in enumerate(source.blocks)
        ),
        "Checked table",
    )
    preview = knowledge.preview_build(document.id, owner())
    assert preview.chunking_policy == TABLE_CHUNKING_POLICY
    assert len(preview.chunks) > 1
    approved_text = source.blocks[1].text
    assert approved_text is not None
    assert "".join(c.original_text for c in preview.chunks) == approved_text
    assert preview.chunks[0].original_text.startswith("R2C1: BCRM | ")
    assert all(
        c.token_count <= 768 and c.context_token_count <= CONTEXT_MAX_BUDGET for c in preview.chunks
    )
    assert all(
        approved_text[c.start_offset : c.end_offset] == c.original_text for c in preview.chunks
    )
    assert all("Private appendix" not in c.context_text for c in preview.chunks)
    if " | " not in value:
        assert any(c.field_context == "R2C2:" and "r2c2:" in c.search_text for c in preview.chunks)
    build = start_build(service, knowledge, document.id)
    assert knowledge.index_next()
    ready = service.get(build.id, owner())
    assert ready.published_id is None and knowledge.search("BCRM") == ()
    publication = ready.publications[-1]
    knowledge.activate_build(
        build.id, publication.id, owner(), ready.version, publication.chunk_manifest or ""
    )
    found = knowledge.search("BCRM")
    assert found and all(c.publication_id == publication.id for c in found)
    assert all(c.original_text in approved_text for c in found)


def start_build(
    service: DocumentLibrary, knowledge: ReferenceKnowledge, document_id: str
) -> LibraryDocument:
    preview = knowledge.preview_build(document_id, owner())
    return knowledge.build_review(
        document_id, owner(), preview.document_version, preview.fingerprint, preview.index_identity
    )


@pytest.mark.parametrize("kind", ["pptx", "docx", "csv", "tsv", "xlsx"])
def test_table_rows_flow_through_review_build_and_exact_search(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    kind: str,
) -> None:
    service, knowledge, _ = library
    word = kind == "docx"
    content = reviewed_word_table_document() if word else reviewed_table_presentation()
    mime = DOCX_MIME if word else PPTX_MIME
    expected_location = "Table 1, row 3" if word else "Slide 1, table 1, row 2"
    extraction_version = "structured-docx-sections-v3" if word else f"structured-{kind}-tables-v2"
    if kind == "xlsx":
        mime, content = XLSX_MIME, reviewed_spreadsheet_document()
        expected_location = "Worksheet 1!3:3"
        extraction_version = "structured-xlsx-sections-v3"
    if kind in {"csv", "tsv"}:
        mime, content = reviewed_delimited_table(kind)
        expected_location = "Row 2"
        extraction_version = "structured-delimited-rows-v1"
    expected_field = "B3=" if kind == "xlsx" else "R3C2:" if word else "R2C2:"
    document = service.submit(
        "Table policy",
        UploadDocumentInput(f"policy.{kind}", mime, content),
        "office-table",
        owner(),
    )
    assert service.process_next()
    view = service.get(document.id, owner())
    source = view.versions[0]
    assert source.extraction_version == extraction_version
    assert len(source.blocks) == (6 if kind in {"docx", "xlsx"} else 3) and source.warnings
    approved = source.blocks[3 if kind in {"docx", "xlsx"} else 1]
    service.review(
        document.id,
        source.id,
        view.version,
        owner(),
        tuple(
            ReviewedPassage(
                b.id, b.text or "", b.id == approved.id, "Private" if b.id != approved.id else ""
            )
            for b in source.blocks
        ),
        "Compared source table; excluded private anchor and notes",
    )
    preview = knowledge.preview_build(document.id, owner())
    assert len(preview.chunks) > 1
    assert any(c.field_context == expected_field for c in preview.chunks)
    assert "".join(c.original_text for c in preview.chunks) == approved.text
    assert all(c.child_strategy in {"table_row", "table_field_fragment"} for c in preview.chunks)
    build = start_build(service, knowledge, document.id)
    assert knowledge.index_next()
    ready = service.get(build.id, owner())
    publication = ready.publications[-1]
    knowledge.activate_build(
        build.id, publication.id, owner(), ready.version, publication.chunk_manifest or ""
    )
    found = knowledge.search("XGPON")
    assert found
    for chunk in found:
        assert (
            "private"
            not in (
                chunk.search_text + chunk.context_text + "/".join(chunk.heading_path)
            ).casefold()
        )
        assert "Different table context" not in chunk.context_text
        assert chunk.location == expected_location
        assert chunk.original_text == (approved.text or "")[chunk.start_offset : chunk.end_offset]
        assert chunk.token_count <= 768 and chunk.context_token_count <= CONTEXT_MAX_BUDGET
        knowledge.require_current((knowledge.citation(chunk),))
    public = service.get(document.id, other())
    assert [p.block_id for p in public.versions[0].revisions[0].passages] == [approved.id]


def test_build_requires_explicit_activation_and_preserves_old_citations_until_then(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
) -> None:
    service, knowledge, _ = library
    original = approve_fixture(service)
    assert knowledge.index_next()
    citation = knowledge.citation(knowledge.search("Coverage")[0])
    build = start_build(service, knowledge, original.id)
    assert build.published_id == citation.publication_id
    with pytest.raises(DocumentVersionConflictError):
        knowledge.activate_build(
            build.id, build.publications[-1].id, owner(), build.version, "0" * 64
        )
    assert knowledge.index_next()
    assert not knowledge.index_next()  # A ready build is not repeatedly claimed.
    view = service.get(build.id, owner())
    ready = view.publications[-1]
    assert ready.built_at and ready.chunk_count == 1 and ready.chunk_manifest
    assert ready.activated_at is None
    assert knowledge.search("Coverage")[0].publication_id == citation.publication_id
    knowledge.require_current((citation,))
    activated = knowledge.activate_build(
        build.id, ready.id, owner(), view.version, ready.chunk_manifest
    )
    assert activated.published_id == ready.id
    assert activated.publications[0] == view.publications[0]  # Approval history untouched.
    assert knowledge.search("Coverage")[0].publication_id == ready.id
    with pytest.raises(RequirementAnalysisConflictError):
        knowledge.require_current((citation,))


@pytest.mark.parametrize("change", ["review", "replacement", "withdrawal", "discard"])
def test_changed_source_or_discard_fences_ready_activation(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    change: str,
) -> None:
    service, knowledge, _ = library
    original = approve_fixture(service)
    knowledge.index_next()
    build = start_build(service, knowledge, original.id)
    knowledge.index_next()
    view = service.get(build.id, owner())
    ready = view.publications[-1]
    if change == "review":
        source = view.versions[-1]
        service.review(
            view.id, source.id, view.version, owner(), source.revisions[-1].passages, "New review"
        )
    elif change == "replacement":
        service.submit(
            view.title,
            UploadDocumentInput("p.txt", "text/plain", b"Replacement"),
            "replace",
            owner(),
            view.id,
            view.version,
        )
    elif change == "withdrawal":
        service.withdraw(view.id, view.version, owner(), "Unsafe")
    else:
        knowledge.discard_build(view.id, ready.id, owner(), view.version)
    current = service.get(view.id, owner())
    with pytest.raises(DocumentVersionConflictError):
        knowledge.activate_build(
            view.id, ready.id, owner(), current.version, ready.chunk_manifest or ""
        )
    if change != "withdrawal":
        assert knowledge.search("Coverage")[0].publication_id == view.published_id


def test_build_owner_preconditions_and_manifest_completeness(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, knowledge, _ = library
    original = approve_fixture(service)
    knowledge.index_next()
    preview = knowledge.preview_build(original.id, owner())
    with pytest.raises(AuthorizationDeniedError):
        knowledge.preview_build(original.id, other())
    with pytest.raises(AuthorizationDeniedError):
        knowledge.build_review(
            original.id,
            other(),
            preview.document_version,
            preview.fingerprint,
            preview.index_identity,
        )
    with pytest.raises(DocumentVersionConflictError):
        knowledge.build_review(
            original.id, owner(), preview.document_version, preview.fingerprint, "changed-model"
        )
    build = start_build(service, knowledge, original.id)
    with pytest.raises(DocumentVersionConflictError):
        start_build(service, knowledge, original.id)
    knowledge.index_next()
    view = service.get(build.id, owner())
    ready = view.publications[-1]
    with pytest.raises(AuthorizationDeniedError):
        knowledge.activate_build(
            view.id, ready.id, other(), view.version, ready.chunk_manifest or ""
        )
    with pytest.raises(DocumentVersionConflictError):
        knowledge.activate_build(view.id, ready.id, owner(), view.version, "0" * 64)
    monkeypatch.setattr(InMemoryReferenceIndex, "manifest", lambda *_args: ())
    with pytest.raises(KnowledgeGenerationError, match="incomplete"):
        knowledge.activate_build(
            view.id, ready.id, owner(), view.version, ready.chunk_manifest or ""
        )
    assert service.get(view.id, owner()).published_id == view.published_id


def test_build_cancel_during_provider_call_cannot_commit(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, knowledge, _ = library
    original = approve_fixture(service)
    knowledge.index_next()
    build = start_build(service, knowledge, original.id)

    def discard(_self: Embeddings, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        view = service.get(build.id, owner())
        knowledge.discard_build(view.id, view.publications[-1].id, owner(), view.version)
        return tuple((1.0,) + (0.0,) * 767 for _ in texts)

    monkeypatch.setattr(Embeddings, "embed", discard)
    with pytest.raises(DocumentVersionConflictError):
        knowledge.index_next()
    view = service.get(build.id, owner())
    assert view.published_id == build.published_id and view.publications[-1].built_at is None


@pytest.mark.parametrize("mime", ["text/plain", "text/markdown"])
@pytest.mark.parametrize("include_heading", [False, True])
def test_text_heading_exclusion_or_correction_reaches_search_without_original_wording(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    mime: str,
    include_heading: bool,
) -> None:
    service, knowledge, _ = library
    content = (
        "# Private heading\nXGPON coverage required.\n"
        "### Private subsection\nBCRM and CPP.\n# Other section\nUnrelated billing."
    )
    document = service.submit(
        "Policy", UploadDocumentInput("policy.md", mime, content.encode()), "text", owner()
    )
    assert service.process_next()
    view = service.get(document.id, owner())
    source = view.versions[0]
    review = service.review(
        document.id,
        source.id,
        view.version,
        owner(),
        tuple(
            ReviewedPassage(
                b.id,
                "# Reviewed heading" if b.kind.value == "heading" else b.text or "",
                include_heading if b.kind.value == "heading" else True,
                "Private heading" if b.kind.value == "heading" and not include_heading else "",
            )
            for b in source.blocks
        ),
        "Reviewed original headings independently",
    )
    preview = knowledge.preview_build(document.id, owner())
    assert all("Private" not in str(chunk) for chunk in preview.chunks)
    coverage = next(c for c in preview.chunks if c.original_text == "XGPON coverage required.")
    assert ("Reviewed heading" in coverage.context_text) == include_heading
    assert "BCRM" not in coverage.context_text and "billing" not in coverage.context_text
    assert coverage.heading_path == ("Heading at line 1",)
    build = start_build(service, knowledge, document.id)
    assert knowledge.index_next()
    ready = service.get(document.id, owner())
    publication = ready.publications[-1]
    knowledge.activate_build(
        document.id, publication.id, owner(), ready.version, publication.chunk_manifest or ""
    )
    results = knowledge.search("XGPON")
    assert results and all("Private" not in str(c) for c in results)
    for chunk in results:
        knowledge.require_current((knowledge.citation(chunk),))
    public = service.get(document.id, other())
    assert "Private" not in str(public)
    # A replacement upload cannot mutate the prior extraction or publication.
    current = service.get(document.id, owner())
    replacement = service.submit(
        "Policy",
        UploadDocumentInput("next.txt", "text/plain", b"Replacement"),
        "replacement-text",
        owner(),
        document.id,
        current.version,
    )
    assert replacement.versions[0] == review.versions[0]
    assert replacement.published_id == publication.id == build.publications[-1].id


@pytest.mark.parametrize("include_heading", [False, True])
def test_word_prose_corrections_do_not_publish_original_labels(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    include_heading: bool,
) -> None:
    service, knowledge, _ = library
    document = service.submit(
        "Word policy",
        UploadDocumentInput("policy.docx", DOCX_MIME, reviewed_word_prose_document()),
        "word-prose",
        owner(),
    )
    assert service.process_next()
    view = service.get(document.id, owner())
    source = view.versions[0]
    selected = {source.blocks[1].id, source.blocks[2].id}
    if include_heading:
        selected.add(source.blocks[0].id)
    reviewed = service.review(
        document.id,
        source.id,
        view.version,
        owner(),
        tuple(
            ReviewedPassage(
                b.id,
                (b.text or "").replace("Private", "Reviewed"),
                b.id in selected,
                "" if b.id in selected else "Not shared",
            )
            for b in source.blocks
        ),
        "Corrected wording and excluded appendix",
    )
    preview = knowledge.preview_build(document.id, owner())
    assert all("Private" not in str(c) and "Never publish" not in str(c) for c in preview.chunks)
    paragraph = next(c for c in preview.chunks if c.location == "Paragraph 2")
    assert ("Reviewed heading" in paragraph.context_text) == include_heading
    assert "Reviewed list" in paragraph.context_text
    assert paragraph.heading_path == ("Heading at paragraph 1",)
    build = start_build(service, knowledge, document.id)
    assert knowledge.index_next()
    ready = service.get(document.id, owner())
    publication = ready.publications[-1]
    knowledge.activate_build(
        document.id, publication.id, owner(), ready.version, publication.chunk_manifest or ""
    )
    found = knowledge.search("XGPON")
    assert found and all("Private" not in str(c) and "Never publish" not in str(c) for c in found)
    for chunk in found:
        knowledge.require_current((knowledge.citation(chunk),))
    assert "Private" not in str(service.get(document.id, other()))
    assert service.get(document.id, owner()).versions[0] == reviewed.versions[0]
    assert build.publications[-1].id == publication.id


@pytest.mark.parametrize("include_heading", [False, True])
def test_worksheet_name_review_isolated_from_published_rows_and_replacement(
    library: tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary],
    include_heading: bool,
) -> None:
    service, knowledge, _ = library
    document = service.submit(
        "Workbook policy",
        UploadDocumentInput("policy.xlsx", XLSX_MIME, reviewed_worksheet_names_document()),
        "worksheet-names",
        owner(),
    )
    assert service.process_next()
    view = service.get(document.id, owner())
    source = view.versions[0]
    selected = {source.blocks[1].id}
    if include_heading:
        selected.add(source.blocks[0].id)
    reviewed = service.review(
        document.id,
        source.id,
        view.version,
        owner(),
        tuple(
            ReviewedPassage(
                b.id,
                "Reviewed heading" if b.kind.value == "heading" else b.text or "",
                b.id in selected,
                "" if b.id in selected else "Not shared",
            )
            for b in source.blocks
        ),
        "Corrected or excluded names; excluded empty and hidden tabs",
    )
    preview = knowledge.preview_build(document.id, owner())
    assert all("Private" not in str(c) and "Never publish" not in str(c) for c in preview.chunks)
    row = next(c for c in preview.chunks if c.location == "Worksheet 1!1:1")
    assert ("Reviewed heading" in row.context_text) == include_heading
    assert row.heading_path == ("Worksheet 1",)
    start_build(service, knowledge, document.id)
    assert knowledge.index_next()
    ready = service.get(document.id, owner())
    publication = ready.publications[-1]
    knowledge.activate_build(
        document.id,
        publication.id,
        owner(),
        ready.version,
        publication.chunk_manifest or "",
    )
    found = knowledge.search("XGPON")
    assert found and all("Private" not in str(c) and "Never publish" not in str(c) for c in found)
    for chunk in found:
        knowledge.require_current((knowledge.citation(chunk),))
    assert "Private" not in str(service.get(document.id, other()))
    current = service.get(document.id, owner())
    replacement = service.submit(
        "Workbook policy",
        UploadDocumentInput("next.txt", "text/plain", b"Replacement"),
        "worksheet-replacement",
        owner(),
        document.id,
        current.version,
    )
    assert replacement.versions[0] == reviewed.versions[0]
    assert replacement.published_id == publication.id
