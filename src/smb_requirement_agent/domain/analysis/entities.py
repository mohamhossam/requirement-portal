"""Requirement Analysis domain aggregate."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from smb_requirement_agent.domain.analysis.errors import (
    AnalysisClarificationConflictError,
    AnalysisConfirmationBlockedError,
    ClarificationVersionConflictError,
    InvalidAnalysisContentError,
    InvalidClarificationTransitionError,
)
from smb_requirement_agent.domain.analysis.value_objects import (
    Ambiguity,
    AnalysisClarificationEvidence,
    AnalysisId,
    Assumption,
    BusinessRule,
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    ClarificationStatus,
    Constraint,
    HumanClarification,
    IntentProposal,
    IntentProposalId,
    IntentProposalKind,
    IntentProposalStatus,
    KnownFact,
    OpenQuestion,
    PotentialDependency,
    QuestionChangeAction,
    QuestionId,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementVersion
from smb_requirement_agent.shared_kernel.actions import ActionAvailability
from smb_requirement_agent.shared_kernel.actors import (
    ActorProfile,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage
from smb_requirement_agent.shared_kernel.staleness import require_aware


def _text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidAnalysisContentError(f"{field} cannot be empty.")
    return stripped


@dataclass(frozen=True)
class QuestionAssignmentChange:
    assignee: ActorSnapshot | None
    changed_by: ActorSnapshot
    changed_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.changed_at, "question assignment changed_at")


@dataclass(frozen=True)
class ClarificationQuestion:
    id: QuestionId
    requirement_id: RequirementId
    first_analysis_id: AnalysisId
    kind: ClarificationKind
    subject: str
    rationale: str | None
    severity: ClarificationSeverity
    is_blocker: bool
    source: ClarificationSource
    status: ClarificationStatus = ClarificationStatus.OPEN
    version: int = 1
    asked_by: ActorSnapshot | None = None
    asked_at: datetime | None = None
    assignee: ActorSnapshot | None = None
    assignment_history: tuple[QuestionAssignmentChange, ...] = ()
    draft_answer: str | None = None
    draft_updated_by: ActorSnapshot | None = None
    draft_updated_at: datetime | None = None
    answer: str | None = None
    answered_by: ActorSnapshot | None = None
    answered_at: datetime | None = None
    classification_changed_by: ActorSnapshot | None = None
    classification_changed_at: datetime | None = None
    replaces_question_id: QuestionId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject", _text(self.subject, "Question subject"))
        if self.rationale is not None:
            object.__setattr__(self, "rationale", self.rationale.strip() or None)
        if self.version < 1:
            raise InvalidAnalysisContentError("Question version must be positive.")
        if (self.asked_by is None) != (self.asked_at is None):
            raise InvalidAnalysisContentError("Question author and time must be supplied together.")
        if self.asked_at is not None:
            require_aware(self.asked_at, "question asked_at")
        if (self.draft_updated_by is None) != (self.draft_updated_at is None):
            raise InvalidAnalysisContentError(
                "Draft answer attribution and time must be supplied together."
            )
        if self.draft_updated_at is not None:
            require_aware(self.draft_updated_at, "question draft_updated_at")
        if (self.answered_by is None) != (self.answered_at is None):
            raise InvalidAnalysisContentError(
                "Question answer actor and time must be supplied together."
            )
        if self.answered_at is not None:
            require_aware(self.answered_at, "question answered_at")
        if (self.classification_changed_by is None) != (self.classification_changed_at is None):
            raise InvalidAnalysisContentError(
                "Question classification actor and time must be supplied together."
            )
        if self.classification_changed_at is not None:
            require_aware(self.classification_changed_at, "classification changed_at")
        if self.replaces_question_id == self.id:
            raise InvalidAnalysisContentError("A question cannot replace itself.")
        terminal = self.status in (
            ClarificationStatus.RESOLVED,
            ClarificationStatus.SUPERSEDED,
        )
        if self.status is ClarificationStatus.RESOLVED and not self.answer:
            raise InvalidAnalysisContentError("A resolved question must retain its answer.")
        if not terminal and self.answer is not None:
            raise InvalidAnalysisContentError("Only a resolved question can retain a final answer.")

    @property
    def key(self) -> tuple[ClarificationKind, str]:
        return self.kind, self.subject.casefold()

    @property
    def is_active(self) -> bool:
        return self.status in (ClarificationStatus.OPEN, ClarificationStatus.IN_PROGRESS)

    def _check(self, expected_version: int) -> None:
        if expected_version != self.version:
            raise ClarificationVersionConflictError(
                "Question changed since it was loaded. Refresh and try again."
            )
        if not self.is_active:
            raise InvalidClarificationTransitionError(
                "Resolved or superseded questions cannot be changed."
            )

    def assign(
        self,
        assignee: ActorProfile | None,
        changed_by: ActorProfile,
        at: datetime,
        expected_version: int,
    ) -> ClarificationQuestion:
        self._check(expected_version)
        require_aware(at, "question assignment changed_at")
        snapshot = assignee.snapshot() if assignee is not None else None
        if (self.assignee.id if self.assignee else None) == (snapshot.id if snapshot else None):
            return self
        return replace(
            self,
            assignee=snapshot,
            assignment_history=(
                *self.assignment_history,
                QuestionAssignmentChange(snapshot, changed_by.snapshot(), at),
            ),
            version=self.version + 1,
        )

    def classify(
        self,
        severity: ClarificationSeverity,
        is_blocker: bool,
        changed_by: ActorProfile,
        at: datetime,
        expected_version: int,
    ) -> ClarificationQuestion:
        self._check(expected_version)
        require_aware(at, "classification changed_at")
        if severity is self.severity and is_blocker == self.is_blocker:
            return self
        return replace(
            self,
            severity=severity,
            is_blocker=is_blocker,
            classification_changed_by=changed_by.snapshot(),
            classification_changed_at=at,
            version=self.version + 1,
        )

    def save_draft(
        self,
        answer: str,
        actor: ActorProfile,
        at: datetime,
        expected_version: int,
    ) -> ClarificationQuestion:
        self._check(expected_version)
        require_aware(at, "question draft_updated_at")
        draft = answer.strip() or None
        return replace(
            self,
            draft_answer=draft,
            draft_updated_by=actor.snapshot() if draft is not None else None,
            draft_updated_at=at if draft is not None else None,
            status=(ClarificationStatus.IN_PROGRESS if draft else ClarificationStatus.OPEN),
            version=self.version + 1,
        )

    def resolve(
        self,
        answer: str,
        actor: ActorProfile,
        at: datetime,
        expected_version: int,
    ) -> ClarificationQuestion:
        self._check(expected_version)
        require_aware(at, "question answered_at")
        final_answer = _text(answer, "Question answer")
        return replace(
            self,
            answer=final_answer,
            answered_by=actor.snapshot(),
            answered_at=at,
            draft_answer=None,
            draft_updated_by=None,
            draft_updated_at=None,
            status=ClarificationStatus.RESOLVED,
            version=self.version + 1,
        )

    def supersede(self) -> ClarificationQuestion:
        if not self.is_active:
            return self
        return replace(self, status=ClarificationStatus.SUPERSEDED, version=self.version + 1)

    def replacement(
        self,
        question_id: QuestionId,
        analysis_id: AnalysisId,
        kind: ClarificationKind,
        subject: str,
        rationale: str | None,
    ) -> ClarificationQuestion:
        """Create a linked AI replacement without carrying an unconfirmed draft."""
        if not self.is_active:
            raise InvalidClarificationTransitionError(
                "Only an active clarification question can be replaced."
            )
        return ClarificationQuestion(
            id=question_id,
            requirement_id=self.requirement_id,
            first_analysis_id=analysis_id,
            kind=kind,
            subject=subject,
            rationale=rationale,
            severity=self.severity,
            is_blocker=self.is_blocker,
            source=ClarificationSource.AI,
            assignee=self.assignee,
            classification_changed_by=self.classification_changed_by,
            classification_changed_at=self.classification_changed_at,
            replaces_question_id=self.id,
        )


@dataclass(frozen=True)
class AnalysisDocumentReference:
    """Exact immutable attachment version used by an analysis."""

    document_id: str
    version_id: str
    filename: str
    checksum_sha256: str


@dataclass(frozen=True)
class AnalysisStageProvenance:
    """Auditable provenance for one packet or consolidation generation stage."""

    stage: str
    model: str
    prompt_version: str
    generated_at: datetime
    input_fingerprint: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.stage, "stage"),
            (self.model, "model"),
            (self.prompt_version, "prompt version"),
            (self.input_fingerprint, "input fingerprint"),
        ):
            if not value.strip():
                raise InvalidAnalysisContentError(
                    f"Analysis stage provenance {field} cannot be empty."
                )
        fingerprint = self.input_fingerprint.strip().lower()
        if len(fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in fingerprint
        ):
            raise InvalidAnalysisContentError(
                "Analysis stage input fingerprint must be a SHA-256 digest."
            )
        require_aware(self.generated_at, "analysis stage generated_at")
        object.__setattr__(self, "stage", self.stage.strip())
        object.__setattr__(self, "model", self.model.strip())
        object.__setattr__(self, "prompt_version", self.prompt_version.strip())
        object.__setattr__(self, "input_fingerprint", fingerprint)


@dataclass(frozen=True)
class RequirementAnalysis:
    """The structured AI analysis of a Requirement."""

    requirement_id: RequirementId
    known_facts: tuple[KnownFact, ...]
    constraints: tuple[Constraint, ...]
    business_rules: tuple[BusinessRule, ...]
    assumptions: tuple[Assumption, ...]
    open_questions: tuple[OpenQuestion, ...]
    ambiguities: tuple[Ambiguity, ...]
    potential_dependencies: tuple[PotentialDependency, ...]
    clarifications: tuple[HumanClarification, ...] = ()
    confirmed_at: datetime | None = None
    confirmed_by: ActorSnapshot | None = None
    document_references: tuple[AnalysisDocumentReference, ...] = ()
    id: AnalysisId | None = None
    round_number: int | None = None
    provenance: Provenance | None = None
    source_requirement_version: RequirementVersion | None = None
    intent_proposals: tuple[IntentProposal, ...] = ()
    source_desired_outcome: str | None = None
    stage_provenance: tuple[AnalysisStageProvenance, ...] = ()
    version: int = 1
    source_lineage: tuple[SourceLineage, ...] = ()
    clarification_evidence: tuple[AnalysisClarificationEvidence, ...] = ()

    def __post_init__(self) -> None:
        if self.version < 1:
            raise InvalidAnalysisContentError("Analysis version must be positive.")
        if self.confirmed_at is not None:
            require_aware(self.confirmed_at, "analysis confirmed_at")
        if self.confirmed_at is None and self.confirmed_by is not None:
            raise AnalysisConfirmationBlockedError(
                "An unconfirmed analysis cannot name a confirming actor."
            )
        identity = (self.id, self.round_number, self.source_requirement_version)
        if any(item is not None for item in identity) and any(item is None for item in identity):
            raise InvalidAnalysisContentError(
                "Analysis identity, round, and source version must be supplied together."
            )
        if self.round_number is not None and self.round_number < 1:
            raise InvalidAnalysisContentError("Analysis round number must be positive.")
        proposal_ids = tuple(item.id for item in self.intent_proposals)
        if len(proposal_ids) != len(set(proposal_ids)):
            raise InvalidAnalysisContentError("Intent proposal ids must be unique.")
        outcome_count = sum(
            item.kind is IntentProposalKind.DESIRED_OUTCOME for item in self.intent_proposals
        )
        if outcome_count > 1:
            raise InvalidAnalysisContentError(
                "An analysis round may propose at most one desired outcome."
            )
        if self.source_desired_outcome is not None:
            outcome = self.source_desired_outcome.strip()
            object.__setattr__(self, "source_desired_outcome", outcome or None)
        evidence_keys = [item.evidence_key for item in self.clarification_evidence]
        if len(evidence_keys) != len(set(evidence_keys)) or any(
            number > len(self.clarifications)
            for item in self.clarification_evidence
            for number in item.clarification_numbers
        ):
            raise InvalidAnalysisContentError(
                "Analysis references unknown or duplicate human evidence."
            )

    def unresolved_keys(self) -> frozenset[tuple[ClarificationKind, str]]:
        """Return stable references for every uncertainty visible to a reviewer."""
        keys = {(ClarificationKind.ASSUMPTION, item.statement.strip()) for item in self.assumptions}
        keys.update(
            (ClarificationKind.OPEN_QUESTION, item.question.strip()) for item in self.open_questions
        )
        keys.update(
            (ClarificationKind.AMBIGUITY, item.statement.strip()) for item in self.ambiguities
        )
        keys.update(
            (ClarificationKind.POTENTIAL_DEPENDENCY, item.statement.strip())
            for item in self.potential_dependencies
        )
        return frozenset(keys)

    @property
    def is_human_confirmed(self) -> bool:
        return self.confirmed_at is not None

    def epic_generation_availability(self) -> ActionAvailability:
        """An Epic is generated only from analysis a human has confirmed."""
        if not self.is_human_confirmed:
            return ActionAvailability.block(
                "The analysis must be human-confirmed before an Epic can be generated."
            )
        return ActionAvailability.allow()

    @property
    def has_pending_intent_proposals(self) -> bool:
        return any(item.status is IntentProposalStatus.PENDING for item in self.intent_proposals)

    def effective_desired_outcome(self, source_outcome: str | None = None) -> str | None:
        source_outcome = source_outcome or self.source_desired_outcome
        if source_outcome and source_outcome.strip():
            return source_outcome.strip()
        return next(
            (
                item.effective_statement
                for item in self.intent_proposals
                if item.kind is IntentProposalKind.DESIRED_OUTCOME
                and item.status in (IntentProposalStatus.ACCEPTED, IntentProposalStatus.EDITED)
            ),
            None,
        )

    @property
    def accepted_business_rules(self) -> tuple[str, ...]:
        return tuple(
            item.effective_statement
            for item in self.intent_proposals
            if item.kind is IntentProposalKind.BUSINESS_RULE
            and item.status in (IntentProposalStatus.ACCEPTED, IntentProposalStatus.EDITED)
            and item.effective_statement is not None
        )

    @property
    def accepted_constraints(self) -> tuple[str, ...]:
        return tuple(
            item.effective_statement
            for item in self.intent_proposals
            if item.kind is IntentProposalKind.CONSTRAINT
            and item.status in (IntentProposalStatus.ACCEPTED, IntentProposalStatus.EDITED)
            and item.effective_statement is not None
        )

    def decide_intent_proposal(
        self,
        proposal_id: IntentProposalId,
        status: IntentProposalStatus,
        actor: ActorProfile,
        at: datetime,
        expected_version: int,
        *,
        replacement_statement: str | None = None,
        success_measures: tuple[str, ...] | None = None,
        rationale: str | None = None,
    ) -> RequirementAnalysis:
        found = False
        proposals: list[IntentProposal] = []
        for proposal in self.intent_proposals:
            if proposal.id != proposal_id:
                proposals.append(proposal)
                continue
            found = True
            proposals.append(
                proposal.decide(
                    status,
                    actor.snapshot(),
                    at,
                    expected_version,
                    replacement_statement=replacement_statement,
                    success_measures=success_measures,
                    analysis_confirmed=self.is_human_confirmed,
                    rationale=rationale,
                )
            )
        if not found:
            raise InvalidAnalysisContentError(
                f"Intent proposal {proposal_id.value!r} does not belong to this analysis."
            )
        updated = tuple(proposals)
        if updated == self.intent_proposals:
            return self
        return replace(self, intent_proposals=updated, version=self.version + 1)

    def record_question_collection_change(self, expected_version: int) -> RequirementAnalysis:
        """Advance the analysis collection version before inserting a question."""
        if expected_version != self.version:
            raise AnalysisClarificationConflictError(
                "Analysis changed since it was loaded. Refresh and try again."
            )
        return replace(self, version=self.version + 1)

    def confirm(
        self,
        at: datetime,
        actor: ActorProfile,
        *,
        has_open_blockers: bool | None = None,
        has_effective_outcome: bool = True,
    ) -> RequirementAnalysis:
        """Record explicit Requirement Owner confirmation of a complete analysis."""
        blocked = self.unresolved_keys() if has_open_blockers is None else has_open_blockers
        if blocked:
            raise AnalysisConfirmationBlockedError(
                "Resolve every Needs confirmation item before confirming the analysis."
            )
        if self.has_pending_intent_proposals:
            raise AnalysisConfirmationBlockedError(
                "Accept, edit, or reject every AI intent proposal before confirming the analysis."
            )
        if not has_effective_outcome:
            raise AnalysisConfirmationBlockedError(
                "A source-authored or owner-confirmed desired outcome is required."
            )
        require_aware(at, "analysis confirmed_at")
        return replace(
            self,
            confirmed_at=at,
            confirmed_by=actor.snapshot(),
            version=self.version + 1,
        )


@dataclass(frozen=True)
class AnalysisQuestionChange:
    action: QuestionChangeAction
    question_id: QuestionId
    rationale: str
    replacement_question_id: QuestionId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rationale", _text(self.rationale, "Question change rationale"))
        if self.action is QuestionChangeAction.REPLACED:
            if self.replacement_question_id is None:
                raise InvalidAnalysisContentError(
                    "A replaced question change requires a replacement question id."
                )
            if self.replacement_question_id == self.question_id:
                raise InvalidAnalysisContentError(
                    "A replacement question must have a new stable identity."
                )
        elif self.replacement_question_id is not None:
            raise InvalidAnalysisContentError(
                "Only a replaced question change may name a replacement question."
            )


@dataclass(frozen=True)
class AnalysisRound:
    analysis: RequirementAnalysis
    question_ids: tuple[QuestionId, ...]
    question_changes: tuple[AnalysisQuestionChange, ...] = ()

    def __post_init__(self) -> None:
        if self.analysis.id is None or self.analysis.round_number is None:
            raise InvalidAnalysisContentError("An immutable round requires identified analysis.")
        changed_ids = tuple(item.question_id for item in self.question_changes)
        if len(changed_ids) != len(set(changed_ids)):
            raise InvalidAnalysisContentError(
                "An analysis round can record only one change per question id."
            )

    @property
    def id(self) -> AnalysisId:
        if self.analysis.id is None:  # pragma: no cover - guarded above
            raise AssertionError("Round analysis must have an id.")
        return self.analysis.id

    @property
    def requirement_id(self) -> RequirementId:
        return self.analysis.requirement_id

    @property
    def number(self) -> int:
        if self.analysis.round_number is None:  # pragma: no cover - guarded above
            raise AssertionError("Round analysis must have a number.")
        return self.analysis.round_number
