"""Revision history and deterministic comparison routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from smb_requirement_agent.application.exports import ExportFormat
from smb_requirement_agent.application.use_cases.export_breakdown import (
    ExportBreakdown,
    formal_final_approval,
    is_exportable_revision,
)
from smb_requirement_agent.application.use_cases.revision_history import (
    CompareBreakdownVersions,
    GetRevisionHistory,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.domain.revision.entities import BreakdownRevision, RevisionNumber
from smb_requirement_agent.domain.shared.generation import GenerationStatus
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_compare_breakdown_versions,
    get_export_breakdown,
    get_revision_history,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse
from smb_requirement_agent.interfaces.api.schemas.revisions import (
    BreakdownComparisonResponse,
    BreakdownRevisionResponse,
    RequirementRevisionResponse,
    RevisionHistoryResponse,
)

router = APIRouter(
    prefix="/requirements", tags=["revisions"], dependencies=[Depends(require_authenticated_actor)]
)


@router.get("/{requirement_id}/revisions", response_model=RevisionHistoryResponse)
def revision_history(
    requirement_id: str,
    use_case: Annotated[GetRevisionHistory, Depends(get_revision_history)],
) -> RevisionHistoryResponse:
    history = use_case.execute(RequirementId(requirement_id))
    return RevisionHistoryResponse(
        requirement_revisions=[
            RequirementRevisionResponse(
                number=item.number.value,
                created_at=item.created_at,
                title=item.requirement.title.value,
                description=item.requirement.description.value,
                status=item.requirement.status.value,
            )
            for item in history.requirement_revisions
        ],
        breakdown_revisions=[_revision_response(item) for item in history.breakdown_revisions],
    )


def _revision_response(item: BreakdownRevision) -> BreakdownRevisionResponse:
    approval = formal_final_approval(item)
    return BreakdownRevisionResponse(
        number=item.number.value,
        created_at=item.created_at,
        has_analysis=item.analysis is not None,
        analysis_human_confirmed=(item.analysis.is_human_confirmed if item.analysis else False),
        clarification_count=len(item.analysis.clarifications) if item.analysis else 0,
        unresolved_count=len(item.analysis.unresolved_keys()) if item.analysis else 0,
        intent_proposal_count=len(item.analysis.intent_proposals) if item.analysis else 0,
        intent_decision_count=(
            sum(len(proposal.decisions) for proposal in item.analysis.intent_proposals)
            if item.analysis
            else 0
        ),
        epic_name=item.epic.name.value if item.epic else None,
        epic_status=item.epic.status.value if item.epic else None,
        feature_count=len(item.features),
        approved_feature_count=sum(
            feature.status is GenerationStatus.APPROVED for feature in item.features
        ),
        story_count=len(item.stories),
        edited_story_count=sum(story.status is GenerationStatus.EDITED for story in item.stories),
        stale_story_count=sum(story.is_stale for story in item.stories),
        has_review=item.review is not None,
        review_blocker_count=(item.review.unresolved_blocker_count if item.review else 0),
        review_decision_count=len(item.review.decisions) if item.review else 0,
        review_status=item.review.status.value if item.review else None,
        approval_count=(
            (len(item.review.approvals) if item.review else 0)
            + (len(item.epic.approvals) if item.epic else 0)
            + sum(len(feature.approvals) for feature in item.features)
            + sum(len(story.approvals) for story in item.stories)
        ),
        comment_count=len(item.review.comments) if item.review else 0,
        submitted_fingerprint=(item.review.submitted_fingerprint if item.review else None),
        exportable=is_exportable_revision(item),
        final_approved_by=(
            ActorResponse(
                id=approval.recorded_by.id.value,
                display_name=approval.recorded_by.display_name,
                email=approval.recorded_by.email,
            )
            if approval
            else None
        ),
        final_approved_at=approval.recorded_at if approval else None,
    )


@router.get("/{requirement_id}/revisions/compare", response_model=BreakdownComparisonResponse)
def compare_revisions(
    requirement_id: str,
    use_case: Annotated[CompareBreakdownVersions, Depends(get_compare_breakdown_versions)],
    from_revision: Annotated[int, Query(ge=1)],
    to_revision: Annotated[int, Query(ge=1)],
) -> BreakdownComparisonResponse:
    result = use_case.execute(
        RequirementId(requirement_id),
        RevisionNumber(from_revision),
        RevisionNumber(to_revision),
    )
    return BreakdownComparisonResponse(
        from_revision=result.from_revision.value,
        to_revision=result.to_revision.value,
        changes=list(result.changes),
    )


@router.get(
    "/{requirement_id}/revisions/{revision_number}/export",
    response_class=Response,
    responses={
        200: {
            "description": "The selected formally approved revision.",
            "content": {
                "application/json": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
            },
        }
    },
)
def export_revision(
    requirement_id: str,
    revision_number: Annotated[int, Path(ge=1)],
    export_format: Annotated[ExportFormat, Query(alias="format")],
    actor: CurrentActorDep,
    use_case: Annotated[ExportBreakdown, Depends(get_export_breakdown)],
) -> Response:
    artifact = use_case.execute(
        RequirementId(requirement_id),
        RevisionNumber(revision_number),
        export_format,
        actor,
    )
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "Cache-Control": "private, no-store",
        },
    )
