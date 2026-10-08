"""Bounded PostgreSQL reader for the maintained Requirement worklist projection."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import cast

from psycopg.types.json import Jsonb

from smb_requirement_agent.application.ports.requirement_knowledge import KnowledgeReviewPort
from smb_requirement_agent.infrastructure.persistence.payload_fields import JsonObject
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import _integer
from smb_requirement_agent.infrastructure.persistence.shared_payloads import actor_from_payload
from smb_requirement_agent.reporting.application.ports.activity import (
    ActivityQuery,
    ActivityReadPort,
)
from smb_requirement_agent.reporting.application.ports.requirement_worklist import (
    CurrentWorklistProjectionPort,
    RequirementWorklistSnapshot,
    RequirementWorklistSnapshotPort,
    WorkflowStatus,
    WorklistSort,
)
from smb_requirement_agent.reporting.application.use_cases.requirement_worklist import (
    ArtifactCounts,
    ListRequirementWorklist,
    NextAction,
    OwnerFacet,
    RequirementWorklistItem,
    RequirementWorklistQuery,
    RequirementWorklistResult,
    WorkflowStage,
)
from smb_requirement_agent.reporting.infrastructure.activity_codec import (
    activity_from_payload,
    activity_to_payload,
    actor_to_payload,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresRequirementWorklistReader:
    """Filter and page projection rows before hydrating aggregate snapshots."""

    def __init__(self, store: PostgresSession, snapshots: RequirementWorklistSnapshotPort) -> None:
        self._store = store
        self._snapshots = snapshots

    def execute(self, query: RequirementWorklistQuery) -> RequirementWorklistResult:
        access_sql, access_params = self._access_filter(query)
        search_sql, search_params = self._search_filter(query.q)
        scope_sql = access_sql + search_sql
        scope_params = access_params + search_params
        status_sql, status_params = self._status_filter(query)

        order_sql = {
            WorklistSort.UPDATED_DESC: "latest_activity DESC, requirement_id ASC",
            WorklistSort.UPDATED_ASC: "latest_activity ASC, requirement_id ASC",
            WorklistSort.TITLE_ASC: 'title_order COLLATE "C" ASC, requirement_id ASC',
            WorklistSort.TITLE_DESC: 'title_order COLLATE "C" DESC, requirement_id ASC',
        }[query.sort]

        with self._store.connection() as connection:
            page_rows = connection.execute(
                """
                SELECT requirement_id, workflow_status, current_stage, next_action,
                       answered_items, unresolved_items, stale_items, epic_count,
                       feature_count, story_count, latest_activity, last_activity_payload
                FROM requirement_worklist_projection
                WHERE true
                """
                + scope_sql
                + status_sql
                + f" ORDER BY {order_sql} OFFSET %s LIMIT %s",
                scope_params + status_params + (query.offset, query.limit),
            ).fetchall()
            total_row = connection.execute(
                "SELECT count(*) FROM requirement_worklist_projection WHERE true"
                + scope_sql
                + status_sql,
                scope_params + status_params,
            ).fetchone()
            count_rows = connection.execute(
                """
                SELECT workflow_status, count(*)
                FROM requirement_worklist_projection WHERE true
                """
                + scope_sql
                + " GROUP BY workflow_status",
                scope_params,
            ).fetchall()
            facet_rows = connection.execute(
                """
                SELECT owner_payload, count(*)
                FROM requirement_worklist_projection
                WHERE true
                """
                + scope_sql
                + " AND owner_payload IS NOT NULL GROUP BY owner_id, owner_payload "
                + "ORDER BY lower(owner_payload->>'display_name')",
                scope_params,
            ).fetchall()
            attention_rows = connection.execute(
                """
                SELECT requirement_id, workflow_status, current_stage, next_action,
                       answered_items, unresolved_items, stale_items, epic_count,
                       feature_count, story_count, latest_activity, last_activity_payload
                FROM requirement_worklist_projection
                WHERE workflow_status IN (
                    'needs_answers','stale','ready_for_review','needs_revision','knowledge_review'
                )
                """
                + access_sql
                + " ORDER BY attention_rank ASC, latest_activity ASC, requirement_id ASC LIMIT 3",
                access_params,
            ).fetchall()

        selected_ids = tuple(
            dict.fromkeys(
                [str(row[0]) for row in page_rows] + [str(row[0]) for row in attention_rows]
            )
        )
        snapshots = {
            item.requirement.id.value: item for item in self._snapshots.list_snapshots(selected_ids)
        }
        items = {
            str(row[0]): self._item(row, snapshots[str(row[0])])
            for row in page_rows + attention_rows
            if str(row[0]) in snapshots
        }
        status_counts = {status: 0 for status in WorkflowStatus}
        for row in count_rows:
            status_counts[WorkflowStatus(str(row[0]))] = _integer(row[1])
        owner_facets = tuple(
            OwnerFacet(self._actor(row[0]).snapshot(), _integer(row[1])) for row in facet_rows
        )
        page = tuple(items[str(row[0])] for row in page_rows if str(row[0]) in items)
        attention = tuple(items[str(row[0])] for row in attention_rows if str(row[0]) in items)
        total = _integer(total_row[0]) if total_row is not None else 0
        return RequirementWorklistResult(
            requirements=page,
            attention=attention,
            total=total,
            offset=query.offset,
            limit=query.limit,
            has_more=query.offset + len(page) < total,
            status_counts=status_counts,
            owner_facets=owner_facets,
        )

    @staticmethod
    def _access_filter(query: RequirementWorklistQuery) -> tuple[str, tuple[object, ...]]:
        sql = ""
        params: tuple[object, ...] = ()
        if query.owner_id is not None:
            sql += " AND owner_id=%s"
            params += (query.owner_id.value,)
        if query.assigned_to_me:
            actor_id = query.current_actor_id.value if query.current_actor_id is not None else ""
            sql += " AND (owner_id=%s OR %s=ANY(reviewer_ids))"
            params += (actor_id, actor_id)
        return sql, params

    @staticmethod
    def _search_filter(raw_query: str | None) -> tuple[str, tuple[object, ...]]:
        query = (raw_query or "").strip().casefold()
        if not query:
            return "", ()
        return (
            " AND search_text LIKE %s ESCAPE '!'",
            ("%" + query.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%",),
        )

    @staticmethod
    def _status_filter(query: RequirementWorklistQuery) -> tuple[str, tuple[object, ...]]:
        if not query.workflow_statuses:
            return "", ()
        return " AND workflow_status=ANY(%s)", ([item.value for item in query.workflow_statuses],)

    @staticmethod
    def _actor(value: object) -> ActorProfile:
        return actor_from_payload(cast(JsonObject, value))

    @staticmethod
    def _item(row: tuple[object, ...], snapshot: object) -> RequirementWorklistItem:

        resolved = cast(RequirementWorklistSnapshot, snapshot)
        resolved = replace(resolved, updated_at=cast(datetime, row[10]))
        return RequirementWorklistItem(
            snapshot=resolved,
            workflow_status=WorkflowStatus(str(row[1])),
            current_stage=WorkflowStage(str(row[2])),
            next_action=NextAction(str(row[3])),
            answered_items=_integer(row[4]),
            unresolved_items=_integer(row[5]),
            stale_items=_integer(row[6]),
            artifact_counts=ArtifactCounts(_integer(row[7]), _integer(row[8]), _integer(row[9])),
            last_activity=activity_from_payload(row[11]),
        )


class PostgresWorklistProjectionMaintainer(CurrentWorklistProjectionPort):
    """Persist the Application-owned pure classification for one Requirement."""

    def __init__(
        self,
        store: PostgresSession,
        snapshots: RequirementWorklistSnapshotPort,
        knowledge: KnowledgeReviewPort,
        activity: ActivityReadPort,
        activity_projection: CurrentWorklistProjectionPort,
    ) -> None:
        self._store = store
        self._snapshots = snapshots
        self._knowledge = knowledge
        self._activity = activity
        self._activity_projection = activity_projection

    def refresh(self, requirement_id: RequirementId) -> None:
        snapshots = self._snapshots.list_snapshots((requirement_id.value,))
        self._activity_projection.refresh(requirement_id)
        with self._store.connection() as connection:
            if not snapshots:
                connection.execute(
                    "DELETE FROM requirement_worklist_projection WHERE requirement_id=%s",
                    (requirement_id.value,),
                )
                return
            snapshot = snapshots[0]
            latest_activity = max(
                (
                    event
                    for event in self._activity.query(
                        ActivityQuery(requirement_id=requirement_id, limit=1)
                    ).items
                ),
                key=lambda event: (event.occurred_at, event.id),
                default=None,
            )
            item = ListRequirementWorklist.classify(
                snapshot,
                latest_activity,
                knowledge=self._knowledge.execute(requirement_id),
            )
            owner = item.owner
            connection.execute(
                """
                INSERT INTO requirement_worklist_projection (
                    requirement_id,title,search_text,requirement_status,workflow_status,
                    current_stage,next_action,answered_items,unresolved_items,stale_items,
                    epic_count,feature_count,story_count,owner_id,owner_payload,
                    reviewer_ids,reviewer_count,active_ai_operation,latest_activity,
                    last_activity_payload,attention_rank,title_order,projected_at
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()
                ) ON CONFLICT (requirement_id) DO UPDATE SET
                    title=EXCLUDED.title,search_text=EXCLUDED.search_text,
                    title_order=EXCLUDED.title_order,
                    requirement_status=EXCLUDED.requirement_status,
                    workflow_status=EXCLUDED.workflow_status,current_stage=EXCLUDED.current_stage,
                    next_action=EXCLUDED.next_action,answered_items=EXCLUDED.answered_items,
                    unresolved_items=EXCLUDED.unresolved_items,stale_items=EXCLUDED.stale_items,
                    epic_count=EXCLUDED.epic_count,feature_count=EXCLUDED.feature_count,
                    story_count=EXCLUDED.story_count,owner_id=EXCLUDED.owner_id,
                    owner_payload=EXCLUDED.owner_payload,reviewer_ids=EXCLUDED.reviewer_ids,
                    reviewer_count=EXCLUDED.reviewer_count,
                    active_ai_operation=EXCLUDED.active_ai_operation,
                    latest_activity=EXCLUDED.latest_activity,
                    last_activity_payload=EXCLUDED.last_activity_payload,
                    attention_rank=EXCLUDED.attention_rank,projected_at=EXCLUDED.projected_at
                """,
                (
                    requirement_id.value,
                    snapshot.requirement.title.value,
                    " ".join(
                        (
                            requirement_id.value,
                            snapshot.requirement.title.value,
                            snapshot.requirement.description.value,
                        )
                    ).casefold(),
                    snapshot.requirement.status.value,
                    item.workflow_status.value,
                    item.current_stage.value,
                    item.next_action.value,
                    item.answered_items,
                    item.unresolved_items,
                    item.stale_items,
                    item.artifact_counts.epics,
                    item.artifact_counts.features,
                    item.artifact_counts.stories,
                    owner.id.value if owner is not None else None,
                    Jsonb(actor_to_payload(owner)) if owner is not None else None,
                    [reviewer.actor.id.value for reviewer in snapshot.access.reviewers]
                    if snapshot.access is not None
                    else [],
                    item.reviewer_count,
                    snapshot.active_ai_operation.value
                    if snapshot.active_ai_operation is not None
                    else None,
                    latest_activity.occurred_at if latest_activity else snapshot.updated_at,
                    Jsonb(activity_to_payload(latest_activity))
                    if latest_activity is not None
                    else None,
                    self._attention_rank(item.workflow_status),
                    snapshot.requirement.title.value.casefold(),
                ),
            )

    @staticmethod
    def _attention_rank(status: WorkflowStatus) -> int:
        return {
            WorkflowStatus.NEEDS_ANSWERS: 0,
            WorkflowStatus.KNOWLEDGE_REVIEW: 0,
            WorkflowStatus.STALE: 1,
            WorkflowStatus.NEEDS_REVISION: 1,
            WorkflowStatus.READY_FOR_REVIEW: 2,
        }.get(status, 100)
