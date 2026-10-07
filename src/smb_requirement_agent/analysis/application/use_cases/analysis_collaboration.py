"""Collaborative clarification questions and immutable analysis rounds."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.analysis_context import AnalysisContextPort
from smb_requirement_agent.analysis.application.ports.knowledge_screening import (
    AnswerSuggestionRequestPort,
    SuggestionProvenancePort,
)
from smb_requirement_agent.analysis.application.ports.reference_analysis import (
    ReferenceAnalysisPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    RequirementAnalysisCandidate,
    RequirementAnalyzerPort,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_documents import (
    AssembleAnalysisDocuments,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_mapping import build_analysis
from smb_requirement_agent.analysis.application.use_cases.analysis_reconciliation import (
    reconcile_round,
)
from smb_requirement_agent.analysis.application.use_cases.generation_effects import (
    accepted_generation_effects,
)
from smb_requirement_agent.analysis.domain.entities import (
    AnalysisDocumentReference,
    AnalysisQuestionChange,
    AnalysisRound,
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.analysis.domain.errors import (
    AnalysisClarificationConflictError,
    InvalidClarificationError,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    AnalysisId,
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    HumanClarification,
    IntentProposal,
    IntentProposalId,
    IntentProposalStatus,
    QuestionId,
)
from smb_requirement_agent.application.errors import (
    ActorNotFoundError,
    AnalysisRoundNotFoundError,
    ClarificationQuestionNotFoundError,
    IntentProposalNotFoundError,
    RequirementAnalysisConflictError,
    RequirementAnalysisIneligibleError,
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.reference_grounding import (
    ReferenceEvidencePort,
    ReferenceReviewPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.identity.domain.entities import RequirementAccess
from smb_requirement_agent.identity.domain.errors import AuthorizationDeniedError
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.screening_requests import (
    ScreeningRequestPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


@dataclass(frozen=True)
class AnalysisWorkspace:
    analysis: RequirementAnalysis
    questions: tuple[ClarificationQuestion, ...]
    question_changes: tuple[AnalysisQuestionChange, ...] = ()
    stale_reference_proposal_ids: tuple[str, ...] = ()
    # Cited library documents past their review date, with that date (Knowledge Center D).
    overdue_reference_reviews: Mapping[str, date] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisRoundView:
    round: AnalysisRound
    questions: tuple[ClarificationQuestion, ...]


@dataclass(frozen=True)
class ClarificationResolutionInput:
    question_id: QuestionId
    answer: str
    expected_version: int
    source_suggestion_id: str | None = None


class AnalysisCollaboration:
    """Coordinate current analysis, durable questions, and immutable rounds."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        analyses: RequirementAnalysisRepositoryPort,
        audits: AnalysisAuditRepositoryPort,
        analyzer: RequirementAnalyzerPort,
        documents: AssembleAnalysisDocuments,
        access: AccessRepositoryPort,
        actors: ActorDirectoryPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        knowledge: ScreeningRequestPort,
        suggestion_scheduler: AnswerSuggestionRequestPort,
        suggestions: SuggestionProvenancePort,
        *,
        contexts: AnalysisContextPort,
        reference_grounding: ReferenceAnalysisPort,
        references: ReferenceEvidencePort,
        authorization: RequirementAccessService,
        reviews: ReferenceReviewPort | None = None,
    ) -> None:
        self._reviews = reviews
        self._requirements = requirements
        self._reference_grounding, self._references = reference_grounding, references
        self._contexts = contexts
        self._analyses = analyses
        self._audits = audits
        self._analyzer = analyzer
        self._documents = documents
        self._access = access
        self._authorization = authorization
        self._actors = actors
        self._clock = clock
        self._transactions = transactions
        self._knowledge = knowledge
        self._suggestion_scheduler = suggestion_scheduler
        self._suggestions = suggestions

    def workspace(self, requirement_id: RequirementId) -> AnalysisWorkspace:
        self._require_requirement(requirement_id)
        analysis = self._require_analysis(requirement_id)
        questions = tuple(
            item for item in self._audits.list_questions(requirement_id) if item.is_active
        )
        round_ = self._audits.get_round(requirement_id, analysis.id) if analysis.id else None
        return AnalysisWorkspace(
            analysis,
            questions,
            round_.question_changes if round_ is not None else (),
            self._references.stale_analysis(analysis),
            self._overdue_reviews(analysis),
        )

    def list_rounds(self, requirement_id: RequirementId) -> tuple[AnalysisRoundView, ...]:
        self._require_requirement(requirement_id)
        questions = self._audits.list_questions(requirement_id)
        return tuple(
            AnalysisRoundView(
                round_,
                tuple(item for item in questions if item.id in _round_audit_question_ids(round_)),
            )
            for round_ in self._audits.list_rounds(requirement_id)
        )

    def get_round(
        self, requirement_id: RequirementId, analysis_id: AnalysisId
    ) -> AnalysisRoundView:
        self._require_requirement(requirement_id)
        round_ = self._audits.get_round(requirement_id, analysis_id)
        if round_ is None:
            raise AnalysisRoundNotFoundError(f"Analysis round {analysis_id.value!r} not found.")
        questions = tuple(
            item
            for item in self._audits.list_questions(requirement_id)
            if item.id in _round_audit_question_ids(round_)
        )
        return AnalysisRoundView(round_, questions)

    def question(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> ClarificationQuestion:
        self._require_requirement(requirement_id)
        return self._require_question(requirement_id, question_id)

    def generate(
        self, actor: ActorProfile, requirement_id: RequirementId, *, force: bool
    ) -> AnalysisWorkspace:
        with (
            self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER),
            self._contexts.guard(lambda: self._contexts.analysis(requirement_id)),
            accepted_generation_effects(),
        ):
            self._transactions.lock_requirement(requirement_id)
            return self._generate(requirement_id, force=force)

    def _generate(self, requirement_id: RequirementId, *, force: bool) -> AnalysisWorkspace:
        requirement = self._require_requirement(requirement_id)
        requirement.require_active()
        current = self._analyses.get_by_requirement_id(requirement_id)
        if current is not None and not force:
            raise RequirementAnalysisConflictError(
                "An analysis already exists. Use force=true to create a new audited round."
            )
        eligibility = self._documents.eligibility(requirement)
        if not eligibility.eligible:
            raise RequirementAnalysisIneligibleError(
                "Requirement cannot be analysed until these fields are complete: "
                + ", ".join(eligibility.missing_fields)
            )
        clarifications = current.clarifications if current is not None else ()
        active_questions = tuple(
            item for item in self._audits.list_questions(requirement_id) if item.is_active
        )
        decisions = _decided_intent(current)
        document_snapshot = self._documents.selection_snapshot(requirement_id)
        with self._transactions.external_call():
            documents = self._documents.execute(requirement_id)
            candidate = self._analyzer.analyze(
                requirement,
                clarifications,
                documents.contexts,
                decisions,
                tuple(_question_context(item) for item in active_questions),
            )
            candidate = self._reference_grounding.augment(requirement, candidate, decisions)
        prepared = self._build_next_analysis(
            requirement, candidate, clarifications, documents.references, current
        )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            latest_requirement = self._require_requirement(requirement_id)
            latest = self._analyses.get_by_requirement_id(requirement_id)
            requirement_changed = latest_requirement.version != requirement.version
            analysis_changed = latest != current
            questions_changed = not self._active_snapshot_matches(requirement_id, active_questions)
            documents_changed = (
                self._documents.selection_snapshot(requirement_id) != document_snapshot
            )
            if requirement_changed or analysis_changed or questions_changed or documents_changed:
                raise RequirementAnalysisConflictError(
                    "Requirement, analysis, or active questions changed while "
                    "generation was running."
                )
            self._references.require_current(
                tuple(
                    c
                    for p in candidate["intent_proposals"]
                    for c in p.get("reference_evidence", ())
                )
            )
            return self._persist_round(prepared, candidate, active_questions)

    def ask(
        self,
        requirement_id: RequirementId,
        *,
        subject: str,
        rationale: str | None,
        assignee_id: ActorId | None,
        severity: ClarificationSeverity,
        is_blocker: bool,
        expected_analysis_version: int,
        actor: ActorProfile,
    ) -> ClarificationQuestion:
        analysis = self._require_analysis(requirement_id)
        if expected_analysis_version != analysis.version:
            raise RequirementAnalysisConflictError(
                "Analysis changed since it was loaded. Refresh and reconcile the new question."
            )
        access = self._require_team_member(requirement_id, actor)
        if analysis.id is None:
            raise RequirementAnalysisConflictError(
                "Create a new audited analysis round before adding collaborative questions."
            )
        assignee = self._assignment_target(access, assignee_id) if assignee_id else None
        now = self._clock.now()
        question = ClarificationQuestion(
            QuestionId(str(uuid.uuid4())),
            requirement_id,
            analysis.id,
            ClarificationKind.OPEN_QUESTION,
            subject,
            rationale,
            severity,
            is_blocker,
            ClarificationSource.HUMAN,
            asked_by=actor.snapshot(),
            asked_at=now,
        )
        if assignee is not None:
            question = question.assign(assignee, actor, now, question.version)
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_team_member(requirement_id, actor)
            latest = self._require_analysis(requirement_id)
            if latest.id != analysis.id or latest.version != expected_analysis_version:
                raise RequirementAnalysisConflictError(
                    "Analysis changed since it was loaded. Refresh and reconcile the new question."
                )
            self._audits.add_question(question)
            self._analyses.save(latest.record_question_collection_change(expected_analysis_version))
            self._suggestion_scheduler.schedule(requirement_id, (question,))
        return question

    def decide_intent_proposal(
        self,
        requirement_id: RequirementId,
        proposal_id: IntentProposalId,
        status: IntentProposalStatus,
        expected_version: int,
        actor: ActorProfile,
        *,
        replacement_statement: str | None = None,
        success_measures: tuple[str, ...] | None = None,
        rationale: str | None = None,
    ) -> AnalysisWorkspace:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_requirement(requirement_id)
            analysis = self._require_analysis(requirement_id)
            self._authorization.require(requirement_id, actor, RequirementPermission.OWNER)
            if not any(item.id == proposal_id for item in analysis.intent_proposals):
                raise IntentProposalNotFoundError(
                    f"Intent proposal {proposal_id.value!r} not found in the current analysis."
                )
            updated = analysis.decide_intent_proposal(
                proposal_id,
                status,
                actor,
                self._clock.now(),
                expected_version,
                replacement_statement=replacement_statement,
                success_measures=success_measures,
                rationale=rationale,
            )
            if status is not IntentProposalStatus.REJECTED:
                proposal = next(p for p in updated.intent_proposals if p.id == proposal_id)
                self._references.require_current(proposal.reference_evidence)
            self._analyses.save(updated)
            self._knowledge.schedule(requirement_id)
        return self.workspace(requirement_id)

    def classify(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        severity: ClarificationSeverity,
        is_blocker: bool,
        expected_version: int,
        actor: ActorProfile,
    ) -> ClarificationQuestion:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_team_member(requirement_id, actor)
            question = self._require_question(requirement_id, question_id)
            updated = question.classify(
                severity, is_blocker, actor, self._clock.now(), expected_version
            )
            if updated != question:
                self._audits.save_question(updated)
        return updated

    def assign(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        assignee_id: ActorId | None,
        expected_version: int,
        actor: ActorProfile,
    ) -> ClarificationQuestion:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            access = self._require_team_member(requirement_id, actor)
            target = self._assignment_target(access, assignee_id) if assignee_id else None
            question = self._require_question(requirement_id, question_id)
            updated = question.assign(target, actor, self._clock.now(), expected_version)
            if updated != question:
                self._audits.save_question(updated)
        return updated

    def save_draft(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        answer: str,
        expected_version: int,
        actor: ActorProfile,
    ) -> ClarificationQuestion:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            question = self._require_question(requirement_id, question_id)
            self._require_answerer(requirement_id, question, actor)
            updated = question.save_draft(answer, actor, self._clock.now(), expected_version)
            self._audits.save_question(updated)
        return updated

    def resolve(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        answer: str | None,
        expected_version: int,
        actor: ActorProfile,
        *,
        source_suggestion_id: str | None = None,
    ) -> AnalysisWorkspace:
        question = self._require_question(requirement_id, question_id)
        final_answer = (answer if answer is not None else question.draft_answer) or ""
        return self.resolve_batch(
            requirement_id,
            (
                ClarificationResolutionInput(
                    question_id, final_answer, expected_version, source_suggestion_id
                ),
            ),
            actor,
        )

    def resolve_batch(
        self,
        requirement_id: RequirementId,
        answers: tuple[ClarificationResolutionInput, ...],
        actor: ActorProfile,
    ) -> AnalysisWorkspace:
        return self._resolve_batch(requirement_id, answers, actor, allow_team=False)

    def _resolve_batch(
        self,
        requirement_id: RequirementId,
        answers: tuple[ClarificationResolutionInput, ...],
        actor: ActorProfile,
        *,
        allow_team: bool,
    ) -> AnalysisWorkspace:
        with self._transactions.transaction(), accepted_generation_effects():
            self._transactions.lock_requirement(requirement_id)
            with self._contexts.guard(lambda: self._contexts.analysis(requirement_id)):
                return self._prepare_resolutions(
                    requirement_id, answers, actor, allow_team=allow_team
                )

    def _prepare_resolutions(
        self,
        requirement_id: RequirementId,
        answers: tuple[ClarificationResolutionInput, ...],
        actor: ActorProfile,
        *,
        allow_team: bool,
    ) -> AnalysisWorkspace:
        if not answers:
            raise InvalidClarificationError("At least one clarification answer is required.")
        question_ids = [item.question_id for item in answers]
        if len(question_ids) != len(set(question_ids)):
            raise InvalidClarificationError(
                "Each clarification question can be answered only once per request."
            )

        requirement = self._require_requirement(requirement_id)
        current = self._require_analysis(requirement_id)
        active_questions = tuple(
            item for item in self._audits.list_questions(requirement_id) if item.is_active
        )
        answered_at = self._clock.now()
        selected: list[tuple[ClarificationQuestion, ClarificationQuestion]] = []
        clarifications: list[HumanClarification] = []
        for item in answers:
            question = self._require_question(requirement_id, item.question_id)
            self._require_answerer(requirement_id, question, actor, allow_team=allow_team)
            lineage: tuple[SourceLineage, ...] = ()
            if item.source_suggestion_id is not None:
                lineage = self._suggestions.suggestion_provenance(
                    requirement_id, question.id, item.source_suggestion_id
                )
            resolved = question.resolve(
                item.answer,
                actor,
                answered_at,
                item.expected_version,
            )
            selected.append((question, resolved))
            clarifications.append(
                HumanClarification(
                    question.kind,
                    question.subject,
                    resolved.answer or item.answer,
                    question.id,
                    actor.snapshot(),
                    answered_at,
                    item.source_suggestion_id,
                    lineage,
                )
            )

        combined = (*current.clarifications, *clarifications)
        document_snapshot = self._documents.selection_snapshot(requirement_id)
        with self._transactions.external_call():
            documents = self._documents.execute(requirement_id)
            candidate = self._analyzer.analyze(
                requirement,
                combined,
                documents.contexts,
                _decided_intent(current),
                tuple(
                    _question_context(item)
                    for item in active_questions
                    if item.id not in set(question_ids)
                ),
            )
        prepared = self._build_next_analysis(
            requirement, candidate, combined, documents.references, current
        )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            latest_requirement = self._require_requirement(requirement_id)
            latest_analysis = self._analyses.get_by_requirement_id(requirement_id)
            changed_question = not self._active_snapshot_matches(requirement_id, active_questions)
            if (
                latest_requirement.version != requirement.version
                or latest_analysis != current
                or self._documents.selection_snapshot(requirement_id) != document_snapshot
                or changed_question
            ):
                raise RequirementAnalysisConflictError(
                    "Requirement, analysis, or a question changed while re-analysis was running."
                )
            for item in answers:
                if item.source_suggestion_id is not None:
                    self._suggestions.suggestion_provenance(
                        requirement_id, item.question_id, item.source_suggestion_id
                    )
            for _, resolved in selected:
                self._require_answerer(requirement_id, resolved, actor, allow_team=allow_team)
                self._audits.save_question(resolved)
            remaining = tuple(item for item in active_questions if item.id not in set(question_ids))
            return self._persist_round(prepared, candidate, remaining)

    def resolve_legacy_batch(
        self,
        requirement_id: RequirementId,
        answers: tuple[tuple[ClarificationKind, str, str], ...],
        expected_analysis_version: int,
        actor: ActorProfile,
    ) -> AnalysisWorkspace:
        workspace = self.workspace(requirement_id)
        if workspace.analysis.version != expected_analysis_version:
            raise RequirementAnalysisConflictError(
                "Analysis changed since it was loaded. Refresh the clarification form."
            )
        selected: list[ClarificationResolutionInput] = []
        for kind, subject, answer in answers:
            key = (kind, subject.strip().casefold())
            matches = [item for item in workspace.questions if item.key == key]
            if len(matches) != 1:
                raise AnalysisClarificationConflictError(
                    "An answered item is stale or ambiguous in the current analysis. "
                    "Refresh and use its stable question ID."
                )
            question = matches[0]
            selected.append(ClarificationResolutionInput(question.id, answer, question.version))
        return self._resolve_batch(
            requirement_id,
            tuple(selected),
            actor,
            allow_team=True,
        )

    def _build_next_analysis(
        self,
        requirement: Requirement,
        candidate: RequirementAnalysisCandidate,
        clarifications: tuple[HumanClarification, ...],
        document_references: tuple[AnalysisDocumentReference, ...],
        current: RequirementAnalysis | None,
    ) -> RequirementAnalysis:
        rounds = self._audits.list_rounds(requirement.id)
        now = self._clock.now()
        analysis_id = AnalysisId(str(uuid.uuid4()))
        return build_analysis(
            requirement.id,
            candidate,
            clarifications,
            document_references,
            analysis_id=analysis_id,
            round_number=len(rounds) + 1,
            provenance=Provenance(now, candidate["model"], candidate["prompt_version"]),
            source_requirement_version=requirement.version,
            carried_intent_proposals=_decided_intent(current),
            has_source_outcome=requirement.desired_outcome is not None,
            source_desired_outcome=(
                requirement.desired_outcome.value
                if requirement.desired_outcome is not None
                else None
            ),
            version=current.version + 1 if current is not None else 1,
        )

    def _persist_round(
        self,
        analysis: RequirementAnalysis,
        candidate: RequirementAnalysisCandidate,
        previous_active: tuple[ClarificationQuestion, ...],
    ) -> AnalysisWorkspace:
        reconciled = reconcile_round(analysis, candidate, previous_active)
        for question in reconciled.superseded_questions:
            self._audits.save_question(question)
        self._audits.append_round(reconciled.round)
        for question in reconciled.new_questions:
            self._audits.add_question(question)
        self._analyses.save(analysis)
        self._knowledge.schedule(analysis.requirement_id)
        active_questions = tuple(
            item for item in self._audits.list_questions(analysis.requirement_id) if item.is_active
        )
        self._suggestion_scheduler.schedule(analysis.requirement_id, active_questions)
        return AnalysisWorkspace(
            analysis,
            active_questions,
            reconciled.round.question_changes,
            self._references.stale_analysis(analysis),
            self._overdue_reviews(analysis),
        )

    def _overdue_reviews(self, analysis: RequirementAnalysis) -> Mapping[str, date]:
        """Which documents its proposals cite are past their review date: a flag, not a block."""
        if self._reviews is None:
            return {}
        cited = {
            citation.document_id
            for proposal in analysis.intent_proposals
            for citation in proposal.reference_evidence
        }
        return self._reviews.overdue_reviews(tuple(cited), self._clock.now().date())

    def _active_snapshot_matches(
        self,
        requirement_id: RequirementId,
        expected: tuple[ClarificationQuestion, ...],
    ) -> bool:
        current = {
            item.id: item.version
            for item in self._audits.list_questions(requirement_id)
            if item.is_active
        }
        return current == {item.id: item.version for item in expected}

    def _require_requirement(self, requirement_id: RequirementId) -> Requirement:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        return requirement

    def _require_analysis(self, requirement_id: RequirementId) -> RequirementAnalysis:
        analysis = self._analyses.get_by_requirement_id(requirement_id)
        if analysis is None:
            raise RequirementAnalysisNotFoundError(
                f"Analysis for requirement {requirement_id.value!r} not found."
            )
        return analysis

    def _require_question(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> ClarificationQuestion:
        question = self._audits.get_question(requirement_id, question_id)
        if question is None:
            raise ClarificationQuestionNotFoundError(
                f"Clarification question {question_id.value!r} not found."
            )
        return question

    def _require_team_member(
        self, requirement_id: RequirementId, actor: ActorProfile
    ) -> RequirementAccess:
        return self._authorization.require(requirement_id, actor, RequirementPermission.MEMBER)

    def _assignment_target(self, access: RequirementAccess, actor_id: ActorId) -> ActorProfile:
        if not access.includes(actor_id):
            raise AuthorizationDeniedError(
                "Question assignees must be the Requirement owner or an assigned reviewer."
            )
        actor = self._actors.get(actor_id)
        if actor is None:
            raise ActorNotFoundError(f"Actor {actor_id.value!r} is not known to this workspace.")
        return actor

    def _require_answerer(
        self,
        requirement_id: RequirementId,
        question: ClarificationQuestion,
        actor: ActorProfile,
        *,
        allow_team: bool = False,
    ) -> None:
        self._authorization.require_answerer(
            requirement_id,
            actor,
            question.assignee.id if question.assignee is not None else None,
            allow_team=allow_team,
        )


def _analysis_id(analysis: RequirementAnalysis | None) -> AnalysisId | None:
    return analysis.id if analysis is not None else None


def _decided_intent(
    analysis: RequirementAnalysis | None,
) -> tuple[IntentProposal, ...]:
    if analysis is None:
        return ()
    return tuple(
        item
        for item in analysis.intent_proposals
        if item.status is not IntentProposalStatus.PENDING
    )


def _question_context(question: ClarificationQuestion) -> ActiveQuestionContext:
    return ActiveQuestionContext(
        question_id=question.id.value,
        kind=question.kind,
        subject=question.subject,
        rationale=question.rationale,
        source=question.source,
    )


def _round_audit_question_ids(round_: AnalysisRound) -> frozenset[QuestionId]:
    """Include terminal questions referenced by reconciliation records in history."""
    return frozenset(
        (
            *round_.question_ids,
            *(item.question_id for item in round_.question_changes),
            *(
                item.replacement_question_id
                for item in round_.question_changes
                if item.replacement_question_id is not None
            ),
        )
    )
