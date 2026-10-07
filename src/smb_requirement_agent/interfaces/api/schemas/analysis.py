"""Analysis API schemas."""

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from smb_requirement_agent.domain.analysis.value_objects import (
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    ClarificationStatus,
    IntentProposalKind,
    IntentProposalStatus,
    QuestionChangeAction,
)
from smb_requirement_agent.domain.shared.citation import PublishedReference
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_IDENTIFIER_CHARACTERS,
    MAX_ITEMS,
    MAX_TEXT_CHARACTERS,
    Identifier,
    Text,
)
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse
from smb_requirement_agent.interfaces.api.schemas.generation import ActionAvailabilityResponse
from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_CHARACTERS),
]
NonBlankIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS),
]


class AnalysisEvidenceReferenceResponse(BaseModel):
    document_id: str
    version_id: str
    checksum_sha256: str
    block_id: str
    label: str
    model_config = ConfigDict(frozen=True)


class KnownFactResponse(BaseModel):
    statement: str
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class ConstraintResponse(BaseModel):
    statement: str
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class BusinessRuleResponse(BaseModel):
    statement: str
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class AssumptionResponse(BaseModel):
    statement: str
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class OpenQuestionResponse(BaseModel):
    question: str
    rationale: str
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class AmbiguityResponse(BaseModel):
    statement: str
    reason: str
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class PotentialDependencyResponse(BaseModel):
    statement: str
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class HumanClarificationResponse(BaseModel):
    kind: ClarificationKind
    subject: str
    answer: str
    question_id: str | None = None
    answered_by: ActorResponse | None = None
    answered_at: datetime | None = None
    source_suggestion_id: str | None = None
    model_config = ConfigDict(frozen=True)


class AnalysisDocumentReferenceResponse(BaseModel):
    document_id: str
    version_id: str
    filename: str
    checksum_sha256: str
    model_config = ConfigDict(frozen=True)


class IntentProposalDecisionResponse(BaseModel):
    rationale: str | None = None
    status: IntentProposalStatus
    final_statement: str | None
    success_measures: list[str]
    decided_by: ActorResponse
    decided_at: datetime
    version: int
    model_config = ConfigDict(frozen=True)


class IntentProposalResponse(BaseModel):
    reference_evidence: list[PublishedReference] = []
    reference_conflict: bool = False
    reference_provenance: ProvenanceResponse | None = None
    id: str
    kind: IntentProposalKind
    statement: str
    rationale: str
    success_measures: list[str]
    status: IntentProposalStatus
    version: int
    effective_statement: str | None
    effective_success_measures: list[str]
    decisions: list[IntentProposalDecisionResponse]
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class ConfirmedIntentItemResponse(BaseModel):
    statement: str
    origin: str
    proposal_id: str | None = None
    model_config = ConfigDict(frozen=True)


class BusinessIntentResponse(BaseModel):
    desired_outcome: ConfirmedIntentItemResponse | None
    accepted_business_rules: list[ConfirmedIntentItemResponse]
    accepted_constraints: list[ConfirmedIntentItemResponse]
    proposals: list[IntentProposalResponse]
    model_config = ConfigDict(frozen=True)


class DecideIntentProposalRequest(BaseModel):
    rationale: Annotated[NonBlankText | None, Field(max_length=2000)] = None
    decision: IntentProposalStatus
    replacement_statement: NonBlankText | None = None
    success_measures: Annotated[list[NonBlankText], Field(max_length=MAX_ITEMS)] | None = None
    expected_version: Annotated[int, Field(ge=1)]
    model_config = ConfigDict(frozen=True)


class ClarificationAnswerRequest(BaseModel):
    kind: ClarificationKind
    subject: NonBlankText
    answer: NonBlankText
    model_config = ConfigDict(frozen=True)


class ClarifyAnalysisRequest(BaseModel):
    answers: Annotated[list[ClarificationAnswerRequest], Field(min_length=1, max_length=MAX_ITEMS)]
    expected_analysis_version: Annotated[int, Field(ge=1)]
    model_config = ConfigDict(frozen=True)


class ConfirmAnalysisRequest(BaseModel):
    expected_version: Annotated[int, Field(ge=1)]
    model_config = ConfigDict(frozen=True)


class AnalysisActionsResponse(BaseModel):
    generate_epic: ActionAvailabilityResponse

    model_config = ConfigDict(frozen=True)


