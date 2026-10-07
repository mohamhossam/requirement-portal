"""The order of the writes a change cascades into (ADR-0004, ADR-0103 PR 1).

ADR-0103 replaces `InvalidateDerivedArtifacts` and `InvalidateApprovalWorkflow` with domain-event
handlers that must run in the same order as these direct calls. This test records that order.
In PR 4 it drives the publishing facade, and in PR 5 the events themselves; the expected
sequences below must not change.
"""

from __future__ import annotations

from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.use_cases.invalidate_approval_workflow import (
    InvalidateApprovalWorkflow,
)
from smb_requirement_agent.application.use_cases.invalidate_derived_artifacts import (
    InvalidateDerivedArtifacts,
)
from smb_requirement_agent.domain.analysis.entities import ClarificationQuestion
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_repository import (
    InMemoryRequirementAnalysisRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_breakdown_review_repository import (
    InMemoryBreakdownReviewRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_epic_repository import (
    InMemoryEpicRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_feature_repository import (
    InMemoryFeatureRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_story_repository import (
    InMemoryStoryRepository,
)
from tests.characterisation import samples

Writes = list[tuple[str, str]]


class _Reviews(InMemoryBreakdownReviewRepository):
    def __init__(self, writes: Writes) -> None:
        super().__init__()
        self._writes = writes

    def save(self, review: BreakdownReview) -> None:
        super().save(review)
        self._writes.append(("review.save", review.status.value))


class _Analyses(InMemoryRequirementAnalysisRepository):
    def __init__(self, writes: Writes) -> None:
        super().__init__()
        self._writes = writes

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        super().delete_by_requirement_id(requirement_id)
        self._writes.append(("analysis.delete", requirement_id.value))


class _Audits(InMemoryAnalysisAuditRepository):
    def __init__(self, writes: Writes) -> None:
        super().__init__(lambda requirement_id: None)
        self._writes = writes

    def save_question(self, question: ClarificationQuestion) -> None:
        super().save_question(question)
        self._writes.append(("question.save", f"{question.id.value}:{question.status.value}"))


class _Epics(InMemoryEpicRepository):
    def __init__(self, writes: Writes) -> None:
        super().__init__()
        self._writes = writes

    def save(self, epic: Epic) -> None:
        super().save(epic)
        self._writes.append(("epic.save", _stale(epic)))


class _Features(InMemoryFeatureRepository):
    def __init__(self, writes: Writes) -> None:
        super().__init__()
        self._writes = writes

    def save(self, feature: Feature) -> None:
        super().save(feature)
        self._writes.append(("feature.save", f"{feature.id.value}:{_stale(feature)}"))


class _Stories(InMemoryStoryRepository):
    def __init__(self, writes: Writes) -> None:
        super().__init__()
        self._writes = writes

    def save(self, story: UserStory) -> None:
        super().save(story)
        self._writes.append(("story.save", f"{story.id.value}:{_stale(story)}"))


def _stale(item: Epic | Feature | UserStory) -> str:
    return item.staleness.reason.value if item.staleness else "current"


def _cascade() -> tuple[InvalidateDerivedArtifacts, Writes]:
    """A full sample breakdown under review, with every write recorded once seeded.

    The second Feature is already stale (`epic_changed`): it shows that a stale artifact keeps
    its first reason and is still written.
    """
    writes: Writes = []
    reviews = _Reviews(writes)
    analyses = _Analyses(writes)
    audits = _Audits(writes)
    epics = _Epics(writes)
    features = _Features(writes)
    stories = _Stories(writes)

    reviews.save(samples.review())
    analyses.save(samples.analysis())
    audits.add_question(samples.open_question())
    audits.add_question(samples.resolved_question())
    epics.save(samples.epic())
    features.replace_for_epic(
        samples.EPIC_ID,
        [samples.feature(), samples.second_feature()],
        expected_set_version=1,
    )
    stories.replace_for_feature(
        samples.FEATURE_ID, [samples.story(), samples.second_story()], expected_set_version=1
    )
    writes.clear()
    invalidation = InvalidateDerivedArtifacts(
        analyses,
        epics,
        features,
        stories,
        FixedClock(samples.T3),
        audits,
        InvalidateApprovalWorkflow(reviews),
    )
    return invalidation, writes


def test_requirement_change_order() -> None:
    invalidation, writes = _cascade()

    invalidation.for_changed_requirement(samples.REQUIREMENT_ID)

    assert writes == [
        ("review.save", "needs_revision"),
        ("analysis.delete", "req-golden-1"),
        ("question.save", "question-golden-1:superseded"),
        ("epic.save", "requirement_changed"),
        ("story.save", "story-golden-1:requirement_changed"),
        ("story.save", "story-golden-2:requirement_changed"),
        ("feature.save", "feature-golden-1:requirement_changed"),
        ("feature.save", "feature-golden-2:epic_changed"),
    ]


def test_epic_change_order() -> None:
    invalidation, writes = _cascade()

    invalidation.for_changed_epic(samples.epic())

    assert writes == [
        ("review.save", "needs_revision"),
        ("story.save", "story-golden-1:epic_changed"),
        ("story.save", "story-golden-2:epic_changed"),
        ("feature.save", "feature-golden-1:epic_changed"),
        ("feature.save", "feature-golden-2:epic_changed"),
    ]


def test_feature_change_order() -> None:
    invalidation, writes = _cascade()

    invalidation.for_changed_feature(samples.REQUIREMENT_ID, samples.feature())

    assert writes == [
        ("review.save", "needs_revision"),
        ("story.save", "story-golden-1:feature_changed"),
        ("story.save", "story-golden-2:feature_changed"),
    ]


def test_approval_reset_alone_writes_only_the_review() -> None:
    """What every Story, Feature-set and mapping change triggers today."""
    writes: Writes = []
    reviews = _Reviews(writes)
    reviews.save(samples.review())
    writes.clear()

    InvalidateApprovalWorkflow(reviews).execute(samples.REQUIREMENT_ID)

    assert writes == [("review.save", "needs_revision")]
