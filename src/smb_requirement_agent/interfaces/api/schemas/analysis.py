"""Analysis API schemas."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from smb_requirement_agent.analysis.domain.product_impact import (
    ProductImpactDecision,
    ProductImpactStatus,
    ProductVerdict,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    ClarificationStatus,
    IntentProposalKind,
    IntentProposalStatus,
    QuestionChangeAction,
)
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
from smb_requirement_agent.shared_kernel.citation import PublishedReference

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


class NonFunctionalRequirementResponse(BaseModel):
    statement: str
    kind: str
    evidence_references: list[AnalysisEvidenceReferenceResponse] = []
    model_config = ConfigDict(frozen=True)


class BusinessUseCaseResponse(BaseModel):
    name: str
    actor: str
    trigger: str | None
    goal: str
    main_steps: list[str]
    alternate_paths: list[str]
    business_rules: list[str]
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


class DecideProductImpactRequest(BaseModel):
    """Accept the suggested verdict, override it with another, or mark it unknown."""

    decision: ProductImpactDecision
    # Required to override; ignored otherwise.
    verdict: ProductVerdict | None = None
    # Required to override: why the suggested verdict is wrong.
    rationale: Annotated[NonBlankText | None, Field(max_length=2000)] = None
    expected_version: Annotated[int, Field(ge=1)]
    model_config = ConfigDict(frozen=True)


class ImpactPathStepResponse(BaseModel):
    # Text, not a closed list: the knowledge portal may add kinds (an interface, an entity).
    kind: str
    id: str
    label: str
    model_config = ConfigDict(frozen=True)


class CapabilityNeedResponse(BaseModel):
    concept_id: str
    label: str
    path: str
    covered: bool
    weak: bool
    model_config = ConfigDict(frozen=True)


class ImpactGapResponse(BaseModel):
    kind: str
    concept_id: str
    label: str
    reason: str
    system_id: str | None
    model_config = ConfigDict(frozen=True)


class ImpactSystemResponse(BaseModel):
    id: str
    name: str
    role: str
    change_type: str
    paths: list[list[ImpactPathStepResponse]]
    model_config = ConfigDict(frozen=True)


class ImpactOwnerResponse(BaseModel):
    concept_id: str
    system_id: str
    squads: list[str]
    people: list[str]
    open_seats: int
    model_config = ConfigDict(frozen=True)


class ImpactQuestionResponse(BaseModel):
    facet: str
    question: str
    options: list[str]
    model_config = ConfigDict(frozen=True)


class DraftComponentResponse(BaseModel):
    name: str
    system_ids: list[str]
    model_config = ConfigDict(frozen=True)


class OfferingDraftResponse(BaseModel):
    """The offering and journey drafted for a new-offering verdict (ontology plan Phase 9)."""

    offering_id: str
    offering_name: str
    # The offering it was drafted from, if any.
    based_on: str | None
    components: list[DraftComponentResponse]
    # What it leaves for architecture review.
    questions: list[str]
    journey_name: str | None
    journey_steps: int
    model_config = ConfigDict(frozen=True)


class ProductImpactResponse(BaseModel):
    """Where the knowledge portal places the requirement, and the decision on it (ADR-0115)."""

    release_id: str
    suggested_verdict: ProductVerdict | None
    # False until the live models meet the verdict gate: show the verdict as a suggestion.
    verdict_validated: bool
    reason: str
    assessed_at: datetime
    offering_id: str | None
    offering_name: str | None
    proposal: str | None
    new_values: list[str]
    draft: OfferingDraftResponse | None
    needs: list[CapabilityNeedResponse]
    gaps: list[ImpactGapResponse]
    systems: list[ImpactSystemResponse]
    owners: list[ImpactOwnerResponse]
    questions: list[ImpactQuestionResponse]
    uncertainty: str | None
    model: str | None
    prompt_version: str | None
    decision: ProductImpactDecision | None
    verdict: ProductVerdict | None
    rationale: str | None
    decided_by: ActorResponse | None
    decided_at: datetime | None
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
    # Settled categories a standard BRD carries (ADR-0120); empty for older analyses.
    non_functional_requirements: list[NonFunctionalRequirementResponse] = []
    business_use_cases: list[BusinessUseCaseResponse] = []
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
    # What checking the published reference library found when this analysis was generated;
    # null for analyses from before it was recorded and for re-analysis rounds.
    reference_grounding: (
        Literal["grounded", "no_evidence", "not_connected", "unavailable"] | None
    ) = None
    # Whether this round could ask the knowledge portal for a product impact, and what it
    # placed the requirement as; null for analyses from before it was recorded.
    product_impact_status: ProductImpactStatus | None = None
    product_impact: ProductImpactResponse | None = None
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
    # Answers to pick from, for a question the catalogue asks; any answer is allowed.
    options: list[str] = []
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


RequirementAnalysisResponse.model_rebuild()
