"""Requirement knowledge, semantic findings, and grounded answer suggestions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.analysis.domain.value_objects import QuestionId
from smb_requirement_agent.domain.knowledge.errors import (
    InvalidKnowledgeError,
    KnowledgeFindingConflictError,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage
from smb_requirement_agent.shared_kernel.staleness import require_aware


def _text(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise InvalidKnowledgeError(f"Knowledge {field} must not be blank.")
    return cleaned


@dataclass(frozen=True, order=True)
class KnowledgeChunkId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "chunk id"))


@dataclass(frozen=True, order=True)
class KnowledgeScreenId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "screen id"))


@dataclass(frozen=True, order=True)
class KnowledgeFindingId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "finding id"))


@dataclass(frozen=True, order=True)
class AnswerSuggestionSetId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "suggestion-set id"))


@dataclass(frozen=True, order=True)
class AnswerSuggestionId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "suggestion id"))


class KnowledgeSourceKind(StrEnum):
    SOURCE = "source"
    CLARIFICATION = "clarification"
    INTENT_DECISION = "intent_decision"
    CURRENT_ANALYSIS = "current_analysis"
    CONFIRMED_ANALYSIS = "confirmed_analysis"
    CONFLICT_RESOLUTION = "conflict_resolution"
    ATTACHMENT = "attachment"


class AnswerSuggestionSource(StrEnum):
    CURRENT_ANALYSIS = "current_analysis"
    TRUSTED_KNOWLEDGE = "trusted_knowledge"
    COMBINED = "combined"
    PUBLISHED_REFERENCE = "published_reference"


class KnowledgeRelationshipKind(StrEnum):
    POSSIBLE_DUPLICATE = "possible_duplicate"
    POSSIBLE_CONTRADICTION = "possible_contradiction"


class KnowledgeFindingStatus(StrEnum):
    OPEN = "open"
    DISTINCT = "distinct"
    DUPLICATE = "duplicate"
    RESOLUTION_PENDING = "resolution_pending"
    RESOLVED = "resolved"
    # Closed because a knowledge admin retired one of its Requirements from the corpus.
    SOURCE_RETIRED = "source_retired"


class KnowledgeDecisionKind(StrEnum):
    DISTINCT = "distinct"
    DUPLICATE = "duplicate"
    RESOLUTION_PROPOSED = "resolution_proposed"
    RESOLUTION_ACCEPTED = "resolution_accepted"
    SOURCE_RETIRED = "source_retired"


@dataclass(frozen=True)
class KnowledgeChunk:
    id: KnowledgeChunkId
    requirement_id: RequirementId
    requirement_version: int
    source_kind: KnowledgeSourceKind
    field: str
    text: str
    fingerprint: str
    evidence_path: str
    owner: ActorSnapshot | None = None
    source_lineage: tuple[SourceLineage, ...] = ()

    def __post_init__(self) -> None:
        if self.requirement_version < 1:
            raise InvalidKnowledgeError("Knowledge requirement version must be positive.")
        for field in ("field", "text", "fingerprint", "evidence_path"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if not self.evidence_path.startswith("/"):
            raise InvalidKnowledgeError("Knowledge evidence paths must be application-relative.")


@dataclass(frozen=True)
class KnowledgeMatch:
    chunk: KnowledgeChunk
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    fused_score: float = 0.0


@dataclass(frozen=True)
class RelationshipEvidence:
    chunk_id: KnowledgeChunkId
    requirement_id: RequirementId
    field: str
    excerpt: str
    evidence_path: str
    fingerprint: str
    source_lineage: tuple[SourceLineage, ...] = ()

    def __post_init__(self) -> None:
        for field in ("field", "excerpt", "evidence_path", "fingerprint"):
            object.__setattr__(self, field, _text(getattr(self, field), field))


@dataclass(frozen=True)
class KnowledgeDecision:
    kind: KnowledgeDecisionKind
    actor: ActorSnapshot
    recorded_at: datetime
    rationale: str | None = None

    def __post_init__(self) -> None:
        require_aware(self.recorded_at, "knowledge decision recorded_at")
        if self.rationale is not None:
            object.__setattr__(self, "rationale", _text(self.rationale, "decision rationale"))


@dataclass(frozen=True)
class KnowledgeFinding:
    id: KnowledgeFindingId
    screen_id: KnowledgeScreenId
    subject_requirement_id: RequirementId
    subject_version: int
    related_requirement_id: RequirementId
    related_version: int
    kind: KnowledgeRelationshipKind
    rationale: str
    evidence: tuple[RelationshipEvidence, ...]
    status: KnowledgeFindingStatus = KnowledgeFindingStatus.OPEN
    version: int = 1
    resolution_statement: str | None = None
    resolution_approvals: tuple[ActorId, ...] = ()
    decisions: tuple[KnowledgeDecision, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "rationale", _text(self.rationale, "finding rationale"))
        if self.subject_requirement_id == self.related_requirement_id:
            raise InvalidKnowledgeError("A requirement cannot conflict with itself.")
        if self.subject_version < 1 or self.related_version < 1 or self.version < 1:
            raise InvalidKnowledgeError("Knowledge finding versions must be positive.")
        if not self.evidence:
            raise InvalidKnowledgeError("Knowledge findings require cited evidence.")
        if self.resolution_statement is not None:
            object.__setattr__(
                self,
                "resolution_statement",
                _text(self.resolution_statement, "resolution statement"),
            )

    @property
    def actionable(self) -> bool:
        return self.status in {
            KnowledgeFindingStatus.OPEN,
            KnowledgeFindingStatus.RESOLUTION_PENDING,
        }

    def mark_distinct(
        self, actor: ActorProfile, rationale: str, at: datetime, expected_version: int
    ) -> KnowledgeFinding:
        self._require_version(expected_version)
        if self.kind is not KnowledgeRelationshipKind.POSSIBLE_DUPLICATE or not self.actionable:
            raise KnowledgeFindingConflictError(
                "Only an open possible duplicate can be marked distinct."
            )
        decision = KnowledgeDecision(
            KnowledgeDecisionKind.DISTINCT, actor.snapshot(), at, rationale
        )
        return replace(
            self,
            status=KnowledgeFindingStatus.DISTINCT,
            version=self.version + 1,
            decisions=(*self.decisions, decision),
        )

    def mark_duplicate(
        self, actor: ActorProfile, at: datetime, expected_version: int
    ) -> KnowledgeFinding:
        self._require_version(expected_version)
        if self.kind is not KnowledgeRelationshipKind.POSSIBLE_DUPLICATE or not self.actionable:
            raise KnowledgeFindingConflictError(
                "Only an open possible duplicate can close a Requirement as duplicate."
            )
        decision = KnowledgeDecision(KnowledgeDecisionKind.DUPLICATE, actor.snapshot(), at)
        return replace(
            self,
            status=KnowledgeFindingStatus.DUPLICATE,
            version=self.version + 1,
            decisions=(*self.decisions, decision),
        )

    def propose_resolution(
        self, actor: ActorProfile, statement: str, at: datetime, expected_version: int
    ) -> KnowledgeFinding:
        self._require_version(expected_version)
        if self.kind is not KnowledgeRelationshipKind.POSSIBLE_CONTRADICTION or not self.actionable:
            raise KnowledgeFindingConflictError(
                "Only an open possible contradiction accepts a shared resolution."
            )
        cleaned = _text(statement, "resolution statement")
        decision = KnowledgeDecision(
            KnowledgeDecisionKind.RESOLUTION_PROPOSED, actor.snapshot(), at, cleaned
        )
        return replace(
            self,
            status=KnowledgeFindingStatus.RESOLUTION_PENDING,
            resolution_statement=cleaned,
            resolution_approvals=(),
            version=self.version + 1,
            decisions=(*self.decisions, decision),
        )

    def accept_resolution(
        self,
        actor: ActorProfile,
        owner_ids: tuple[ActorId, ActorId],
        at: datetime,
        expected_version: int,
    ) -> KnowledgeFinding:
        self._require_version(expected_version)
        if (
            self.kind is not KnowledgeRelationshipKind.POSSIBLE_CONTRADICTION
            or self.status is not KnowledgeFindingStatus.RESOLUTION_PENDING
            or self.resolution_statement is None
        ):
            raise KnowledgeFindingConflictError("A resolution must be proposed before acceptance.")
        if actor.id not in owner_ids:
            raise KnowledgeFindingConflictError(
                "Only the current owners of both Requirements may accept the resolution."
            )
        current_approvals = tuple(
            approval for approval in self.resolution_approvals if approval in owner_ids
        )
        approvals = tuple(dict.fromkeys((*current_approvals, actor.id)))
        resolved = set(approvals) == set(owner_ids)
        decision = KnowledgeDecision(
            KnowledgeDecisionKind.RESOLUTION_ACCEPTED,
            actor.snapshot(),
            at,
            self.resolution_statement,
        )
        return replace(
            self,
            status=(KnowledgeFindingStatus.RESOLVED if resolved else self.status),
            resolution_approvals=approvals,
            version=self.version + 1,
            decisions=(*self.decisions, decision),
        )

    def close_source_retired(
        self, actor: ActorSnapshot, reason: str, at: datetime
    ) -> KnowledgeFinding:
        """Closed by a knowledge admin's retirement of either Requirement, with their reason.

        Reinstating the Requirement does not reopen it; a new screen raises a fresh finding.
        """
        if not self.actionable:
            raise KnowledgeFindingConflictError("Only an open finding can close as source retired.")
        decision = KnowledgeDecision(KnowledgeDecisionKind.SOURCE_RETIRED, actor, at, reason)
        return replace(
            self,
            status=KnowledgeFindingStatus.SOURCE_RETIRED,
            version=self.version + 1,
            decisions=(*self.decisions, decision),
        )

    def _require_version(self, expected_version: int) -> None:
        if self.version != expected_version:
            raise KnowledgeFindingConflictError(
                "The knowledge finding changed since it was loaded. Refresh and try again."
            )


@dataclass(frozen=True)
class KnowledgeScreen:
    id: KnowledgeScreenId
    requirement_id: RequirementId
    input_fingerprint: str
    subject_version: int
    finding_ids: tuple[KnowledgeFindingId, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "input_fingerprint", _text(self.input_fingerprint, "screen fingerprint")
        )
        if self.subject_version < 1:
            raise InvalidKnowledgeError("Knowledge screen subject version must be positive.")


@dataclass(frozen=True)
class AnswerSuggestion:
    id: AnswerSuggestionId
    answer: str
    rationale: str
    evidence: tuple[RelationshipEvidence, ...]
    reference_evidence: tuple[PublishedReference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer", _text(self.answer, "suggested answer"))
        object.__setattr__(self, "rationale", _text(self.rationale, "suggestion rationale"))
        if not self.evidence and not self.reference_evidence:
            raise InvalidKnowledgeError("An answer suggestion requires cited evidence.")

    def source_for(self, requirement_id: RequirementId) -> AnswerSuggestionSource:
        """Derive origin from validated citations rather than provider-supplied labels."""
        if self.reference_evidence:
            return (
                AnswerSuggestionSource.COMBINED
                if self.evidence
                else AnswerSuggestionSource.PUBLISHED_REFERENCE
            )
        cites_current = any(item.requirement_id == requirement_id for item in self.evidence)
        cites_knowledge = any(item.requirement_id != requirement_id for item in self.evidence)
        if cites_current and cites_knowledge:
            return AnswerSuggestionSource.COMBINED
        if cites_current:
            return AnswerSuggestionSource.CURRENT_ANALYSIS
        return AnswerSuggestionSource.TRUSTED_KNOWLEDGE


@dataclass(frozen=True)
class AnswerSuggestionSet:
    id: AnswerSuggestionSetId
    requirement_id: RequirementId
    question_id: QuestionId
    question_fingerprint: str
    suggestions: tuple[AnswerSuggestion, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "question_fingerprint",
            _text(self.question_fingerprint, "question fingerprint"),
        )
        if len(self.suggestions) > 3:
            raise InvalidKnowledgeError("At most three answer suggestions may be stored.")
