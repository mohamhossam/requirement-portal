"""Asynchronous attachment ingestion: cancel, retry, quarantine and atomic completion.

Attachments are requirement work and never pass through the reference library
(ADR-0099); the library's own review and publication live in the knowledge service.
"""

import pytest

from smb_requirement_agent.application.errors import DocumentVersionConflictError
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.application.use_cases.requirement_drafts import RequirementDraftInput
from smb_requirement_agent.domain.document.attachment import AttachmentTarget
from smb_requirement_agent.domain.document.value_objects import DocumentId
from smb_requirement_agent.identity.domain.errors import AuthorizationDeniedError
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.container import build_container


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
    cancelled = service.control(
        requirement.id.value, is_draft, queued.id, queued.version, False, actor
    )
    assert cancelled.stage == "cancelled"
    assert not service.scan_next()
    retried = service.control(
        requirement.id.value, is_draft, queued.id, cancelled.version, True, actor
    )
    with pytest.raises(DocumentVersionConflictError):
        service.control(requirement.id.value, is_draft, queued.id, cancelled.version, False, actor)
    assert retried.stage == "queued"
    assert service.scan_next()
    assert service.attach_next()
    completed = service.list(requirement.id.value, is_draft, actor)[0]
    assert completed.attached_document_id is not None
    assert not service.attach_next()
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
    assert service.scan_next()
    assert not service.attach_next()
    status = service.list(requirement.id.value, False, actor)[0]
    assert status.stage == "quarantined" and status.attached_document_id is None
    with pytest.raises(DocumentVersionConflictError):
        service.control(requirement.id.value, False, queued.id, status.version, True, actor)
    excluded = service.control(requirement.id.value, False, queued.id, status.version, None, actor)
    assert excluded.excluded and excluded.stage == "quarantined"
    with pytest.raises(DocumentVersionConflictError):
        service.control(requirement.id.value, False, queued.id, excluded.version, True, actor)