class RequirementAnalysisResponse(BaseModel):
    stale_reference_proposal_ids: list[str] = []
    # Cited library documents past their review date, by id (Knowledge Center D).
    overdue_reference_reviews: dict[str, date] = {}
    clarification_evidence: list["AnalysisClarificationEvidenceResponse"] = []
    requirement_id: str
    version: int
    known_facts: list[KnownFactResponse]
    constraints: list[ConstraintResponse]
    business_rules: list[BusinessRuleResponse]
    assumptions: list[AssumptionResponse]
    open_questions: list[OpenQuestionResponse]
    ambiguities: list[AmbiguityResponse]
    potential_dependencies: list[PotentialDependencyResponse]
    clarifications: list[HumanClarificationResponse]
    human_confirmed: bool
    confirmed_at: datetime | None
    actions: AnalysisActionsResponse
    confirmed_by: ActorResponse | None
    document_references: list[AnalysisDocumentReferenceResponse]
    analysis_id: str | None
    round_number: int | None
    provenance: ProvenanceResponse | None
    source_requirement_version: int | None
    questions: list["ClarificationQuestionResponse"]
    question_changes: list["AnalysisQuestionChangeResponse"]
    business_intent: BusinessIntentResponse
    stage_provenance: list["AnalysisStageProvenanceResponse"] = []
    analysis_context_token: str | None = None
    epic_context_token: str | None = None

    model_config = ConfigDict(frozen=True)


class AnalysisClarificationEvidenceResponse(BaseModel):
    evidence_key: str
    clarification_numbers: list[int]
    model_config = ConfigDict(frozen=True)


class AnalysisStageProvenanceResponse(BaseModel):
    stage: str
    model: str
    prompt_version: str
    generated_at: datetime
    input_fingerprint: str
    model_config = ConfigDict(frozen=True)


class QuestionAssignmentChangeResponse(BaseModel):
    assignee: ActorResponse | None
    changed_by: ActorResponse
    changed_at: datetime
    model_config = ConfigDict(frozen=True)


class ClarificationQuestionResponse(BaseModel):
    id: str
    analysis_id: str
    kind: ClarificationKind
    subject: str
    rationale: str | None
    severity: ClarificationSeverity
    is_blocker: bool
    source: ClarificationSource
    status: ClarificationStatus
    version: int
    asked_by: ActorResponse | None
    asked_at: datetime | None
    assignee: ActorResponse | None
    assignment_history: list[QuestionAssignmentChangeResponse]
    draft_answer: str | None
    draft_updated_by: ActorResponse | None
    draft_updated_at: datetime | None
    answer: str | None
    answered_by: ActorResponse | None
    answered_at: datetime | None
    classification_changed_by: ActorResponse | None
    classification_changed_at: datetime | None
    replaces_question_id: str | None
    model_config = ConfigDict(frozen=True)


class AnalysisQuestionChangeResponse(BaseModel):
    action: QuestionChangeAction
    question_id: str
    rationale: str
    replacement_question_id: str | None
    model_config = ConfigDict(frozen=True)


class AnalysisRoundResponse(BaseModel):
    analysis: RequirementAnalysisResponse
    questions: list[ClarificationQuestionResponse]
    model_config = ConfigDict(frozen=True)


class AskClarificationQuestionRequest(BaseModel):
    subject: NonBlankText
    rationale: Text | None = None
    assignee_id: Identifier | None = None
    severity: ClarificationSeverity = ClarificationSeverity.MEDIUM
    is_blocker: bool = False
    expected_analysis_version: Annotated[int, Field(ge=1)]
    model_config = ConfigDict(frozen=True)


class ClassifyClarificationQuestionRequest(BaseModel):
    severity: ClarificationSeverity
    is_blocker: bool
    expected_version: Annotated[int, Field(ge=1)]
    model_config = ConfigDict(frozen=True)


class AssignClarificationQuestionRequest(BaseModel):
    assignee_id: Identifier | None
    expected_version: Annotated[int, Field(ge=1)]
    model_config = ConfigDict(frozen=True)


class SaveClarificationDraftRequest(BaseModel):
    answer: Text
    expected_version: Annotated[int, Field(ge=1)]
    model_config = ConfigDict(frozen=True)


class ResolveClarificationQuestionRequest(BaseModel):
    answer: NonBlankText | None = None
    expected_version: Annotated[int, Field(ge=1)]
    source_suggestion_id: NonBlankIdentifier | None = None
    model_config = ConfigDict(frozen=True)


class ClarificationResolutionRequest(BaseModel):
    question_id: NonBlankIdentifier
    answer: NonBlankText
    expected_version: Annotated[int, Field(ge=1)]
    source_suggestion_id: NonBlankIdentifier | None = None
    model_config = ConfigDict(frozen=True)


def _unique_question_resolutions(
    answers: list[ClarificationResolutionRequest],
) -> list[ClarificationResolutionRequest]:
    ids = [item.question_id for item in answers]
    if len(ids) != len(set(ids)):
        raise ValueError("Each clarification question can be answered only once per request.")
    return answers


ClarificationResolutionBatch = Annotated[
    list[ClarificationResolutionRequest],
    Field(min_length=1, max_length=MAX_ITEMS),
    AfterValidator(_unique_question_resolutions),
]


class ResolveClarificationQuestionsRequest(BaseModel):
    answers: ClarificationResolutionBatch
    model_config = ConfigDict(frozen=True)


RequirementAnalysisResponse.model_rebuild()
