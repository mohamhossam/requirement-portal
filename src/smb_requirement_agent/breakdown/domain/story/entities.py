"""User Story and pending AI change-proposal entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from smb_requirement_agent.breakdown.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.errors import InvalidStoryContentError
from smb_requirement_agent.breakdown.domain.story.quality import InvestAssessment
from smb_requirement_agent.breakdown.domain.story.value_objects import (
    AcceptanceCriterion,
    BusinessValue,
    DesiredAction,
    StoryId,
    StoryProposalId,
    UserRole,
)
from smb_requirement_agent.shared_kernel.approval import (
    Approval,
    ApprovalDecision,
    ApprovalTargetKind,
)
from smb_requirement_agent.shared_kernel.generation import Provenance, ReviewableGeneration


@dataclass(frozen=True, kw_only=True)
class UserStory(ReviewableGeneration):
    """One sprint-sized, testable slice of exactly one Feature."""

    id: StoryId
    feature_id: FeatureId
    role: UserRole
    action: DesiredAction
    value: BusinessValue
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    architecture: ArchitectureImpact | None = None

    review_label = "Story"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.acceptance_criteria:
            raise InvalidStoryContentError("A User Story needs at least one acceptance criterion.")

    @property
    def voice(self) -> str:
        return f"As a {self.role.value}, I want {self.action.value}, so that {self.value.value}."

    def edit(
        self,
        role: UserRole,
        action: DesiredAction,
        value: BusinessValue,
        acceptance_criteria: tuple[AcceptanceCriterion, ...],
        *,
        source_reconciled: bool = False,
    ) -> UserStory:
        if not acceptance_criteria:
            raise InvalidStoryContentError("A User Story needs at least one acceptance criterion.")
        return self._edited(
            role=role,
            action=action,
            value=value,
            acceptance_criteria=acceptance_criteria,
            architecture=None,
            source_reconciled=source_reconciled,
        )

    def with_architecture(self, impact: ArchitectureImpact) -> UserStory:
        """Attach a current mapping without changing content ownership or approval."""
        return replace(self, architecture=impact, version=self.version + 1)

    def approve(self, approval: Approval) -> UserStory:
        if self.is_stale:
            raise InvalidStoryContentError(
                f"Story {self.id.value!r} is stale and cannot be approved."
            )
        self._require_target(approval, ApprovalDecision.APPROVED)
        return self._approved(approval)

    def reject(self, approval: Approval) -> UserStory:
        self._require_target(approval, ApprovalDecision.REJECTED)
        return self._rejected(approval)

    def _require_target(self, approval: Approval, decision: ApprovalDecision) -> None:
        if (
            approval.decision is not decision
            or approval.target.kind is not ApprovalTargetKind.STORY
            or approval.target.item_id != self.id.value
        ):
            raise InvalidStoryContentError("The decision does not target this Story.")


class StoryChangeOperation(Enum):
    SPLIT = "split"
    MERGE = "merge"


@dataclass(frozen=True)
class StoryDraft:
    role: UserRole
    action: DesiredAction
    value: BusinessValue
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not self.acceptance_criteria:
            raise InvalidStoryContentError("A Story draft needs at least one acceptance criterion.")


@dataclass(frozen=True)
class StoryChangeProposal:
    id: StoryProposalId
    feature_id: FeatureId
    operation: StoryChangeOperation
    source_story_ids: tuple[StoryId, ...]
    source_fingerprint: str
    candidates: tuple[StoryDraft, ...]
    version: int = 1
    prepared_candidates: tuple[UserStory, ...] = ()
    quality_assessments: tuple[InvestAssessment, ...] = ()
    source_set_fingerprint: str | None = None
    generation_context: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise InvalidStoryContentError("A Story proposal version must be positive.")
        if self.prepared_candidates:
            if not self.source_set_fingerprint or not self.generation_context:
                raise InvalidStoryContentError(
                    "Checked proposals need source and context evidence."
                )
            drafts = tuple(
                StoryDraft(
                    item.role, item.action, item.value, item.acceptance_criteria, item.provenance
                )
                for item in self.prepared_candidates
            )
            assessed_ids = {item.story_id for item in self.quality_assessments}
            if drafts != self.candidates or any(
                item.feature_id != self.feature_id or item.id not in assessed_ids
                for item in self.prepared_candidates
            ):
                raise InvalidStoryContentError(
                    "Checked evidence must describe every proposal candidate."
                )
        if not self.source_story_ids:
            raise InvalidStoryContentError("A Story proposal needs source Stories.")
        if not self.source_fingerprint.strip():
            raise InvalidStoryContentError("A Story proposal needs a source fingerprint.")
        if self.operation is StoryChangeOperation.SPLIT and (
            len(self.source_story_ids) != 1 or len(self.candidates) < 2
        ):
            raise InvalidStoryContentError("A split proposal needs one source and two candidates.")
        if self.operation is StoryChangeOperation.MERGE and (
            len(self.source_story_ids) < 2 or len(self.candidates) != 1
        ):
            raise InvalidStoryContentError("A merge proposal needs two sources and one candidate.")
