"""Requirement-scoped human approval workflow routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from smb_requirement_agent.application.use_cases.approval_workflow import (
    AddReviewComment,
    ApprovalWorkflowView,
    ApproveBreakdown,
    GetApprovalWorkflow,
    SubmitForReview,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.domain.shared.approval import ApprovalTarget
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_add_review_comment,
    get_approval_workflow,
    get_approve_breakdown,
    get_submit_for_review,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.schemas.governance import (
    ApprovalCompletionResponse,
    ApprovalResponse,
    ApprovalTargetResponse,
    ApprovalWorkflowResponse,
    ArtifactApprovalResponse,
    FingerprintRequest,
    ReviewCommentRequest,
    ReviewCommentResponse,
)

router = APIRouter(
    prefix="/requirements",
    tags=["approval-workflow"],
    dependencies=[Depends(require_authenticated_actor)],
)


def workflow_response(view: ApprovalWorkflowView) -> ApprovalWorkflowResponse:
    completion = view.completion
    return ApprovalWorkflowResponse(
        requirement_id=view.review.requirement_id.value,
        review_version=view.review.version,
        status=view.status,
        subject_fingerprint=view.subject_fingerprint,
        submitted_fingerprint=view.review.submitted_fingerprint,
        artifacts=[
            ArtifactApprovalResponse(
                target=ApprovalTargetResponse.from_domain(item.target),
                parent_id=item.parent_id,
                label=item.label,
                status=item.status,
                fingerprint=item.fingerprint,
                version=item.version,
                current_approval=(
                    ApprovalResponse.from_domain(item.current_approval)
                    if item.current_approval
                    else None
                ),
                approval_history=[
                    ApprovalResponse.from_domain(approval) for approval in item.approvals
                ],
            )
            for item in view.artifacts
        ],
        completion=ApprovalCompletionResponse(
            epic_approved=completion.epic_approved,
            epic_total=completion.epic_total,
            features_approved=completion.features_approved,
            features_total=completion.features_total,
            stories_approved=completion.stories_approved,
            stories_total=completion.stories_total,
        ),
        readiness_reasons=list(view.readiness_reasons),
        blocking_reasons=list(view.blocking_reasons),
        can_submit=view.can_submit,
        can_approve_breakdown=view.can_approve_breakdown,
        can_comment=view.can_comment,
        breakdown_approvals=[ApprovalResponse.from_domain(item) for item in view.review.approvals],
        comments=[ReviewCommentResponse.from_domain(item) for item in view.review.comments],
    )


@router.get("/{requirement_id}/approval-workflow", response_model=ApprovalWorkflowResponse)
def get_workflow(
    requirement_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[GetApprovalWorkflow, Depends(get_approval_workflow)],
) -> ApprovalWorkflowResponse:
    return workflow_response(use_case.execute(RequirementId(requirement_id), actor))


@router.post("/{requirement_id}/review-submission", response_model=ApprovalWorkflowResponse)
def submit_review(
    requirement_id: str,
    body: FingerprintRequest,
    actor: CurrentActorDep,
    use_case: Annotated[SubmitForReview, Depends(get_submit_for_review)],
) -> ApprovalWorkflowResponse:
    return workflow_response(
        use_case.execute(
            RequirementId(requirement_id),
            actor,
            body.expected_fingerprint,
            body.expected_version,
        )
    )


@router.post("/{requirement_id}/breakdown-approval", response_model=ApprovalWorkflowResponse)
def approve_breakdown(
    requirement_id: str,
    body: FingerprintRequest,
    actor: CurrentActorDep,
    use_case: Annotated[ApproveBreakdown, Depends(get_approve_breakdown)],
) -> ApprovalWorkflowResponse:
    return workflow_response(
        use_case.execute(
            RequirementId(requirement_id),
            actor,
            body.expected_fingerprint,
            body.expected_version,
            body.rationale,
        )
    )


@router.post(
    "/{requirement_id}/breakdown-review/comments",
    response_model=ApprovalWorkflowResponse,
)
def add_comment(
    requirement_id: str,
    body: ReviewCommentRequest,
    actor: CurrentActorDep,
    use_case: Annotated[AddReviewComment, Depends(get_add_review_comment)],
) -> ApprovalWorkflowResponse:
    return workflow_response(
        use_case.execute(
            RequirementId(requirement_id),
            actor,
            ApprovalTarget(body.target_kind, body.target_id),
            body.body,
            body.expected_version,
        )
    )
