"""LLM schema definitions for requirement analysis."""

from types import GenericAlias
from typing import Annotated, Literal

from pydantic import BaseModel, Field, create_model

from smb_requirement_agent.domain.analysis.value_objects import ClarificationKind


class OpenQuestionSchema(BaseModel):
    question: str = Field(description="The open question identified.")
    rationale: str = Field(description="The reason why this question is important to resolve.")


class AmbiguitySchema(BaseModel):
    statement: str = Field(description="The ambiguous statement from the requirement.")
    reason: str = Field(description="Why the statement is ambiguous.")


class UncertaintySchema(BaseModel):
    kind: ClarificationKind
    subject: str = Field(description="The concise uncertainty or question shown to reviewers.")
    rationale: str | None = Field(
        default=None,
        description="Why clarification is needed; required for questions and ambiguities.",
    )


class ActiveQuestionReviewSchema(BaseModel):
    question_id: str = Field(description="Stable ID supplied with the active AI question.")
    action: Literal["retain", "retire", "replace"]
    rationale: str = Field(description="Why this lifecycle decision follows from current context.")
    replacement: UncertaintySchema | None = Field(
        default=None,
        description="Required only when action is replace.",
    )


class IndexedActiveQuestionReviewSchema(BaseModel):
    """Provider-local review reference mapped back to an application-owned stable ID."""

    question_number: int = Field(
        ge=1,
        description="One-based question number from the supplied recovery list.",
    )
    action: Literal["retain", "retire", "replace"]
    rationale: str = Field(description="Why this lifecycle decision follows from current context.")
    replacement: UncertaintySchema | None = Field(
        default=None,
        description="Required only when action is replace.",
    )


class IndexedQuestionReconciliationSchema(BaseModel):
    """Focused local recovery shape that avoids asking small models to copy UUIDs."""

    active_question_reviews: list[IndexedActiveQuestionReviewSchema] = Field(
        min_length=1,
        description="Exactly one lifecycle review for every supplied active AI question.",
    )
    new_uncertainties: list[UncertaintySchema] = Field(
        default_factory=list,
        max_length=12,
        description="Only genuinely new uncertainties after reviewing every active question.",
    )


class IndexedUncertaintyRationaleSchema(BaseModel):
    """Provider-local rationale mapped back to one frozen uncertainty."""

    uncertainty_number: int = Field(ge=1)
    rationale: str = Field(min_length=1)


class IndexedUncertaintyRationaleRecoverySchema(BaseModel):
    """Focused result for every uncertainty whose rationale was unusable."""

    rationales: list[IndexedUncertaintyRationaleSchema] = Field(min_length=1, max_length=12)


class DesiredOutcomeProposalSchema(BaseModel):
    statement: str = Field(
        description="One observable business or customer result, not a technical solution."
    )
    rationale: str = Field(description="How the stated business need supports this candidate.")
    success_measures: list[str] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Observable success signals. Never invent numeric targets that are absent "
            "from the supplied source."
        ),
    )


class IntentStatementProposalSchema(BaseModel):
    statement: str = Field(description="A candidate rule or boundary requiring human approval.")
    rationale: str = Field(description="Why this candidate may be needed for the stated need.")


type AnalysisEvidenceKind = Literal[
    "known_fact",
    "constraint",
    "business_rule",
    "assumption",
    "open_question",
    "ambiguity",
    "potential_dependency",
    "intent_proposal",
]


class AnalysisEvidenceCitationSchema(BaseModel):
    kind: AnalysisEvidenceKind
    subject: str = Field(description="Exact output statement or question being supported.")
    block_ids: list[str] = Field(
        default_factory=list,
        description="Evidence block IDs supplied in this request; never invent IDs.",
    )
    clarification_numbers: list[int] = Field(
        default_factory=list,
        description="One-based supplied human answer numbers supporting this output.",
    )


class IndexedAnalysisEvidenceDecisionSchema(BaseModel):
    """One support decision mapped back to application-owned values."""

    output_number: int = Field(ge=1)
    supported: bool
    clarification_numbers: list[int] = Field(default_factory=list)
    block_numbers: list[int] = Field(
        default_factory=list,
        description=(
            "Unique supplied evidence block numbers supporting the complete statement. "
            "Include every necessary block; never repeat or invent a number."
        ),
    )


