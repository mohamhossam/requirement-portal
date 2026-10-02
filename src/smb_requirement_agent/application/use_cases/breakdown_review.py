"""Generate and mutate the evidence-backed Slice 8 breakdown review."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
    BreakdownReviewNotFoundError,
    BreakdownReviewStaleError,
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
    ReviewFlagNotFoundError,
)
from smb_requirement_agent.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidencePort
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.ports.story_quality_evaluator import StoryQualityEvidence
from smb_requirement_agent.application.ports.story_quality_repository import (
    StoryQualityRepositoryPort,
)
from smb_requirement_agent.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.application.use_cases.breakdown_review_evidence import (
    ReviewEvidence,
    evidence_fingerprint,
)
from smb_requirement_agent.application.use_cases.breakdown_review_policy import (
    REVIEW_RULESET_VERSION,
    BreakdownReviewPolicy,
)
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.application.use_cases.story_quality import (
    ValidateStory,
    story_set_fingerprint,
)
from smb_requirement_agent.domain.analysis.entities import (
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.value_objects import QuestionId
from smb_requirement_agent.domain.identity.entities import ActorProfile
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.domain.review.entities import (
    BreakdownReview,
    Decision,
    DecisionId,
    FlagCategory,
    FlagId,
    FlagStatus,
    ResolutionPolicy,
)
from smb_requirement_agent.domain.review.errors import InvalidReviewContentError
from smb_requirement_agent.domain.story.quality import FeatureQualitySnapshot, InvestAssessment


@dataclass(frozen=True)
class BreakdownReviewView:
    review: BreakdownReview
    fresh: bool


@dataclass(frozen=True)
class GeneratedBreakdownReview:
    view: BreakdownReviewView
    created: bool


@dataclass(frozen=True)
class OpenQuestionResolution:
    analysis: RequirementAnalysis
    review: BreakdownReviewView


class ReviewEvidenceLoader:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        analyses: RequirementAnalysisRepositoryPort,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
        audits: AnalysisAuditRepositoryPort,
        references: ReferenceEvidencePort,
    ) -> None:
        self._requirements = requirements
        self._references = references
        self._analyses = analyses
        self._epics = epics
        self._features = features
        self._stories = stories
        self._audits = audits

    def load(self, requirement_id: RequirementId) -> ReviewEvidence:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        analysis = self._analyses.get_by_requirement_id(requirement_id)
        if analysis is None:
            raise RequirementAnalysisNotFoundError(
                f"Analysis for requirement {requirement_id.value!r} not found."
            )
        epic = self._epics.get_by_requirement_id(requirement_id)
        features = tuple(self._features.get_by_epic_id(epic.id)) if epic else ()
        stories = tuple(
            story for feature in features for story in self._stories.get_by_feature_id(feature.id)
        )
        questions = tuple(
            item for item in self._audits.list_questions(requirement_id) if item.is_active
        )
        return ReviewEvidence(
            requirement,
            analysis,
            epic,
            features,
            stories,
            questions,
            self._references.stale_analysis(analysis),
        )


class RefreshSavedBreakdownReview:
    """Assemble current saved evidence; caller owns the atomic write boundary."""

    def __init__(
        self,
        evidence: ReviewEvidenceLoader,
        reviews: BreakdownReviewRepositoryPort,
        quality: StoryQualityRepositoryPort,
        policy: BreakdownReviewPolicy,
        clock: ClockPort,
        knowledge: ArchitectureKnowledgeRepositoryPort,
    ) -> None:
        self._evidence = evidence
        self._reviews = reviews
        self._quality = quality
        self._policy = policy
        self._clock = clock
        self._knowledge = knowledge

    def execute(self, requirement_id: RequirementId) -> BreakdownReview:
        evidence = self._evidence.load(requirement_id)
        assessments: list[InvestAssessment] = []
        for feature in evidence.features:
            siblings = tuple(s for s in evidence.stories if s.feature_id == feature.id)
            snapshot = self._quality.get(feature.id)
            if snapshot is not None and snapshot.source_fingerprint == story_set_fingerprint(
                siblings,
                StoryQualityEvidence.from_context(evidence.requirement, evidence.analysis, feature),
            ):
                assessments.extend(snapshot.assessments)
        review = replace(
            self._policy.build(evidence, tuple(assessments), self._clock.now()),
            knowledge_version=self._knowledge.active().id,
        )
        existing = self._reviews.get(requirement_id)
        if existing is not None:
            review = _carry_forward_decisions(review, existing)
        self._reviews.save(review)
        return review


class GenerateBreakdownReview:
    def __init__(
        self,
        evidence: ReviewEvidenceLoader,
        reviews: BreakdownReviewRepositoryPort,
        validator: ValidateStory,
        policy: BreakdownReviewPolicy,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        knowledge: ArchitectureKnowledgeRepositoryPort,
        *,
        authorization: RequirementAccessService,
        quality: StoryQualityRepositoryPort,
    ) -> None:
        self._quality = quality
        self._authorization = authorization
        self._evidence = evidence
        self._reviews = reviews
        self._validator = validator
        self._policy = policy
        self._clock = clock
        self._transactions = transactions
        self._knowledge = knowledge

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId
    ) -> GeneratedBreakdownReview:
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(requirement_id=requirement_id),
        )

    def _execute(self, requirement_id: RequirementId) -> GeneratedBreakdownReview:
        evidence = self._evidence.load(requirement_id)
        evidence.requirement.require_active()
        active_knowledge_version = self._knowledge.active().id
        if not _architecture_knowledge_is_current(evidence, active_knowledge_version):
            raise BreakdownReviewStaleError(
                "Architecture mappings were generated from an inactive knowledge release. "
                "Remap the breakdown and try again."
            )
        with self._transactions.external_call():
            assessments = self._assess(evidence)
        review = replace(
            self._policy.build(evidence, assessments, self._clock.now()),
            knowledge_version=active_knowledge_version,
        )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            if evidence_fingerprint(self._evidence.load(requirement_id)) != (
                review.evidence_fingerprint
            ):
                raise BreakdownReviewStaleError(
                    "The breakdown changed while its review was generated. Refresh and try again."
                )
            if self._knowledge.active().id != active_knowledge_version:
                raise BreakdownReviewStaleError(
                    "The active architecture knowledge release changed while the review was "
                    "generated. Refresh and try again."
                )
            existing = self._reviews.get(requirement_id)
            if existing is not None:
                review = _carry_forward_decisions(review, existing)
            for feature in evidence.features:
                siblings = tuple(s for s in evidence.stories if s.feature_id == feature.id)
                self._quality.save(
                    FeatureQualitySnapshot(
                        feature.id,
                        story_set_fingerprint(
                            siblings,
                            StoryQualityEvidence.from_context(
                                evidence.requirement, evidence.analysis, feature
                            ),
                        ),
                        tuple(a for a in assessments if any(s.id == a.story_id for s in siblings)),
                        self._clock.now(),
                    )
                )
            self._reviews.save(review)
        return GeneratedBreakdownReview(BreakdownReviewView(review, True), existing is None)

    def _assess(self, evidence: ReviewEvidence) -> tuple[InvestAssessment, ...]:
        result: list[InvestAssessment] = []
        for feature in evidence.features:
            siblings = tuple(item for item in evidence.stories if item.feature_id == feature.id)
            snapshot = self._quality.get(feature.id)
            if snapshot is not None and snapshot.source_fingerprint == story_set_fingerprint(
                siblings,
                StoryQualityEvidence.from_context(evidence.requirement, evidence.analysis, feature),
            ):
                result.extend(snapshot.assessments)
            else:
                result.extend(
                    self._validator.assess(
                        story,
                        siblings,
                        StoryQualityEvidence.from_context(
                            evidence.requirement, evidence.analysis, feature
                        ),
                    )
                    for story in siblings
                )
        return tuple(result)


class GetBreakdownReview:
    def __init__(
        self,
        evidence: ReviewEvidenceLoader,
        reviews: BreakdownReviewRepositoryPort,
        knowledge: ArchitectureKnowledgeRepositoryPort,
    ) -> None:
        self._evidence = evidence
        self._reviews = reviews
        self._knowledge = knowledge

    def execute(self, requirement_id: RequirementId) -> BreakdownReviewView:
        review = self._reviews.get(requirement_id)
        try:
            evidence = self._evidence.load(requirement_id)
        except RequirementAnalysisNotFoundError:
            if review is not None:
                return BreakdownReviewView(review, False)
            raise
        if review is None:
            raise BreakdownReviewNotFoundError(
                f"No breakdown review exists for requirement {requirement_id.value!r}."
            )
        active_knowledge_version = self._knowledge.active().id
        return BreakdownReviewView(
            review,
            review.ruleset_version == REVIEW_RULESET_VERSION
            and review.evidence_fingerprint == evidence_fingerprint(evidence)
            and review.knowledge_version == active_knowledge_version
            and _architecture_knowledge_is_current(evidence, active_knowledge_version),
        )


class RecordDecision:
    def __init__(
        self,
        current: GetBreakdownReview,
        reviews: BreakdownReviewRepositoryPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
    ) -> None:
        self._authorization = authorization
        self._current = current
        self._reviews = reviews
        self._clock = clock
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        decision: str,
        rationale: str,
        expected_fingerprint: str,
        expected_version: int,
        actor: ActorProfile,
        target_flag_id: FlagId | None = None,
    ) -> BreakdownReviewView:
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(
                requirement_id=requirement_id,
                decision=decision,
                rationale=rationale,
                expected_fingerprint=expected_fingerprint,
                expected_version=expected_version,
                actor=actor,
                target_flag_id=target_flag_id,
            ),
        )

    def _execute(
        self,
        requirement_id: RequirementId,
        decision: str,
        rationale: str,
        expected_fingerprint: str,
        expected_version: int,
        actor: ActorProfile,
        target_flag_id: FlagId | None = None,
    ) -> BreakdownReviewView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            review = _require_current(
                self._current, requirement_id, expected_fingerprint, expected_version
            )
            if target_flag_id is not None and review.find_flag(target_flag_id) is None:
                raise ReviewFlagNotFoundError(f"Review flag {target_flag_id.value!r} not found.")
            updated = review.record(
                Decision(
                    DecisionId(str(uuid.uuid4())),
                    decision,
                    rationale,
                    self._clock.now(),
                    target_flag_id,
                    actor.snapshot(),
                )
            )
            self._reviews.save(updated)
        return BreakdownReviewView(updated, True)


class ResolveFlag:
    def __init__(
        self,
        current: GetBreakdownReview,
        reviews: BreakdownReviewRepositoryPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
    ) -> None:
        self._authorization = authorization
        self._current = current
        self._reviews = reviews
        self._clock = clock
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        flag_id: FlagId,
        decision: str,
        rationale: str,
        expected_fingerprint: str,
        expected_version: int,
        actor: ActorProfile,
    ) -> BreakdownReviewView:
        return self._authorization.execute_mutation(
            requirement_id,
            actor,
            RequirementPermission.MEMBER,
            lambda: self._execute(
                requirement_id=requirement_id,
                flag_id=flag_id,
                decision=decision,
                rationale=rationale,
                expected_fingerprint=expected_fingerprint,
                expected_version=expected_version,
                actor=actor,
            ),
        )

    def _execute(
        self,
        requirement_id: RequirementId,
        flag_id: FlagId,
        decision: str,
        rationale: str,
        expected_fingerprint: str,
        expected_version: int,
        actor: ActorProfile,
    ) -> BreakdownReviewView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            review = _require_current(
                self._current, requirement_id, expected_fingerprint, expected_version
            )
            if review.find_flag(flag_id) is None:
                raise ReviewFlagNotFoundError(f"Review flag {flag_id.value!r} not found.")
            updated = review.resolve(
                flag_id,
                Decision(
                    DecisionId(str(uuid.uuid4())),
                    decision,
                    rationale,
                    self._clock.now(),
                    flag_id,
                    actor.snapshot(),
                ),
            )
            self._reviews.save(updated)
        return BreakdownReviewView(updated, True)


class ResolveOpenQuestion:
    def __init__(
        self,
        current: GetBreakdownReview,
        reviews: BreakdownReviewRepositoryPort,
        collaboration: AnalysisCollaboration,
        clock: ClockPort,
        transactions: TransactionManagerPort,
    ) -> None:
        self._current = current
        self._reviews = reviews
        self._collaboration = collaboration
        self._clock = clock
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        flag_id: FlagId,
        answer: str,
        expected_fingerprint: str,
        expected_version: int,
        actor: ActorProfile,
    ) -> OpenQuestionResolution:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            review = _require_current(
                self._current, requirement_id, expected_fingerprint, expected_version
            )
            flag = review.find_flag(flag_id)
            if flag is None:
                raise ReviewFlagNotFoundError(f"Review flag {flag_id.value!r} not found.")
            if (
                flag.category is not FlagCategory.OPEN_QUESTION
                or flag.resolution_policy is not ResolutionPolicy.CLARIFICATION
                or flag.status is not FlagStatus.OPEN
            ):
                raise InvalidReviewContentError(
                    "Only a current open-question flag can be answered."
                )
            question_id = QuestionId(flag.source.item_id)
            workspace = self._collaboration.resolve(
                requirement_id,
                question_id,
                answer,
                self._collaboration.question(requirement_id, question_id).version,
                actor,
            )
            updated = review.record(
                Decision(
                    DecisionId(str(uuid.uuid4())),
                    "Answered open question",
                    answer,
                    self._clock.now(),
                    flag_id,
                    actor.snapshot(),
                )
            )
            self._reviews.save(updated)
        return OpenQuestionResolution(workspace.analysis, BreakdownReviewView(updated, False))


def _architecture_knowledge_is_current(
    evidence: ReviewEvidence, active_knowledge_version: str
) -> bool:
    impacts = (
        *(feature.architecture for feature in evidence.features),
        *(story.architecture for story in evidence.stories),
    )
    return all(
        impact is None or impact.knowledge_version == active_knowledge_version for impact in impacts
    )


def _carry_forward_decisions(
    candidate: BreakdownReview, existing: BreakdownReview
) -> BreakdownReview:
    current_flag_ids = {item.id for item in candidate.flags}
    carried = candidate
    for decision in existing.decisions:
        if decision.target_flag_id is None or decision.target_flag_id in current_flag_ids:
            carried = carried.record(decision)
    resolved = {
        item.id: item.resolution_decision_id
        for item in existing.flags
        if item.status is FlagStatus.RESOLVED and item.id in current_flag_ids
    }
    for flag_id, decision_id in resolved.items():
        if decision_id is None:  # pragma: no cover - protected by Flag invariant
            continue
        decision = next(item for item in carried.decisions if item.id == decision_id)
        carried = carried.resolve(flag_id, decision)
    governance = existing
    if candidate.evidence_fingerprint != existing.evidence_fingerprint:
        governance = existing.request_revision()
    return replace(
        carried,
        status=governance.status,
        submitted_fingerprint=governance.submitted_fingerprint,
        approvals=existing.approvals,
        comments=existing.comments,
        version=existing.version + 1,
    )


def _require_current(
    current: GetBreakdownReview,
    requirement_id: RequirementId,
    expected_fingerprint: str,
    expected_version: int,
) -> BreakdownReview:
    view = current.execute(requirement_id)
    if view.review.version != expected_version:
        raise ArtifactVersionConflictError(
            f"Breakdown review changed from version {expected_version} to "
            f"{view.review.version}. Reload it."
        )
    if not view.fresh or view.review.evidence_fingerprint != expected_fingerprint.strip():
        raise BreakdownReviewStaleError(
            "The review evidence changed. Refresh the breakdown review and try again."
        )
    return view.review
