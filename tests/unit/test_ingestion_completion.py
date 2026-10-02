"""Source comparison, scoped warning resolution and asynchronous attachment regression cases."""

import io
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from PIL import Image
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import (
    DocumentNotFoundError,
    DocumentVersionConflictError,
)
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.document_library import DocumentLibrary
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.application.use_cases.reference_knowledge import ReferenceKnowledge
from smb_requirement_agent.application.use_cases.requirement_drafts import RequirementDraftInput
from smb_requirement_agent.domain.document.entities import DocumentExtractionWarning
from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.document.library import (
    AttachmentTarget,
    ExtractionRevision,
    LibraryDocument,
    ReviewedPassage,
)
from smb_requirement_agent.domain.document.value_objects import (
    DocumentId,
    ExtractionWarningSeverity,
)
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.persistence.document_library import (
    InMemoryDocumentLibrary,
)
from smb_requirement_agent.interfaces.api.container import build_container
from tests.presentation_fixtures import PPTX_MIME, drawing_paragraph, presentation
from tests.unit.test_document_library import library as library  # noqa: F401
from tests.unit.test_document_library import other, owner

LibraryFixture = tuple[DocumentLibrary, ReferenceKnowledge, InMemoryDocumentLibrary]


def test_warning_exclusion_is_exact_reversible_and_legacy_safe(library: LibraryFixture) -> None:
    service, _, _ = library
    uploaded = service.submit(
        "Policy",
        UploadDocumentInput("rules.txt", "text/plain", b"Keep\nProblem\nOther"),
        "scope",
        owner(),
    )
    service.process_next()
    source = service.get(uploaded.id, owner()).versions[0]
    warnings = (
        DocumentExtractionWarning(
            "region", ExtractionWarningSeverity.BLOCKING, "Region failed", source.blocks[1].id
        ),
        DocumentExtractionWarning("global", ExtractionWarningSeverity.BLOCKING, "Document failed"),
    )
    source = replace(
        source, warning_details=warnings, blocking_warnings=tuple(w.message for w in warnings)
    )

    def reviewed(excluded: str) -> ExtractionRevision:
        return ExtractionRevision(
            "r",
            datetime.now(UTC),
            owner().snapshot(),
            tuple(
                ReviewedPassage(
                    b.id, b.text or "", b.id != excluded, "Irrelevant" if b.id == excluded else ""
                )
                for b in source.blocks
            ),
            "Checked source",
        )

    unrelated = replace(source, revisions=(reviewed(source.blocks[2].id),))
    assert unrelated.unresolved_blocking_warnings == ("Region failed", "Document failed")
    scoped = replace(source, revisions=(reviewed(source.blocks[1].id),))
    assert scoped.unresolved_blocking_warnings == ("Document failed",)
    assert replace(scoped, revisions=()).unresolved_blocking_warnings == (
        "Region failed",
        "Document failed",
    )
    assert replace(scoped, warning_details=()).unresolved_blocking_warnings == (
        "Region failed",
        "Document failed",
    )
    # Stored JSON round-trips preserve warning scope; legacy payloads remain readable.
    doc = replace(uploaded, versions=(scoped,))
    codec = TypeAdapter(LibraryDocument)
    assert codec.validate_json(codec.dump_json(doc)) == doc


def test_original_image_preview_is_owner_only_and_sanitized(library: LibraryFixture) -> None:
    service, _, _ = library
    output = io.BytesIO()
    Image.new("RGB", (128, 128), "white").save(output, format="PNG")
    upload = service.submit(
        "Source",
        UploadDocumentInput("image.png", "image/png", output.getvalue()),
        "preview",
        owner(),
    )
    service.process_next()
    source = service.get(upload.id, owner()).versions[0]
    block = source.blocks[0]
    result = service.preview_original(upload.id, source.id, block.id, owner())
    assert result.image_data is not None
    assert result.image_data.startswith("data:image/")
    with pytest.raises(AuthorizationDeniedError):
        service.preview_original(upload.id, source.id, block.id, other())
    with pytest.raises(DocumentNotFoundError):
        service.preview_original(upload.id, source.id, "another-version-block", owner())


