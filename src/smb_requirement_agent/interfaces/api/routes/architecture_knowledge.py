"""Maintainer administration of architecture knowledge releases.

Routes translate HTTP to use-case calls and domain results to API schemas.
Authorization is decided by the use cases, never here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.catalogue_file import CatalogueFileFormat
from smb_requirement_agent.application.use_cases.architecture_comparison import (
    CompareArchitectureImpact,
    ManageSampleRequirements,
)
from smb_requirement_agent.application.use_cases.architecture_documents import (
    ReadKnowledgeDocument,
    UploadKnowledgeDocument,
)
from smb_requirement_agent.application.use_cases.architecture_jobs import ArchitectureJobs
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.application.use_cases.architecture_mapping_impact import (
    ReportMappingImpact,
)
from smb_requirement_agent.application.use_cases.architecture_preview import (
    PreviewArchitectureImpact,
)
from smb_requirement_agent.application.use_cases.catalogue_candidates import (
    DecideCatalogueCandidate,
)
from smb_requirement_agent.domain.architecture.knowledge import InvalidKnowledgeError
from smb_requirement_agent.interfaces.api.dependencies import (
    KnowledgeActorDep,
    get_architecture_jobs,
    get_clock,
    get_compare_architecture_impact,
    get_decide_catalogue_candidates,
    get_manage_architecture_knowledge,
    get_manage_sample_requirements,
    get_preview_architecture_impact,
    get_read_knowledge_document,
    get_report_mapping_impact,
    get_upload_knowledge_document,
    limit_provider_calls,
)
from smb_requirement_agent.interfaces.api.schemas.architecture_knowledge import (
    AcceptAllResponse,
    ActivateRequest,
    ArchitectureJobResponse,
    CatalogueDiffResponse,
    CatalogueSuggestionsResponse,
    CreateVersionRequest,
    DocumentExtractionResponse,
    DocumentPassageResponse,
    DocumentSelectionRequest,
    DraftUpdateRequest,
    ImpactComparisonResponse,
    KnowledgeAuditEventResponse,
    KnowledgeDocumentVersionResponse,
    KnowledgeReleaseResponse,
    MappingImpactResponse,
    PublishRequest,
    RejectSuggestionsRequest,
    RejectSuggestionsResponse,
    RenameVersionRequest,
    RevisionRequest,
    SampleRequirementsRequest,
    SampleRequirementsResponse,
    SuggestionDecisionRequest,
    SystemUpdateRequest,
)
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    Text,
)

router = APIRouter(prefix="/architecture-knowledge", tags=["architecture knowledge"])
job_router = APIRouter(prefix="/jobs", tags=["architecture jobs"])

KnowledgeDep = Annotated[ManageArchitectureKnowledge, Depends(get_manage_architecture_knowledge)]
JobsDep = Annotated[ArchitectureJobs, Depends(get_architecture_jobs)]
SuggestionsDep = Annotated[DecideCatalogueCandidate, Depends(get_decide_catalogue_candidates)]
ClockDep = Annotated[ClockPort, Depends(get_clock)]
ReadDocumentDep = Annotated[ReadKnowledgeDocument, Depends(get_read_knowledge_document)]
SamplesDep = Annotated[ManageSampleRequirements, Depends(get_manage_sample_requirements)]
CompareDep = Annotated[CompareArchitectureImpact, Depends(get_compare_architecture_impact)]


class PreviewRequest(BaseModel):
    query: Text


@router.get("/documents", response_model=list[KnowledgeDocumentVersionResponse])
def list_documents(
    knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> list[KnowledgeDocumentVersionResponse]:
    return [
        KnowledgeDocumentVersionResponse.from_domain(item)
        for item in knowledge.document_versions(actor)
    ]


@router.get("/documents/versions/{version_id}", response_model=KnowledgeDocumentVersionResponse)
def document_version(
    version_id: str, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> KnowledgeDocumentVersionResponse:
    return KnowledgeDocumentVersionResponse.from_domain(
        knowledge.document_version(version_id, actor)
    )


@router.get("/documents/versions/{version_id}/content")
def document_content(
    version_id: str,
    actor: KnowledgeActorDep,
    use_case: Annotated[ReadKnowledgeDocument, Depends(get_read_knowledge_document)],
) -> Response:
    version, content = use_case.execute(version_id, actor)
    return Response(
        content=content,
        media_type=version.mime_type,
        headers={"Content-Disposition": f"attachment; filename={version.id}"},
    )


@router.get("/releases", response_model=list[KnowledgeReleaseResponse])
def list_releases(
    knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> list[KnowledgeReleaseResponse]:
    return [KnowledgeReleaseResponse.from_domain(item) for item in knowledge.list_releases(actor)]


@router.get("/releases/active", response_model=KnowledgeReleaseResponse)
def active_release(knowledge: KnowledgeDep, actor: KnowledgeActorDep) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(knowledge.view_active(actor))


@router.get("/releases/{release_id}", response_model=KnowledgeReleaseResponse)
def get_release(
    release_id: str, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(knowledge.view(release_id, actor))


@router.get("/releases/{release_id}/audit", response_model=list[KnowledgeAuditEventResponse])
def release_audit(
    release_id: str, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> list[KnowledgeAuditEventResponse]:
    return [
        KnowledgeAuditEventResponse.from_domain(item) for item in knowledge.audit(release_id, actor)
    ]


@router.post("/releases", response_model=KnowledgeReleaseResponse, status_code=201)
def create_draft(
    body: CreateVersionRequest, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> KnowledgeReleaseResponse:
    """Start the one version in progress; 409 names the version already in progress."""
    return KnowledgeReleaseResponse.from_domain(knowledge.create_draft(actor, body.name))


@router.put("/releases/{release_id}/name", response_model=KnowledgeReleaseResponse)
def rename_draft(
    release_id: str, body: RenameVersionRequest, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(
        knowledge.rename(release_id, body.expected_revision, body.name, actor)
    )


@router.delete("/releases/{release_id}", status_code=204)
def discard_draft(
    release_id: str, body: RevisionRequest, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> Response:
    """Delete a version in progress, with its index and suggestions."""
    knowledge.discard_draft(release_id, body.expected_revision, actor)
    return Response(status_code=204)


@router.put("/releases/{release_id}", response_model=KnowledgeReleaseResponse)
def update_draft(
    release_id: str, body: DraftUpdateRequest, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(
        knowledge.update(
            release_id,
            body.expected_revision,
            actor,
            systems=tuple(item.to_domain() for item in body.systems),
            relationships=tuple(item.to_domain() for item in body.relationships),
            capability_domains=(
                None
                if body.capability_domains is None
                else tuple(item.to_domain() for item in body.capability_domains)
            ),
            landscape_domains=(
                None
                if body.landscape_domains is None
                else tuple(item.to_domain() for item in body.landscape_domains)
            ),
            products=(
                None if body.products is None else tuple(item.to_domain() for item in body.products)
            ),
            journeys=(
                None if body.journeys is None else tuple(item.to_domain() for item in body.journeys)
            ),
        )
    )


@router.put("/releases/{release_id}/systems/{system_id}", response_model=KnowledgeReleaseResponse)
def put_system(
    release_id: str,
    system_id: str,
    body: SystemUpdateRequest,
    knowledge: KnowledgeDep,
    actor: KnowledgeActorDep,
) -> KnowledgeReleaseResponse:
    if system_id != body.system.id:
        raise InvalidKnowledgeError("System id in the URL and body must match.")
    return KnowledgeReleaseResponse.from_domain(
        knowledge.upsert_system(release_id, body.expected_revision, body.system.to_domain(), actor)
    )


@router.delete(
    "/releases/{release_id}/systems/{system_id}", response_model=KnowledgeReleaseResponse
)
def remove_system(
    release_id: str,
    system_id: str,
    body: RevisionRequest,
    knowledge: KnowledgeDep,
    actor: KnowledgeActorDep,
) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(
        knowledge.remove_system(release_id, body.expected_revision, system_id, actor)
    )


@router.post(
    "/releases/{release_id}/build",
    response_model=ArchitectureJobResponse,
    status_code=202,
    dependencies=[Depends(limit_provider_calls)],
)
def build_release(
    release_id: str, body: RevisionRequest, jobs: JobsDep, actor: KnowledgeActorDep
) -> ArchitectureJobResponse:
    return ArchitectureJobResponse.from_domain(
        jobs.start_build(release_id, body.expected_revision, actor)
    )


@router.get("/catalogue-template.xlsx")
def catalogue_template(knowledge: KnowledgeDep, actor: KnowledgeActorDep) -> Response:
    return _file_response(
        knowledge.file_template(actor), CatalogueFileFormat.XLSX, "catalogue-template"
    )


@router.get("/releases/{release_id}/catalogue-file")
def export_catalogue_file(
    release_id: str,
    knowledge: KnowledgeDep,
    actor: KnowledgeActorDep,
    file_format: Annotated[CatalogueFileFormat, Query(alias="format")] = CatalogueFileFormat.XLSX,
) -> Response:
    return _file_response(
        knowledge.export_file(release_id, file_format, actor), file_format, release_id
    )


@router.post("/releases/{release_id}/catalogue-file/preview", response_model=CatalogueDiffResponse)
async def preview_catalogue_file(
    release_id: str,
    knowledge: KnowledgeDep,
    actor: KnowledgeActorDep,
    file: Annotated[UploadFile, File()],
) -> CatalogueDiffResponse:
    content = await file.read(knowledge.max_file_bytes + 1)
    return CatalogueDiffResponse.from_domain(
        knowledge.preview_file_import(release_id, file.filename or "", content, actor)
    )


@router.post("/releases/{release_id}/catalogue-file", response_model=KnowledgeReleaseResponse)
async def import_catalogue_file(
    release_id: str,
    knowledge: KnowledgeDep,
    actor: KnowledgeActorDep,
    file: Annotated[UploadFile, File()],
    expected_revision: Annotated[int, Form()],
) -> KnowledgeReleaseResponse:
    content = await file.read(knowledge.max_file_bytes + 1)
    return KnowledgeReleaseResponse.from_domain(
        knowledge.apply_file_import(
            release_id, expected_revision, file.filename or "", content, actor
        )
    )


@router.get("/releases/{release_id}/changes", response_model=CatalogueDiffResponse)
def release_changes(
    release_id: str, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> CatalogueDiffResponse:
    return CatalogueDiffResponse.from_domain(knowledge.changes(release_id, actor))


def _file_response(content: bytes, file_format: CatalogueFileFormat, name: str) -> Response:
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in name)
    return Response(
        content=content,
        media_type=file_format.media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.{file_format.value}"'},
    )


@router.post(
    "/releases/{release_id}/documents", response_model=KnowledgeReleaseResponse, status_code=201
)
async def upload_document(
    release_id: str,
    actor: KnowledgeActorDep,
    clock: ClockDep,
    use_case: Annotated[UploadKnowledgeDocument, Depends(get_upload_knowledge_document)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    language: Annotated[str, Form()],
    expected_revision: Annotated[int, Form()],
) -> KnowledgeReleaseResponse:
    # One byte past the limit is enough for validation to reject an oversized
    # file without buffering the rest of an arbitrarily large body.
    content = await file.read(use_case.max_bytes + 1)
    return KnowledgeReleaseResponse.from_domain(
        use_case.execute(
            release_id,
            expected_revision,
            title,
            file.filename or "",
            file.content_type or "",
            language,
            content,
            actor,
            clock.now(),
        )
    )


@router.put("/releases/{release_id}/documents", response_model=KnowledgeReleaseResponse)
def select_documents(
    release_id: str,
    body: DocumentSelectionRequest,
    knowledge: KnowledgeDep,
    actor: KnowledgeActorDep,
) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(
        knowledge.select_documents(
            release_id, body.expected_revision, actor, tuple(body.version_ids)
        )
    )


@router.get("/releases/{release_id}/evidence/{chunk_id}")
def get_evidence(
    release_id: str, chunk_id: str, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> dict[str, object]:
    chunk = knowledge.evidence(release_id, chunk_id, actor)
    return {
        "id": chunk.id,
        "source_label": chunk.source_label,
        "location": chunk.location,
        "text": chunk.text,
        "document_version_id": chunk.document_version_id,
    }


@router.post("/releases/{release_id}/preview", dependencies=[Depends(limit_provider_calls)])
def preview_release(
    release_id: str, body: PreviewRequest, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> list[dict[str, object]]:
    return [
        {
            "id": chunk.id,
            "source_label": chunk.source_label,
            "location": chunk.location,
            "text": chunk.text,
        }
        for chunk in knowledge.preview(release_id, body.query, actor)
    ]


@router.post("/releases/{release_id}/preview-impact", dependencies=[Depends(limit_provider_calls)])
def preview_impact(
    release_id: str,
    body: PreviewRequest,
    actor: KnowledgeActorDep,
    use_case: Annotated[PreviewArchitectureImpact, Depends(get_preview_architecture_impact)],
) -> dict[str, object]:
    result = use_case.execute(release_id, body.query, actor)
    return {
        "release_id": result.release_id,
        "system_ids": result.system_ids,
        "citation_ids": result.citation_ids,
        "citations": [
            {"system_id": item.system_id, "chunk_id": item.chunk_id, "quote": item.quote}
            for item in result.citations
        ],
        "uncertainty": result.uncertainty,
        "evidence": [
            {
                "id": chunk.id,
                "source_label": chunk.source_label,
                "location": chunk.location,
                "text": chunk.text,
            }
            for chunk in result.evidence
        ],
    }


@router.post(
    "/releases/{release_id}/suggestions/rejection", response_model=RejectSuggestionsResponse
)
def reject_suggestions(
    release_id: str,
    body: RejectSuggestionsRequest,
    suggestions: SuggestionsDep,
    clock: ClockDep,
    actor: KnowledgeActorDep,
) -> RejectSuggestionsResponse:
    """Reject several waiting suggestions at once, such as every one for a system."""
    rejected = suggestions.reject_many(
        release_id, body.expected_revision, tuple(body.suggestion_ids), actor, clock.now()
    )
    return RejectSuggestionsResponse(rejected=rejected)


@router.get(
    "/releases/{release_id}/documents/{version_id}/passage",
    response_model=DocumentPassageResponse,
)
def document_passage(
    release_id: str,
    version_id: str,
    location: Annotated[str, Query(min_length=1, max_length=200)],
    reader: ReadDocumentDep,
    actor: KnowledgeActorDep,
) -> DocumentPassageResponse:
    """A cited passage and its neighbours, re-read from the stored document."""
    return DocumentPassageResponse.from_domain(
        reader.passage(release_id, version_id, location, actor)
    )


@router.get("/mapping-impact", response_model=MappingImpactResponse)
def mapping_impact(
    actor: KnowledgeActorDep,
    report: Annotated[ReportMappingImpact, Depends(get_report_mapping_impact)],
) -> MappingImpactResponse:
    """Counts of mapped and outdated requirements, features and stories; no titles."""
    return MappingImpactResponse.from_domain(report.execute(actor))


@router.get("/sample-requirements", response_model=SampleRequirementsResponse)
def sample_requirements(
    samples: SamplesDep, actor: KnowledgeActorDep
) -> SampleRequirementsResponse:
    """The team's shared sample requirements, checked against every new version."""
    return SampleRequirementsResponse.from_domain(samples.view(actor))


