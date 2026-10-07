"""Provider-neutral boundaries for requirement-derived knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from smb_kernel.embeddings import Embedding as Embedding

from smb_requirement_agent.application.ports.embedding import (
    KnowledgeEmbeddingPort as KnowledgeEmbeddingPort,
)
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.domain.analysis.entities import ClarificationQuestion
from smb_requirement_agent.domain.analysis.value_objects import QuestionId
from smb_requirement_agent.domain.knowledge.entities import (
    AnswerSuggestion,
    AnswerSuggestionSet,
    KnowledgeChunk,
    KnowledgeFinding,
    KnowledgeFindingId,
    KnowledgeMatch,
    KnowledgeRelationshipKind,
    KnowledgeScreen,
)
from smb_requirement_agent.domain.knowledge.membership import CorpusMembership
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.jobs.domain.entities import AiJobId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class KnowledgeReview:
    screen: KnowledgeScreen | None
    findings: tuple[KnowledgeFinding, ...]
    current_fingerprint: str
    linked_versions_current: bool = True
    reference_conflict_ids: tuple[str, ...] = ()
    # Retired from the corpus by a knowledge admin (B3): not screened, so nothing waits on it.
    retirement: CorpusMembership | None = None

    @property
    def current(self) -> bool:
        if self.retirement is not None:
            return True
        return (
            self.screen is not None
            and self.screen.input_fingerprint == self.current_fingerprint
            and self.linked_versions_current
        )

    @property
    def ready(self) -> bool:
        return (
            self.current
            and not self.reference_conflict_ids
            and not any(item.actionable for item in self.findings)
        )


class KnowledgeScreenEnsureOutcome(StrEnum):
    CURRENT = "current"
    SCHEDULED = "scheduled"
    ALREADY_SCHEDULED = "already_scheduled"
    MANUAL_RETRY_REQUIRED = "manual_retry_required"


@dataclass(frozen=True)
class KnowledgeScreenEnsureResult:
    outcome: KnowledgeScreenEnsureOutcome
    job_id: AiJobId | None = None


@dataclass(frozen=True)
class RelationshipCandidate:
    related_requirement_id: RequirementId
    kind: KnowledgeRelationshipKind
    rationale: str
    cited_chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnswerSuggestionCandidate:
    answer: str
    rationale: str
    cited_chunk_ids: tuple[str, ...]


class RequirementKnowledgeIndexPort(Protocol):
    def pending_sources(
        self, limit: int, after: str = ""
    ) -> tuple[tuple[RequirementId, int], ...]: ...

    def replace_if_current(
        self,
        requirement_id: RequirementId,
        expected_change: int,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> bool: ...

    def indexed_fingerprint(self, requirement_id: RequirementId) -> str | None: ...

    def replace(
        self,
        requirement_id: RequirementId,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> None: ...

    def search(
        self,
        query_text: str,
        query_embedding: Embedding,
        exclude_requirement_id: RequirementId | None,
        limit: int,
    ) -> tuple[KnowledgeMatch, ...]: ...

    def get_chunks(self, chunk_ids: tuple[str, ...]) -> tuple[KnowledgeChunk, ...]: ...


class RequirementRelationshipClassifierPort(Protocol):
    model: str
    prompt_version: str

    def classify(
        self,
        requirement: Requirement,
        subject_text: str,
        matches: tuple[KnowledgeMatch, ...],
    ) -> tuple[RelationshipCandidate, ...]: ...


class ClarificationAnswerSuggesterPort(Protocol):
    model: str
    prompt_version: str

    def suggest(
        self,
        requirement: Requirement,
        question: ClarificationQuestion,
        current_analysis: tuple[KnowledgeChunk, ...],
        matches: tuple[KnowledgeMatch, ...],
        references: tuple[ReferenceEvidence, ...] = (),
    ) -> tuple[AnswerSuggestionCandidate, ...]: ...


class RequirementKnowledgeRepositoryPort(Protocol):
    def append_screen(
        self, screen: KnowledgeScreen, findings: tuple[KnowledgeFinding, ...]
    ) -> None: ...

    def current_screen(self, requirement_id: RequirementId) -> KnowledgeScreen | None: ...

    def get_finding(self, finding_id: KnowledgeFindingId) -> KnowledgeFinding | None: ...

    def list_findings(self, screen_id: str) -> tuple[KnowledgeFinding, ...]: ...

    def save_finding(self, finding: KnowledgeFinding, expected_version: int) -> None: ...

    def list_related_findings(
        self, requirement_id: RequirementId
    ) -> tuple[KnowledgeFinding, ...]: ...

    def append_suggestion_set(self, suggestions: AnswerSuggestionSet) -> None: ...

    def latest_suggestion_set(
        self, requirement_id: RequirementId, question_id: str
    ) -> AnswerSuggestionSet | None: ...


class KnowledgeScreenSchedulerPort(Protocol):
    def schedule(self, requirement_id: RequirementId) -> None: ...

    def ensure(self, requirement_id: RequirementId) -> KnowledgeScreenEnsureResult: ...


class AnswerSuggestionSchedulerPort(Protocol):
    def schedule(
        self,
        requirement_id: RequirementId,
        questions: tuple[ClarificationQuestion, ...],
    ) -> None: ...


class KnowledgeReviewPort(Protocol):
    def execute(self, requirement_id: RequirementId) -> KnowledgeReview: ...

    def require_ready(self, requirement_id: RequirementId) -> None: ...


class AnswerSuggestionValidatorPort(Protocol):
    def require_suggestion(
        self, requirement_id: RequirementId, question_id: QuestionId, suggestion_id: str
    ) -> AnswerSuggestion: ...
