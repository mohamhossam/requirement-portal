"""Upload and safely review Requirement source documents."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from smb_requirement_agent.application.errors import UnsupportedDocumentError
from smb_requirement_agent.application.use_cases.attachment_ingestion import (
    AttachmentIngestion,
    AttachmentIngestionView,
)
from smb_requirement_agent.application.use_cases.documents import (
    GetDocument,
    ListDocuments,
    RemoveDocument,
    SetDocumentInclusion,
    SetHiddenWorksheetInclusion,
    UploadDocument,
    UploadDocumentInput,
)
from smb_requirement_agent.domain.document.entities import SourceDocument, SourceDocumentVersion
from smb_requirement_agent.domain.document.library import AttachmentTarget
from smb_requirement_agent.domain.document.value_objects import (
    DocumentId,
    DocumentVersionId,
    EvidenceBlockKind,
    ExtractionWarningSeverity,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_attachment_ingestion,
    get_get_document,
    get_list_documents,
    get_remove_document,
    get_set_document_inclusion,
    get_set_hidden_worksheet_inclusion,
    get_upload_document,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.documents import (
    DocumentContentResponse,
    DocumentDetailResponse,
    DocumentEvidenceBlockResponse,
    DocumentEvidenceSummaryResponse,
    DocumentExtractionWarningResponse,
    DocumentSummaryResponse,
    DocumentVersionDetailResponse,
    DocumentVersionMetadataResponse,
    SetDocumentInclusionRequest,
    SetHiddenWorksheetInclusionRequest,
)

router = APIRouter(tags=["documents"], dependencies=[Depends(require_authenticated_actor)])

AttachmentDep = Annotated[AttachmentIngestion, Depends(get_attachment_ingestion)]


class IngestionControlRequest(BaseModel):
    expected_version: int = Field(ge=1)


@router.post("/{scope}/{source_id}/document-ingestions", status_code=202)
async def submit_attachment(
    scope: Literal["requirements", "requirement-drafts"],
    source_id: str,
    actor: CurrentActorDep,
    service: AttachmentDep,
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Form()],
    include_in_analysis: bool = Form(False),
    document_id: str | None = Form(None),
    expected_version: int | None = Form(None),
) -> AttachmentIngestionView:
    data = await _upload_input(file, service.max_file_bytes, include_in_analysis)
    target = AttachmentTarget(
        source_id, scope == "requirement-drafts", include_in_analysis, document_id, expected_version
    )
    return await run_in_threadpool(service.submit, target, data, idempotency_key, actor)


@router.get("/{scope}/{source_id}/document-ingestions")
def attachment_status(
    scope: Literal["requirements", "requirement-drafts"],
    source_id: str,
    actor: CurrentActorDep,
    service: AttachmentDep,
) -> tuple[AttachmentIngestionView, ...]:
    return service.list(source_id, scope == "requirement-drafts", actor)


@router.post("/{scope}/{source_id}/document-ingestions/{ingestion_id}/{action}")
def control_attachment(
    scope: Literal["requirements", "requirement-drafts"],
    source_id: str,
    ingestion_id: str,
    action: Literal["retry", "cancellation", "exclusion"],
    data: IngestionControlRequest,
    actor: CurrentActorDep,
    service: AttachmentDep,
) -> AttachmentIngestionView:
    return service.control(
        source_id,
        scope == "requirement-drafts",
        ingestion_id,
        data.expected_version,
        None if action == "exclusion" else action == "retry",
        actor,
    )


def _version_metadata(version: SourceDocumentVersion) -> DocumentVersionMetadataResponse:
    sections = {item.section_path for item in version.evidence_blocks if item.section_path}
    return DocumentVersionMetadataResponse(
        id=version.id.value,
        number=version.number,
        filename=version.filename,
        mime_type=version.mime_type,
        size_bytes=version.size_bytes,
        checksum_sha256=version.checksum_sha256,
        extraction_status=version.extraction_status,
        extraction_error=version.extraction_error,
        created_at=version.created_at,
        analysis_readiness=version.analysis_readiness,
        evidence_summary=DocumentEvidenceSummaryResponse(
            section_count=len(sections),
            table_count=len(
                {
                    item.label.split(", row", 1)[0]
                    for item in version.evidence_blocks
                    if item.kind is EvidenceBlockKind.TABLE_ROW
                }
            ),
            image_count=len(
                {
                    item.content_fingerprint
                    for item in version.evidence_blocks
                    if item.kind is EvidenceBlockKind.IMAGE
                }
            ),
            worksheet_count=len(
                {
                    item.section_path[0]
                    for item in version.evidence_blocks
                    if item.kind is EvidenceBlockKind.WORKSHEET_RANGE and item.section_path
                }
            ),
            block_count=len(version.evidence_blocks),
        ),
        extraction_warnings=[
            DocumentExtractionWarningResponse(
                code=item.code,
                severity=item.severity,
                message=item.message,
                block_id=item.block_id,
            )
            for item in version.extraction_warnings
        ]
        + (
            [
                DocumentExtractionWarningResponse(
                    code="legacy_plain_text",
                    severity=ExtractionWarningSeverity.WARNING,
                    message=(
                        "This version uses legacy plain-text extraction. Upload a new version "
                        "for structured table and image analysis."
                    ),
                    block_id=None,
                )
            ]
            if version.extraction_status.value == "ready" and version.extraction_version is None
            else []
        ),
    )


def _summary(document: SourceDocument) -> DocumentSummaryResponse:
    hidden_worksheets = sorted(
        {
            item.section_path[0].removeprefix("Hidden worksheet: ")
            for item in document.current_version.evidence_blocks
            if item.section_path and item.section_path[0].startswith("Hidden worksheet: ")
        }
    )
    return DocumentSummaryResponse(
        id=document.id.value,
        version=document.version_number,
        requirement_id=(document.requirement_id.value if document.requirement_id else None),
        draft_id=document.draft_id.value if document.draft_id else None,
        included_in_analysis=document.is_included,
        requires_attention=document.requires_attention,
        included_version_id=(
            document.included_version_id.value if document.included_version_id else None
        ),
        version_count=len(document.versions),
        current_version=_version_metadata(document.current_version),
        hidden_worksheets=hidden_worksheets,
        included_hidden_worksheets=list(document.included_hidden_worksheets),
    )


def _detail(document: SourceDocument) -> DocumentDetailResponse:
    summary = _summary(document)
    return DocumentDetailResponse(
        **summary.model_dump(),
        versions=[
            DocumentVersionDetailResponse(
                **_version_metadata(version).model_dump(),
                extracted_text=version.extracted_text,
                extraction_version=version.extraction_version,
                evidence_blocks=[
                    DocumentEvidenceBlockResponse(
                        id=block.id,
                        kind=block.kind,
                        ordinal=block.ordinal,
                        section_path=list(block.section_path),
                        label=block.label,
                        text=block.text,
                        asset_id=block.asset_id,
                    )
                    for block in version.evidence_blocks
                ],
            )
            for version in document.versions
        ],
    )


async def _upload_input(
    file: UploadFile, max_file_bytes: int, include_in_analysis: bool = False
) -> UploadDocumentInput:
    return UploadDocumentInput(
        filename=file.filename or "",
        mime_type=file.content_type or "",
        content=await file.read(max_file_bytes + 1),
        include_in_analysis=include_in_analysis,
    )


@router.post(
    "/requirements/{requirement_id}/attachments",
    response_model=DocumentDetailResponse,
    status_code=201,
)
async def upload_requirement_document(
    requirement_id: str,
    file: Annotated[UploadFile, File()],
    actor: CurrentActorDep,
    use_case: Annotated[UploadDocument, Depends(get_upload_document)],
    include_in_analysis: Annotated[bool, Form()] = False,
) -> DocumentDetailResponse:
    document = await run_in_threadpool(
        use_case.for_requirement,
        RequirementId(requirement_id),
        await _upload_input(file, use_case.max_file_bytes, include_in_analysis),
        actor,
    )
    return _detail(document)


@router.post(
    "/requirements/{requirement_id}/attachments/{document_id}/versions",
    response_model=DocumentDetailResponse,
    status_code=201,
)
async def upload_requirement_document_version(
    requirement_id: str,
    document_id: str,
    file: Annotated[UploadFile, File()],
    expected_version: Annotated[int, Form(ge=1)],
    actor: CurrentActorDep,
    use_case: Annotated[UploadDocument, Depends(get_upload_document)],
    include_in_analysis: Annotated[bool, Form()] = False,
) -> DocumentDetailResponse:
    document = await run_in_threadpool(
        use_case.for_requirement,
        RequirementId(requirement_id),
        await _upload_input(file, use_case.max_file_bytes, include_in_analysis),
        actor,
        DocumentId(document_id),
        expected_version=expected_version,
    )
    return _detail(document)


@router.get(
    "/requirements/{requirement_id}/attachments",
    response_model=list[DocumentSummaryResponse],
)
def list_requirement_documents(
    requirement_id: str,
    use_case: Annotated[ListDocuments, Depends(get_list_documents)],
) -> list[DocumentSummaryResponse]:
    return [_summary(item) for item in use_case.for_requirement(RequirementId(requirement_id))]


@router.post(
    "/requirement-drafts/{draft_id}/attachments",
    response_model=DocumentDetailResponse,
    status_code=201,
)
async def upload_draft_document(
    draft_id: str,
    file: Annotated[UploadFile, File()],
    actor: CurrentActorDep,
    use_case: Annotated[UploadDocument, Depends(get_upload_document)],
    include_in_analysis: Annotated[bool, Form()] = False,
) -> DocumentDetailResponse:
    document = await run_in_threadpool(
        use_case.for_draft,
        RequirementId(draft_id),
        await _upload_input(file, use_case.max_file_bytes, include_in_analysis),
        actor,
    )
    return _detail(document)


@router.get(
    "/requirement-drafts/{draft_id}/attachments",
    response_model=list[DocumentSummaryResponse],
)
def list_draft_documents(
    draft_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[ListDocuments, Depends(get_list_documents)],
) -> list[DocumentSummaryResponse]:
    return [_summary(item) for item in use_case.for_owned_draft(RequirementId(draft_id), actor)]


@router.post(
    "/requirement-drafts/{draft_id}/attachments/{document_id}/versions",
    response_model=DocumentDetailResponse,
    status_code=201,
)
async def upload_draft_document_version(
    draft_id: str,
    document_id: str,
    file: Annotated[UploadFile, File()],
    expected_version: Annotated[int, Form(ge=1)],
    actor: CurrentActorDep,
    use_case: Annotated[UploadDocument, Depends(get_upload_document)],
    include_in_analysis: Annotated[bool, Form()] = False,
) -> DocumentDetailResponse:
    document = await run_in_threadpool(
        use_case.for_draft,
        RequirementId(draft_id),
        await _upload_input(file, use_case.max_file_bytes, include_in_analysis),
        actor,
        DocumentId(document_id),
        expected_version=expected_version,
    )
    return _detail(document)


@router.get("/documents", response_model=list[DocumentSummaryResponse])
def list_documents(
    actor: CurrentActorDep,
    use_case: Annotated[ListDocuments, Depends(get_list_documents)],
) -> list[DocumentSummaryResponse]:
    return [_summary(item) for item in use_case.visible_to(actor)]


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[GetDocument, Depends(get_get_document)],
) -> DocumentDetailResponse:
    document = use_case.execute(DocumentId(document_id), actor)
    return _detail(document)


@router.get("/documents/{document_id}/content", response_model=DocumentContentResponse)
def get_document_content(
    document_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[GetDocument, Depends(get_get_document)],
) -> DocumentContentResponse:
    document = use_case.execute(DocumentId(document_id), actor)
    version = document.current_version
    if version.extracted_text is None:
        raise UnsupportedDocumentError("This document has no extracted text to preview.")
    return DocumentContentResponse(
        document_id=document.id.value,
        version_id=version.id.value,
        filename=version.filename,
        extracted_text=version.extracted_text,
    )


@router.get("/documents/{document_id}/pdf")
def preview_document_pdf(
    document_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[GetDocument, Depends(get_get_document)],
) -> Response:
    document = use_case.execute(DocumentId(document_id), actor)
    version = document.current_version
    if version.mime_type != "application/pdf":
        raise UnsupportedDocumentError("Browser blob preview is available only for PDF files.")
    content = use_case.blob(document.id, DocumentVersionId(version.id.value), actor)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{document.id.value}.pdf"'},
    )


@router.get("/documents/{document_id}/versions/{version_id}/assets/{asset_id}")
def preview_document_asset(
    document_id: str,
    version_id: str,
    asset_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[GetDocument, Depends(get_get_document)],
) -> Response:
    document = use_case.execute(DocumentId(document_id), actor)
    mime_type, content = use_case.asset(document.id, DocumentVersionId(version_id), asset_id, actor)
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{asset_id}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.put(
    "/requirements/{requirement_id}/attachments/{document_id}/analysis-inclusion",
    response_model=DocumentDetailResponse,
)
def set_document_inclusion(
    requirement_id: str,
    document_id: str,
    body: SetDocumentInclusionRequest,
    actor: CurrentActorDep,
    use_case: Annotated[SetDocumentInclusion, Depends(get_set_document_inclusion)],
) -> DocumentDetailResponse:
    requirement = RequirementId(requirement_id)
    return _detail(
        use_case.execute(
            actor, requirement, DocumentId(document_id), body.included, body.expected_version
        )
    )


@router.put(
    "/requirements/{requirement_id}/attachments/{document_id}/hidden-worksheets",
    response_model=DocumentDetailResponse,
)
def set_hidden_worksheet_inclusion(
    requirement_id: str,
    document_id: str,
    body: SetHiddenWorksheetInclusionRequest,
    actor: CurrentActorDep,
    use_case: Annotated[SetHiddenWorksheetInclusion, Depends(get_set_hidden_worksheet_inclusion)],
) -> DocumentDetailResponse:
    requirement = RequirementId(requirement_id)
    return _detail(
        use_case.execute(
            actor,
            requirement,
            DocumentId(document_id),
            tuple(body.worksheet_names),
            body.expected_version,
        )
    )


@router.delete("/requirements/{requirement_id}/attachments/{document_id}", status_code=204)
def remove_document(
    requirement_id: str,
    document_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[RemoveDocument, Depends(get_remove_document)],
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    requirement = RequirementId(requirement_id)
    use_case.execute(actor, requirement, DocumentId(document_id), expected_version)
    return Response(status_code=204)


@router.put(
    "/requirement-drafts/{draft_id}/attachments/{document_id}/analysis-inclusion",
    response_model=DocumentDetailResponse,
)
def set_draft_document_inclusion(
    draft_id: str,
    document_id: str,
    body: SetDocumentInclusionRequest,
    actor: CurrentActorDep,
    use_case: Annotated[SetDocumentInclusion, Depends(get_set_document_inclusion)],
) -> DocumentDetailResponse:
    return _detail(
        use_case.for_draft(
            actor,
            RequirementId(draft_id),
            DocumentId(document_id),
            body.included,
            body.expected_version,
        )
    )


@router.delete("/requirement-drafts/{draft_id}/attachments/{document_id}", status_code=204)
def remove_draft_document(
    draft_id: str,
    document_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[RemoveDocument, Depends(get_remove_document)],
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    use_case.for_draft(actor, RequirementId(draft_id), DocumentId(document_id), expected_version)
    return Response(status_code=204)
