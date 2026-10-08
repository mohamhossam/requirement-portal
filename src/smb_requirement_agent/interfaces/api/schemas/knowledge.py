"""HTTP schemas for requirement knowledge and grounded suggestions."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from smb_requirement_agent.interfaces.api.schemas.bounds import (
    Text,
)
from smb_requirement_agent.interfaces.api.schemas.epic import ProvenanceResponse
from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse
from smb_requirement_agent.knowledge.application.ports.requirement_knowledge import (
    KnowledgeScreenEnsureOutcome,
)
from smb_requirement_agent.knowledge.domain.entities import (
    AnswerSuggestionSource,
    KnowledgeFindingStatus,
    KnowledgeRelationshipKind,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference


class KnowledgeEvidenceResponse(BaseModel):
    chunk_id: str
    requirement_id: str
    field: str
    excerpt: str
    evidence_path: str
    fingerprint: str


class KnowledgeDecisionResponse(BaseModel):
    kind: str
    actor: ActorResponse
    recorded_at: datetime
    rationale: str | None


class KnowledgeFindingResponse(BaseModel):
    id: str
    kind: KnowledgeRelationshipKind
    status: KnowledgeFindingStatus
    version: int
    subject_requirement_id: str
    related_requirement_id: str
    rationale: str
    evidence: list[KnowledgeEvidenceResponse]
    resolution_statement: str | None
    resolution_approvals: list[str]
    decisions: list[KnowledgeDecisionResponse]


class CorpusRetirementResponse(BaseModel):
    """Retired from the knowledge corpus by a knowledge admin: when, by whom and why."""

    retired_at: datetime
    retired_by: str
    reason: str


class KnowledgeReviewResponse(BaseModel):
    reference_conflict_ids: tuple[str, ...] = ()
    corpus_retirement: CorpusRetirementResponse | None = None
    status: Literal["required", "stale", "action_required", "ready"]
    current: bool
    ready: bool
    input_fingerprint: str
    screen_id: str | None
    provenance: ProvenanceResponse | None
    findings: list[KnowledgeFindingResponse]


class KnowledgeScreenEnsureResponse(BaseModel):
    outcome: KnowledgeScreenEnsureOutcome
    job_id: str | None


class KnowledgeFindingDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["distinct", "duplicate", "propose_resolution", "accept_resolution"]
    expected_version: int = Field(ge=1)
    text: Text | None = None

    @model_validator(mode="after")
    def require_text(self) -> KnowledgeFindingDecisionRequest:
        if self.decision in {"distinct", "propose_resolution"} and not (
            self.text and self.text.strip()
        ):
            raise ValueError("This knowledge decision requires non-blank text.")
        return self


class AnswerSuggestionResponse(BaseModel):
    reference_evidence: tuple[PublishedReference, ...] = ()
    id: str
    source: AnswerSuggestionSource
    answer: str
    rationale: str
    evidence: list[KnowledgeEvidenceResponse]


class AnswerSuggestionSetResponse(BaseModel):
    # Cited library documents past their review date, by id (Knowledge Center D).
    overdue_reference_reviews: dict[str, date] = {}
    id: str
    question_id: str
    suggestions: list[AnswerSuggestionResponse]
    provenance: ProvenanceResponse


# --- Prior art from historic requirements (Knowledge Center E2, ADR-0102) --------------------


class PriorArtLineageItem(BaseModel):
    id: int
    type: Literal["epic", "feature", "user_story"]
    title: str
    state: str
    # A link to the work item in Azure DevOps, when it is a web address.
    url: str | None


class PriorArtPassageResponse(BaseModel):
    source_kind: Literal["historic_brd", "historic_backlog"]
    excerpt: str
    # A BRD passage says which BRD and where; a work item says its lineage, Epic first.
    brd_filename: str | None = None
    label: str | None = None
    section_path: list[str] = []
    lineage: list[PriorArtLineageItem] = []


class PriorArtMatchResponse(BaseModel):
    historic_requirement_id: str
    title: str
    publication: int
    verdict: Literal["similar_past_requirement"]
    rationale: str
    passages: list[PriorArtPassageResponse]


class PriorArtResponse(BaseModel):
    """Similar past requirements: reference only, never a finding or a blocker."""

    status: Literal[
        "disabled",
        "no_historic_knowledge",
        "not_checked",
        "checking",
        "waiting",
        "current",
        "out_of_date",
        "failed",
    ]
    # Changes when the Requirement or the historic corpus does: ask for a check when it does.
    input_key: str
    label: Literal["historic"] = "historic"
    trust: Literal["reference"] = "reference"
    checked_at: datetime | None = None
    provenance: ProvenanceResponse | None = None
    matches: list[PriorArtMatchResponse] = []