@pytest.mark.parametrize("is_draft", [False, True])
def test_async_attachment_cancel_retry_and_atomic_completion(is_draft: bool) -> None:
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE, library_scan_mode="offline")
    )
    actor = FAKE_ACTORS[0]
    requirement = (
        container.create_requirement_draft.execute(
            RequirementDraftInput("Need", "Order a bundle"), actor
        )
        if is_draft
        else container.create_requirement.execute(
            CreateRequirementInput("Need", "Order a bundle"), actor
        )
    )
    service = container.attachment_ingestion
    target = AttachmentTarget(requirement.id.value, is_draft, True)
    data = UploadDocumentInput("policy.txt", "text/plain", b"Approved channels are BCRM and CPP.")
    with pytest.raises(AuthorizationDeniedError):
        service.list(requirement.id.value, is_draft, FAKE_ACTORS[2])
    with pytest.raises(AuthorizationDeniedError):
        service.submit(target, data, "denied", FAKE_ACTORS[2])
    queued = service.submit(target, data, "attachment-key", actor)
    assert service.submit(target, data, "attachment-key", actor).id == queued.id
    assert container.document_library.list(actor) == ()
    with pytest.raises(DocumentNotFoundError):
        container.document_library.get(queued.id, actor)
    cancelled = service.control(
        requirement.id.value, is_draft, queued.id, queued.version, False, actor
    )
    assert cancelled.stage == "cancelled"
    assert not container.document_library.process_next()
    retried = service.control(
        requirement.id.value, is_draft, queued.id, cancelled.version, True, actor
    )
    with pytest.raises(DocumentVersionConflictError):
        service.control(requirement.id.value, is_draft, queued.id, cancelled.version, False, actor)
    assert retried.stage == "queued"
    assert container.document_library.process_next()
    assert service.process_next()
    completed = service.list(requirement.id.value, is_draft, actor)[0]
    assert completed.attached_document_id is not None
    assert not service.process_next()
    attached = container.get_document.execute(DocumentId(completed.attached_document_id), actor)
    assert attached.is_included
    assert attached.current_version.extracted_text == data.content.decode()


def test_async_attachment_quarantine_cannot_attach_or_retry() -> None:
    container = build_container(
        Settings(llm_provider=LLMProvider.FAKE, library_scan_mode="offline")
    )
    actor = FAKE_ACTORS[0]
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Need", "Order a bundle"), actor
    )
    service = container.attachment_ingestion
    queued = service.submit(
        AttachmentTarget(requirement.id.value, False, True),
        UploadDocumentInput("bad.txt", "text/plain", b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"),
        "infected",
        actor,
    )
    assert container.document_library.process_next()
    assert not service.process_next()
    status = service.list(requirement.id.value, False, actor)[0]
    assert status.stage == "quarantined" and status.attached_document_id is None
    with pytest.raises(DocumentVersionConflictError):
        service.control(requirement.id.value, False, queued.id, status.version, True, actor)
    excluded = service.control(requirement.id.value, False, queued.id, status.version, None, actor)
    assert excluded.excluded and excluded.stage == "quarantined"
    with pytest.raises(DocumentVersionConflictError):
        service.control(requirement.id.value, False, queued.id, excluded.version, True, actor)


def test_excluding_the_unsupported_region_allows_only_selected_publication(
    library: LibraryFixture,
) -> None:
    service, knowledge, _ = library
    content = presentation(
        drawing_paragraph("Keep coverage policy.")
        + '<p:graphicFrame><a:graphic><a:graphicData uri="chart"/></a:graphic></p:graphicFrame>'
    )
    uploaded = service.submit(
        "Scoped evidence",
        UploadDocumentInput("scope.pptx", PPTX_MIME, content),
        "scope-chart",
        owner(),
    )
    service.process_next()
    current = service.get(uploaded.id, owner())
    source = current.versions[0]
    affected = source.warning_details[0].block_id
    reviewed = service.review(
        uploaded.id,
        source.id,
        current.version,
        owner(),
        tuple(ReviewedPassage(b.id, b.text or "[Image]", True) for b in source.blocks),
        "Compared source",
    )
    view = service.get(uploaded.id, owner())
    assert view.review_fingerprint is not None
    with pytest.raises(InvalidDocumentError, match="Blocking"):
        service.approve(
            uploaded.id,
            source.id,
            reviewed.versions[0].revisions[-1].id,
            view.review_fingerprint,
            reviewed.version,
            owner(),
        )
    reviewed = service.review(
        uploaded.id,
        source.id,
        reviewed.version,
        owner(),
        tuple(
            ReviewedPassage(
                b.id,
                b.text or "[Image]",
                b.id != affected,
                "Outside this reference scope" if b.id == affected else "",
            )
            for b in source.blocks
        ),
        "Excluded only the unsupported graphic",
    )
    view = service.get(uploaded.id, owner())
    assert view.review_fingerprint is not None
    assert view.versions[0].blocking_warnings == ()
    assert view.versions[0].warnings  # Original warning remains in review history.
    service.approve(
        uploaded.id,
        source.id,
        reviewed.versions[0].revisions[-1].id,
        view.review_fingerprint,
        reviewed.version,
        owner(),
    )
    assert knowledge.index_next()
    shared = service.get(uploaded.id, other()).versions[0]
    assert [b.text for b in shared.blocks] == ["Keep coverage policy."]
    assert shared.warning_details == () and shared.assets == ()
