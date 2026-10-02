"""Reusable cross-owner rollout/rollback exercise for memory and PostgreSQL."""

import pytest

from smb_requirement_agent.application.errors import (
    KnowledgeGenerationError,
    RequirementAnalysisConflictError,
)
from smb_requirement_agent.application.use_cases.document_library import DocumentLibrary
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.application.use_cases.reference_knowledge import ReferenceKnowledge
from smb_requirement_agent.domain.document.library import ReviewedPassage
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS


def exercise_owner_rollout(
    service: DocumentLibrary, first: ReferenceKnowledge, second: ReferenceKnowledge
) -> None:
    documents: list[str] = []
    owners = FAKE_ACTORS[:2]
    for number, owner in enumerate(owners):
        document = service.submit(
            f"Coverage {number}",
            UploadDocumentInput(
                "rules.txt",
                "text/plain",
                f"Coverage policy {number} applies.\nPrivate excluded {number}.".encode(),
            ),
            f"rollout-{number}",
            owner,
        )
        assert service.process_next()
        view = service.get(document.id, owner)
        source = view.versions[-1]
        service.review(
            document.id,
            source.id,
            view.version,
            owner,
            tuple(
                ReviewedPassage(b.id, b.text or "", i == 0, "Excluded" if i else "")
                for i, b in enumerate(source.blocks)
            ),
            "Reviewed",
        )
        preview = first.preview_build(document.id, owner)
        first.build_review(
            document.id,
            owner,
            preview.document_version,
            preview.fingerprint,
            preview.index_identity,
        )
        assert first.index_next()
        ready = service.get(document.id, owner)
        publication = ready.publications[-1]
        first.activate_build(
            document.id, publication.id, owner, ready.version, publication.chunk_manifest or ""
        )
        documents.append(document.id)
    original = tuple(
        service.get(doc, owner).versions for doc, owner in zip(documents, owners, strict=True)
    )
    original_citation = first.citation(first.search("Coverage")[0])
    for previous, target in ((first, second), (second, first)):
        with pytest.raises(KnowledgeGenerationError, match="another index generation"):
            target.search("Coverage")
        for number, (doc, owner) in enumerate(zip(documents, owners, strict=True)):
            preview = target.preview_build(doc, owner)
            target.build_review(
                doc, owner, preview.document_version, preview.fingerprint, preview.index_identity
            )
            assert target.index_next()
            ready = service.get(doc, owner)
            publication = ready.publications[-1]
            with pytest.raises(AuthorizationDeniedError):
                target.activate_build(
                    doc,
                    publication.id,
                    owners[1 - number],
                    ready.version,
                    publication.chunk_manifest or "",
                )
            # Readiness never transfers authority or activates another owner's document.
            target.activate_build(
                doc, publication.id, owner, ready.version, publication.chunk_manifest or ""
            )
            if number == 0:
                for model in (previous, target):
                    with pytest.raises(KnowledgeGenerationError, match="another index generation"):
                        model.search("Coverage")
        matches = target.search("Coverage")
        assert {c.document_id for c in matches} == set(documents)
        assert "Private excluded" not in str(matches)
        for chunk in matches:
            target.require_current((target.citation(chunk),))
    with pytest.raises(RequirementAnalysisConflictError):
        first.require_current((original_citation,))
    assert (
        tuple(
            service.get(doc, owner).versions for doc, owner in zip(documents, owners, strict=True)
        )
        == original
    )
