"""Build the searchable, filterable Requirement review worklist."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from smb_requirement_agent.application.ports.requirement_knowledge import (
    KnowledgeReview,
    KnowledgeReviewPort,
)
from smb_requirement_agent.governance.domain.review.entities import BreakdownStatus
from smb_requirement_agent.governance.domain.review.evidence import (
    ReviewEvidence,
    evidence_fingerprint,
)
from smb_requirement_agent.governance.domain.review.fingerprints import breakdown_fingerprint
from smb_requirement_agent.reporting.application.ports.activity import (
    ActivityEvent,
    ActivityReadPort,
)
from smb_requirement_agent.reporting.application.ports.requirement_worklist import (
    RequirementWorklistSnapshot,
    RequirementWorklistSnapshotPort,
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import RequirementStatus
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.generation import GenerationStatus


class WorkflowStage(StrEnum):
    CAPTURE = "capture"
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    EPIC = "epic"
    FEATURES = "features"
    STORIES = "stories"
    COMPLETE = "complete"
    REVIEW = "review"
    KNOWLEDGE = "knowledge"


class NextAction(StrEnum):
    ANALYSE = "analyse"
    ANSWER_QUESTIONS = "answer_questions"
    CONFIRM_ANALYSIS = "confirm_analysis"
    GENERATE_EPIC = "generate_epic"
    REVIEW_EPIC = "review_epic"
    GENERATE_FEATURES = "generate_features"
    REVIEW_FEATURES = "review_features"
    GENERATE_STORIES = "generate_stories"
    REVIEW_STORIES = "review_stories"
    SUBMIT_FOR_REVIEW = "submit_for_review"
    REVISE_BACKLOG = "revise_backlog"
    APPROVE_BREAKDOWN = "approve_breakdown"
    RECONCILE_STALE = "reconcile_stale"
    OPEN = "open"
    REVIEW_KNOWLEDGE = "review_knowledge"


@dataclass(frozen=True)
class ArtifactCounts:
    epics: int
    features: int
    stories: int


@dataclass(frozen=True)
class RequirementWorklistItem:
    snapshot: RequirementWorklistSnapshot
    workflow_status: WorkflowStatus
    current_stage: WorkflowStage
    next_action: NextAction
    answered_items: int
    unresolved_items: int
    stale_items: int
    artifact_counts: ArtifactCounts
    last_activity: ActivityEvent | None = None

    @property
    def owner(self) -> ActorSnapshot | None:
        access = self.snapshot.access
        return access.owner.actor if access is not None and access.owner is not None else None

    @property
    def reviewer_count(self) -> int:
        return len(self.snapshot.access.reviewers) if self.snapshot.access is not None else 0


@dataclass(frozen=True)
class RequirementWorklistQuery:
    q: str | None = None
    workflow_statuses: frozenset[WorkflowStatus] = frozenset()
    sort: WorklistSort = WorklistSort.UPDATED_DESC
    offset: int = 0
    limit: int = 20
    owner_id: ActorId | None = None
    assigned_to_me: bool = False
    current_actor_id: ActorId | None = None


@dataclass(frozen=True)
class OwnerFacet:
    actor: ActorSnapshot
    count: int


@dataclass(frozen=True)
class RequirementWorklistResult:
    requirements: tuple[RequirementWorklistItem, ...]
    attention: tuple[RequirementWorklistItem, ...]
    total: int
    offset: int
    limit: int
    has_more: bool
    status_counts: dict[WorkflowStatus, int]
    owner_facets: tuple[OwnerFacet, ...]


class RequirementWorklistReader(Protocol):
    """Query boundary shared by the in-memory projector and durable projection."""

    def execute(self, query: RequirementWorklistQuery) -> RequirementWorklistResult: ...


class ListRequirementWorklist:
    """Classify repository snapshots and apply worklist query semantics."""

    def __init__(
        self,
        snapshots: RequirementWorklistSnapshotPort,
        activity: ActivityReadPort,
        knowledge: KnowledgeReviewPort,
    ) -> None:
        self._snapshots = snapshots
        self._activity = activity
        self._knowledge = knowledge

    def execute(self, query: RequirementWorklistQuery) -> RequirementWorklistResult:
        latest: dict[str, ActivityEvent] = {}
        for event in self._activity.list_events():
            key = event.requirement_id.value
            current = latest.get(key)
            if current is None or (event.occurred_at, event.id) > (
                current.occurred_at,
                current.id,
            ):
                latest[key] = event
        items = [
            self.classify(
                snapshot,
                latest.get(snapshot.requirement.id.value),
                self._knowledge.execute(snapshot.requirement.id),
            )
            for snapshot in self._snapshots.list_snapshots()
        ]
        scoped = [item for item in items if self._matches_access(item, query)]
        attention = tuple(sorted(self._attention(scoped), key=self._attention_key)[:3])

        searched = [item for item in scoped if self._matches_query(item, query.q)]
        status_counts = {status: 0 for status in WorkflowStatus}
        for item in searched:
            status_counts[item.workflow_status] += 1
        facet_counts: dict[ActorSnapshot, int] = {}
        for item in searched:
            if item.owner is not None:
                facet_counts[item.owner] = facet_counts.get(item.owner, 0) + 1

        filtered = [
            item
            for item in searched
            if not query.workflow_statuses or item.workflow_status in query.workflow_statuses
        ]
        ordered = self._sort(filtered, query.sort)
        page = tuple(ordered[query.offset : query.offset + query.limit])
        total = len(ordered)
        return RequirementWorklistResult(
            requirements=page,
            attention=attention,
            total=total,
            offset=query.offset,
            limit=query.limit,
            has_more=query.offset + len(page) < total,
            status_counts=status_counts,
            owner_facets=tuple(
                OwnerFacet(actor, count)
                for actor, count in sorted(
                    facet_counts.items(), key=lambda pair: pair[0].display_name.casefold()
                )
            ),
        )

    @staticmethod
    def _matches_access(item: RequirementWorklistItem, query: RequirementWorklistQuery) -> bool:
        access = item.snapshot.access
        if query.owner_id is not None and (
            access is None or access.owner is None or access.owner.actor.id != query.owner_id
        ):
            return False
        if query.assigned_to_me and (
            query.current_actor_id is None
            or access is None
            or not access.includes(query.current_actor_id)
        ):
            return False
        return True

    @staticmethod
    def classify(
        snapshot: RequirementWorklistSnapshot,
        last_activity: ActivityEvent | None = None,
        knowledge: KnowledgeReview | None = None,
    ) -> RequirementWorklistItem:
        analysis = snapshot.analysis
        unresolved = sum(item.is_active for item in snapshot.questions)
        blocking = sum(item.is_active and item.is_blocker for item in snapshot.questions)
        answered = sum(item.status.value == "resolved" for item in snapshot.questions)
        if analysis is not None and not snapshot.questions:
            unresolved = len(analysis.unresolved_keys())
            blocking = unresolved
            answered = len(analysis.clarifications)
        stale = (
            int(snapshot.epic is not None and snapshot.epic.is_stale)
            + sum(item.is_stale for item in snapshot.features)
            + sum(item.is_stale for item in snapshot.stories)
        )
        counts = ArtifactCounts(
            epics=int(snapshot.epic is not None),
            features=len(snapshot.features),
            stories=len(snapshot.stories),
        )

        if snapshot.requirement.status is RequirementStatus.DUPLICATE:
            status = WorkflowStatus.DUPLICATE
            stage = WorkflowStage.KNOWLEDGE
            action = NextAction.OPEN
        elif (
            snapshot.active_ai_operation is not None
            and snapshot.active_ai_operation.uses_analyzer
            and analysis is not None
        ):
            status = WorkflowStatus.REANALYSING
            stage = WorkflowStage.CLARIFY
            action = NextAction.OPEN
        elif stale:
            status = WorkflowStatus.STALE
            stage = WorkflowStage.STORIES if snapshot.stories else WorkflowStage.FEATURES
            action = NextAction.RECONCILE_STALE
        elif analysis is None:
            status = WorkflowStatus.DRAFT
            stage = WorkflowStage.CAPTURE
            action = NextAction.ANALYSE
        elif blocking:
            status = WorkflowStatus.NEEDS_ANSWERS
            stage = WorkflowStage.CLARIFY
            action = NextAction.ANSWER_QUESTIONS
        elif knowledge is not None and not knowledge.ready:
            status = WorkflowStatus.KNOWLEDGE_REVIEW
            stage = WorkflowStage.KNOWLEDGE
            action = NextAction.REVIEW_KNOWLEDGE
        elif not analysis.is_human_confirmed:
            status = WorkflowStatus.READY_FOR_REVIEW
            stage = WorkflowStage.CONFIRM
            action = NextAction.CONFIRM_ANALYSIS
        elif snapshot.epic is None:
            status = WorkflowStatus.READY_FOR_REVIEW
            stage = WorkflowStage.EPIC
            action = NextAction.GENERATE_EPIC
        elif snapshot.epic.status is not GenerationStatus.APPROVED:
            status = WorkflowStatus.READY_FOR_REVIEW
            stage = WorkflowStage.EPIC
            action = NextAction.REVIEW_EPIC
        elif not snapshot.features:
            status = WorkflowStatus.READY_FOR_REVIEW
            stage = WorkflowStage.FEATURES
            action = NextAction.GENERATE_FEATURES
        elif any(item.status is not GenerationStatus.APPROVED for item in snapshot.features):
            status = WorkflowStatus.READY_FOR_REVIEW
            stage = WorkflowStage.FEATURES
            action = NextAction.REVIEW_FEATURES
        elif not snapshot.stories:
            status = WorkflowStatus.READY_FOR_REVIEW
            stage = WorkflowStage.STORIES
            action = NextAction.GENERATE_STORIES
        elif any(item.status is not GenerationStatus.APPROVED for item in snapshot.stories):
            status = WorkflowStatus.READY_FOR_REVIEW
            stage = WorkflowStage.STORIES
            action = NextAction.REVIEW_STORIES
        elif snapshot.review is None:
            status = WorkflowStatus.READY_FOR_REVIEW
            stage = WorkflowStage.REVIEW
            action = NextAction.SUBMIT_FOR_REVIEW
        else:
            current_evidence = ReviewEvidence(
                snapshot.requirement,
                analysis,
                snapshot.epic,
                snapshot.features,
                snapshot.stories,
                tuple(item for item in snapshot.questions if item.is_active),
            )
            subject = breakdown_fingerprint(
                snapshot.requirement,
                analysis,
                snapshot.epic,
                snapshot.features,
                snapshot.stories,
                snapshot.review,
            )
            current_submission = snapshot.review.submitted_fingerprint == subject
            review_fresh = snapshot.review.evidence_fingerprint == evidence_fingerprint(
                current_evidence
            )
            if (
                snapshot.review.status is BreakdownStatus.APPROVED
                and current_submission
                and review_fresh
            ):
                status = WorkflowStatus.APPROVED
                stage = WorkflowStage.COMPLETE
                action = NextAction.OPEN
            elif snapshot.review.status is BreakdownStatus.NEEDS_REVISION or (
                snapshot.review.submitted_fingerprint is not None
                and (not current_submission or not review_fresh)
            ):
                status = WorkflowStatus.NEEDS_REVISION
                stage = WorkflowStage.REVIEW
                action = NextAction.REVISE_BACKLOG
            elif snapshot.review.status is BreakdownStatus.UNDER_REVIEW:
                status = WorkflowStatus.READY_FOR_REVIEW
                stage = WorkflowStage.REVIEW
                action = NextAction.APPROVE_BREAKDOWN
            else:
                status = WorkflowStatus.READY_FOR_REVIEW
                stage = WorkflowStage.REVIEW
                action = NextAction.SUBMIT_FOR_REVIEW

        return RequirementWorklistItem(
            snapshot=snapshot,
            workflow_status=status,
            current_stage=stage,
            next_action=action,
            answered_items=answered,
            unresolved_items=unresolved,
            stale_items=stale,
            artifact_counts=counts,
            last_activity=last_activity,
        )

    @staticmethod
    def _matches_query(item: RequirementWorklistItem, raw_query: str | None) -> bool:
        query = (raw_query or "").strip().casefold()
        if not query:
            return True
        requirement = item.snapshot.requirement
        return (
            query
            in " ".join(
                (
                    requirement.id.value,
                    requirement.title.value,
                    requirement.description.value,
                )
            ).casefold()
        )

    @staticmethod
    def _sort(
        items: list[RequirementWorklistItem], sort: WorklistSort
    ) -> list[RequirementWorklistItem]:
        items = sorted(items, key=lambda item: item.snapshot.requirement.id.value)
        if sort is WorklistSort.UPDATED_ASC:
            return sorted(items, key=lambda item: item.snapshot.updated_at)
        if sort is WorklistSort.TITLE_ASC:
            return sorted(items, key=lambda item: item.snapshot.requirement.title.value.casefold())
        if sort is WorklistSort.TITLE_DESC:
            return sorted(
                items,
                key=lambda item: item.snapshot.requirement.title.value.casefold(),
                reverse=True,
            )
        return sorted(items, key=lambda item: item.snapshot.updated_at, reverse=True)

    @staticmethod
    def _attention(items: list[RequirementWorklistItem]) -> list[RequirementWorklistItem]:
        attention_statuses = {
            WorkflowStatus.NEEDS_ANSWERS,
            WorkflowStatus.STALE,
            WorkflowStatus.READY_FOR_REVIEW,
            WorkflowStatus.NEEDS_REVISION,
            WorkflowStatus.KNOWLEDGE_REVIEW,
        }
        return [item for item in items if item.workflow_status in attention_statuses]

    @staticmethod
    def _attention_key(item: RequirementWorklistItem) -> tuple[int, datetime]:
        priority = {
            WorkflowStatus.NEEDS_ANSWERS: 0,
            WorkflowStatus.STALE: 1,
            WorkflowStatus.READY_FOR_REVIEW: 2,
            WorkflowStatus.NEEDS_REVISION: 1,
            WorkflowStatus.KNOWLEDGE_REVIEW: 0,
        }
        return priority[item.workflow_status], item.snapshot.updated_at