@router.put("/sample-requirements", response_model=SampleRequirementsResponse)
def replace_sample_requirements(
    body: SampleRequirementsRequest, samples: SamplesDep, actor: KnowledgeActorDep
) -> SampleRequirementsResponse:
    return SampleRequirementsResponse.from_domain(
        samples.replace(
            tuple((item.id or None, item.text) for item in body.items),
            body.expected_revision,
            actor,
        )
    )


@router.post(
    "/releases/{release_id}/compare-impact",
    response_model=ImpactComparisonResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def compare_impact(
    release_id: str, body: PreviewRequest, compare: CompareDep, actor: KnowledgeActorDep
) -> ImpactComparisonResponse:
    """One requirement mapped by the version in use and by this built version."""
    return ImpactComparisonResponse.from_domain(compare.execute(release_id, body.query, actor))


@router.post(
    "/releases/{release_id}/documents/{version_id}/extractions",
    response_model=ArchitectureJobResponse,
    status_code=202,
    dependencies=[Depends(limit_provider_calls)],
)
def start_extraction(
    release_id: str, version_id: str, jobs: JobsDep, actor: KnowledgeActorDep
) -> ArchitectureJobResponse:
    return ArchitectureJobResponse.from_domain(jobs.start_extraction(release_id, version_id, actor))


@router.get("/releases/{release_id}/build", response_model=ArchitectureJobResponse | None)
def latest_build(
    release_id: str, jobs: JobsDep, actor: KnowledgeActorDep
) -> ArchitectureJobResponse | None:
    """The latest index build for this release, so its status survives a reload."""
    job = jobs.latest_build(release_id, actor)
    return ArchitectureJobResponse.from_domain(job) if job is not None else None


@router.get("/releases/{release_id}/extractions", response_model=list[DocumentExtractionResponse])
def list_extractions(
    release_id: str, jobs: JobsDep, actor: KnowledgeActorDep
) -> list[DocumentExtractionResponse]:
    return [
        DocumentExtractionResponse(
            document_version_id=version_id, job=ArchitectureJobResponse.from_domain(job)
        )
        for version_id, job in jobs.extractions(release_id, actor)
    ]


@router.get("/releases/{release_id}/suggestions", response_model=CatalogueSuggestionsResponse)
def list_suggestions(
    release_id: str, suggestions: SuggestionsDep, actor: KnowledgeActorDep
) -> CatalogueSuggestionsResponse:
    return CatalogueSuggestionsResponse.from_domain(suggestions.overview(release_id, actor))


@router.post(
    "/releases/{release_id}/suggestions/{suggestion_id}/decision",
    response_model=KnowledgeReleaseResponse,
)
def decide_suggestion(
    release_id: str,
    suggestion_id: str,
    body: SuggestionDecisionRequest,
    suggestions: SuggestionsDep,
    actor: KnowledgeActorDep,
    clock: ClockDep,
) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(
        suggestions.decide(
            release_id,
            suggestion_id,
            body.expected_revision,
            body.accept,
            actor,
            clock.now(),
            body.content.to_domain() if body.content is not None else None,
        )
    )


@router.post("/releases/{release_id}/suggestions/acceptance", response_model=AcceptAllResponse)
def accept_all_suggestions(
    release_id: str,
    body: RevisionRequest,
    suggestions: SuggestionsDep,
    actor: KnowledgeActorDep,
    clock: ClockDep,
) -> AcceptAllResponse:
    release, remaining = suggestions.accept_all(
        release_id, body.expected_revision, actor, clock.now()
    )
    return AcceptAllResponse(
        release=KnowledgeReleaseResponse.from_domain(release), remaining=remaining
    )


@router.post("/releases/{release_id}/publish", response_model=KnowledgeReleaseResponse)
def publish_release(
    release_id: str,
    body: PublishRequest,
    knowledge: KnowledgeDep,
    actor: KnowledgeActorDep,
    clock: ClockDep,
) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(
        knowledge.publish(release_id, body.expected_revision, actor, clock.now(), body.rationale)
    )


@router.post("/releases/{release_id}/activate", response_model=KnowledgeReleaseResponse)
def activate_release(
    release_id: str, body: ActivateRequest, knowledge: KnowledgeDep, actor: KnowledgeActorDep
) -> KnowledgeReleaseResponse:
    return KnowledgeReleaseResponse.from_domain(
        knowledge.activate(release_id, actor, body.rationale)
    )


@job_router.get("/{job_id}", response_model=ArchitectureJobResponse)
def get_job(job_id: str, jobs: JobsDep, actor: KnowledgeActorDep) -> ArchitectureJobResponse:
    return ArchitectureJobResponse.from_domain(jobs.get_for_actor(job_id, actor))


@job_router.post("/{job_id}/cancel", response_model=ArchitectureJobResponse)
def cancel_job(job_id: str, jobs: JobsDep, actor: KnowledgeActorDep) -> ArchitectureJobResponse:
    return ArchitectureJobResponse.from_domain(jobs.cancel(job_id, actor))


@job_router.post(
    "/{job_id}/retry",
    response_model=ArchitectureJobResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def retry_job(job_id: str, jobs: JobsDep, actor: KnowledgeActorDep) -> ArchitectureJobResponse:
    return ArchitectureJobResponse.from_domain(jobs.retry(job_id, actor))
