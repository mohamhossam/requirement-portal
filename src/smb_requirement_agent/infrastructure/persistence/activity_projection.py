"""Audit-derived activity projection shared by memory and PostgreSQL modes."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Protocol

from smb_requirement_agent.application.ports.activity import (
    ActivityAction,
    ActivityCategory,
    ActivityEvent,
    ActivityQuery,
    ActivityReadPort,
    ActivityReportEvidence,
    ActivityResult,
    AuditSourceKind,
    AuditSourceReference,
    BlockerEvidence,
    ReportingReadPort,
)
from smb_requirement_agent.application.ports.ai_jobs import AiJobRecord
from smb_requirement_agent.application.ports.requirement_worklist import (
    RequirementWorklistSnapshot,
    RequirementWorklistSnapshotPort,
)
from smb_requirement_agent.application.use_cases.activity_reporting import (
    ListActivity,
    aggregate_activity_events,
)
from smb_requirement_agent.application.use_cases.breakdown_review_evidence import (
    ReviewEvidence,
    evidence_fingerprint,
)
from smb_requirement_agent.domain.analysis.entities import AnalysisRound, ClarificationQuestion
from smb_requirement_agent.domain.analysis.value_objects import QuestionChangeAction
from smb_requirement_agent.domain.identity.entities import AccessChangeKind
from smb_requirement_agent.domain.jobs.entities import AiJobOperation, AiJobStatus
from smb_requirement_agent.domain.knowledge.entities import (
    KnowledgeDecisionKind,
    KnowledgeFinding,
    KnowledgeFindingStatus,
)
from smb_requirement_agent.domain.review.entities import (
    BreakdownStatus,
    FlagSeverity,
    FlagStatus,
)
from smb_requirement_agent.domain.revision.entities import BreakdownRevision, RequirementRevision
from smb_requirement_agent.domain.shared.actors import ActorSnapshot
from smb_requirement_agent.domain.shared.approval import (
    Approval,
    ApprovalDecision,
    ApprovalTargetKind,
)
from smb_requirement_agent.domain.shared.identifiers import RequirementId


def _event_id(*parts: object) -> str:
    material = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class ActivityRevisionSource(Protocol):
    def list_requirement_revisions(
        self, requirement_id: RequirementId
    ) -> list[RequirementRevision]: ...

    def list_breakdown_revisions(
        self, requirement_id: RequirementId
    ) -> list[BreakdownRevision]: ...


class ActivityAuditSource(Protocol):
    def list_rounds(self, requirement_id: RequirementId) -> list[AnalysisRound]: ...

    def list_questions(self, requirement_id: RequirementId) -> list[ClarificationQuestion]: ...


class ActivityJobSource(Protocol):
    def list_for_requirement(
        self, requirement_id: RequirementId, *, active_only: bool = False
    ) -> list[AiJobRecord]: ...


class ActivityKnowledgeSource(Protocol):
    def list_related_findings(
        self, requirement_id: RequirementId
    ) -> tuple[KnowledgeFinding, ...]: ...


class RepositoryActivityProjection(ActivityReadPort, ReportingReadPort):
    """Normalise persisted audit-bearing aggregates without storing a second log."""

    def __init__(
        self,
        snapshots: RequirementWorklistSnapshotPort,
        revisions: ActivityRevisionSource,
        analysis_audit: ActivityAuditSource,
        jobs: ActivityJobSource,
        knowledge: ActivityKnowledgeSource,
        *,
        previous_review_status: BreakdownStatus | None = None,
        first_recorded_at: datetime | None = None,
    ) -> None:
        self._snapshots = snapshots
        self._revisions = revisions
        self._analysis_audit = analysis_audit
        self._jobs = jobs
        self._knowledge = knowledge
        self._previous_review_status = previous_review_status
        self._first_recorded_at = first_recorded_at

    def list_events(self) -> list[ActivityEvent]:
        events: dict[str, ActivityEvent] = {}
        for snapshot in self._snapshots.list_snapshots():
            self._project_requirement(snapshot, events)
        return list(events.values())

    def query(self, query: ActivityQuery) -> ActivityResult:

        events = sorted(
            (event for event in self.list_events() if ListActivity.matches(event, query)),
            key=lambda event: (event.occurred_at, event.id),
            reverse=True,
        )
        items = tuple(events[query.offset : query.offset + query.limit])
        return ActivityResult(
            items, len(events), query.offset, query.limit, query.offset + len(items) < len(events)
        )

    def aggregate_report(self, start: datetime, before: datetime) -> ActivityReportEvidence:

        return aggregate_activity_events(self.window_events(start, before))

    def window_events(self, start: datetime, before: datetime) -> list[ActivityEvent]:
        return [event for event in self.list_events() if start <= event.occurred_at < before]

    def list_events_for_requirement(self, requirement_id: RequirementId) -> list[ActivityEvent]:
        events: dict[str, ActivityEvent] = {}
        for snapshot in self._snapshots.list_snapshots((requirement_id.value,)):
            self._project_requirement(snapshot, events)
        return list(events.values())

    def _project_requirement(
        self, snapshot: RequirementWorklistSnapshot, events: dict[str, ActivityEvent]
    ) -> None:
        requirement_id = snapshot.requirement.id
        title = snapshot.requirement.title.value
        requirement_revisions = self._revisions.list_requirement_revisions(requirement_id)
        breakdown_revisions = self._revisions.list_breakdown_revisions(requirement_id)
        fallback = self._first_recorded_at or (
            requirement_revisions[0].created_at if requirement_revisions else snapshot.updated_at
        )
        for revision in requirement_revisions:
            action = (
                ActivityAction.REQUIREMENT_CREATED
                if revision.number.value == 1
                else ActivityAction.REQUIREMENT_UPDATED
            )
            actor = None
            if revision.number.value == 1 and revision.access and revision.access.changes:
                actor = revision.access.changes[0].performed_by
            self._put(
                events,
                requirement_id,
                title,
                ActivityCategory.REQUIREMENT,
                action,
                "Requirement created"
                if revision.number.value == 1
                else "Requirement source updated",
                revision.created_at,
                actor,
                requirement_id.value,
                f"/requirements/{requirement_id.value}/capture",
                AuditSourceReference(
                    AuditSourceKind.REQUIREMENT_REVISION,
                    f"{requirement_id.value}:{revision.number.value}",
                ),
            )
        if snapshot.access is not None:
            for index, change in enumerate(snapshot.access.changes):
                action, summary = _access_event(change.kind, change.actor.display_name)
                self._put(
                    events,
                    requirement_id,
                    title,
                    ActivityCategory.ACCESS,
                    action,
                    summary,
                    change.recorded_at,
                    change.performed_by,
                    change.actor.id.value,
                    f"/requirements/{requirement_id.value}/capture",
                    AuditSourceReference(
                        AuditSourceKind.ACCESS_CHANGE,
                        f"{requirement_id.value}:{index}:{change.recorded_at.isoformat()}",
                    ),
                )
        rounds = self._analysis_audit.list_rounds(requirement_id)
        round_times = self._round_times(rounds, breakdown_revisions, fallback)
        for round_ in rounds:
            occurred_at = round_times[round_.id.value]
            self._put(
                events,
                requirement_id,
                title,
                ActivityCategory.CLARIFICATION,
                ActivityAction.ANALYSIS_GENERATED,
                f"Analysis round {round_.number} generated",
                occurred_at,
                None,
                round_.id.value,
                f"/requirements/{requirement_id.value}/clarify",
                AuditSourceReference(AuditSourceKind.ANALYSIS_ROUND, round_.id.value),
            )
            for index, question_change in enumerate(round_.question_changes):
                if question_change.action not in (
                    QuestionChangeAction.RETIRED,
                    QuestionChangeAction.REPLACED,
                ):
                    continue
                description = (
                    "Clarification revised after re-analysis"
                    if question_change.action is QuestionChangeAction.REPLACED
                    else "Clarification retired after re-analysis"
                )
                self._put(
                    events,
                    requirement_id,
                    title,
                    ActivityCategory.CLARIFICATION,
                    ActivityAction.QUESTION_SUPERSEDED,
                    description,
                    occurred_at,
                    None,
                    question_change.question_id.value,
                    f"/requirements/{requirement_id.value}/clarify",
                    AuditSourceReference(
                        AuditSourceKind.ANALYSIS_ROUND,
                        f"{round_.id.value}:question-change:{index}",
                    ),
                )
        for question in self._analysis_audit.list_questions(requirement_id):
            self._question_events(
                question,
                title,
                round_times.get(question.first_analysis_id.value, fallback),
                events,
            )
        self._breakdown_events(requirement_id, title, breakdown_revisions, events)
        self._knowledge_events(requirement_id, title, events)
        for record in self._jobs.list_for_requirement(requirement_id):
            job = record.job
            if not job.status.terminal:
                continue
            action = {
                AiJobStatus.SUCCEEDED: ActivityAction.AI_SUCCEEDED,
                AiJobStatus.FAILED: ActivityAction.AI_FAILED,
                AiJobStatus.CANCELLED: ActivityAction.AI_CANCELLED,
            }[job.status]
            if (
                job.operation is AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE
                and job.status is AiJobStatus.SUCCEEDED
            ):
                action = ActivityAction.KNOWLEDGE_SCREENED
            resource_path = (
                job.result_resources[0].path
                if job.result_resources
                else f"/requirements/{requirement_id.value}"
            )
            self._put(
                events,
                requirement_id,
                title,
                (
                    ActivityCategory.KNOWLEDGE
                    if job.operation
                    in {
                        AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE,
                        AiJobOperation.SCREEN_PRIOR_ART,
                    }
                    else ActivityCategory.GENERATION
                ),
                action,
                f"{job.operation.value.replace('_', ' ').capitalize()} {job.status.value}",
                job.completed_at or job.updated_at,
                job.created_by,
                job.id.value,
                resource_path,
                AuditSourceReference(AuditSourceKind.AI_JOB, job.id.value),
            )

    def _knowledge_events(
        self,
        requirement_id: RequirementId,
        title: str,
        events: dict[str, ActivityEvent],
    ) -> None:
        path = f"/requirements/{requirement_id.value}/knowledge"
        for finding in self._knowledge.list_related_findings(requirement_id):
            for index, decision in enumerate(finding.decisions):
                action, summary = _knowledge_decision_event(finding, decision.kind, index)
                self._put(
                    events,
                    requirement_id,
                    title,
                    ActivityCategory.KNOWLEDGE,
                    action,
                    summary,
                    decision.recorded_at,
                    decision.actor,
                    finding.id.value,
                    path,
                    AuditSourceReference(
                        AuditSourceKind.KNOWLEDGE_FINDING,
                        f"{requirement_id.value}:{finding.id.value}:{index}",
                    ),
                )

    @staticmethod
    def _round_times(
        rounds: list[AnalysisRound],
        revisions: list[BreakdownRevision],
        fallback: datetime,
    ) -> dict[str, datetime]:
        result: dict[str, datetime] = {}
        for round_ in rounds:
            provenance = round_.analysis.provenance
            if provenance is not None:
                result[round_.id.value] = provenance.generated_at
                continue
            matching = next(
                (
                    revision.created_at
                    for revision in revisions
                    if revision.analysis is not None and revision.analysis.id == round_.analysis.id
                ),
                fallback,
            )
            result[round_.id.value] = matching
        return result

    def _question_events(
        self,
        question: ClarificationQuestion,
        title: str,
        opened_at: datetime,
        events: dict[str, ActivityEvent],
    ) -> None:
        requirement_id = question.requirement_id
        path = f"/requirements/{requirement_id.value}/clarify"
        self._put(
            events,
            requirement_id,
            title,
            ActivityCategory.CLARIFICATION,
            ActivityAction.QUESTION_ASKED,
            f"Clarification opened: {question.subject}",
            question.asked_at or opened_at,
            question.asked_by,
            question.id.value,
            path,
            AuditSourceReference(AuditSourceKind.CLARIFICATION_QUESTION, question.id.value),
        )
        for index, change in enumerate(question.assignment_history):
            assignee = change.assignee.display_name if change.assignee else "Unassigned"
            self._put(
                events,
                requirement_id,
                title,
                ActivityCategory.CLARIFICATION,
                ActivityAction.QUESTION_ASSIGNED,
                f"Clarification assignment changed to {assignee}",
                change.changed_at,
                change.changed_by,
                question.id.value,
                path,
                AuditSourceReference(
                    AuditSourceKind.CLARIFICATION_QUESTION,
                    f"{question.id.value}:assignment:{index}",
                ),
            )
        if question.classification_changed_at is not None:
            self._put(
                events,
                requirement_id,
                title,
                ActivityCategory.CLARIFICATION,
                ActivityAction.QUESTION_CLASSIFIED,
                "Clarification severity or blocker status changed",
                question.classification_changed_at,
                question.classification_changed_by,
                question.id.value,
                path,
                AuditSourceReference(
                    AuditSourceKind.CLARIFICATION_QUESTION,
                    f"{question.id.value}:classification:{question.version}",
                ),
            )
        if question.answered_at is not None:
            self._put(
                events,
                requirement_id,
                title,
                ActivityCategory.CLARIFICATION,
                ActivityAction.QUESTION_RESOLVED,
                f"Clarification resolved: {question.subject}",
                question.answered_at,
                question.answered_by,
                question.id.value,
                path,
                AuditSourceReference(AuditSourceKind.CLARIFICATION_QUESTION, question.id.value),
            )

    def _breakdown_events(
        self,
        requirement_id: RequirementId,
        title: str,
        revisions: list[BreakdownRevision],
        events: dict[str, ActivityEvent],
    ) -> None:
        previous_status = self._previous_review_status
        for revision in revisions:
            source = AuditSourceReference(
                AuditSourceKind.BREAKDOWN_REVISION,
                f"{requirement_id.value}:{revision.number.value}",
            )
            if revision.analysis:
                for proposal in revision.analysis.intent_proposals:
                    for intent_decision in proposal.decisions:
                        self._put(
                            events,
                            requirement_id,
                            title,
                            ActivityCategory.GOVERNANCE,
                            ActivityAction.INTENT_PROPOSAL_DECIDED,
                            (
                                f"{proposal.kind.value.replace('_', ' ').capitalize()} "
                                f"proposal {intent_decision.status.value}"
                            ),
                            intent_decision.decided_at,
                            intent_decision.decided_by,
                            proposal.id.value,
                            f"/requirements/{requirement_id.value}/confirm",
                            AuditSourceReference(
                                AuditSourceKind.INTENT_PROPOSAL,
                                f"{proposal.id.value}:{intent_decision.version}",
                            ),
                        )
                if revision.analysis.confirmed_at:
                    analysis_source_id = (
                        revision.analysis.id.value
                        if revision.analysis.id is not None
                        else f"{requirement_id.value}:legacy-analysis"
                    )
                    self._put(
                        events,
                        requirement_id,
                        title,
                        ActivityCategory.GOVERNANCE,
                        ActivityAction.ANALYSIS_CONFIRMED,
                        "Analysis confirmed",
                        revision.analysis.confirmed_at,
                        revision.analysis.confirmed_by,
                        revision.analysis.id.value if revision.analysis.id else None,
                        f"/requirements/{requirement_id.value}/confirm",
                        AuditSourceReference(
                            AuditSourceKind.ANALYSIS_ROUND,
                            analysis_source_id,
                        ),
                    )
            artifacts = tuple(
                item
                for item in (revision.epic, *revision.features, *revision.stories)
                if item is not None
            )
            for artifact in artifacts:
                for approval in artifact.approvals:
                    self._approval_event(requirement_id, title, approval, events)
            review = revision.review
            if review is None:
                continue
            for approval in review.approvals:
                self._approval_event(requirement_id, title, approval, events)
            for comment in review.comments:
                self._put(
                    events,
                    requirement_id,
                    title,
                    ActivityCategory.GOVERNANCE,
                    ActivityAction.REVIEW_COMMENTED,
                    f"Comment added to {comment.target.kind.value}",
                    comment.recorded_at,
                    comment.recorded_by,
                    comment.target.item_id,
                    f"/requirements/{requirement_id.value}/review",
                    AuditSourceReference(AuditSourceKind.REVIEW_COMMENT, comment.id),
                )
            for decision in review.decisions:
                if decision.target_flag_id is None:
                    continue
                self._put(
                    events,
                    requirement_id,
                    title,
                    ActivityCategory.GOVERNANCE,
                    ActivityAction.REVIEW_FLAG_RESOLVED,
                    "Review flag resolved",
                    decision.recorded_at,
                    decision.recorded_by,
                    decision.target_flag_id.value,
                    f"/requirements/{requirement_id.value}/review",
                    AuditSourceReference(AuditSourceKind.REVIEW_DECISION, decision.id.value),
                )
            if review.status != previous_status:
                transition = {
                    BreakdownStatus.UNDER_REVIEW: (
                        ActivityAction.BREAKDOWN_SUBMITTED,
                        "Breakdown submitted for review",
                    ),
                    BreakdownStatus.NEEDS_REVISION: (
                        ActivityAction.BREAKDOWN_NEEDS_REVISION,
                        "Breakdown needs revision",
                    ),
                }.get(review.status)
                if transition is not None:
                    self._put(
                        events,
                        requirement_id,
                        title,
                        ActivityCategory.GOVERNANCE,
                        transition[0],
                        transition[1],
                        revision.created_at,
                        None,
                        requirement_id.value,
                        f"/requirements/{requirement_id.value}/review",
                        source,
                    )
            previous_status = review.status

    def _approval_event(
        self,
        requirement_id: RequirementId,
        title: str,
        approval: Approval,
        events: dict[str, ActivityEvent],
    ) -> None:
        if approval.target.kind is ApprovalTargetKind.BREAKDOWN:
            action = ActivityAction.BREAKDOWN_APPROVED
            summary = "Breakdown received final approval"
        elif approval.decision is ApprovalDecision.REJECTED:
            action = ActivityAction.STORY_REJECTED
            summary = "Story rejected"
        else:
            action = ActivityAction.ARTIFACT_APPROVED
            summary = f"{approval.target.kind.value.capitalize()} approved"
        self._put(
            events,
            requirement_id,
            title,
            ActivityCategory.GOVERNANCE,
            action,
            summary,
            approval.recorded_at,
            approval.recorded_by,
            approval.target.item_id,
            f"/requirements/{requirement_id.value}/review",
            AuditSourceReference(AuditSourceKind.APPROVAL, approval.id.value),
        )

    @staticmethod
    def _put(
        events: dict[str, ActivityEvent],
        requirement_id: RequirementId,
        title: str,
        category: ActivityCategory,
        action: ActivityAction,
        summary: str,
        occurred_at: datetime,
        actor: ActorSnapshot | None,
        target_id: str | None,
        resource_path: str,
        source: AuditSourceReference,
    ) -> None:
        event_id = _event_id(action.value, source.kind.value, source.source_id)
        events[event_id] = ActivityEvent(
            event_id,
            requirement_id,
            title,
            category,
            action,
            summary,
            occurred_at,
            actor,
            target_id,
            resource_path,
            (source,),
        )

    def list_current_blockers(self) -> list[BlockerEvidence]:
        blockers: list[BlockerEvidence] = []
        for snapshot in self._snapshots.list_snapshots():
            requirement_id = snapshot.requirement.id
            title = snapshot.requirement.title.value
            round_times = self._round_times(
                self._analysis_audit.list_rounds(requirement_id),
                self._revisions.list_breakdown_revisions(requirement_id),
                snapshot.updated_at,
            )
            for question in snapshot.questions:
                if not question.is_active or not question.is_blocker:
                    continue
                opened_at = question.asked_at or round_times.get(
                    question.first_analysis_id.value, snapshot.updated_at
                )
                blockers.append(
                    BlockerEvidence(
                        f"question:{question.id.value}",
                        requirement_id,
                        title,
                        question.subject,
                        opened_at,
                        question.asked_by,
                        f"/requirements/{requirement_id.value}/clarify",
                        AuditSourceReference(
                            AuditSourceKind.CLARIFICATION_QUESTION, question.id.value
                        ),
                    )
                )
            if snapshot.review is None or not self._review_is_fresh(snapshot):
                continue
            for flag in snapshot.review.flags:
                if flag.status is FlagStatus.OPEN and flag.severity is FlagSeverity.BLOCKING:
                    blockers.append(
                        BlockerEvidence(
                            f"flag:{flag.id.value}",
                            requirement_id,
                            title,
                            flag.title,
                            snapshot.review.generated_at,
                            None,
                            f"/requirements/{requirement_id.value}/review",
                            AuditSourceReference(AuditSourceKind.REVIEW_FLAG, flag.id.value),
                        )
                    )
        return blockers

    @staticmethod
    def _review_is_fresh(snapshot: RequirementWorklistSnapshot) -> bool:
        if snapshot.review is None or snapshot.analysis is None or snapshot.epic is None:
            return False
        evidence = ReviewEvidence(
            snapshot.requirement,
            snapshot.analysis,
            snapshot.epic,
            snapshot.features,
            snapshot.stories,
            tuple(question for question in snapshot.questions if question.is_active),
        )
        return snapshot.review.evidence_fingerprint == evidence_fingerprint(evidence)


class InMemoryActivityReadAdapter(RepositoryActivityProjection):
    """Named offline adapter for composition-root clarity."""


def _knowledge_decision_event(
    finding: KnowledgeFinding,
    kind: KnowledgeDecisionKind,
    index: int,
) -> tuple[ActivityAction, str]:
    if kind is KnowledgeDecisionKind.DISTINCT:
        return ActivityAction.REQUIREMENT_MARKED_DISTINCT, "Possible duplicate marked distinct"
    if kind is KnowledgeDecisionKind.DUPLICATE:
        return ActivityAction.REQUIREMENT_MARKED_DUPLICATE, "Requirement closed as duplicate"
    if kind is KnowledgeDecisionKind.SOURCE_RETIRED:
        return (
            ActivityAction.FINDING_SOURCE_RETIRED,
            "Finding closed: a Requirement was retired from the knowledge corpus",
        )
    if kind is KnowledgeDecisionKind.RESOLUTION_PROPOSED:
        return ActivityAction.CONFLICT_RESOLUTION_PROPOSED, "Shared conflict resolution proposed"
    if finding.status is KnowledgeFindingStatus.RESOLVED and index == len(finding.decisions) - 1:
        return ActivityAction.CONFLICT_RESOLVED, "Both Requirement owners accepted the resolution"
    return ActivityAction.CONFLICT_RESOLUTION_ACCEPTED, "Conflict resolution accepted by an owner"


def _access_event(kind: AccessChangeKind, actor_name: str) -> tuple[ActivityAction, str]:
    return {
        AccessChangeKind.CLAIMED: (
            ActivityAction.OWNER_CLAIMED,
            f"{actor_name} claimed ownership",
        ),
        AccessChangeKind.TRANSFERRED: (
            ActivityAction.OWNER_TRANSFERRED,
            f"Ownership transferred to {actor_name}",
        ),
        AccessChangeKind.REVIEWER_ASSIGNED: (
            ActivityAction.REVIEWER_ASSIGNED,
            f"{actor_name} assigned as reviewer",
        ),
        AccessChangeKind.REVIEWER_REMOVED: (
            ActivityAction.REVIEWER_REMOVED,
            f"{actor_name} removed as reviewer",
        ),
    }[kind]
