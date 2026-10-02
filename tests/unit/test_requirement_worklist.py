"""Application tests for the cross-aggregate Requirement worklist."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import RLock

from smb_requirement_agent.application.ports.activity import (
    ActivityEvent,
    ActivityQuery,
    ActivityReportEvidence,
    ActivityResult,
)
from smb_requirement_agent.application.ports.requirement_worklist import (
    RequirementWorklistSnapshot,
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.application.use_cases.approval_policy import breakdown_fingerprint
from smb_requirement_agent.application.use_cases.breakdown_review_evidence import (
    ReviewEvidence,
    evidence_fingerprint,
)
from smb_requirement_agent.application.use_cases.breakdown_review_policy import (
    REVIEW_RULESET_VERSION,
)
from smb_requirement_agent.application.use_cases.requirement_worklist import (
    ListRequirementWorklist,
    NextAction,
    RequirementWorklistQuery,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.value_objects import Assumption, KnownFact
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
)
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureName,
    FeatureOutcome,
    SplittingPattern,
    SplittingRationale,
)
from smb_requirement_agent.domain.jobs.entities import AiJobOperation
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementId,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.domain.review.entities import BreakdownReview, BreakdownStatus
from smb_requirement_agent.domain.shared.generation import GenerationStatus, Provenance
from smb_requirement_agent.domain.shared.staleness import Staleness, StaleReason
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.value_objects import (
    AcceptanceCriterion,
    BusinessValue,
    DesiredAction,
    StoryId,
    UserRole,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_ai_jobs import InMemoryAiJobStore
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
from smb_requirement_agent.infrastructure.persistence.in_memory_identity import (
    InMemoryAccessRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_revision_repository import (
    InMemoryRevisionRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_story_repository import (
    InMemoryStoryRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_worklist import (
    InMemoryRequirementWorklistSnapshotAdapter,
)
from smb_requirement_agent.infrastructure.time.fixed_clock import FixedClock
from tests.conftest import AlwaysReadyKnowledgeReview

NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)


class Snapshots:
    def __init__(self, *items: RequirementWorklistSnapshot) -> None:
        self.items = list(items)

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]:
        if requirement_ids is None:
            return list(self.items)
        return [item for item in self.items if item.requirement.id.value in requirement_ids]


class EmptyActivity:
    def list_events(self) -> list[ActivityEvent]:
        return []

    def query(self, query: ActivityQuery) -> ActivityResult:
        return ActivityResult((), 0, query.offset, query.limit, False)

    def aggregate_report(self, start: datetime, before: datetime) -> ActivityReportEvidence:
        return ActivityReportEvidence((), (), (), None)

    def window_events(self, start: datetime, before: datetime) -> list[ActivityEvent]:
        return []

    def list_events_for_requirement(self, requirement_id: RequirementId) -> list[ActivityEvent]:
        return []


EMPTY_ACTIVITY = EmptyActivity()


def requirement(raw_id: str, title: str) -> Requirement:
    return Requirement(
        RequirementId(raw_id),
        RequirementTitle(title),
        RequirementDescription(f"Description for {title}"),
        RequirementStatus.DRAFT,
    )


def analysis(
    raw_id: str, *, unresolved: bool = False, confirmed: bool = False
) -> RequirementAnalysis:
    return RequirementAnalysis(
        requirement_id=RequirementId(raw_id),
        known_facts=(KnownFact("A fact"),),
        constraints=(),
        business_rules=(),
        assumptions=(Assumption("Needs confirmation"),) if unresolved else (),
        open_questions=(),
        ambiguities=(),
        potential_dependencies=(),
        confirmed_at=NOW if confirmed else None,
    )


def epic(raw_id: str, *, approved: bool = False, stale: bool = False) -> Epic:
    return Epic(
        id=EpicId(f"epic-{raw_id}"),
        requirement_id=RequirementId(raw_id),
        name=EpicName("An epic"),
        outcome=BusinessOutcome("A measurable outcome"),
        business_case=BusinessCase("A useful business case"),
        status=GenerationStatus.APPROVED if approved else GenerationStatus.GENERATED,
        provenance=Provenance(NOW, "fake", "v1"),
        staleness=Staleness(StaleReason.REQUIREMENT_CHANGED, NOW) if stale else None,
    )


def feature(raw_id: str, *, approved: bool = True) -> Feature:
    return Feature(
        id=FeatureId(f"feature-{raw_id}"),
        epic_id=EpicId(f"epic-{raw_id}"),
        name=FeatureName("A feature"),
        outcome=FeatureOutcome("A feature outcome"),
        delivery_drop=DeliveryDrop.MVP,
        splitting_pattern=SplittingPattern.COMPONENT_SYSTEM,
        splitting_rationale=SplittingRationale("A clear system boundary"),
        status=GenerationStatus.APPROVED if approved else GenerationStatus.GENERATED,
        provenance=Provenance(NOW, "fake", "v1"),
    )


def story(raw_id: str, *, approved: bool = False) -> UserStory:
    return UserStory(
        id=StoryId(f"story-{raw_id}"),
        feature_id=FeatureId(f"feature-{raw_id}"),
        role=UserRole("business owner"),
        action=DesiredAction("review the work"),
        value=BusinessValue("the outcome is correct"),
        acceptance_criteria=(AcceptanceCriterion("work exists", "I review it", "I can decide"),),
        status=GenerationStatus.APPROVED if approved else GenerationStatus.GENERATED,
        provenance=Provenance(NOW, "fake", "v1"),
    )


def snapshot(
    raw_id: str,
    title: str,
    *,
    analysed: RequirementAnalysis | None = None,
    generated_epic: Epic | None = None,
    features: tuple[Feature, ...] = (),
    stories: tuple[UserStory, ...] = (),
    updated_at: datetime = NOW,
    active_ai_operation: AiJobOperation | None = None,
) -> RequirementWorklistSnapshot:
    return RequirementWorklistSnapshot(
        requirement(raw_id, title),
        analysed,
        generated_epic,
        features,
        stories,
        updated_at,
        active_ai_operation=active_ai_operation,
    )


def test_classifies_the_supported_journey_actions() -> None:
    items = (
        snapshot("draft", "Draft"),
        snapshot("questions", "Questions", analysed=analysis("questions", unresolved=True)),
        snapshot("confirm", "Confirm", analysed=analysis("confirm")),
        snapshot("epic", "Epic", analysed=analysis("epic", confirmed=True)),
        snapshot(
            "review-epic",
            "Review epic",
            analysed=analysis("review-epic", confirmed=True),
            generated_epic=epic("review-epic"),
        ),
        snapshot(
            "features",
            "Features",
            analysed=analysis("features", confirmed=True),
            generated_epic=epic("features", approved=True),
        ),
        snapshot(
            "stories",
            "Stories",
            analysed=analysis("stories", confirmed=True),
            generated_epic=epic("stories", approved=True),
            features=(feature("stories"),),
        ),
        snapshot(
            "review-stories",
            "Review stories",
            analysed=analysis("review-stories", confirmed=True),
            generated_epic=epic("review-stories", approved=True),
            features=(feature("review-stories"),),
            stories=(story("review-stories"),),
        ),
    )

    result = ListRequirementWorklist(
        Snapshots(*items), EMPTY_ACTIVITY, AlwaysReadyKnowledgeReview()
    ).execute(RequirementWorklistQuery(limit=20))
    actions = {item.snapshot.requirement.id.value: item.next_action for item in result.requirements}

    assert actions == {
        "draft": NextAction.ANALYSE,
        "questions": NextAction.ANSWER_QUESTIONS,
        "confirm": NextAction.CONFIRM_ANALYSIS,
        "epic": NextAction.GENERATE_EPIC,
        "review-epic": NextAction.REVIEW_EPIC,
        "features": NextAction.GENERATE_FEATURES,
        "stories": NextAction.GENERATE_STORIES,
        "review-stories": NextAction.REVIEW_STORIES,
    }


def test_stale_content_takes_precedence_over_open_questions() -> None:
    item = snapshot(
        "stale",
        "Stale",
        analysed=analysis("stale", unresolved=True),
        generated_epic=epic("stale", stale=True),
    )

    result = ListRequirementWorklist(
        Snapshots(item), EMPTY_ACTIVITY, AlwaysReadyKnowledgeReview()
    ).execute(RequirementWorklistQuery())

    assert result.requirements[0].workflow_status is WorkflowStatus.STALE
    assert result.requirements[0].next_action is NextAction.RECONCILE_STALE
    assert result.requirements[0].stale_items == 1


def test_active_analysis_job_exposes_live_reanalysing_status() -> None:
    item = snapshot(
        "reanalyzing",
        "Reanalyzing",
        analysed=analysis("reanalyzing", unresolved=True),
        generated_epic=epic("reanalyzing", stale=True),
        active_ai_operation=AiJobOperation.ANALYSE_REQUIREMENT,
    )

    result = ListRequirementWorklist(
        Snapshots(item), EMPTY_ACTIVITY, AlwaysReadyKnowledgeReview()
    ).execute(RequirementWorklistQuery())

    assert result.requirements[0].workflow_status is WorkflowStatus.REANALYSING
    assert result.requirements[0].next_action is NextAction.OPEN


def test_approved_worklist_requires_current_review_evidence() -> None:
    source = requirement("approved", "Approved")
    original_analysis = analysis("approved", confirmed=True)
    current_epic = epic("approved", approved=True)
    current_features = (feature("approved"),)
    current_stories = (story("approved", approved=True),)
    evidence = ReviewEvidence(
        source,
        original_analysis,
        current_epic,
        current_features,
        current_stories,
    )
    generated_review = BreakdownReview(
        source.id,
        NOW,
        REVIEW_RULESET_VERSION,
        evidence_fingerprint(evidence),
        (),
        (),
        (),
        (),
    )
    submitted_fingerprint = breakdown_fingerprint(
        source,
        original_analysis,
        current_epic,
        current_features,
        current_stories,
        generated_review,
    )
    approved_review = replace(
        generated_review,
        status=BreakdownStatus.APPROVED,
        submitted_fingerprint=submitted_fingerprint,
    )
    changed_analysis = replace(
        original_analysis,
        known_facts=(KnownFact("The evidence changed after final approval."),),
    )
    item = RequirementWorklistSnapshot(
        source,
        changed_analysis,
        current_epic,
        current_features,
        current_stories,
        NOW,
        review=approved_review,
    )

    result = ListRequirementWorklist(
        Snapshots(item), EMPTY_ACTIVITY, AlwaysReadyKnowledgeReview()
    ).execute(RequirementWorklistQuery())

    assert result.requirements[0].workflow_status is WorkflowStatus.NEEDS_REVISION
    assert result.requirements[0].next_action is NextAction.REVISE_BACKLOG


def test_search_status_filter_sort_and_pagination_are_server_semantics() -> None:
    older = snapshot("one", "Zebra Fibre", updated_at=NOW - timedelta(days=2))
    newer = snapshot(
        "two",
        "Alpha Mobile",
        analysed=analysis("two", unresolved=True),
        updated_at=NOW,
    )
    middle = snapshot("three", "Beta Fibre", updated_at=NOW - timedelta(days=1))
    use_case = ListRequirementWorklist(
        Snapshots(older, newer, middle), EMPTY_ACTIVITY, AlwaysReadyKnowledgeReview()
    )

    result = use_case.execute(
        RequirementWorklistQuery(
            q="fibre",
            workflow_statuses=frozenset({WorkflowStatus.DRAFT}),
            sort=WorklistSort.TITLE_ASC,
            offset=1,
            limit=1,
        )
    )

    assert [item.snapshot.requirement.id.value for item in result.requirements] == ["one"]
    assert result.total == 2
    assert result.has_more is False
    assert result.status_counts[WorkflowStatus.DRAFT] == 2
    assert result.status_counts[WorkflowStatus.NEEDS_ANSWERS] == 0


def test_attention_is_ranked_by_status_then_oldest_activity() -> None:
    ready = snapshot("ready", "Ready", analysed=analysis("ready"), updated_at=NOW)
    stale_item = snapshot(
        "stale",
        "Stale",
        generated_epic=epic("stale", stale=True),
        updated_at=NOW - timedelta(days=3),
    )
    newer_question = snapshot(
        "question-new",
        "New question",
        analysed=analysis("question-new", unresolved=True),
        updated_at=NOW,
    )
    older_question = replace(
        snapshot(
            "question-old",
            "Old question",
            analysed=analysis("question-old", unresolved=True),
        ),
        updated_at=NOW - timedelta(days=4),
    )

    result = ListRequirementWorklist(
        Snapshots(ready, stale_item, newer_question, older_question),
        EMPTY_ACTIVITY,
        AlwaysReadyKnowledgeReview(),
    ).execute(RequirementWorklistQuery())

    assert [item.snapshot.requirement.id.value for item in result.attention] == [
        "question-old",
        "question-new",
        "stale",
    ]


def test_in_memory_adapter_returns_the_cross_aggregate_snapshot_contract() -> None:
    requirements = InMemoryRequirementRepository()
    analyses = InMemoryRequirementAnalysisRepository()
    epics = InMemoryEpicRepository()
    features = InMemoryFeatureRepository()
    stories = InMemoryStoryRepository()
    access = InMemoryAccessRepository()
    reviews = InMemoryBreakdownReviewRepository()
    revisions = InMemoryRevisionRepository(
        requirements,
        analyses,
        epics,
        features,
        stories,
        reviews,
        access,
        FixedClock(NOW),
    )
    source = requirement("adapter", "Adapter contract")
    current_analysis = analysis("adapter", confirmed=True)
    current_epic = epic("adapter", approved=True)
    current_feature = feature("adapter")
    current_story = story("adapter")
    requirements.add(source)
    analyses.save(current_analysis)
    epics.save(current_epic)
    features.replace_for_epic(
        current_epic.id, [current_feature], features.set_version(current_epic.id)
    )
    stories.replace_for_feature(
        current_feature.id, [current_story], stories.set_version(current_feature.id)
    )
    revisions.create_current_revisions(source.id)

    result = InMemoryRequirementWorklistSnapshotAdapter(
        requirements,
        analyses,
        epics,
        features,
        stories,
        revisions,
        access,
        InMemoryAnalysisAuditRepository(lambda requirement_id: None),
        InMemoryAiJobStore(RLock()),
        reviews,
    ).list_snapshots()

    assert result == [
        RequirementWorklistSnapshot(
            source,
            current_analysis,
            current_epic,
            (current_feature,),
            (current_story,),
            NOW,
        )
    ]
