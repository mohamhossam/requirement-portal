"""Authenticated shared library; private working versions are owner-only."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from smb_requirement_agent.application.errors import UnsupportedDocumentError
from smb_requirement_agent.application.ports.reference_index import ReferenceChunk
from smb_requirement_agent.application.use_cases.document_library import (
    DocumentLibrary,
    LibraryView,
    OriginalPreview,
)
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.application.use_cases.library_governance import (
    LibraryDependencyPage,
    LibraryGovernance,
)
from smb_requirement_agent.application.use_cases.reference_knowledge import (
    CorpusBuildPreview,
    ReferenceKnowledge,
)
from smb_requirement_agent.application.use_cases.source_impact import (
    DependencyImpact,
    DependencyImpactPage,
    SourceImpactReview,
)
from smb_requirement_agent.application.use_cases.unified_knowledge_search import (
    UnifiedKnowledgeSearch,
    UnifiedSearchHit,
)
from smb_requirement_agent.domain.document.library import OwnershipTransfer, ReviewedPassage
from smb_requirement_agent.domain.document.lineage import ImpactDecisionKind
from smb_requirement_agent.domain.identity.entities import ActorId
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_document_library,
    get_library_governance,
    get_reference_knowledge,
    get_source_impact,
    get_unified_knowledge_search,
    limit_provider_calls,
    require_authenticated_actor,
)

router = APIRouter(
    prefix="/library", tags=["library"], dependencies=[Depends(require_authenticated_actor)]
)
LibraryDep = Annotated[DocumentLibrary, Depends(get_document_library)]
KnowledgeDep = Annotated[ReferenceKnowledge, Depends(get_reference_knowledge)]
GovernanceDep = Annotated[LibraryGovernance, Depends(get_library_governance)]
ImpactDep = Annotated[SourceImpactReview, Depends(get_source_impact)]


@router.get("/documents/{document_id}/source-impact")
def document_source_impact(
    document_id: str,
    actor: CurrentActorDep,
    service: ImpactDep,
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    active_only: bool = False,
    query: str = Query("", max_length=200),
) -> DependencyImpactPage:
    response.headers["Cache-Control"] = "private, no-store"
    return service.page(
        actor,
        document_id=document_id,
        offset=offset,
        limit=limit,
        active_only=active_only,
        query=query,
    )


@router.get("/requirements/{requirement_id}/source-impact")
def requirement_source_impact(
    requirement_id: str,
    actor: CurrentActorDep,
    service: ImpactDep,
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    active_only: bool = False,
    query: str = Query("", max_length=200),
) -> DependencyImpactPage:
    response.headers["Cache-Control"] = "private, no-store"
    return service.page(
        actor,
        requirement_id=requirement_id,
        offset=offset,
        limit=limit,
        active_only=active_only,
        query=query,
    )


class ImpactDecisionRequest(BaseModel):
    publication_state: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=0)
    decision: ImpactDecisionKind
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/source-impact/{dependency_id}/decisions")
def decide_source_impact(
    dependency_id: str,
    data: ImpactDecisionRequest,
    actor: CurrentActorDep,
    service: ImpactDep,
) -> DependencyImpact:
    return service.decide(
        dependency_id,
        actor,
        data.publication_state,
        data.expected_version,
        data.decision,
        data.reason,
    )


@router.get("/documents/{document_id}/versions/{version_id}/blocks/{block_id}/original-preview")
def original_preview(
    document_id: str,
    version_id: str,
    block_id: str,
    actor: CurrentActorDep,
    service: LibraryDep,
    response: Response,
) -> OriginalPreview:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return service.preview_original(document_id, version_id, block_id, actor)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


search_router = APIRouter(tags=["knowledge"], dependencies=[Depends(require_authenticated_actor)])


@search_router.post("/knowledge/search", dependencies=[Depends(limit_provider_calls)])
def search(data: KnowledgeSearchRequest, service: KnowledgeDep) -> tuple[ReferenceChunk, ...]:
    return service.search(data.query)


@search_router.post("/knowledge/search/unified", dependencies=[Depends(limit_provider_calls)])
def unified_search(
    data: KnowledgeSearchRequest,
    service: Annotated[UnifiedKnowledgeSearch, Depends(get_unified_knowledge_search)],
) -> tuple[UnifiedSearchHit, ...]:
    # The router requires a signed-in actor; results do not depend on which one (ADR-0075).
    return service.execute(data.query)


@router.get("/documents/{document_id}/chunks/preview")
def preview_chunks(
    document_id: str, service: KnowledgeDep, actor: CurrentActorDep
) -> tuple[ReferenceChunk, ...]:
    return service.preview_review(document_id, actor)


class LibraryMutation(BaseModel):
    expected_version: int = Field(ge=1)


class LibraryOwnershipRequest(LibraryMutation):
    actor_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/documents/{document_id}/ownership")
def transfer_ownership(
    document_id: str, data: LibraryOwnershipRequest, service: GovernanceDep, actor: CurrentActorDep
) -> OwnershipTransfer:
    return service.transfer(
        document_id, actor, ActorId(data.actor_id), data.expected_version, data.reason
    )


@router.get("/documents/{document_id}/ownership/history")
def ownership_history(
    document_id: str, service: GovernanceDep, actor: CurrentActorDep
) -> tuple[OwnershipTransfer, ...]:
    return service.history(document_id, actor)


@router.get("/documents/{document_id}/dependencies")
def dependencies(
    document_id: str,
    service: GovernanceDep,
    actor: CurrentActorDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> LibraryDependencyPage:
    return service.dependencies(document_id, actor, offset, limit)


class LibraryReviewRequest(LibraryMutation):
    passages: list[ReviewedPassage] = Field(min_length=1, max_length=10000)
    explanation: str = Field(min_length=1, max_length=2000)


class LibraryApprovalRequest(LibraryMutation):
    revision_id: str = Field(min_length=1, max_length=200)
    fingerprint: str = Field(min_length=64, max_length=64)


class LibraryWithdrawalRequest(LibraryMutation):
    reason: str = Field(min_length=1, max_length=2000)


class CorpusBuildRequest(LibraryMutation):
    fingerprint: str = Field(min_length=64, max_length=64)
    index_identity: str = Field(min_length=1, max_length=1000)


class CorpusActivationRequest(LibraryMutation):
    manifest: str = Field(min_length=64, max_length=64)


@router.get("/documents/{document_id}/builds/preview")
def preview_build(
    document_id: str, service: KnowledgeDep, actor: CurrentActorDep
) -> CorpusBuildPreview:
    return service.preview_build(document_id, actor)


@router.post(
    "/documents/{document_id}/builds", status_code=202, dependencies=[Depends(limit_provider_calls)]
)
def build_corpus_member(
    document_id: str,
    data: CorpusBuildRequest,
    service: KnowledgeDep,
    library: LibraryDep,
    actor: CurrentActorDep,
) -> LibraryView:
    service.build_review(
        document_id, actor, data.expected_version, data.fingerprint, data.index_identity
    )
    return library.get(document_id, actor)


@router.post("/documents/{document_id}/builds/{build_id}/activation")
def activate_build(
    document_id: str,
    build_id: str,
    data: CorpusActivationRequest,
    service: KnowledgeDep,
    library: LibraryDep,
    actor: CurrentActorDep,
) -> LibraryView:
    service.activate_build(document_id, build_id, actor, data.expected_version, data.manifest)
    return library.get(document_id, actor)


@router.post("/documents/{document_id}/builds/{build_id}/discard")
def discard_build(
    document_id: str,
    build_id: str,
    data: LibraryMutation,
    service: KnowledgeDep,
    library: LibraryDep,
    actor: CurrentActorDep,
) -> LibraryView:
    service.discard_build(document_id, build_id, actor, data.expected_version)
    return library.get(document_id, actor)


@router.post(
    "/documents/{document_id}/index-retry",
    status_code=202,
    dependencies=[Depends(limit_provider_calls)],
)
def retry_index(
    document_id: str, data: LibraryMutation, service: LibraryDep, actor: CurrentActorDep
) -> LibraryView:
    service.retry_index(document_id, data.expected_version, actor)
    return service.get(document_id, actor)


@router.get("/documents")
def list_documents(
    service: LibraryDep,
    actor: CurrentActorDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> tuple[LibraryView, ...]:
    return service.list(actor, offset, limit)


@router.get("/documents/{document_id}")
def get_document(document_id: str, service: LibraryDep, actor: CurrentActorDep) -> LibraryView:
    return service.get(document_id, actor)


@router.post("/ingestions", status_code=202)
async def submit(
    service: LibraryDep,
    actor: CurrentActorDep,
    file: Annotated[UploadFile, File()],
    title: str = Form(...),
    idempotency_key: str = Form(...),
    document_id: str | None = Form(None),
    expected_version: int | None = Form(None),
) -> LibraryView:
    content = await file.read(service.max_file_bytes + 1)
    if len(content) > service.max_file_bytes:
        raise UnsupportedDocumentError("Document exceeds the configured upload limit.")

    document = await run_in_threadpool(
        service.submit,
        title,
        UploadDocumentInput(file.filename or "", file.content_type or "", content),
        idempotency_key,
        actor,
        document_id,
        expected_version,
    )
    return service.get(document.id, actor)


@router.get("/documents/{document_id}/versions/{version_id}/original")
def original(
    document_id: str, version_id: str, service: LibraryDep, actor: CurrentActorDep
) -> Response:
    version, content = service.original(document_id, version_id, actor)
    return Response(
        content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "X-Document-Checksum": version.checksum,
        },
    )


@router.post("/documents/{document_id}/versions/{version_id}/review")
def review(
    document_id: str,
    version_id: str,
    data: LibraryReviewRequest,
    service: LibraryDep,
    actor: CurrentActorDep,
) -> LibraryView:
    service.review(
        document_id,
        version_id,
        data.expected_version,
        actor,
        tuple(data.passages),
        data.explanation,
    )
    return service.get(document_id, actor)


@router.post("/documents/{document_id}/versions/{version_id}/approval")
def approve(
    document_id: str,
    version_id: str,
    data: LibraryApprovalRequest,
    service: LibraryDep,
    actor: CurrentActorDep,
) -> LibraryView:
    service.approve(
        document_id, version_id, data.revision_id, data.fingerprint, data.expected_version, actor
    )
    return service.get(document_id, actor)


@router.post("/documents/{document_id}/withdrawal")
def withdraw(
    document_id: str, data: LibraryWithdrawalRequest, service: LibraryDep, actor: CurrentActorDep
) -> LibraryView:
    service.withdraw(document_id, data.expected_version, actor, data.reason)
    return service.get(document_id, actor)


@router.post("/documents/{document_id}/versions/{version_id}/retry", status_code=202)
def retry(
    document_id: str,
    version_id: str,
    data: LibraryMutation,
    service: LibraryDep,
    actor: CurrentActorDep,
) -> LibraryView:
    service.control(document_id, version_id, data.expected_version, actor, retry=True)
    return service.get(document_id, actor)


@router.post("/documents/{document_id}/versions/{version_id}/cancellation")
def cancel(
    document_id: str,
    version_id: str,
    data: LibraryMutation,
    service: LibraryDep,
    actor: CurrentActorDep,
) -> LibraryView:
    service.control(document_id, version_id, data.expected_version, actor, retry=False)
    return service.get(document_id, actor)
