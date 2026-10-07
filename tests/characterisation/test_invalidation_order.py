"""The order of the writes a change cascades into (ADR-0004, ADR-0103 PR 1).

ADR-0103 replaced `InvalidateDerivedArtifacts` and `InvalidateApprovalWorkflow` with domain-event
handlers that must run in the same order as those direct calls did. This test recorded that order
in PR 1. Since PR 5 it publishes the events themselves, through handlers subscribed exactly as
the composition root subscribes them, inside an in-memory unit of work. The expected sequences
below have not changed since PR 1.
"""

from __future__ import annotations

from threading import RLock

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.analysis.domain.entities import ClarificationQuestion
from smb_requirement_agent.analysis.infrastructure.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.analysis.infrastructure.in_memory_analysis_repository import (
    InMemoryRequirementAnalysisRepository,
)
from smb_requirement_agent.application.events import InProcessEventDispatcher
from smb_requirement_agent.domain.architecture.events import ArchitectureImpactChanged
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.events import EpicChanged
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.events import FeatureChanged, FeaturesReplaced
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.events import StoriesChanged
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
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.interfaces.api.composition.events import (
    subscribe_domain_event_handlers,
)
from smb_requirement_agent.requirements.domain.requirement.events import RequirementRevised
from smb_requirement_agent.shared_kernel.events import DomainEvent
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
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


def _cascade() -> tuple[InProcessEventDispatcher, Writes, InMemoryTransactionManager]:
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
    transactions = InMemoryTransactionManager(lambda requirement_id: None, RLock())
    events = InProcessEventDispatcher(transactions)
    subscribe_domain_event_handlers(
        events,
        analyses=analyses,
        audits=audits,
        epics=epics,
        features=features,
        stories=stories,
        reviews=reviews,
        clock=FixedClock(samples.T3),
    )
    return events, writes, transactions


def test_requirement_change_order() -> None:
    events, writes, transactions = _cascade()

    with transactions.transaction():
        events.publish(RequirementRevised(requirement_id=samples.REQUIREMENT_ID))

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
    events, writes, transactions = _cascade()

    with transactions.transaction():
        events.publish(EpicChanged(requirement_id=samples.REQUIREMENT_ID, epic_id=samples.EPIC_ID))

    assert writes == [
        ("review.save", "needs_revision"),
        ("story.save", "story-golden-1:epic_changed"),
        ("story.save", "story-golden-2:epic_changed"),
        ("feature.save", "feature-golden-1:epic_changed"),
        ("feature.save", "feature-golden-2:epic_changed"),
    ]


def test_feature_change_order() -> None:
    events, writes, transactions = _cascade()

    with transactions.transaction():
        events.publish(
            FeatureChanged(requirement_id=samples.REQUIREMENT_ID, feature_id=samples.FEATURE_ID)
        )

    assert writes == [
        ("review.save", "needs_revision"),
        ("story.save", "story-golden-1:feature_changed"),
        ("story.save", "story-golden-2:feature_changed"),
    ]


@pytest.mark.parametrize(
    "event",
    [
        FeaturesReplaced(requirement_id=samples.REQUIREMENT_ID, epic_id=samples.EPIC_ID),
        StoriesChanged(requirement_id=samples.REQUIREMENT_ID, feature_id=samples.FEATURE_ID),
        ArchitectureImpactChanged(requirement_id=samples.REQUIREMENT_ID),
    ],
    ids=lambda event: type(event).__name__,
)
def test_approval_reset_alone_writes_only_the_review(event: DomainEvent) -> None:
    """What every Story, Feature-set and mapping change triggers (PR 1: the reset alone)."""
    events, writes, transactions = _cascade()

    with transactions.transaction():
        events.publish(event)

    assert writes == [("review.save", "needs_revision")]
