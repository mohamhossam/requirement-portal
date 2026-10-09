"""Requirement analyzer port."""

from collections.abc import Sequence
from datetime import datetime
from typing import NotRequired, Protocol, TypedDict

from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSource,
    HumanClarification,
    IntentProposal,
    IntentProposalKind,
    QuestionChangeAction,
    ReferenceGroundingStatus,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.generation import Provenance


class AnalysisDocumentContext(TypedDict):
    document_id: str
    version_id: str
    filename: str
    checksum_sha256: str
    extracted_text: str
    extraction_version: NotRequired[str]
    evidence_blocks: NotRequired[list["AnalysisEvidenceBlock"]]
    image_assets: NotRequired[list["AnalysisImageAsset"]]


class AnalysisEvidenceBlock(TypedDict):
    block_id: str
    kind: str
    section_path: list[str]
    label: str
    text: str | None
    asset_id: str | None


class AnalysisImageAsset(TypedDict):
    asset_id: str
    block_id: str
    mime_type: str
    content: bytes


class AnalysisEvidenceReferenceCandidate(TypedDict):
    document_id: str
    version_id: str
    checksum_sha256: str
    block_id: str
    label: str


class AnalysisStageProvenanceCandidate(TypedDict):
    stage: str
    model: str
    prompt_version: str
    generated_at: datetime
    input_fingerprint: str


class OpenQuestionCandidate(TypedDict):
    question: str
    rationale: str


class AmbiguityCandidate(TypedDict):
    statement: str
    reason: str


class ActiveQuestionContext(TypedDict):
    question_id: str
    kind: ClarificationKind
    subject: str
    rationale: str | None
    source: ClarificationSource


class UncertaintyCandidate(TypedDict):
    kind: ClarificationKind
    subject: str
    rationale: str | None


class QuestionReviewCandidate(TypedDict):
    question_id: str
    action: QuestionChangeAction
    rationale: str
    replacement: UncertaintyCandidate | None


class IntentProposalCandidate(TypedDict):
    kind: IntentProposalKind
    statement: str
    rationale: str
    success_measures: list[str]
    reference_evidence: NotRequired[tuple[PublishedReference, ...]]
    reference_conflict: NotRequired[bool]
    reference_provenance: NotRequired[Provenance]


class RequirementAnalysisCandidate(TypedDict):
    """A provider-independent structured representation of an analysis result."""

    known_facts: list[str]
    constraints: list[str]
    business_rules: list[str]
    assumptions: list[str]
    open_questions: list[OpenQuestionCandidate]
    ambiguities: list[AmbiguityCandidate]
    potential_dependencies: list[str]
    intent_proposals: list[IntentProposalCandidate]
    model: str
    prompt_version: str
    question_reviews: NotRequired[list[QuestionReviewCandidate]]
    new_uncertainties: NotRequired[list[UncertaintyCandidate]]
    evidence_references: NotRequired[dict[str, list[AnalysisEvidenceReferenceCandidate]]]
    clarification_references: NotRequired[dict[str, list[int]]]
    stage_provenance: NotRequired[list[AnalysisStageProvenanceCandidate]]
    reference_grounding: NotRequired[ReferenceGroundingStatus]


class RequirementAnalyzerPort(Protocol):
    """Outbound port for generating a requirement analysis using an AI model."""

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        """Analyze a requirement and return a structured candidate.

        Raises RequirementAnalysisGenerationError on failure.
        """
        ...