class IndexedAnalysisEvidenceRecoverySchema(BaseModel):
    """Focused result that accounts for every frozen analysis output."""

    decisions: list[IndexedAnalysisEvidenceDecisionSchema] = Field(
        min_length=1,
    )


def citation_recovery_schema(
    output_count: int, block_count: int, clarification_count: int = 0
) -> type[IndexedAnalysisEvidenceRecoverySchema]:
    """Constrain both independent number spaces to this packet, without global state."""
    if output_count < 1 or block_count < 1:
        raise ValueError("Citation recovery requires nonempty outputs and evidence.")
    decision = create_model(
        "PacketAnalysisEvidenceDecision",
        __base__=IndexedAnalysisEvidenceDecisionSchema,
        output_number=(int, Field(ge=1, le=output_count)),
        block_numbers=(
            list[Annotated[int, Field(ge=1, le=block_count)]],
            Field(default_factory=list, max_length=block_count),
        ),
        clarification_numbers=(
            list[Annotated[int, Field(ge=1, le=max(1, clarification_count))]],
            Field(default_factory=list, max_length=clarification_count),
        ),
    )
    return create_model(
        "PacketAnalysisEvidenceRecovery",
        __base__=IndexedAnalysisEvidenceRecoverySchema,
        decisions=(
            GenericAlias(list, decision),
            Field(min_length=output_count, max_length=output_count),
        ),
    )


class RequirementAnalysisSchema(BaseModel):
    """Structured output schema for LLM requirement analysis."""

    known_facts: list[str] = Field(
        description=(
            "Information directly and explicitly supported by the submitted business requirement."
        ),
        min_length=1,
    )
    constraints: list[str] = Field(
        description="Explicit restrictions or boundaries defined in the requirement.",
        default_factory=list,
    )
    business_rules: list[str] = Field(
        description="Explicit behavioral rules contained in the requirement.",
        default_factory=list,
    )
    active_question_reviews: list[ActiveQuestionReviewSchema] = Field(
        default_factory=list,
        description="Exactly one lifecycle review for every supplied active AI question.",
    )
    new_uncertainties: list[UncertaintySchema] = Field(
        default_factory=list,
        max_length=12,
        description="Only genuinely new uncertainties, excluding retained and replacement items.",
    )
    desired_outcome_proposal: DesiredOutcomeProposalSchema | None = Field(
        default=None,
        description=(
            "One proposed desired outcome only when no source-authored desired outcome exists "
            "and the business need supports a responsible candidate."
        ),
    )
    business_rule_proposals: list[IntentStatementProposalSchema] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Useful candidate rules not stated as source facts. These remain AI proposals."
        ),
    )
    constraint_proposals: list[IntentStatementProposalSchema] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Useful candidate boundaries not stated as source facts. These remain AI proposals."
        ),
    )
    evidence_citations: list[AnalysisEvidenceCitationSchema] = Field(
        default_factory=list,
        description=(
            "Citation records for every generated item when evidence blocks are supplied."
        ),
    )


class DesiredOutcomeReviewSchema(BaseModel):
    """Focused result when the broad analysis omitted an outcome decision."""

    can_infer: bool = Field(
        description="True only when the business need supports an observable outcome."
    )
    statement: str = Field(
        description="The proposed outcome when can_infer is true; otherwise an empty string."
    )
    rationale: str = Field(description="Evidence-based proposal rationale when can_infer is true.")
    success_measures: list[str] = Field(default_factory=list, max_length=8)
    blocker_question: str = Field(
        description="The outcome question when can_infer is false; otherwise an empty string."
    )
    blocker_rationale: str = Field(
        description="Why owner input is required when can_infer is false."
    )


class ClarificationReviewSchema(BaseModel):
    """Focused fallback output when vague input produced no uncertainty."""

    open_questions: list[OpenQuestionSchema] = Field(
        min_length=1,
        max_length=12,
        description=(
            "One to twelve non-overlapping questions required to define vague criteria "
            "before implementation or acceptance testing."
        ),
    )
