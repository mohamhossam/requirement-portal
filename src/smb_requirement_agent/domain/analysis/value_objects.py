"""Value objects used by requirement analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.domain.analysis.errors import (
    IntentProposalVersionConflictError,
    InvalidAnalysisContentError,
    InvalidClarificationError,
    InvalidIntentProposalDecisionError,
    InvalidIntentProposalTransitionError,
)
from smb_requirement_agent.shared_kernel.actors import ActorSnapshot
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.lineage import SourceLineage
from smb_requirement_agent.shared_kernel.staleness import require_aware


def _require_text(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise InvalidAnalysisContentError(f"{field_name} cannot be empty.")


@dataclass(frozen=True)
class AnalysisClarificationEvidence:
    """An output's support in the immutable round's ordered human answers."""

    evidence_key: str
    clarification_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_text(self.evidence_key, "Clarification evidence key")
        if (
            not self.clarification_numbers
            or len(self.clarification_numbers) != len(set(self.clarification_numbers))
            or any(
                isinstance(number, bool) or not isinstance(number, int) or number < 1
                for number in self.clarification_numbers
            )
        ):
            raise InvalidAnalysisContentError(
                "Clarification evidence numbers must be unique and positive."
            )


@dataclass(frozen=True)
class AnalysisEvidenceReference:
    document_id: str
    version_id: str
    checksum_sha256: str
    block_id: str
    label: str

    def __post_init__(self) -> None:
        values = tuple(
            value.strip()
            for value in (
                self.document_id,
                self.version_id,
                self.checksum_sha256,
                self.block_id,
                self.label,
            )
        )
        if any(not value for value in values):
            raise InvalidAnalysisContentError("Analysis evidence reference is incomplete.")
        if len(values[2]) != 64 or any(char not in "0123456789abcdef" for char in values[2]):
            raise InvalidAnalysisContentError(
                "Analysis evidence checksum must be a SHA-256 digest."
            )
        object.__setattr__(self, "document_id", values[0])
        object.__setattr__(self, "version_id", values[1])
        object.__setattr__(self, "checksum_sha256", values[2].lower())
        object.__setattr__(self, "block_id", values[3])
        object.__setattr__(self, "label", values[4])


@dataclass(frozen=True)
class KnownFact:
    statement: str
    evidence_references: tuple[AnalysisEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.statement, "KnownFact statement")


@dataclass(frozen=True)
class Constraint:
    statement: str
    evidence_references: tuple[AnalysisEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.statement, "Constraint statement")


@dataclass(frozen=True)
class BusinessRule:
    statement: str
    evidence_references: tuple[AnalysisEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.statement, "BusinessRule statement")


@dataclass(frozen=True)
class Assumption:
    statement: str
    evidence_references: tuple[AnalysisEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.statement, "Assumption statement")


@dataclass(frozen=True)
class OpenQuestion:
    question: str
    rationale: str
    evidence_references: tuple[AnalysisEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.question, "OpenQuestion question")
        _require_text(self.rationale, "OpenQuestion rationale")


@dataclass(frozen=True)
class Ambiguity:
    statement: str
    reason: str
    evidence_references: tuple[AnalysisEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.statement, "Ambiguity statement")
        _require_text(self.reason, "Ambiguity reason")


@dataclass(frozen=True)
class PotentialDependency:
    statement: str
    evidence_references: tuple[AnalysisEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.statement, "PotentialDependency statement")


class ClarificationKind(StrEnum):
    """The uncertainty category a human clarification resolves."""

    ASSUMPTION = "assumption"
    OPEN_QUESTION = "open_question"
    AMBIGUITY = "ambiguity"
    POTENTIAL_DEPENDENCY = "potential_dependency"


@dataclass(frozen=True, order=True)
class AnalysisId:
    value: str

    def __post_init__(self) -> None:
        _require_text(self.value, "Analysis id")
        object.__setattr__(self, "value", self.value.strip())


@dataclass(frozen=True, order=True)
class QuestionId:
    value: str

    def __post_init__(self) -> None:
        _require_text(self.value, "Question id")
        object.__setattr__(self, "value", self.value.strip())


@dataclass(frozen=True, order=True)
class IntentProposalId:
    value: str

    def __post_init__(self) -> None:
        _require_text(self.value, "Intent proposal id")
        object.__setattr__(self, "value", self.value.strip())


class IntentProposalKind(StrEnum):
    DESIRED_OUTCOME = "desired_outcome"
    BUSINESS_RULE = "business_rule"
    CONSTRAINT = "constraint"


class IntentProposalStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


@dataclass(frozen=True)
class IntentProposalDecision:
    status: IntentProposalStatus
    final_statement: str | None
    success_measures: tuple[str, ...]
    decided_by: ActorSnapshot
    decided_at: datetime
    version: int
    rationale: str | None = None

    def __post_init__(self) -> None:
        if self.status is IntentProposalStatus.PENDING:
            raise InvalidIntentProposalDecisionError("A recorded decision cannot be pending.")
        if self.version < 2:
            raise InvalidIntentProposalDecisionError("A proposal decision version must exceed one.")
        require_aware(self.decided_at, "intent proposal decided_at")
        if self.status is IntentProposalStatus.REJECTED:
            if self.final_statement is not None or self.success_measures:
                raise InvalidIntentProposalDecisionError(
                    "A rejected proposal cannot retain accepted content."
                )
            return
        if self.final_statement is None or not self.final_statement.strip():
            raise InvalidIntentProposalDecisionError(
                "An accepted or edited proposal requires a final statement."
            )
        object.__setattr__(self, "final_statement", self.final_statement.strip())
        measures = tuple(item.strip() for item in self.success_measures if item.strip())
        object.__setattr__(self, "success_measures", measures)


@dataclass(frozen=True)
class IntentProposal:
    id: IntentProposalId
    kind: IntentProposalKind
    statement: str
    rationale: str
    success_measures: tuple[str, ...] = ()
    decisions: tuple[IntentProposalDecision, ...] = ()
    evidence_references: tuple[AnalysisEvidenceReference, ...] = ()
    reference_evidence: tuple[PublishedReference, ...] = ()
    reference_conflict: bool = False
    reference_provenance: Provenance | None = None

    def __post_init__(self) -> None:
        _require_text(self.statement, "Intent proposal statement")
        if self.reference_conflict and not self.reference_evidence:
            raise InvalidIntentProposalDecisionError(
                "A reference conflict requires cited evidence."
            )
        if self.reference_evidence and self.reference_provenance is None:
            raise InvalidIntentProposalDecisionError(
                "Reference proposals require generation provenance."
            )
        if self.reference_evidence and any(not (d.rationale or "").strip() for d in self.decisions):
            raise InvalidIntentProposalDecisionError(
                "Reference decision history requires a rationale."
            )
        _require_text(self.rationale, "Intent proposal rationale")
        object.__setattr__(self, "statement", self.statement.strip())
        object.__setattr__(self, "rationale", self.rationale.strip())
        measures = tuple(item.strip() for item in self.success_measures if item.strip())
        object.__setattr__(self, "success_measures", measures)
        expected_versions = tuple(range(2, len(self.decisions) + 2))
        if tuple(item.version for item in self.decisions) != expected_versions:
            raise InvalidIntentProposalDecisionError(
                "Intent proposal decision history must have consecutive versions."
            )
        if self.kind is not IntentProposalKind.DESIRED_OUTCOME and measures:
            raise InvalidIntentProposalDecisionError(
                "Only desired-outcome proposals may carry success measures."
            )

    @property
    def version(self) -> int:
        return len(self.decisions) + 1

    @property
    def status(self) -> IntentProposalStatus:
        return self.decisions[-1].status if self.decisions else IntentProposalStatus.PENDING

    @property
    def effective_statement(self) -> str | None:
        return self.decisions[-1].final_statement if self.decisions else None

    @property
    def effective_success_measures(self) -> tuple[str, ...]:
        return self.decisions[-1].success_measures if self.decisions else ()

    def decide(
        self,
        status: IntentProposalStatus,
        actor: ActorSnapshot,
        at: datetime,
        expected_version: int,
        *,
        replacement_statement: str | None = None,
        success_measures: tuple[str, ...] | None = None,
        analysis_confirmed: bool = False,
        rationale: str | None = None,
    ) -> IntentProposal:
        if analysis_confirmed:
            raise InvalidIntentProposalTransitionError(
                "Intent proposals cannot change after analysis confirmation."
            )
        if self.reference_evidence and not (rationale or "").strip():
            raise InvalidIntentProposalDecisionError(
                "Explain why the cited policy applies or does not apply."
            )
        if expected_version != self.version:
            raise IntentProposalVersionConflictError(
                "Intent proposal changed since it was loaded. Refresh and try again."
            )
        if status is IntentProposalStatus.PENDING:
            raise InvalidIntentProposalDecisionError("Pending is not a review decision.")
        final_statement: str | None
        if status is IntentProposalStatus.EDITED:
            final_statement = (replacement_statement or "").strip()
            if not final_statement:
                raise InvalidIntentProposalDecisionError(
                    "Editing a proposal requires a replacement statement."
                )
        else:
            if replacement_statement is not None:
                raise InvalidIntentProposalDecisionError(
                    "Only an edited proposal accepts a replacement statement."
                )
            final_statement = self.statement if status is IntentProposalStatus.ACCEPTED else None
        resolved_measures = (
            tuple(success_measures) if success_measures is not None else self.success_measures
        )
        if self.kind is not IntentProposalKind.DESIRED_OUTCOME and resolved_measures:
            raise InvalidIntentProposalDecisionError(
                "Only desired-outcome proposals accept success measures."
            )
        if status is IntentProposalStatus.REJECTED:
            resolved_measures = ()
        decision = IntentProposalDecision(
            status,
            final_statement,
            resolved_measures,
            actor,
            at,
            self.version + 1,
            (rationale or "").strip() or None,
        )
        return IntentProposal(
            self.id,
            self.kind,
            self.statement,
            self.rationale,
            self.success_measures,
            (*self.decisions, decision),
            self.evidence_references,
            self.reference_evidence,
            self.reference_conflict,
            self.reference_provenance,
        )


def is_additional_intent_proposal(
    kind: IntentProposalKind,
    statement: str,
    decided_proposals: tuple[IntentProposal, ...],
    *,
    has_source_outcome: bool,
) -> bool:
    """Keep prior owner decisions authoritative during same-source re-analysis."""
    decided = tuple(p for p in decided_proposals if p.status is not IntentProposalStatus.PENDING)
    if kind is IntentProposalKind.DESIRED_OUTCOME and (
        has_source_outcome
        or any(
            p.kind is IntentProposalKind.DESIRED_OUTCOME and p.effective_statement is not None
            for p in decided
        )
    ):
        return False
    decided_statements = {
        (p.kind, text.casefold())
        for p in decided
        for text in (p.statement, p.effective_statement)
        if text is not None
    }
    return (kind, statement.casefold()) not in decided_statements


class ClarificationSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClarificationStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


class QuestionChangeAction(StrEnum):
    """How one analysis round changed the clarification-question set."""

    RETAINED = "retained"
    RETIRED = "retired"
    REPLACED = "replaced"
    CREATED = "created"


class ClarificationSource(StrEnum):
    AI = "ai"
    HUMAN = "human"


@dataclass(frozen=True)
class HumanClarification:
    """A human answer to one explicitly identified analysis uncertainty."""

    kind: ClarificationKind
    subject: str
    answer: str
    question_id: QuestionId | None = None
    answered_by: ActorSnapshot | None = None
    answered_at: datetime | None = None
    source_suggestion_id: str | None = None
    source_lineage: tuple[SourceLineage, ...] = ()

    def __post_init__(self) -> None:
        if not self.subject or not self.subject.strip():
            raise InvalidClarificationError("Clarification subject cannot be empty.")
        if not self.answer or not self.answer.strip():
            raise InvalidClarificationError("Clarification answer cannot be empty.")
        if (self.answered_by is None) != (self.answered_at is None):
            raise InvalidClarificationError(
                "Clarification answer attribution and time must be supplied together."
            )
        if self.answered_at is not None:
            require_aware(self.answered_at, "clarification answered_at")
        if self.source_suggestion_id is not None:
            cleaned = self.source_suggestion_id.strip()
            if not cleaned:
                raise InvalidClarificationError("Source suggestion id cannot be blank.")
            object.__setattr__(self, "source_suggestion_id", cleaned)

    @property
    def key(self) -> tuple[ClarificationKind, str]:
        return (self.kind, self.subject.strip())
