"""Domain model for a durable, evidence-backed breakdown review."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from smb_requirement_agent.breakdown.domain.story.quality import InvestAssessment
from smb_requirement_agent.governance.domain.review.errors import (
    FlagResolutionConflictError,
    FlagResolutionNotAllowedError,
    InvalidReviewContentError,
    InvalidReviewTransitionError,
)
from smb_requirement_agent.shared_kernel.actors import ActorSnapshot
from smb_requirement_agent.shared_kernel.approval import (
    Approval,
    ApprovalDecision,
    ApprovalTargetKind,
    ReviewComment,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import require_aware


def _text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidReviewContentError(f"Review {field} must not be blank.")
    return stripped


@dataclass(frozen=True, order=True)
class FlagId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "flag id"))


@dataclass(frozen=True, order=True)
class DependencyId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "dependency id"))


@dataclass(frozen=True, order=True)
class RiskId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "risk id"))


@dataclass(frozen=True, order=True)
class RecommendationId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "recommendation id"))


@dataclass(frozen=True, order=True)
class DecisionId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "decision id"))


class ReviewSourceKind(StrEnum):
    ANALYSIS = "analysis"
    EPIC = "epic"
    FEATURE = "feature"
    STORY = "story"


class DependencyEvidenceKind(StrEnum):
    POTENTIAL = "potential"
    CATALOGUED = "catalogued"


class FlagSeverity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"


class FlagCategory(StrEnum):
    OPEN_QUESTION = "open_question"
    ASSUMPTION = "assumption"
    AMBIGUITY = "ambiguity"
    DEPENDENCY = "dependency"
    ARCHITECTURE = "architecture"
    QUALITY = "quality"
    STALENESS = "staleness"


class FlagStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class ResolutionPolicy(StrEnum):
    DECISION = "decision"
    CLARIFICATION = "clarification"
    SOURCE_ACTION = "source_action"


class BreakdownStatus(StrEnum):
    GENERATED = "generated"
    UNDER_REVIEW = "under_review"
    NEEDS_REVISION = "needs_revision"
    APPROVED = "approved"


@dataclass(frozen=True)
class ReviewSource:
    kind: ReviewSourceKind
    item_id: str
    label: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _text(self.item_id, "source item id"))
        object.__setattr__(self, "label", _text(self.label, "source label"))


@dataclass(frozen=True)
class Dependency:
    id: DependencyId
    description: str
    source: ReviewSource
    evidence_kind: DependencyEvidenceKind

    def __post_init__(self) -> None:
        object.__setattr__(self, "description", _text(self.description, "dependency description"))


@dataclass(frozen=True)
class Risk:
    id: RiskId
    severity: FlagSeverity
    description: str
    source: ReviewSource

    def __post_init__(self) -> None:
        object.__setattr__(self, "description", _text(self.description, "risk description"))


@dataclass(frozen=True)
class Recommendation:
    id: RecommendationId
    action: str
    rationale: str
    source: ReviewSource

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", _text(self.action, "recommendation action"))
        object.__setattr__(self, "rationale", _text(self.rationale, "recommendation rationale"))


@dataclass(frozen=True)
class Decision:
    id: DecisionId
    decision: str
    rationale: str
    recorded_at: datetime
    target_flag_id: FlagId | None = None
    recorded_by: ActorSnapshot | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", _text(self.decision, "decision"))
        object.__setattr__(self, "rationale", _text(self.rationale, "decision rationale"))
        require_aware(self.recorded_at, "decision recorded_at")


@dataclass(frozen=True)
class Flag:
    id: FlagId
    category: FlagCategory
    severity: FlagSeverity
    title: str
    detail: str
    source: ReviewSource
    resolution_policy: ResolutionPolicy
    status: FlagStatus = FlagStatus.OPEN
    resolution_decision_id: DecisionId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _text(self.title, "flag title"))
        object.__setattr__(self, "detail", _text(self.detail, "flag detail"))
        if (self.status is FlagStatus.RESOLVED) != (self.resolution_decision_id is not None):
            raise InvalidReviewContentError(
                "A resolved flag must name its resolution decision and an open flag must not."
            )

    def resolve(self, decision_id: DecisionId) -> Flag:
        if self.resolution_policy is not ResolutionPolicy.DECISION:
            raise FlagResolutionNotAllowedError(
                "This flag requires clarification or a source change and cannot be dismissed."
            )
        if self.status is FlagStatus.RESOLVED:
            if self.resolution_decision_id == decision_id:
                return self
            raise FlagResolutionConflictError("This flag was already resolved by another decision.")
        return replace(
            self,
            status=FlagStatus.RESOLVED,
            resolution_decision_id=decision_id,
        )


@dataclass(frozen=True)
class BreakdownReview:
    requirement_id: RequirementId
    generated_at: datetime
    ruleset_version: str
    evidence_fingerprint: str
    dependencies: tuple[Dependency, ...]
    risks: tuple[Risk, ...]
    flags: tuple[Flag, ...]
    recommendations: tuple[Recommendation, ...]
    quality_assessments: tuple[InvestAssessment, ...] = ()
    decisions: tuple[Decision, ...] = ()
    status: BreakdownStatus = BreakdownStatus.GENERATED
    submitted_fingerprint: str | None = None
    approvals: tuple[Approval, ...] = ()
    comments: tuple[ReviewComment, ...] = ()
    version: int = 1
    knowledge_version: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise InvalidReviewContentError("Review version must be a positive integer.")
        require_aware(self.generated_at, "breakdown review generated_at")
        object.__setattr__(self, "ruleset_version", _text(self.ruleset_version, "ruleset version"))
        object.__setattr__(
            self,
            "evidence_fingerprint",
            _text(self.evidence_fingerprint, "evidence fingerprint"),
        )
        self._require_unique("dependency", tuple(item.id.value for item in self.dependencies))
        self._require_unique("risk", tuple(item.id.value for item in self.risks))
        self._require_unique("flag", tuple(item.id.value for item in self.flags))
        self._require_unique(
            "recommendation", tuple(item.id.value for item in self.recommendations)
        )
        self._require_unique("decision", tuple(item.id.value for item in self.decisions))
        self._require_unique("approval", tuple(item.id.value for item in self.approvals))
        self._require_unique("comment", tuple(item.id for item in self.comments))
        self._require_unique(
            "Story quality assessment",
            tuple(item.story_id.value for item in self.quality_assessments),
        )
        flag_ids = {item.id for item in self.flags}
        decision_ids = {item.id for item in self.decisions}
        if any(
            item.target_flag_id is not None and item.target_flag_id not in flag_ids
            for item in self.decisions
        ):
            raise InvalidReviewContentError("A decision targets a flag outside this review.")
        if any(
            item.resolution_decision_id is not None
            and item.resolution_decision_id not in decision_ids
            for item in self.flags
        ):
            raise InvalidReviewContentError("A flag references an unknown resolution decision.")
        if self.submitted_fingerprint is not None:
            submitted = self.submitted_fingerprint.strip()
            if not submitted:
                raise InvalidReviewContentError("A submitted fingerprint must not be blank.")
            object.__setattr__(self, "submitted_fingerprint", submitted)
        if self.status in (BreakdownStatus.UNDER_REVIEW, BreakdownStatus.APPROVED) and (
            self.submitted_fingerprint is None
        ):
            raise InvalidReviewContentError("A submitted or approved review needs a fingerprint.")

    @staticmethod
    def _require_unique(label: str, values: tuple[str, ...]) -> None:
        if len(values) != len(set(values)):
            raise InvalidReviewContentError(f"Review {label} identifiers must be unique.")

    @property
    def unresolved_blocker_count(self) -> int:
        return sum(
            item.status is FlagStatus.OPEN and item.severity is FlagSeverity.BLOCKING
            for item in self.flags
        )

    @property
    def unresolved_warning_count(self) -> int:
        return sum(
            item.status is FlagStatus.OPEN and item.severity is FlagSeverity.WARNING
            for item in self.flags
        )

    def find_flag(self, flag_id: FlagId) -> Flag | None:
        return next((item for item in self.flags if item.id == flag_id), None)

    def record(self, decision: Decision) -> BreakdownReview:
        existing = next((item for item in self.decisions if item.id == decision.id), None)
        if existing is not None:
            if existing == decision:
                return self
            raise FlagResolutionConflictError("A different decision already uses this ID.")
        if decision.target_flag_id is not None and self.find_flag(decision.target_flag_id) is None:
            raise InvalidReviewContentError("A decision targets an unknown flag.")
        return replace(self, decisions=(*self.decisions, decision), version=self.version + 1)

    def resolve(self, flag_id: FlagId, decision: Decision) -> BreakdownReview:
        if decision.target_flag_id != flag_id:
            raise InvalidReviewContentError("A resolution decision must target the resolved flag.")
        flag = self.find_flag(flag_id)
        if flag is None:
            raise InvalidReviewContentError("Cannot resolve a flag outside this review.")
        if flag.status is FlagStatus.RESOLVED:
            existing = next(
                item for item in self.decisions if item.id == flag.resolution_decision_id
            )
            if (
                existing.decision == decision.decision.strip()
                and existing.rationale == decision.rationale.strip()
            ):
                return self
            raise FlagResolutionConflictError(
                "This flag was already resolved by a different decision."
            )
        existing_decision = next((item for item in self.decisions if item.id == decision.id), None)
        if existing_decision is not None and existing_decision != decision:
            raise FlagResolutionConflictError("A different decision already uses this ID.")
        resolved = flag.resolve(decision.id)
        status = self.status
        if status in (BreakdownStatus.UNDER_REVIEW, BreakdownStatus.APPROVED):
            status = BreakdownStatus.NEEDS_REVISION
        return replace(
            self,
            decisions=(
                self.decisions if existing_decision is not None else (*self.decisions, decision)
            ),
            flags=tuple(resolved if item.id == flag_id else item for item in self.flags),
            status=status,
            version=self.version + 1,
        )

    def submit(self, fingerprint: str) -> BreakdownReview:
        subject = _text(fingerprint, "submitted fingerprint")
        if self.status is BreakdownStatus.UNDER_REVIEW:
            if self.submitted_fingerprint == subject:
                return self
            raise InvalidReviewTransitionError("A different breakdown is already under review.")
        if self.status is BreakdownStatus.APPROVED:
            raise InvalidReviewTransitionError(
                "An approved breakdown must change before resubmission."
            )
        return replace(
            self,
            status=BreakdownStatus.UNDER_REVIEW,
            submitted_fingerprint=subject,
            version=self.version + 1,
        )

    def request_revision(self) -> BreakdownReview:
        if self.status is BreakdownStatus.NEEDS_REVISION:
            return self
        if self.status not in (BreakdownStatus.UNDER_REVIEW, BreakdownStatus.APPROVED):
            return self
        return replace(
            self,
            status=BreakdownStatus.NEEDS_REVISION,
            version=self.version + 1,
        )

    def approve_breakdown(self, approval: Approval) -> BreakdownReview:
        if self.status is BreakdownStatus.APPROVED and approval in self.approvals:
            return self
        if self.status is not BreakdownStatus.UNDER_REVIEW:
            raise InvalidReviewTransitionError("Only a submitted breakdown can be approved.")
        if (
            approval.decision is not ApprovalDecision.APPROVED
            or approval.target.kind is not ApprovalTargetKind.BREAKDOWN
            or approval.target.item_id != self.requirement_id.value
            or approval.subject_fingerprint != self.submitted_fingerprint
        ):
            raise InvalidReviewContentError("The approval does not attest to this submission.")
        return replace(
            self,
            status=BreakdownStatus.APPROVED,
            approvals=(*self.approvals, approval),
            version=self.version + 1,
        )

    def effective_status(self, subject: str | None, evidence_fingerprint: str) -> BreakdownStatus:
        """The status a reader sees: a submission whose content or evidence moved on is stale.

        A review that is under review or approved attests to one subject and one set of
        evidence. Once either changes it needs revision, even before anything saves that.
        """
        if self.status in (BreakdownStatus.UNDER_REVIEW, BreakdownStatus.APPROVED) and (
            subject != self.submitted_fingerprint
            or self.evidence_fingerprint != evidence_fingerprint
        ):
            return BreakdownStatus.NEEDS_REVISION
        return self.status

    def with_knowledge_version(self, knowledge_version: str | None) -> BreakdownReview:
        """Record the architecture knowledge release this review was built against."""
        return replace(self, knowledge_version=knowledge_version)

    def carry_forward_from(self, existing: BreakdownReview) -> BreakdownReview:
        """This newly built review, keeping what people already decided on `existing`.

        Decisions on flags that still exist, and their resolutions, are kept. Submission,
        approvals and comments come from `existing`; if the evidence changed, a submitted or
        approved review needs revision. The version follows on from `existing`.
        """
        current_flag_ids = {item.id for item in self.flags}
        carried = self
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
        if self.evidence_fingerprint != existing.evidence_fingerprint:
            governance = existing.request_revision()
        return replace(
            carried,
            status=governance.status,
            submitted_fingerprint=governance.submitted_fingerprint,
            approvals=existing.approvals,
            comments=existing.comments,
            version=existing.version + 1,
        )

    def add_comment(self, comment: ReviewComment) -> BreakdownReview:
        if comment in self.comments:
            return self
        return replace(
            self,
            comments=(*self.comments, comment),
            version=self.version + 1,
        )
