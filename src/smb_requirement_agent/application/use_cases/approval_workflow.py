"""Actor-attributed Slice 9 review and approval orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    ApprovalPolicyBlockedError,
    ApprovalWorkflowNotReadyError,
    ArtifactVersionConflictError,
    BreakdownReviewNotFoundError,
    EpicNotFoundError,
    FeatureNotFoundError,
    RequirementNotFoundError,
    StoryNotFoundError,
)
from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.approval_policy import (
    ApprovalPolicy,
    artifact_fingerprint,
    breakdown_fingerprint,
)
from smb_requirement_agent.application.use_cases.breakdown_review import ReviewEvidenceLoader
from smb_requirement_agent.application.use_cases.breakdown_review_evidence import (
    ReviewEvidence,
    evidence_fingerprint,
)
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.identity.entities import (
    ActorProfile,
    RequirementAccess,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.domain.review.entities import BreakdownReview, BreakdownStatus, FlagId
from smb_requirement_agent.domain.review.errors import InvalidReviewContentError
from smb_requirement_agent.domain.shared.approval import (
    Approval,
    ApprovalDecision,
    ApprovalId,
    ApprovalTarget,
    ApprovalTargetKind,
    ReviewComment,
)
from smb_requirement_agent.domain.shared.generation import GenerationStatus
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.value_objects import StoryId


@dataclass(frozen=True)
class ArtifactApprovalState:
    target: ApprovalTarget
    parent_id: str | None
    label: str
    status: GenerationStatus
    fingerprint: str
    version: int
    current_approval: Approval | None
    approvals: tuple[Approval, ...]


@dataclass(frozen=True)
class ApprovalCompletion:
    epic_approved: int
    epic_total: int
    features_approved: int
    features_total: int
    stories_approved: int
    stories_total: int


@dataclass(frozen=True)
class ApprovalWorkflowView:
    review: BreakdownReview
    status: BreakdownStatus
    subject_fingerprint: str | None
    artifacts: tuple[ArtifactApprovalState, ...]
    completion: ApprovalCompletion
    readiness_reasons: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    can_submit: bool
    can_approve_breakdown: bool
    can_comment: bool


class ApprovalRecorder:
    """Create content-bound decisions after enforcing Requirement team access."""

    def __init__(
        self,
        access: AccessRepositoryPort,
        clock: ClockPort,
        authorization: RequirementAccessService,
    ) -> None:
        self._access = access
        self._clock = clock
        self._authorization = authorization

    def require_member(self, requirement_id: RequirementId, actor: ActorProfile) -> None:
        self._authorization.require(requirement_id, actor, RequirementPermission.MEMBER)

    def require_owner(self, requirement_id: RequirementId, actor: ActorProfile) -> None:
        self._authorization.require(requirement_id, actor, RequirementPermission.OWNER)

    def access(self, requirement_id: RequirementId) -> RequirementAccess:
        return self._access.get_requirement(requirement_id) or RequirementAccess(requirement_id)

    def decision(
        self,
        target: ApprovalTarget,
        fingerprint: str,
        actor: ActorProfile,
        decision: ApprovalDecision,
        rationale: str | None = None,
    ) -> Approval:
        return Approval(
            ApprovalId(str(uuid.uuid4())),
            target,
            decision,
            fingerprint,
            actor.snapshot(),
            self._clock.now(),
            rationale,
        )


class GetApprovalWorkflow:
    def __init__(
        self,
        evidence: ReviewEvidenceLoader,
        reviews: BreakdownReviewRepositoryPort,
        recorder: ApprovalRecorder,
        policy: ApprovalPolicy,
    ) -> None:
        self._evidence = evidence
        self._reviews = reviews
        self._recorder = recorder
        self._policy = policy

    def execute(self, requirement_id: RequirementId, actor: ActorProfile) -> ApprovalWorkflowView:
        evidence = self._evidence.load(requirement_id)
        review = self._reviews.get(requirement_id)
        if review is None:
            raise BreakdownReviewNotFoundError(
                f"No breakdown review exists for requirement {requirement_id.value!r}."
            )
        return self.build(evidence, review, actor)

    def build(
        self,
        evidence: ReviewEvidence,
        review: BreakdownReview,
        actor: ActorProfile,
    ) -> ApprovalWorkflowView:
        artifacts = _artifact_states(evidence)
        completion = ApprovalCompletion(
            epic_approved=sum(
                item.current_approval is not None
                for item in artifacts
                if item.target.kind is ApprovalTargetKind.EPIC
            ),
            epic_total=sum(item.target.kind is ApprovalTargetKind.EPIC for item in artifacts),
            features_approved=sum(
                item.current_approval is not None
                for item in artifacts
                if item.target.kind is ApprovalTargetKind.FEATURE
            ),
            features_total=sum(
                item.target.kind is ApprovalTargetKind.FEATURE for item in artifacts
            ),
            stories_approved=sum(
                item.current_approval is not None
                for item in artifacts
                if item.target.kind is ApprovalTargetKind.STORY
            ),
            stories_total=sum(item.target.kind is ApprovalTargetKind.STORY for item in artifacts),
        )
        readiness = _readiness(evidence, review, artifacts)
        subject = _subject(evidence, review)
        status = review.status
        if status in (BreakdownStatus.UNDER_REVIEW, BreakdownStatus.APPROVED) and (
            subject != review.submitted_fingerprint
            or review.evidence_fingerprint != evidence_fingerprint(evidence)
        ):
            status = BreakdownStatus.NEEDS_REVISION
        active_blocking_questions = sum(
            item.is_active and item.is_blocker for item in evidence.questions
        )
        blockers = self._policy.blocking_reasons(
            review, active_blocking_questions=active_blocking_questions
        )
        access = self._recorder.access(evidence.requirement.id)
        is_owner = access.is_owner(actor.id)
        is_member = access.includes(actor.id)
        can_submit = (
            is_owner
            and not readiness
            and status
            in (
                BreakdownStatus.GENERATED,
                BreakdownStatus.NEEDS_REVISION,
            )
        )
        can_approve = (
            is_owner
            and not readiness
            and not blockers
            and status is BreakdownStatus.UNDER_REVIEW
            and subject == review.submitted_fingerprint
        )
        return ApprovalWorkflowView(
            review,
            status,
            subject,
            artifacts,
            completion,
            readiness,
            blockers,
            can_submit,
            can_approve,
            is_member,
        )


class SubmitForReview:
    def __init__(
        self,
        current: GetApprovalWorkflow,
        reviews: BreakdownReviewRepositoryPort,
        recorder: ApprovalRecorder,
        transactions: TransactionManagerPort,
    ) -> None:
        self._current = current
        self._reviews = reviews
        self._recorder = recorder
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        actor: ActorProfile,
        expected_fingerprint: str,
        expected_version: int,
    ) -> ApprovalWorkflowView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._recorder.require_owner(requirement_id, actor)
            view = self._current.execute(requirement_id, actor)
            _match_review_version(view.review, expected_version)
            if view.readiness_reasons:
                raise ApprovalWorkflowNotReadyError(" ".join(view.readiness_reasons))
            if view.subject_fingerprint != expected_fingerprint.strip():
                raise ApprovalWorkflowNotReadyError(
                    "The breakdown changed. Reload the approval workflow and try again."
                )
            review = view.review
            if view.status is BreakdownStatus.NEEDS_REVISION:
                review = review.request_revision()
            updated = review.submit(expected_fingerprint)
            self._reviews.save(updated)
            return self._current.execute(requirement_id, actor)


class ApproveStory:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
        recorder: ApprovalRecorder,
        transactions: TransactionManagerPort,
    ) -> None:
        self._requirements = requirements
        self._epics = epics
        self._features = features
        self._stories = stories
        self._recorder = recorder
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        actor: ActorProfile,
        expected_version: int,
        expected_fingerprint: str,
        rationale: str | None = None,
    ) -> UserStory:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            story = _story(
                self._requirements,
                self._epics,
                self._features,
                self._stories,
                requirement_id,
                feature_id,
                story_id,
            )
            self._recorder.require_member(requirement_id, actor)
            fingerprint = artifact_fingerprint(story)
            _match_expected(fingerprint, expected_fingerprint)
            if story.current_approval(fingerprint) is not None:
                return story
            if story.version != expected_version:
                raise ArtifactVersionConflictError(
                    f"Story changed from version {expected_version} to {story.version}. Reload it."
                )
            updated = story.approve(
                self._recorder.decision(
                    ApprovalTarget(ApprovalTargetKind.STORY, story.id.value),
                    fingerprint,
                    actor,
                    ApprovalDecision.APPROVED,
                    rationale,
                )
            )
            self._stories.save(updated)
            return updated


class RejectStory:
    def __init__(
        self,
        current: GetApprovalWorkflow,
        requirements: RequirementRepositoryPort,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
        reviews: BreakdownReviewRepositoryPort,
        recorder: ApprovalRecorder,
        transactions: TransactionManagerPort,
    ) -> None:
        self._current = current
        self._requirements = requirements
        self._epics = epics
        self._features = features
        self._stories = stories
        self._reviews = reviews
        self._recorder = recorder
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        actor: ActorProfile,
        reason: str,
        expected_fingerprint: str,
        expected_version: int,
        expected_review_version: int,
    ) -> UserStory:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._recorder.require_member(requirement_id, actor)
            workflow = self._current.execute(requirement_id, actor)
            _match_review_version(workflow.review, expected_review_version)
            if (
                workflow.status is not BreakdownStatus.UNDER_REVIEW
                or workflow.subject_fingerprint != expected_fingerprint.strip()
                or workflow.review.submitted_fingerprint != expected_fingerprint.strip()
            ):
                raise ApprovalWorkflowNotReadyError(
                    "Story rejection requires the current submitted breakdown."
                )
            story = _story(
                self._requirements,
                self._epics,
                self._features,
                self._stories,
                requirement_id,
                feature_id,
                story_id,
            )
            if story.version != expected_version:
                raise ArtifactVersionConflictError(
                    f"Story changed from version {expected_version} to {story.version}. Reload it."
                )
            updated = story.reject(
                self._recorder.decision(
                    ApprovalTarget(ApprovalTargetKind.STORY, story.id.value),
                    artifact_fingerprint(story),
                    actor,
                    ApprovalDecision.REJECTED,
                    reason,
                )
            )
            self._stories.save(updated)
            self._reviews.save(workflow.review.request_revision())
            return updated


class ApproveBreakdown:
    def __init__(
        self,
        current: GetApprovalWorkflow,
        reviews: BreakdownReviewRepositoryPort,
        recorder: ApprovalRecorder,
        transactions: TransactionManagerPort,
    ) -> None:
        self._current = current
        self._reviews = reviews
        self._recorder = recorder
        self._transactions = transactions

    def execute(
        self,
        requirement_id: RequirementId,
        actor: ActorProfile,
        expected_fingerprint: str,
        expected_version: int,
        rationale: str | None = None,
    ) -> ApprovalWorkflowView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._recorder.require_owner(requirement_id, actor)
            view = self._current.execute(requirement_id, actor)
            if (
                view.status is BreakdownStatus.APPROVED
                and view.subject_fingerprint == expected_fingerprint.strip()
                and any(item.attests_to(expected_fingerprint) for item in view.review.approvals)
            ):
                return view
            _match_review_version(view.review, expected_version)
            if view.readiness_reasons:
                raise ApprovalWorkflowNotReadyError(" ".join(view.readiness_reasons))
            if view.blocking_reasons:
                raise ApprovalPolicyBlockedError(" ".join(view.blocking_reasons))
            if (
                not view.can_approve_breakdown
                or view.subject_fingerprint != expected_fingerprint.strip()
            ):
                raise ApprovalWorkflowNotReadyError(
                    "The submitted breakdown is not current and ready for final approval."
                )
            approval = self._recorder.decision(
                ApprovalTarget(ApprovalTargetKind.BREAKDOWN, requirement_id.value),
                expected_fingerprint,
                actor,
                ApprovalDecision.APPROVED,
                rationale,
            )
            self._reviews.save(view.review.approve_breakdown(approval))
            return self._current.execute(requirement_id, actor)


class AddReviewComment:
    def __init__(
        self,
        current: GetApprovalWorkflow,
        reviews: BreakdownReviewRepositoryPort,
        recorder: ApprovalRecorder,
        transactions: TransactionManagerPort,
        clock: ClockPort,
    ) -> None:
        self._current = current
        self._reviews = reviews
        self._recorder = recorder
        self._transactions = transactions
        self._clock = clock

    def execute(
        self,
        requirement_id: RequirementId,
        actor: ActorProfile,
        target: ApprovalTarget,
        body: str,
        expected_version: int,
    ) -> ApprovalWorkflowView:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._recorder.require_member(requirement_id, actor)
            view = self._current.execute(requirement_id, actor)
            _match_review_version(view.review, expected_version)
            _require_comment_target(view, requirement_id, target)
            updated = view.review.add_comment(
                ReviewComment(str(uuid.uuid4()), target, body, actor.snapshot(), self._clock.now())
            )
            self._reviews.save(updated)
            return self._current.execute(requirement_id, actor)


def _match_review_version(review: BreakdownReview, expected_version: int) -> None:
    if review.version != expected_version:
        raise ArtifactVersionConflictError(
            f"Breakdown review changed from version {expected_version} to "
            f"{review.version}. Reload it."
        )


def _artifact_states(evidence: ReviewEvidence) -> tuple[ArtifactApprovalState, ...]:
    items: list[tuple[ApprovalTargetKind, Epic | Feature | UserStory, str]] = []
    if evidence.epic is not None:
        items.append((ApprovalTargetKind.EPIC, evidence.epic, evidence.epic.name.value))
    items.extend((ApprovalTargetKind.FEATURE, item, item.name.value) for item in evidence.features)
    items.extend((ApprovalTargetKind.STORY, item, item.voice) for item in evidence.stories)
    result: list[ArtifactApprovalState] = []
    for kind, item, label in items:
        fingerprint = artifact_fingerprint(item)
        result.append(
            ArtifactApprovalState(
                ApprovalTarget(kind, item.id.value),
                (
                    item.requirement_id.value
                    if isinstance(item, Epic)
                    else item.epic_id.value
                    if isinstance(item, Feature)
                    else item.feature_id.value
                ),
                label,
                item.status,
                fingerprint,
                item.version,
                item.current_approval(fingerprint),
                item.approvals,
            )
        )
    return tuple(result)


def _readiness(
    evidence: ReviewEvidence,
    review: BreakdownReview,
    artifacts: tuple[ArtifactApprovalState, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if evidence.stale_reference_proposal_ids:
        reasons.append(
            "Cited reference evidence changed. "
            "Re-analyse and reconcile its applicability before approval."
        )
    if not evidence.analysis.is_human_confirmed:
        reasons.append("The current analysis is not owner-confirmed.")
    if evidence.epic is None:
        reasons.append("The breakdown has no Epic.")
    if not evidence.features:
        reasons.append("The breakdown has no Features.")
    story_feature_ids = {item.feature_id for item in evidence.stories}
    missing_story_features = [
        item.id.value for item in evidence.features if item.id not in story_feature_ids
    ]
    if missing_story_features:
        reasons.append("Every Feature must have at least one Story.")
    if any(item.is_stale for item in ([evidence.epic] if evidence.epic else [])) or any(
        item.is_stale for item in (*evidence.features, *evidence.stories)
    ):
        reasons.append("All backlog artifacts must be current.")
    if any(
        item.current_approval is None or item.status is not GenerationStatus.APPROVED
        for item in artifacts
    ):
        reasons.append("Every Epic, Feature, and Story needs a current attributed approval.")
    if review.evidence_fingerprint != evidence_fingerprint(evidence):
        reasons.append("The breakdown review is stale and must be refreshed.")
    return tuple(reasons)


def _subject(evidence: ReviewEvidence, review: BreakdownReview) -> str | None:
    if evidence.epic is None or not evidence.features:
        return None
    return breakdown_fingerprint(
        evidence.requirement,
        evidence.analysis,
        evidence.epic,
        evidence.features,
        evidence.stories,
        review,
    )


def _match_expected(actual: str, expected: str | None) -> None:
    if expected is not None and actual != expected.strip():
        raise ApprovalWorkflowNotReadyError(
            "The artifact changed. Reload it before approving the current content."
        )


def _story(
    requirements: RequirementRepositoryPort,
    epics: EpicRepositoryPort,
    features: FeatureRepositoryPort,
    stories: StoryRepositoryPort,
    requirement_id: RequirementId,
    feature_id: FeatureId,
    story_id: StoryId,
) -> UserStory:
    if requirements.get(requirement_id) is None:
        raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
    epic = epics.get_by_requirement_id(requirement_id)
    if epic is None:
        raise EpicNotFoundError(f"No Epic exists for requirement {requirement_id.value!r}.")
    if features.get(epic.id, feature_id) is None:
        raise FeatureNotFoundError(f"Feature {feature_id.value!r} not found.")
    story = stories.get(feature_id, story_id)
    if story is None:
        raise StoryNotFoundError(f"Story {story_id.value!r} not found.")
    return story


def _require_comment_target(
    view: ApprovalWorkflowView,
    requirement_id: RequirementId,
    target: ApprovalTarget,
) -> None:
    if target.kind is ApprovalTargetKind.BREAKDOWN and target.item_id == requirement_id.value:
        return
    if target.kind is ApprovalTargetKind.FLAG and view.review.find_flag(FlagId(target.item_id)):
        return
    if any(item.target == target for item in view.artifacts):
        return
    raise InvalidReviewContentError("The comment target is not part of this breakdown review.")
