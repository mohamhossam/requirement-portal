"""Analysis API routes.

Domain and application errors are translated to status codes centrally in
``interfaces.api.error_handlers``.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
    AnalysisRoundView,
    AnalysisWorkspace,
    ClarificationResolutionInput,
)
from smb_requirement_agent.application.use_cases.analyze_requirement import AnalyzeRequirement
from smb_requirement_agent.application.use_cases.clarify_requirement_analysis import (
    ClarificationAnswerInput,
    ClarifyRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.confirm_requirement_analysis import (
    ConfirmRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.get_requirement_analysis import (
    GetRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.requirement_commands import ExpectedContext
from smb_requirement_agent.domain.analysis.entities import (
    AnalysisQuestionChange,
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.value_objects import (
    AnalysisEvidenceReference,
    AnalysisId,
    IntentProposalId,
    IntentProposalKind,
    IntentProposalStatus,
    QuestionId,
)
from smb_requirement_agent.domain.shared.actors import ActorId
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.interfaces.api.dependencies import (
    CurrentActorDep,
    RequirementCommandsDep,
    get_analysis_collaboration,
    get_analyze_requirement,
    get_clarify_requirement_analysis,
    get_confirm_requirement_analysis,
    get_generation_context_tokens,
    get_get_requirement_analysis,
    limit_provider_calls,
    require_authenticated_actor,
)
from smb_requirement_agent.interfaces.api.routes.identity import actor_response
from smb_requirement_agent.interfaces.api.schemas.analysis import (
    AmbiguityResponse,
    AnalysisActionsResponse,
    AnalysisClarificationEvidenceResponse,
    AnalysisDocumentReferenceResponse,
    AnalysisEvidenceReferenceResponse,
    AnalysisQuestionChangeResponse,
    AnalysisRoundResponse,
    AnalysisStageProvenanceResponse,
    AskClarificationQuestionRequest,
    AssignClarificationQuestionRequest,
    AssumptionResponse,
    BusinessIntentResponse,
    BusinessRuleResponse,
    ClarificationQuestionResponse,
    ClarifyAnalysisRequest,
    ClassifyClarificationQuestionRequest,
    ConfirmAnalysisRequest,
    ConfirmedIntentItemResponse,
    ConstraintResponse,
    DecideIntentProposalRequest,
    HumanClarificationResponse,
    IntentProposalDecisionResponse,
    IntentProposalResponse,
    KnownFactResponse,
    OpenQuestionResponse,
    PotentialDependencyResponse,
    QuestionAssignmentChangeResponse,
    RequirementAnalysisResponse,
    ResolveClarificationQuestionRequest,
    ResolveClarificationQuestionsRequest,
    SaveClarificationDraftRequest,
)
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse
from smb_requirement_agent.interfaces.api.schemas.generation import (
    ActionAvailabilityResponse,
    GenerationRequest,
)

router = APIRouter(
    prefix="/requirements", tags=["analysis"], dependencies=[Depends(require_authenticated_actor)]
)


def _evidence_response(
    values: tuple[AnalysisEvidenceReference, ...],
) -> list[AnalysisEvidenceReferenceResponse]:
    return [
        AnalysisEvidenceReferenceResponse(
            document_id=item.document_id,
            version_id=item.version_id,
            checksum_sha256=item.checksum_sha256,
            block_id=item.block_id,
            label=item.label,
        )
        for item in values
    ]


def question_response(question: ClarificationQuestion) -> ClarificationQuestionResponse:
    return ClarificationQuestionResponse(
        id=question.id.value,
        analysis_id=question.first_analysis_id.value,
        kind=question.kind,
        subject=question.subject,
        rationale=question.rationale,
        severity=question.severity,
        is_blocker=question.is_blocker,
        source=question.source,
        status=question.status,
        version=question.version,
        asked_by=actor_response(question.asked_by) if question.asked_by else None,
        asked_at=question.asked_at,
        assignee=actor_response(question.assignee) if question.assignee else None,
        assignment_history=[
            QuestionAssignmentChangeResponse(
                assignee=actor_response(item.assignee) if item.assignee else None,
                changed_by=actor_response(item.changed_by),
                changed_at=item.changed_at,
            )
            for item in question.assignment_history
        ],
        draft_answer=question.draft_answer,
        draft_updated_by=(
            actor_response(question.draft_updated_by) if question.draft_updated_by else None
        ),
        draft_updated_at=question.draft_updated_at,
        answer=question.answer,
        answered_by=actor_response(question.answered_by) if question.answered_by else None,
        answered_at=question.answered_at,
        classification_changed_by=(
            actor_response(question.classification_changed_by)
            if question.classification_changed_by
            else None
        ),
        classification_changed_at=question.classification_changed_at,
        replaces_question_id=(
            question.replaces_question_id.value if question.replaces_question_id else None
        ),
    )


def analysis_response(
    analysis: RequirementAnalysis,
    questions: tuple[ClarificationQuestion, ...] = (),
    question_changes: tuple[AnalysisQuestionChange, ...] = (),
) -> RequirementAnalysisResponse:
    outcome = analysis.effective_desired_outcome()
    outcome_proposal = next(
        (
            item
            for item in analysis.intent_proposals
            if item.kind is IntentProposalKind.DESIRED_OUTCOME
            and item.status in (IntentProposalStatus.ACCEPTED, IntentProposalStatus.EDITED)
        ),
        None,
    )
    return RequirementAnalysisResponse(
        clarification_evidence=[
            AnalysisClarificationEvidenceResponse(
                evidence_key=item.evidence_key,
                clarification_numbers=list(item.clarification_numbers),
            )
            for item in analysis.clarification_evidence
        ],
        requirement_id=analysis.requirement_id.value,
        version=analysis.version,
        known_facts=[
            KnownFactResponse(
                statement=f.statement,
                evidence_references=_evidence_response(f.evidence_references),
            )
            for f in analysis.known_facts
        ],
        constraints=[
            ConstraintResponse(
                statement=c.statement,
                evidence_references=_evidence_response(c.evidence_references),
            )
            for c in analysis.constraints
        ],
        business_rules=[
            BusinessRuleResponse(
                statement=r.statement,
                evidence_references=_evidence_response(r.evidence_references),
            )
            for r in analysis.business_rules
        ],
        assumptions=[
            AssumptionResponse(
                statement=a.statement,
                evidence_references=_evidence_response(a.evidence_references),
            )
            for a in analysis.assumptions
        ],
        open_questions=[
            OpenQuestionResponse(
                question=q.question,
                rationale=q.rationale,
                evidence_references=_evidence_response(q.evidence_references),
            )
            for q in analysis.open_questions
        ],
        ambiguities=[
            AmbiguityResponse(
                statement=a.statement,
                reason=a.reason,
                evidence_references=_evidence_response(a.evidence_references),
            )
            for a in analysis.ambiguities
        ],
        potential_dependencies=[
            PotentialDependencyResponse(
                statement=d.statement,
                evidence_references=_evidence_response(d.evidence_references),
            )
            for d in analysis.potential_dependencies
        ],
        clarifications=[
            HumanClarificationResponse(
                kind=item.kind,
                subject=item.subject,
                answer=item.answer,
                question_id=item.question_id.value if item.question_id else None,
                answered_by=actor_response(item.answered_by) if item.answered_by else None,
                answered_at=item.answered_at,
                source_suggestion_id=item.source_suggestion_id,
            )
            for item in analysis.clarifications
        ],
        human_confirmed=analysis.is_human_confirmed,
        actions=AnalysisActionsResponse(
            generate_epic=ActionAvailabilityResponse.from_domain(
                analysis.epic_generation_availability()
            )
        ),
        confirmed_at=analysis.confirmed_at,
        confirmed_by=(actor_response(analysis.confirmed_by) if analysis.confirmed_by else None),
        document_references=[
            AnalysisDocumentReferenceResponse(
                document_id=item.document_id,
                version_id=item.version_id,
                filename=item.filename,
                checksum_sha256=item.checksum_sha256,
            )
            for item in analysis.document_references
        ],
        analysis_id=analysis.id.value if analysis.id else None,
        round_number=analysis.round_number,
        provenance=(
            ProvenanceResponse(
                generated_at=analysis.provenance.generated_at,
                model=analysis.provenance.model,
                prompt_version=analysis.provenance.prompt_version,
            )
            if analysis.provenance
            else None
        ),
        source_requirement_version=(
            analysis.source_requirement_version.value
            if analysis.source_requirement_version
            else None
        ),
        questions=[question_response(item) for item in questions],
        question_changes=[
            AnalysisQuestionChangeResponse(
                action=item.action,
                question_id=item.question_id.value,
                rationale=item.rationale,
                replacement_question_id=(
                    item.replacement_question_id.value if item.replacement_question_id else None
                ),
            )
            for item in question_changes
        ],
        business_intent=BusinessIntentResponse(
            desired_outcome=(
                ConfirmedIntentItemResponse(
                    statement=outcome,
                    origin=("source" if analysis.source_desired_outcome else "human_confirmed_ai"),
                    proposal_id=(outcome_proposal.id.value if outcome_proposal else None),
                )
                if outcome
                else None
            ),
            accepted_business_rules=[
                ConfirmedIntentItemResponse(
                    statement=item.effective_statement or "",
                    origin="human_confirmed_ai",
                    proposal_id=item.id.value,
                )
                for item in analysis.intent_proposals
                if item.kind is IntentProposalKind.BUSINESS_RULE
                and item.status in (IntentProposalStatus.ACCEPTED, IntentProposalStatus.EDITED)
            ],
            accepted_constraints=[
                ConfirmedIntentItemResponse(
                    statement=item.effective_statement or "",
                    origin="human_confirmed_ai",
                    proposal_id=item.id.value,
                )
                for item in analysis.intent_proposals
                if item.kind is IntentProposalKind.CONSTRAINT
                and item.status in (IntentProposalStatus.ACCEPTED, IntentProposalStatus.EDITED)
            ],
            proposals=[
                IntentProposalResponse(
                    reference_evidence=list(item.reference_evidence),
                    reference_conflict=item.reference_conflict,
                    reference_provenance=(
                        ProvenanceResponse(
                            generated_at=item.reference_provenance.generated_at,
                            model=item.reference_provenance.model,
                            prompt_version=item.reference_provenance.prompt_version,
                        )
                        if item.reference_provenance
                        else None
                    ),
                    id=item.id.value,
                    kind=item.kind,
                    statement=item.statement,
                    rationale=item.rationale,
                    success_measures=list(item.success_measures),
                    status=item.status,
                    version=item.version,
                    effective_statement=item.effective_statement,
                    effective_success_measures=list(item.effective_success_measures),
                    decisions=[
                        IntentProposalDecisionResponse(
                            rationale=decision.rationale,
                            status=decision.status,
                            final_statement=decision.final_statement,
                            success_measures=list(decision.success_measures),
                            decided_by=actor_response(decision.decided_by),
                            decided_at=decision.decided_at,
                            version=decision.version,
                        )
                        for decision in item.decisions
                    ],
                    evidence_references=_evidence_response(item.evidence_references),
                )
                for item in analysis.intent_proposals
            ],
        ),
        stage_provenance=[
            AnalysisStageProvenanceResponse(
                stage=item.stage,
                model=item.model,
                prompt_version=item.prompt_version,
                generated_at=item.generated_at,
                input_fingerprint=item.input_fingerprint,
            )
            for item in analysis.stage_provenance
        ],
    )


def workspace_response(workspace: AnalysisWorkspace) -> RequirementAnalysisResponse:
    return analysis_response(
        workspace.analysis,
        workspace.questions,
        workspace.question_changes,
    ).model_copy(
        update={
            "stale_reference_proposal_ids": list(workspace.stale_reference_proposal_ids),
            "overdue_reference_reviews": dict(workspace.overdue_reference_reviews),
        }
    )


def round_response(view: AnalysisRoundView) -> AnalysisRoundResponse:
    return AnalysisRoundResponse(
        analysis=analysis_response(
            view.round.analysis,
            tuple(item for item in view.questions if item.id in view.round.question_ids),
            view.round.question_changes,
        ),
        questions=[question_response(item) for item in view.questions],
    )


@router.post(
    "/{requirement_id}/analysis",
    response_model=RequirementAnalysisResponse,
    status_code=200,
    dependencies=[Depends(limit_provider_calls)],
)
def analyze_requirement(
    requirement_id: str,
    body: GenerationRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
    use_case: Annotated[AnalyzeRequirement, Depends(get_analyze_requirement)],
) -> RequirementAnalysisResponse:
    resolved = RequirementId(requirement_id)
    return commands.run_and_present(
        resolved,
        actor,
        lambda: use_case.execute_workspace(actor, resolved, force=body.force),
        lambda workspace: _with_context_tokens(
            workspace_response(workspace), resolved, generation_context
        ),
        expected=ExpectedContext(body.context_token, lambda: generation_context.analysis(resolved)),
    )


def _with_context_tokens(
    response: RequirementAnalysisResponse,
    requirement_id: RequirementId,
    generation_context: GenerationContextTokens,
) -> RequirementAnalysisResponse:
    return response.model_copy(
        update={
            "analysis_context_token": generation_context.analysis(requirement_id),
            "epic_context_token": generation_context.epic(requirement_id),
        }
    )


@router.get("/{requirement_id}/analysis", response_model=RequirementAnalysisResponse)
def get_requirement_analysis(
    requirement_id: str,
    use_case: Annotated[GetRequirementAnalysis, Depends(get_get_requirement_analysis)],
    collaboration: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
    generation_context: Annotated[GenerationContextTokens, Depends(get_generation_context_tokens)],
    commands: RequirementCommandsDep,
) -> RequirementAnalysisResponse:
    resolved = RequirementId(requirement_id)

    def read() -> RequirementAnalysisResponse:
        use_case.execute(resolved)
        return _with_context_tokens(
            workspace_response(collaboration.workspace(resolved)), resolved, generation_context
        )

    return commands.read(resolved, read)


@router.post(
    "/{requirement_id}/analysis/clarifications",
    response_model=RequirementAnalysisResponse,
    status_code=200,
    dependencies=[Depends(limit_provider_calls)],
)
def clarify_requirement_analysis(
    requirement_id: str,
    request: ClarifyAnalysisRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[
        ClarifyRequirementAnalysis,
        Depends(get_clarify_requirement_analysis),
    ],
) -> RequirementAnalysisResponse:
    answers = tuple(
        ClarificationAnswerInput(
            kind=item.kind,
            subject=item.subject,
            answer=item.answer,
        )
        for item in request.answers
    )
    resolved = RequirementId(requirement_id)
    return workspace_response(
        commands.run(
            resolved,
            actor,
            lambda: use_case.execute_workspace(
                resolved, answers, request.expected_analysis_version, actor
            ),
        )
    )


@router.post(
    "/{requirement_id}/analysis/confirmation",
    response_model=RequirementAnalysisResponse,
    status_code=200,
)
def confirm_requirement_analysis(
    requirement_id: str,
    request: ConfirmAnalysisRequest,
    actor: CurrentActorDep,
    use_case: Annotated[
        ConfirmRequirementAnalysis,
        Depends(get_confirm_requirement_analysis),
    ],
    collaboration: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> RequirementAnalysisResponse:
    resolved_id = RequirementId(requirement_id)
    use_case.execute(resolved_id, actor, request.expected_version)
    return workspace_response(collaboration.workspace(resolved_id))


@router.patch(
    "/{requirement_id}/analysis/proposals/{proposal_id}",
    response_model=RequirementAnalysisResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def decide_intent_proposal(
    requirement_id: str,
    proposal_id: str,
    request: DecideIntentProposalRequest,
    actor: CurrentActorDep,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> RequirementAnalysisResponse:
    return workspace_response(
        use_case.decide_intent_proposal(
            RequirementId(requirement_id),
            IntentProposalId(proposal_id),
            request.decision,
            request.expected_version,
            actor,
            replacement_statement=request.replacement_statement,
            rationale=request.rationale,
            success_measures=(
                tuple(request.success_measures) if request.success_measures is not None else None
            ),
        )
    )


@router.get("/{requirement_id}/analysis/rounds", response_model=list[AnalysisRoundResponse])
def list_analysis_rounds(
    requirement_id: str,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> list[AnalysisRoundResponse]:
    return [round_response(item) for item in use_case.list_rounds(RequirementId(requirement_id))]


@router.get(
    "/{requirement_id}/analysis/rounds/{analysis_id}",
    response_model=AnalysisRoundResponse,
)
def get_analysis_round(
    requirement_id: str,
    analysis_id: str,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> AnalysisRoundResponse:
    return round_response(
        use_case.get_round(RequirementId(requirement_id), AnalysisId(analysis_id))
    )


@router.post(
    "/{requirement_id}/analysis/questions",
    response_model=ClarificationQuestionResponse,
    status_code=201,
    dependencies=[Depends(limit_provider_calls)],
)
def ask_clarification_question(
    requirement_id: str,
    request: AskClarificationQuestionRequest,
    actor: CurrentActorDep,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> ClarificationQuestionResponse:
    return question_response(
        use_case.ask(
            RequirementId(requirement_id),
            subject=request.subject,
            rationale=request.rationale,
            assignee_id=ActorId(request.assignee_id) if request.assignee_id else None,
            severity=request.severity,
            is_blocker=request.is_blocker,
            expected_analysis_version=request.expected_analysis_version,
            actor=actor,
        )
    )


@router.patch(
    "/{requirement_id}/analysis/questions/{question_id}",
    response_model=ClarificationQuestionResponse,
)
def classify_clarification_question(
    requirement_id: str,
    question_id: str,
    request: ClassifyClarificationQuestionRequest,
    actor: CurrentActorDep,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> ClarificationQuestionResponse:
    return question_response(
        use_case.classify(
            RequirementId(requirement_id),
            QuestionId(question_id),
            request.severity,
            request.is_blocker,
            request.expected_version,
            actor,
        )
    )


@router.put(
    "/{requirement_id}/analysis/questions/{question_id}/assignment",
    response_model=ClarificationQuestionResponse,
)
def assign_clarification_question(
    requirement_id: str,
    question_id: str,
    request: AssignClarificationQuestionRequest,
    actor: CurrentActorDep,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> ClarificationQuestionResponse:
    return question_response(
        use_case.assign(
            RequirementId(requirement_id),
            QuestionId(question_id),
            ActorId(request.assignee_id) if request.assignee_id else None,
            request.expected_version,
            actor,
        )
    )


@router.put(
    "/{requirement_id}/analysis/questions/{question_id}/draft",
    response_model=ClarificationQuestionResponse,
)
def save_clarification_draft(
    requirement_id: str,
    question_id: str,
    request: SaveClarificationDraftRequest,
    actor: CurrentActorDep,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> ClarificationQuestionResponse:
    return question_response(
        use_case.save_draft(
            RequirementId(requirement_id),
            QuestionId(question_id),
            request.answer,
            request.expected_version,
            actor,
        )
    )


@router.post(
    "/{requirement_id}/analysis/question-resolutions",
    response_model=RequirementAnalysisResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def resolve_clarification_questions(
    requirement_id: str,
    request: ResolveClarificationQuestionsRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> RequirementAnalysisResponse:
    resolved = RequirementId(requirement_id)
    answers = tuple(
        ClarificationResolutionInput(
            QuestionId(item.question_id),
            item.answer,
            item.expected_version,
            item.source_suggestion_id,
        )
        for item in request.answers
    )
    return workspace_response(
        commands.run(resolved, actor, lambda: use_case.resolve_batch(resolved, answers, actor))
    )


@router.post(
    "/{requirement_id}/analysis/questions/{question_id}/resolution",
    response_model=RequirementAnalysisResponse,
    dependencies=[Depends(limit_provider_calls)],
)
def resolve_clarification_question(
    requirement_id: str,
    question_id: str,
    request: ResolveClarificationQuestionRequest,
    actor: CurrentActorDep,
    commands: RequirementCommandsDep,
    use_case: Annotated[AnalysisCollaboration, Depends(get_analysis_collaboration)],
) -> RequirementAnalysisResponse:
    resolved = RequirementId(requirement_id)
    return workspace_response(
        commands.run(
            resolved,
            actor,
            lambda: use_case.resolve(
                resolved,
                QuestionId(question_id),
                request.answer,
                request.expected_version,
                actor,
                source_suggestion_id=request.source_suggestion_id,
            ),
        )
    )
