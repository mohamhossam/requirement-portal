"""SQL-filtered activity reads from the rebuildable audit projection."""

from datetime import datetime
from typing import cast

from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.governance.domain.review.entities import BreakdownStatus
from smb_requirement_agent.infrastructure.persistence.payload_fields import JsonObject
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import _integer
from smb_requirement_agent.infrastructure.persistence.shared_payloads import actor_from_payload
from smb_requirement_agent.reporting.application.ports.activity import (
    ActivityAction,
    ActivityEvent,
    ActivityQuery,
    ActivityReportEvidence,
    ActivityResult,
    AuditSourceKind,
    AuditSourceReference,
    BlockerEvidence,
    WeeklyActivityEvidence,
)
from smb_requirement_agent.reporting.infrastructure.activity_codec import (
    activity_from_payload,
    activity_to_payload,
    actor_to_payload,
)
from smb_requirement_agent.reporting.infrastructure.postgres_activity_reader import (
    PostgresActivityReadAdapter,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresProjectedActivity:
    def __init__(self, store: PostgresSession, source: PostgresActivityReadAdapter) -> None:
        self._store = store
        self._source = source

    def refresh(self, requirement_id: RequirementId) -> None:
        with self._store.connection() as connection:
            cursor = connection.execute(
                "SELECT requirement_revision,breakdown_revision,review_status,first_recorded_at "
                "FROM activity_projection_cursors WHERE requirement_id=%s",
                (requirement_id.value,),
            ).fetchone()
            delta = self._source.project_since(
                requirement_id,
                _integer(cursor[0]) if cursor else 0,
                _integer(cursor[1]) if cursor else 0,
                BreakdownStatus(str(cursor[2])) if cursor and cursor[2] else None,
                cast(datetime, cursor[3]) if cursor else None,
            )
            for event in delta.events:
                connection.execute(
                    "INSERT INTO activity_event_projection "
                    "(event_id,requirement_id,category,action,actor_id,occurred_at,payload) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (event_id) DO NOTHING",
                    (
                        event.id,
                        requirement_id.value,
                        event.category.value,
                        event.action.value,
                        event.actor.id.value if event.actor else None,
                        event.occurred_at,
                        Jsonb(activity_to_payload(event)),
                    ),
                )
            for kind, source_id, version in delta.source_versions:
                connection.execute(
                    "INSERT INTO activity_input_cursors "
                    "(requirement_id,source_kind,source_id,source_version) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT (requirement_id,source_kind,source_id) "
                    "DO UPDATE SET source_version=EXCLUDED.source_version",
                    (requirement_id.value, kind, source_id, version),
                )
            connection.execute(
                "DELETE FROM current_blocker_projection WHERE requirement_id=%s",
                (requirement_id.value,),
            )
            for blocker in delta.blockers:
                payload = {
                    "id": blocker.id,
                    "requirement_id": requirement_id.value,
                    "requirement_title": blocker.requirement_title,
                    "title": blocker.title,
                    "opened_at": blocker.opened_at.isoformat(),
                    "actor": actor_to_payload(blocker.actor) if blocker.actor else None,
                    "resource_path": blocker.resource_path,
                    "source": {
                        "kind": blocker.source.kind.value,
                        "source_id": blocker.source.source_id,
                    },
                }
                connection.execute(
                    "INSERT INTO current_blocker_projection "
                    "(blocker_id,requirement_id,opened_at,payload) "
                    "VALUES (%s,%s,%s,%s)",
                    (blocker.id, requirement_id.value, blocker.opened_at, Jsonb(payload)),
                )
            connection.execute(
                "INSERT INTO activity_projection_cursors "
                "(requirement_id,requirement_revision,breakdown_revision,"
                "review_status,first_recorded_at) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (requirement_id) DO UPDATE SET "
                "requirement_revision=EXCLUDED.requirement_revision, "
                "breakdown_revision=EXCLUDED.breakdown_revision,review_status=EXCLUDED.review_status",
                (
                    requirement_id.value,
                    delta.requirement_revision,
                    delta.breakdown_revision,
                    delta.review_status.value if delta.review_status else None,
                    delta.first_recorded_at,
                ),
            )

    def query(self, query: ActivityQuery) -> ActivityResult:
        clauses: list[str] = []
        values: list[object] = []
        for column, value in (
            ("requirement_id", query.requirement_id.value if query.requirement_id else None),
            ("actor_id", query.actor_id.value if query.actor_id else None),
        ):
            if value is not None:
                clauses.append(f"{column}=%s")
                values.append(value)
        for column, choices in (("category", query.categories), ("action", query.actions)):
            if choices:
                clauses.append(f"{column}=ANY(%s)")
                values.append([item.value for item in choices])
        if query.occurred_from is not None:
            clauses.append("occurred_at >= %s")
            values.append(query.occurred_from)
        if query.occurred_before is not None:
            clauses.append("occurred_at < %s")
            values.append(query.occurred_before)
        where = " AND ".join(clauses) or "true"
        with self._store.connection() as connection:
            # One statement gives the count and page the same database snapshot.
            row = connection.execute(
                "WITH selected AS (SELECT * FROM activity_event_projection WHERE " + where + "), "  # noqa: S608 - constant fragments; values are parameters
                "page AS (SELECT payload,occurred_at,event_id FROM selected "
                "ORDER BY occurred_at DESC,event_id DESC OFFSET %s LIMIT %s) "
                "SELECT (SELECT count(*) FROM selected), "
                "COALESCE(jsonb_agg(payload ORDER BY occurred_at DESC,event_id DESC),'[]') "
                "FROM page",
                (*values, query.offset, query.limit),
            ).fetchone()
        if row is None:
            raise PersistenceError("Activity aggregate query returned no row.")
        items = tuple(self._event(payload) for payload in cast(list[object], row[1]))
        total = _integer(row[0])
        return ActivityResult(
            items, total, query.offset, query.limit, query.offset + len(items) < total
        )

    def window_events(self, start: datetime, before: datetime) -> list[ActivityEvent]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM activity_event_projection WHERE occurred_at >= %s "
                "AND occurred_at < %s ORDER BY occurred_at,event_id",
                (start, before),
            ).fetchall()
        return [self._event(row[0]) for row in rows]

    def aggregate_report(self, start: datetime, before: datetime) -> ActivityReportEvidence:
        with self._store.connection() as connection:
            row = connection.execute(
                "WITH events AS (SELECT event_id,action,occurred_at,"
                "payload->>'target_id' AS target_id "
                "FROM activity_event_projection WHERE occurred_at >= %s AND occurred_at < %s), "
                "weekly AS (SELECT date_trunc('week',occurred_at AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'UTC' AS week_start,action,"
                "array_agg(event_id ORDER BY occurred_at,event_id) AS event_ids "
                "FROM events GROUP BY 1,2), "
                "opened AS (SELECT * FROM events WHERE action=%s), "
                "resolved AS (SELECT DISTINCT ON (target_id) * FROM events WHERE action=%s "
                "AND target_id IS NOT NULL ORDER BY target_id,occurred_at DESC,event_id DESC) "
                "SELECT (SELECT COALESCE(jsonb_agg(to_jsonb(weekly) "
                "ORDER BY week_start,action),'[]') FROM weekly), "
                "(SELECT COALESCE(array_agg(event_id ORDER BY occurred_at,event_id),"
                "'{}'::text[]) FROM opened), "
                "COALESCE(array_agg(r.event_id ORDER BY o.occurred_at,o.event_id),"
                "'{}'::text[]), "
                "percentile_cont(0.5) WITHIN GROUP "
                "(ORDER BY EXTRACT(EPOCH FROM (r.occurred_at-o.occurred_at))/3600) "
                "FILTER (WHERE r.occurred_at >= o.occurred_at) "
                "FROM opened o JOIN resolved r ON r.target_id=o.target_id",
                (
                    start,
                    before,
                    ActivityAction.QUESTION_ASKED.value,
                    ActivityAction.QUESTION_RESOLVED.value,
                ),
            ).fetchone()
        if row is None:
            raise PersistenceError("Activity aggregate query returned no row.")
        weekly = tuple(
            WeeklyActivityEvidence(
                datetime.fromisoformat(str(item["week_start"])),
                ActivityAction(str(item["action"])),
                tuple(cast(list[str], item["event_ids"])),
            )
            for item in cast(list[dict[str, object]], row[0])
        )
        return ActivityReportEvidence(
            weekly,
            tuple(cast(list[str], row[1])),
            tuple(cast(list[str], row[2])),
            float(str(row[3])) if row[3] is not None else None,
        )

    def list_events(self) -> list[ActivityEvent]:
        with self._store.connection() as connection:
            rows = connection.execute("SELECT payload FROM activity_event_projection").fetchall()
        return [self._event(row[0]) for row in rows]

    def list_events_for_requirement(self, requirement_id: RequirementId) -> list[ActivityEvent]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM activity_event_projection WHERE requirement_id=%s",
                (requirement_id.value,),
            ).fetchall()
        return [self._event(row[0]) for row in rows]

    def list_current_blockers(self) -> list[BlockerEvidence]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM current_blocker_projection "
                "ORDER BY opened_at,blocker_id LIMIT 10"
            ).fetchall()
        result: list[BlockerEvidence] = []
        for row in rows:
            payload = cast(JsonObject, row[0])
            actor = payload.get("actor")
            source = cast(JsonObject, payload["source"])
            result.append(
                BlockerEvidence(
                    str(payload["id"]),
                    RequirementId(str(payload["requirement_id"])),
                    str(payload["requirement_title"]),
                    str(payload["title"]),
                    datetime.fromisoformat(str(payload["opened_at"])),
                    actor_from_payload(cast(JsonObject, actor)).snapshot() if actor else None,
                    str(payload["resource_path"]),
                    AuditSourceReference(
                        AuditSourceKind(str(source["kind"])), str(source["source_id"])
                    ),
                )
            )
        return result

    @staticmethod
    def _event(payload: object) -> ActivityEvent:
        result = activity_from_payload(payload)
        if result is None:
            raise PersistenceError("A stored activity event could not be decoded.")
        return result
