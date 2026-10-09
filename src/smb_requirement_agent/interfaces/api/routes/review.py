"""Requirement-scoped breakdown review routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from smb_requirement_agent.breakdown.application.use_cases.story_quality import SuggestStorySplit
from smb_requirement_agent.governance.application.use_cases.breakdown_review import (
    BreakdownReviewView,
    GetBreakdownReview,
    RecordDecision,
    ResolveFlag,
)
from smb_requirement_agent.governance.domain.review.entities import FlagId, ReviewSource
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_get_breakdown_review,
    get_record_decision,
    get_resolve_flag,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.routes.identity import actor_response
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse
from smb_requirement_agent.interfaces.api.schemas.governance import (
    ApprovalResponse,
    ReviewCommentResponse,
)
from smb_requirement_agent.interfaces.api.schemas.review import (
    BreakdownReviewResponse,
    DecisionRequest,
    ResolveFlagRequest,
    ReviewDecisionResponse,
    ReviewDependencyResponse,
    ReviewFlagResponse,
    ReviewRecommendationResponse,
    ReviewRiskResponse,
    ReviewSourceResponse,
)
from smb_requirement_agent.interfaces.api.schemas.story import (
    SpidrRecommendationResponse,
    StoryQualityResponse,
    ValidationFindingResponse,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

router = APIRouter(
    prefix="/requirements",
    tags=["breakdown-review"],
    dependencies=[Depends(require_authenticated_actor)],
)


def _source(value: ReviewSource) -> ReviewSourceResponse:
    return ReviewSourceResponse(kind=value.kind, item_id=value.item_id, label=value.label)


def review_response(view: BreakdownReviewView) -> BreakdownReviewResponse:
    review = view.review
    return BreakdownReviewResponse(
        requirement_id=review.requirement_id.value,
        version=review.version,
        generated_at=review.generated_at,
        ruleset_version=review.ruleset_version,
        evidence_fingerprint=review.evidence_fingerprint,
        fresh=view.fresh,
        unresolved_blocker_count=review.unresolved_blocker_count,
        unresolved_warning_count=review.unresolved_warning_count,
        dependencies=[
            ReviewDependencyResponse(
                id=item.id.value,
                description=item.description,
                source=_source(item.source),
                evidence_kind=item.evidence_kind,
            )
            for item in review.dependencies
        ],
        risks=[
            ReviewRiskResponse(
                id=item.id.value,
                severity=item.severity,
                description=item.description,
                source=_source(item.source),
            )
            for item in review.risks
        ],
        flags=[
            ReviewFlagResponse(
                id=item.id.value,
                category=item.category,
                severity=item.severity,
                title=item.title,
                detail=item.detail,
                source=_source(item.source),
                resolution_policy=item.resolution_policy,
                status=item.status,
                resolution_decision_id=(
                    item.resolution_decision_id.value if item.resolution_decision_id else None
                ),
            )
            for item in review.flags
        ],
        recommendations=[
            ReviewRecommendationResponse(
                id=item.id.value,
                action=item.action,
                rationale=item.rationale,
                source=_source(item.source),
            )
            for item in review.recommendations
        ],
        quality_assessments=[
            StoryQualityResponse(
                story_id=item.story_id.value,
                status=item.status,
                failure_count=item.failure_count,
                findings=[
                    ValidationFindingResponse(
                        criterion=finding.criterion,
                        passed=finding.passed,
                        message=finding.message,
                        source=finding.source,
                    )
                    for finding in item.findings
                ],
                recommendations=[
                    SpidrRecommendationResponse(pattern=entry.pattern, reason=entry.reason)
                    for entry in SuggestStorySplit.for_assessment(item)
                ],
                provenance=ProvenanceResponse(
                    generated_at=item.provenance.generated_at,
                    model=item.provenance.model,
                    prompt_version=item.provenance.prompt_version,
                ),
            )
            for item in review.quality_assessments
        ],
        decisions=[
            ReviewDecisionResponse(
                id=item.id.value,
                decision=item.decision,
                rationale=item.rationale,
                recorded_at=item.recorded_at,
                target_flag_id=item.target_flag_id.value if item.target_flag_id else None,
                recorded_by=actor_response(item.recorded_by) if item.recorded_by else None,
            )
            for item in review.decisions
        ],
        status=review.status,
        submitted_fingerprint=review.submitted_fingerprint,
        approval_history=[ApprovalResponse.from_domain(item) for item in review.approvals],
        comments=[ReviewCommentResponse.from_domain(item) for item in review.comments],
    )


@router.get("/{requirement_id}/breakdown-review", response_model=BreakdownReviewResponse)
def get_breakdown_review(
    requirement_id: str,
    use_case: Annotated[GetBreakdownReview, Depends(get_get_breakdown_review)],
) -> BreakdownReviewResponse:
    return review_response(use_case.execute(RequirementId(requirement_id)))


@router.post(
    "/{requirement_id}/breakdown-review/decisions",
    response_model=BreakdownReviewResponse,
)
def record_decision(
    requirement_id: str,
    body: DecisionRequest,
    actor: CurrentActorDep,
    use_case: Annotated[RecordDecision, Depends(get_record_decision)],
) -> BreakdownReviewResponse:
    return review_response(
        use_case.execute(
            RequirementId(requirement_id),
            body.decision,
            body.rationale,
            body.expected_fingerprint,
            body.expected_version,
            actor,
            FlagId(body.target_flag_id) if body.target_flag_id else None,
        )
    )


@router.post(
    "/{requirement_id}/breakdown-review/flags/{flag_id}/resolution",
    response_model=BreakdownReviewResponse,
)
def resolve_flag(
    requirement_id: str,
    flag_id: str,
    body: ResolveFlagRequest,
    actor: CurrentActorDep,
    use_case: Annotated[ResolveFlag, Depends(get_resolve_flag)],
) -> BreakdownReviewResponse:
    return review_response(
        use_case.execute(
            RequirementId(requirement_id),
            FlagId(flag_id),
            body.decision,
            body.rationale,
            body.expected_fingerprint,
            body.expected_version,
            actor,
        )
    )
