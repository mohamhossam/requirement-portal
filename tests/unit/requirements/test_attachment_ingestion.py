"""Attachment uploads on their own pipeline: refusals, failures and stale controls (ADR-0099)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from smb_requirement_agent.application.errors import (
    DocumentNotFoundError,
    DocumentVersionConflictError,
    RequirementDraftNotFoundError,
    UnsupportedDocumentError,
)
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.requirements.application.use_cases.attachment_ingestion import (
    AttachmentIngestion,
)
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.requirements.domain.document.attachment import AttachmentTarget
from smb_requirement_agent.requirements.domain.document.ingestion import IngestionStage

ACTOR = FAKE_ACTORS[0]
POLICY = UploadDocumentInput("policy.txt", "text/plain", b"Approved channels are BCRM and CPP.")


@pytest.fixture
def container() -> Iterator[Container]:
    built = build_container(Settings(llm_provider=LLMProvider.FAKE, library_scan_mode="offline"))
    try:
        yield built
    finally:
        built.close_resources()


def _requirement_id(container: Container) -> str:
    return container.create_requirement.execute(
        CreateRequirementInput("Need", "Order a bundle"), ACTOR
    ).id.value


def test_submission_refuses_bad_keys_files_and_reused_keys(container: Container) -> None:
    service: AttachmentIngestion = container.attachment_ingestion
    target = AttachmentTarget(_requirement_id(container), False, True)
    with pytest.raises(UnsupportedDocumentError):
        service.submit(target, POLICY, " ", ACTOR)
    with pytest.raises(UnsupportedDocumentError):
        service.submit(target, UploadDocumentInput("../policy.txt", "text/plain", b"x"), "k", ACTOR)
    # A generic declared type is read from the extension, as the library does.
    markdown = service.submit(
        target, UploadDocumentInput("notes.md", "application/octet-stream", b"# Notes"), "md", ACTOR
    )
    assert markdown.filename == "notes.md"
    service.submit(target, POLICY, "policy", ACTOR)
    other = UploadDocumentInput("policy.txt", "text/plain", b"Different content.")
    with pytest.raises(DocumentVersionConflictError):
        service.submit(target, other, "policy", ACTOR)


def test_a_file_with_nothing_to_extract_fails_and_is_never_attached(
    container: Container,
) -> None:
    service: AttachmentIngestion = container.attachment_ingestion
    requirement_id = _requirement_id(container)
    blank = UploadDocumentInput("blank.txt", "text/plain", b"   \n  ")
    service.submit(AttachmentTarget(requirement_id, False, True), blank, "blank", ACTOR)

    assert service.scan_next()
    assert not service.attach_next()
    status = service.list(requirement_id, False, ACTOR)[0]
    assert status.stage is IngestionStage.FAILED
    assert status.error and status.attached_document_id is None


def test_a_source_that_changed_before_attaching_fails_with_a_reason(
    container: Container,
) -> None:
    service: AttachmentIngestion = container.attachment_ingestion
    requirement_id = _requirement_id(container)
    # Replacing a document that does not exist cannot be finalised.
    target = AttachmentTarget(requirement_id, False, True, "missing-document", 1)
    service.submit(target, POLICY, "replacement", ACTOR)

    assert service.scan_next()
    assert service.attach_next()
    status = service.list(requirement_id, False, ACTOR)[0]
    assert status.stage is IngestionStage.FAILED
    assert status.error == (
        "Attachment source or access changed. Reload the source before retrying."
    )
    assert not service.attach_next()


def test_controls_refuse_unknown_uploads_and_stale_versions(container: Container) -> None:
    service: AttachmentIngestion = container.attachment_ingestion
    requirement_id = _requirement_id(container)
    queued = service.submit(AttachmentTarget(requirement_id, False, True), POLICY, "p", ACTOR)
    with pytest.raises(DocumentNotFoundError):
        service.control(requirement_id, False, "no-such-upload", 1, False, ACTOR)
    # Authorization comes first: the draft side of this Requirement does not exist.
    with pytest.raises(RequirementDraftNotFoundError):
        service.control(requirement_id, True, queued.id, queued.version, False, ACTOR)
    with pytest.raises(DocumentVersionConflictError):
        service.control(requirement_id, False, queued.id, queued.version + 1, False, ACTOR)
    with pytest.raises(DocumentVersionConflictError):
        # Only stopped uploads can be excluded.
        service.control(requirement_id, False, queued.id, queued.version, None, ACTOR)
