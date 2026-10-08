"""Requirement knowledge review and grounded-answer routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.domain.value_objects import QuestionId
from smb_requirement_agent.application.ports.requirement_knowledge import KnowledgeReview
from smb_requirement_agent.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.application.use_cases.prior_art import GetPriorArt, PriorArtView
from smb_requirement_agent.application.use_cases.requirement_indexing import (
    IndexRequirementKnowledge,
    RequirementIndexStatus,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    DecideKnowledgeFinding,
    EnsureKnowledgeScreen,
    GetKnowledgeReview,
)
from smb_requirement_agent.domain.knowledge.entities import (
    AnswerSuggestionSet,
    KnowledgeFinding,
    KnowledgeFindingId,
    RelationshipEvidence,
)
from smb_requirement_agent.domain.knowledge.prior_art import PriorArtEvidence
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    get_clock,
    get_decide_knowledge_finding,
    get_ensure_knowledge_screen,
    get_get_knowledge_review,
    get_get_prior_art,
    get_reference_reviews,
    get_requirement_indexer,
    get_suggest_clarification_answers,
    limit_provider_calls,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.routes.identity import actor_response
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse
from smb_requirement_agent.interfaces.api.schemas.knowledge import (
    AnswerSuggestionResponse,
    AnswerSuggestionSetResponse,
    CorpusRetirementResponse,
    KnowledgeDecisionResponse,
    KnowledgeEvidenceResponse,
    KnowledgeFindingDecisionRequest,
    KnowledgeFindingResponse,
    KnowledgeReviewResponse,
    KnowledgeScreenEnsureResponse,
    PriorArtLineageItem,
    PriorArtMatchResponse,
    PriorArtPassageResponse,
    PriorArtResponse,
)
from smb_requirement_agent.references.application.ports.reference_grounding import (
    ReferenceReviewPort,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

router = APIRouter(
    prefix="/requirements",
    tags=["requirement-knowledge"],
    dependencies=[Depends(require_authenticated_actor)],
)


@router.get("/{requirement_id}/knowledge-index", response_model=RequirementIndexStatus)
def get_index_status(
    requirement_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[IndexRequirementKnowledge, Depends(get_requirement_indexer)],
) -> RequirementIndexStatus:
    return use_case.status(requirement_id, actor)


@router.post(
    "/{requirement_id}/knowledge-index/retry",
    response_model=RequirementIndexStatus,
    dependencies=[Depends(limit_provider_calls)],
)
def retry_index(
    requirement_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[IndexRequirementKnowledge, Depends(get_requirement_indexer)],
) -> RequirementIndexStatus:
    use_case.retry(requirement_id, actor)
    return use_case.status(requirement_id, actor)


def _evidence(value: RelationshipEvidence) -> KnowledgeEvidenceResponse:
    return KnowledgeEvidenceResponse(
        chunk_id=value.chunk_id.value,
        requirement_id=value.requirement_id.value,
        field=value.field,
        excerpt=value.excerpt,
        evidence_path=value.evidence_path,
        fingerprint=value.fingerprint,
    )


def finding_response(value: KnowledgeFinding) -> KnowledgeFindingResponse:
    return KnowledgeFindingResponse(
        id=value.id.value,
        kind=value.kind,
        status=value.status,
        version=value.version,
        subject_requirement_id=value.subject_requirement_id.value,
        related_requirement_id=value.related_requirement_id.value,
        rationale=value.rationale,
        evidence=[_evidence(item) for item in value.evidence],
        resolution_statement=value.resolution_statement,
        resolution_approvals=[item.value for item in value.resolution_approvals],
        decisions=[
            KnowledgeDecisionResponse(
                kind=item.kind.value,
                actor=actor_response(item.actor),
                recorded_at=item.recorded_at,
                rationale=item.rationale,
            )
            for item in value.decisions
        ],
    )


def review_response(value: KnowledgeReview) -> KnowledgeReviewResponse:
    status: Literal["required", "stale", "action_required", "ready"] = "required"
    if value.screen is not None and not value.current:
        status = "stale"
    elif value.current and (
        value.reference_conflict_ids or any(item.actionable for item in value.findings)
    ):
        status = "action_required"
    elif value.ready:
        status = "ready"
    retirement = value.retirement
    return KnowledgeReviewResponse(
        reference_conflict_ids=value.reference_conflict_ids,
        corpus_retirement=(
            CorpusRetirementResponse(
                retired_at=retirement.changed_at,
                retired_by=retirement.actor.display_name,
                reason=retirement.reason,
            )
            if retirement is not None
            else None
        ),
        status=status,
        current=value.current,
        ready=value.ready,
        input_fingerprint=value.current_fingerprint,
        screen_id=value.screen.id.value if value.screen else None,
        provenance=(
            ProvenanceResponse(
                generated_at=value.screen.provenance.generated_at,
                model=value.screen.provenance.model,
                prompt_version=value.screen.provenance.prompt_version,
            )
            if value.screen
            else None
        ),
        findings=[finding_response(item) for item in value.findings],
    )


def suggestion_response(value: AnswerSuggestionSet) -> AnswerSuggestionSetResponse:
    return AnswerSuggestionSetResponse(
        id=value.id.value,
        question_id=value.question_id.value,
        suggestions=[
            AnswerSuggestionResponse(
                id=item.id.value,
                source=item.source_for(value.requirement_id),
                reference_evidence=item.reference_evidence,
                answer=item.answer,
                rationale=item.rationale,
                evidence=[_evidence(evidence) for evidence in item.evidence],
            )
            for item in value.suggestions
        ],
        provenance=ProvenanceResponse(
            generated_at=value.provenance.generated_at,
            model=value.provenance.model,
            prompt_version=value.provenance.prompt_version,
        ),
    )


@router.get("/{requirement_id}/knowledge-review", response_model=KnowledgeReviewResponse)
def get_knowledge_review(
    requirement_id: str,
    use_case: Annotated[GetKnowledgeReview, Depends(get_get_knowledge_review)],
) -> KnowledgeReviewResponse:
    return review_response(use_case.execute(RequirementId(requirement_id)))


def _lineage(value: object) -> list[PriorArtLineageItem]:
    items = value if isinstance(value, list) else []
    return [PriorArtLineageItem.model_validate(item) for item in items if isinstance(item, dict)]


def _passage(item: PriorArtEvidence) -> PriorArtPassageResponse:
    context = item.context
    path = context.get("section_path")
    return PriorArtPassageResponse(
        source_kind=item.source_kind.value,
        excerpt=item.excerpt,
        brd_filename=str(context["brd_filename"]) if "brd_filename" in context else None,
        label=str(context["label"]) if "label" in context else None,
        section_path=[str(part) for part in path] if isinstance(path, list) else [],
        lineage=_lineage(context.get("lineage")),
    )


def prior_art_response(view: PriorArtView) -> PriorArtResponse:
    check = view.check
    return PriorArtResponse(
        status=view.status.value,
        input_key=view.input_key,
        checked_at=None if check is None else check.checked_at,
        provenance=None
        if check is None
        else ProvenanceResponse(
            generated_at=check.provenance.generated_at,
            model=check.provenance.model,
            prompt_version=check.provenance.prompt_version,
        ),
        matches=[]
        if check is None
        else [
            PriorArtMatchResponse(
                historic_requirement_id=match.historic_requirement_id,
                title=match.title,
                publication=match.publication,
                verdict=match.verdict.value,
                rationale=match.rationale,
                passages=[_passage(item) for item in match.evidence],
            )
            for match in check.matches
        ],
    )


@router.get("/{requirement_id}/prior-art", response_model=PriorArtResponse)
def get_prior_art(
    requirement_id: str,
    use_case: Annotated[GetPriorArt, Depends(get_get_prior_art)],
) -> PriorArtResponse:
    """Similar past requirements, from the historic corpus: reference only (ADR-0102)."""
    return prior_art_response(use_case.execute(RequirementId(requirement_id)))


@router.post(
    "/{requirement_id}/knowledge-screen/ensure",
    response_model=KnowledgeScreenEnsureResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def ensure_knowledge_screen(
    requirement_id: str,
    actor: CurrentActorDep,
    use_case: Annotated[EnsureKnowledgeScreen, Depends(get_ensure_knowledge_screen)],
) -> KnowledgeScreenEnsureResponse:
    result = use_case.execute(RequirementId(requirement_id), actor)
    return KnowledgeScreenEnsureResponse(
        outcome=result.outcome,
        job_id=result.job_id.value if result.job_id is not None else None,
    )


@router.post(
    "/{requirement_id}/knowledge-findings/{finding_id}/decisions",
    response_model=KnowledgeFindingResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def decide_knowledge_finding(
    requirement_id: str,
    finding_id: str,
    body: KnowledgeFindingDecisionRequest,
    actor: CurrentActorDep,
    use_case: Annotated[DecideKnowledgeFinding, Depends(get_decide_knowledge_finding)],
) -> KnowledgeFindingResponse:
    return finding_response(
        use_case.execute(
            RequirementId(requirement_id),
            KnowledgeFindingId(finding_id),
            body.decision,
            body.expected_version,
            actor,
            body.text,
        )
    )


@router.get(
    "/{requirement_id}/analysis/questions/{question_id}/answer-suggestions",
    response_model=AnswerSuggestionSetResponse | None,
)
def get_answer_suggestions(
    requirement_id: str,
    question_id: str,
    use_case: Annotated[SuggestClarificationAnswers, Depends(get_suggest_clarification_answers)],
    reviews: Annotated[ReferenceReviewPort, Depends(get_reference_reviews)],
    clock: Annotated[ClockPort, Depends(get_clock)],
) -> AnswerSuggestionSetResponse | None:
    value = use_case.get_current(RequirementId(requirement_id), QuestionId(question_id))
    if value is None:
        return None
    cited = tuple(
        citation.document_id for item in value.suggestions for citation in item.reference_evidence
    )
    return suggestion_response(value).model_copy(
        update={"overdue_reference_reviews": reviews.overdue_reviews(cited, clock.now().date())}
    )
