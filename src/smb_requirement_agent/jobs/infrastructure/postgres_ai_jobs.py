"""PostgreSQL-leased AI job queue and durable actor notifications."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from psycopg import errors
from psycopg.types.json import Jsonb

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import DbConnection
from smb_requirement_agent.jobs.application.ports.ai_jobs import (
    AiJobBacklog,
    AiJobCommand,
    AiJobRecord,
    JsonValue,
)
from smb_requirement_agent.jobs.domain.entities import (
    ActorNotification,
    AiJob,
    AiJobFailure,
    AiJobId,
    AiJobOperation,
    AiJobOrigin,
    AiJobResultResource,
    AiJobStatus,
    NotificationId,
    NotificationKind,
    NotificationPreference,
)
from smb_requirement_agent.jobs.domain.errors import AiJobConflictError
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

# The operations whose claimed attempt starts in the 'preparing_analysis' phase (AiJob.claim).
_ANALYZER_OPERATIONS = [operation.value for operation in AiJobOperation if operation.uses_analyzer]


class PostgresAiJobStore:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def add(self, record: AiJobRecord) -> None:
        with self._store.connection() as connection:
            self._insert(connection, record)
            self._store.mark_requirement_dirty(record.job.requirement_id)

    def save(self, job: AiJob) -> None:
        with self._store.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE ai_jobs SET status=%s, attempt_count=%s, started_at=%s,
                    completed_at=%s, cancel_requested_at=%s, retry_of_job_id=%s,
                    failure=%s, result_resources=%s, updated_at=%s,
                    phase=%s, completed_units=%s, total_units=%s,
                    current_section_label=%s, version=%s, next_attempt_at=%s,
                    worker_id=CASE WHEN %s THEN NULL ELSE worker_id END,
                    leased_until=CASE WHEN %s THEN NULL ELSE leased_until END,
                    attempt_token=CASE WHEN %s THEN NULL ELSE attempt_token END
                WHERE job_id=%s AND version=%s
                """,
                (
                    job.status.value,
                    job.attempt_count,
                    job.started_at,
                    job.completed_at,
                    job.cancel_requested_at,
                    job.retry_of_job_id.value if job.retry_of_job_id else None,
                    Jsonb(_failure_payload(job.failure)) if job.failure else None,
                    Jsonb([_resource_payload(item) for item in job.result_resources]),
                    job.updated_at,
                    job.phase,
                    job.completed_units,
                    job.total_units,
                    job.current_section_label,
                    job.version,
                    job.next_attempt_at,
                    job.status.terminal,
                    job.status.terminal,
                    job.status.terminal,
                    job.id.value,
                    job.version - 1,
                ),
            )
            if cursor.rowcount != 1:
                raise AiJobConflictError("AI job changed before this mutation could be saved.")
            self._store.mark_requirement_dirty(job.requirement_id)

    def save_fenced(
        self,
        job: AiJob,
        worker_id: str,
        attempt_token: str,
        now: datetime,
    ) -> bool:
        ends_attempt = not job.status.holds_attempt
        with self._store.connection() as connection:
            if not self._lock_attempt(connection, job.id, worker_id, attempt_token, now):
                return False
            cursor = connection.execute(
                """
                UPDATE ai_jobs SET status=%s, attempt_count=%s, started_at=%s,
                    completed_at=%s, cancel_requested_at=%s, retry_of_job_id=%s,
                    failure=%s, result_resources=%s, updated_at=%s,
                    phase=%s, completed_units=%s, total_units=%s,
                    current_section_label=%s, version=%s, next_attempt_at=%s,
                    worker_id=CASE WHEN %s THEN NULL ELSE worker_id END,
                    leased_until=CASE WHEN %s THEN NULL ELSE leased_until END,
                    attempt_token=CASE WHEN %s THEN NULL ELSE attempt_token END
                WHERE job_id=%s AND worker_id=%s AND attempt_token=%s
                  AND leased_until > %s AND version=%s
                """,
                (
                    job.status.value,
                    job.attempt_count,
                    job.started_at,
                    job.completed_at,
                    job.cancel_requested_at,
                    job.retry_of_job_id.value if job.retry_of_job_id else None,
                    Jsonb(_failure_payload(job.failure)) if job.failure else None,
                    Jsonb([_resource_payload(item) for item in job.result_resources]),
                    job.updated_at,
                    job.phase,
                    job.completed_units,
                    job.total_units,
                    job.current_section_label,
                    job.version,
                    job.next_attempt_at,
                    ends_attempt,
                    ends_attempt,
                    ends_attempt,
                    job.id.value,
                    worker_id,
                    attempt_token,
                    now,
                    job.version - 1,
                ),
            )
            if cursor.rowcount != 1:
                return False
            if ends_attempt:
                connection.execute(
                    """
                    UPDATE requirement_ai_job_leases
                    SET job_id=NULL, worker_id=NULL, attempt_token=NULL, leased_until=NULL,
                        updated_at=now()
                    WHERE requirement_id=%s AND job_id=%s AND worker_id=%s
                      AND attempt_token=%s
                    """,
                    (job.requirement_id.value, job.id.value, worker_id, attempt_token),
                )
            self._store.mark_requirement_dirty(job.requirement_id)
            return True

    def report_progress_fenced(
        self,
        job: AiJob,
        worker_id: str,
        attempt_token: str,
        now: datetime,
    ) -> bool:
        with self._store.connection() as connection:
            if not self._lock_attempt(connection, job.id, worker_id, attempt_token, now):
                return False
            cursor = connection.execute(
                """
                UPDATE ai_jobs SET
                    phase=%s, completed_units=%s, total_units=%s,
                    current_section_label=%s, updated_at=%s, version=%s
                WHERE job_id=%s AND worker_id=%s AND attempt_token=%s
                  AND leased_until > %s AND status='running' AND version=%s
                """,
                (
                    job.phase,
                    job.completed_units,
                    job.total_units,
                    job.current_section_label,
                    job.updated_at,
                    job.version,
                    job.id.value,
                    worker_id,
                    attempt_token,
                    now,
                    job.version - 1,
                ),
            )
            return cursor.rowcount == 1

    def get(self, job_id: AiJobId) -> AiJobRecord | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM ai_jobs WHERE job_id=%s", (job_id.value,)
            ).fetchone()
        return record_from_row(row) if row is not None else None

    def get_by_idempotency(self, actor_id: ActorId, key: str) -> AiJobRecord | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT j.* FROM ai_jobs j
                JOIN ai_job_idempotency_keys k ON k.job_id=j.job_id
                WHERE k.actor_id=%s AND k.idempotency_key=%s
                """,
                (actor_id.value, key),
            ).fetchone()
        return record_from_row(row) if row is not None else None

    def bind_idempotency(
        self,
        job_id: AiJobId,
        actor_id: ActorId,
        key: str,
        command_fingerprint: str,
    ) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO ai_job_idempotency_keys
                    (actor_id,idempotency_key,job_id,command_fingerprint)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (actor_id,idempotency_key) DO NOTHING
                """,
                (actor_id.value, key, job_id.value, command_fingerprint),
            )
            row = connection.execute(
                """
                SELECT job_id,command_fingerprint FROM ai_job_idempotency_keys
                WHERE actor_id=%s AND idempotency_key=%s
                """,
                (actor_id.value, key),
            ).fetchone()
            if row is None or str(row[0]) != job_id.value or str(row[1]) != command_fingerprint:
                raise AiJobConflictError("The Idempotency-Key already exists.")

    def find_active_equivalent(
        self, requirement_id: RequirementId, command_fingerprint: str
    ) -> AiJobRecord | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM ai_jobs WHERE requirement_id=%s AND command_fingerprint=%s
                    AND status IN ('queued','running','cancellation_requested')
                ORDER BY created_at LIMIT 1
                """,
                (requirement_id.value, command_fingerprint),
            ).fetchone()
        return record_from_row(row) if row is not None else None

    def reserve_automatic(self, record: AiJobRecord) -> tuple[AiJobRecord, bool]:
        """Serialize automatic scheduling for one Requirement/fingerprint pair."""
        with self._store.connection() as connection:
            lock_key = f"{record.job.requirement_id.value}:{record.job.command_fingerprint}"
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (lock_key,),
            )
            row = connection.execute(
                """
                SELECT * FROM ai_jobs
                WHERE requirement_id=%s AND command_fingerprint=%s
                ORDER BY
                    CASE WHEN status IN ('queued','running','cancellation_requested')
                        THEN 0 ELSE 1 END,
                    created_at DESC,
                    job_id DESC
                LIMIT 1
                """,
                (
                    record.job.requirement_id.value,
                    record.job.command_fingerprint,
                ),
            ).fetchone()
            if row is not None:
                return record_from_row(row), False
            self._insert(connection, record)
            self._store.mark_requirement_dirty(record.job.requirement_id)
            return record, True

    @staticmethod
    def _insert(connection: DbConnection, record: AiJobRecord) -> None:
        # Lock the Requirement row first, as the revision capture at commit does. Otherwise
        # the job's foreign key share-locks it, the lease insert waits on another transaction's
        # new lease row, and that transaction's capture waits on the share lock: a deadlock.
        connection.execute(
            "SELECT 1 FROM requirements WHERE requirement_id = %s FOR UPDATE",
            (record.job.requirement_id.value,),
        )
        try:
            connection.execute(
                """
                INSERT INTO ai_jobs (
                    job_id, requirement_id, operation, status, created_by, command,
                    command_fingerprint, idempotency_key, attempt_count, started_at,
                    completed_at, cancel_requested_at, retry_of_job_id, failure,
                    result_resources, created_at, updated_at, origin,
                    phase, completed_units, total_units, current_section_label
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                _job_values(record),
            )
            connection.execute(
                """
                INSERT INTO ai_job_idempotency_keys
                    (actor_id,idempotency_key,job_id,command_fingerprint)
                VALUES (%s,%s,%s,%s)
                """,
                (
                    record.job.created_by.id.value,
                    record.job.idempotency_key,
                    record.job.id.value,
                    record.job.command_fingerprint,
                ),
            )
            connection.execute(
                """
                INSERT INTO requirement_ai_job_leases (requirement_id)
                VALUES (%s) ON CONFLICT (requirement_id) DO NOTHING
                """,
                (record.job.requirement_id.value,),
            )
        except errors.UniqueViolation as exc:
            raise AiJobConflictError(
                "An equivalent AI job or Idempotency-Key already exists."
            ) from exc

    def list_for_requirement(
        self,
        requirement_id: RequirementId,
        *,
        active_only: bool = False,
        limit: int | None = None,
    ) -> list[AiJobRecord]:
        where = (
            " AND status IN ('queued','running','cancellation_requested')" if active_only else ""
        )
        with self._store.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM ai_jobs WHERE requirement_id=%s{where} "  # noqa: S608 - constant filter; values are parameters
                "ORDER BY created_at DESC LIMIT %s",
                (requirement_id.value, limit),
            ).fetchall()
        return [record_from_row(row) for row in rows]

    def list_all_for_activity(self) -> dict[str, list[AiJobRecord]]:
        """Load portfolio job evidence without a query per Requirement."""
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM ai_jobs ORDER BY requirement_id, created_at DESC"
            ).fetchall()
        records: dict[str, list[AiJobRecord]] = {}
        for row in rows:
            record = record_from_row(row)
            records.setdefault(record.job.requirement_id.value, []).append(record)
        return records

    def prune_finished_inputs(self, completed_before: datetime, batch_size: int) -> int:
        pruned = 0
        while True:
            # One short transaction per batch, so pruning never holds many rows at once.
            with self._store.connection() as connection:
                cursor = connection.execute(
                    """
                    WITH due AS (
                        SELECT job_id FROM ai_jobs
                        WHERE status IN ('succeeded','cancelled') AND completed_at < %s
                            AND payload_pruned_at IS NULL AND operation <> %s
                        ORDER BY completed_at LIMIT %s FOR UPDATE SKIP LOCKED
                    )
                    UPDATE ai_jobs j SET command='{}'::jsonb, payload_pruned_at=now()
                    FROM due WHERE j.job_id=due.job_id
                    """,
                    (
                        completed_before,
                        AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE.value,
                        batch_size,
                    ),
                )
                batch = cursor.rowcount
            pruned += batch
            if batch < batch_size:
                return pruned

    def backlog(self, now: datetime) -> AiJobBacklog:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT operation, count(*), "
                "min(coalesce(next_attempt_at, created_at)) FILTER ("
                "WHERE next_attempt_at IS NULL OR next_attempt_at <= %s) "
                "FROM ai_jobs WHERE status='queued' GROUP BY operation",
                (now,),
            ).fetchall()
        since = [cast(datetime, row[2]) for row in rows if row[2] is not None]
        return AiJobBacklog(
            {str(row[0]): int(cast(int, row[1])) for row in rows}, min(since, default=None)
        )

    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_until: datetime,
        blocked_operations: tuple[AiJobOperation, ...] = (),
    ) -> AiJobRecord | None:
        attempt_token = str(uuid.uuid4())
        with self._store.connection() as connection:
            row = connection.execute(
                """
                WITH candidate AS (
                    SELECT j.job_id, j.requirement_id
                    FROM ai_jobs j
                    JOIN requirement_ai_job_leases lease
                      ON lease.requirement_id=j.requirement_id
                    WHERE (j.operation <> ALL(%s) OR j.status='cancellation_requested') AND (
                        (
                            j.status='queued'
                            AND (j.next_attempt_at IS NULL OR j.next_attempt_at <= %s)
                        )
                        OR (
                            j.status IN ('running','cancellation_requested')
                            AND j.leased_until <= %s
                        )
                    ) AND (lease.leased_until IS NULL OR lease.leased_until <= %s)
                    -- A job waiting out a transient outage keeps its Requirement's order:
                    -- nothing else of that Requirement starts before it runs again.
                    AND NOT EXISTS (
                        SELECT 1 FROM ai_jobs waiting
                        WHERE waiting.requirement_id=j.requirement_id
                          AND waiting.job_id<>j.job_id AND waiting.status='queued'
                          AND waiting.next_attempt_at > %s
                    )
                    ORDER BY
                      CASE WHEN j.status IN ('running','cancellation_requested') THEN 0 ELSE 1 END,
                      CASE WHEN j.origin='user' THEN 0 ELSE 1 END,
                      CASE WHEN j.operation='screen_prior_art' THEN 1 ELSE 0 END,
                      j.created_at
                    FOR UPDATE OF lease SKIP LOCKED
                    LIMIT 1
                ), claimed_lease AS (
                    UPDATE requirement_ai_job_leases lease SET
                      job_id=candidate.job_id, worker_id=%s, attempt_token=%s,
                      leased_until=%s, updated_at=%s
                    FROM candidate
                    WHERE lease.requirement_id=candidate.requirement_id
                    RETURNING candidate.job_id
                )
                UPDATE ai_jobs j SET
                    status=CASE WHEN j.status='cancellation_requested'
                        THEN 'cancellation_requested' ELSE 'running' END,
                    worker_id=%s, attempt_token=%s, leased_until=%s,
                    started_at=COALESCE(j.started_at,%s),
                    attempt_count=CASE WHEN j.status='cancellation_requested'
                        THEN j.attempt_count ELSE j.attempt_count+1 END,
                    -- A new attempt starts from nothing, as AiJob.claim does: a reclaimed
                    -- row must not show the previous attempt's progress or failure.
                    phase=CASE WHEN j.status='cancellation_requested' THEN j.phase
                        WHEN j.operation = ANY(%s::text[]) THEN 'preparing_analysis'
                        ELSE 'running' END,
                    completed_units=CASE WHEN j.status='cancellation_requested'
                        THEN j.completed_units ELSE 0 END,
                    total_units=CASE WHEN j.status='cancellation_requested'
                        THEN j.total_units ELSE NULL END,
                    current_section_label=CASE WHEN j.status='cancellation_requested'
                        THEN j.current_section_label ELSE NULL END,
                    failure=CASE WHEN j.status='cancellation_requested'
                        THEN j.failure ELSE NULL END,
                    next_attempt_at=NULL,
                    updated_at=%s, version=j.version+1
                FROM claimed_lease WHERE j.job_id=claimed_lease.job_id
                RETURNING j.*
                """,
                (
                    [op.value for op in blocked_operations],
                    now,
                    now,
                    now,
                    now,
                    worker_id,
                    attempt_token,
                    lease_until,
                    now,
                    worker_id,
                    attempt_token,
                    lease_until,
                    now,
                    _ANALYZER_OPERATIONS,
                    now,
                ),
            ).fetchone()
            if row is None:
                return None
            record = record_from_row(row)
            self._store.mark_requirement_dirty(record.job.requirement_id)
            return record

    def heartbeat(
        self,
        job_id: AiJobId,
        worker_id: str,
        attempt_token: str,
        now: datetime,
        lease_until: datetime,
    ) -> bool:
        with self._store.connection() as connection:
            cursor = connection.execute(
                """
                WITH renewed AS (
                  UPDATE requirement_ai_job_leases SET leased_until=%s, updated_at=%s
                  WHERE job_id=%s AND worker_id=%s AND attempt_token=%s
                    AND leased_until > %s
                  RETURNING job_id
                )
                UPDATE ai_jobs SET leased_until=%s, updated_at=now()
                FROM renewed
                WHERE ai_jobs.job_id=renewed.job_id AND ai_jobs.worker_id=%s
                  AND ai_jobs.attempt_token=%s
                  AND status IN ('running','cancellation_requested')
                """,
                (
                    lease_until,
                    now,
                    job_id.value,
                    worker_id,
                    attempt_token,
                    now,
                    lease_until,
                    worker_id,
                    attempt_token,
                ),
            )
            return cursor.rowcount == 1

    def release(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                UPDATE requirement_ai_job_leases SET
                  job_id=NULL, worker_id=NULL, attempt_token=NULL, leased_until=NULL,
                  updated_at=now()
                WHERE job_id=%s AND worker_id=%s AND attempt_token=%s
                  AND NOT EXISTS (
                    SELECT 1 FROM ai_jobs j WHERE j.job_id=%s
                      AND j.status IN ('running','cancellation_requested')
                  )
                """,
                (job_id.value, worker_id, attempt_token, job_id.value),
            )

    def fence_attempt(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> bool:
        with self._store.connection() as connection:
            lease = connection.execute(
                "SELECT job_id FROM requirement_ai_job_leases "
                "WHERE job_id=%s AND worker_id=%s AND attempt_token=%s FOR UPDATE",
                (job_id.value, worker_id, attempt_token),
            ).fetchone()
            if lease is None:
                return False
            row = connection.execute(
                """
                UPDATE ai_jobs
                SET worker_id=NULL, leased_until=now(), attempt_token=NULL,
                    updated_at=now(), version=version+1
                WHERE job_id=%s AND worker_id=%s AND attempt_token=%s
                  AND status IN ('running','cancellation_requested')
                RETURNING requirement_id
                """,
                (job_id.value, worker_id, attempt_token),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                """
                UPDATE requirement_ai_job_leases
                SET job_id=NULL, worker_id=NULL, attempt_token=NULL, leased_until=NULL,
                    updated_at=now()
                WHERE requirement_id=%s AND job_id=%s
                  AND worker_id=%s AND attempt_token=%s
                """,
                (str(row[0]), job_id.value, worker_id, attempt_token),
            )
            self._store.mark_requirement_dirty(RequirementId(str(row[0])))
            return True

    @staticmethod
    def _lock_attempt(
        connection: DbConnection,
        job_id: AiJobId,
        worker_id: str,
        attempt_token: str,
        now: datetime,
    ) -> bool:
        """Every attempt mutation locks the Requirement lease before the job row."""
        return (
            connection.execute(
                "SELECT job_id FROM requirement_ai_job_leases "
                "WHERE job_id=%s AND worker_id=%s AND attempt_token=%s "
                "AND leased_until > %s FOR UPDATE",
                (job_id.value, worker_id, attempt_token, now),
            ).fetchone()
            is not None
        )


class PostgresNotificationRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def add(self, notification: ActorNotification) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO actor_notifications
                    (notification_id,recipient_id,job_id,kind,message,resource_path,created_at,read_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (notification_id) DO NOTHING
                """,
                (
                    notification.id.value,
                    notification.recipient_id.value,
                    notification.job_id.value if notification.job_id is not None else None,
                    notification.kind.value,
                    notification.message,
                    notification.resource_path,
                    notification.created_at,
                    notification.read_at,
                ),
            )

    def get(self, notification_id: NotificationId) -> ActorNotification | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM actor_notifications WHERE notification_id=%s",
                (notification_id.value,),
            ).fetchone()
        return _notification(row) if row is not None else None

    def save(self, notification: ActorNotification) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "UPDATE actor_notifications SET read_at=%s WHERE notification_id=%s",
                (notification.read_at, notification.id.value),
            )

    def list_for_actor(
        self, actor_id: ActorId, *, unread_only: bool = False, limit: int | None = None
    ) -> list[ActorNotification]:
        where = " AND read_at IS NULL" if unread_only else ""
        with self._store.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM actor_notifications WHERE recipient_id=%s{where} "  # noqa: S608 - constant filter; values are parameters
                "ORDER BY created_at DESC LIMIT %s",
                (actor_id.value, limit),
            ).fetchall()
        return [_notification(row) for row in rows]

    def delete_read_before(self, cutoff: datetime) -> int:
        with self._store.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM actor_notifications WHERE read_at IS NOT NULL AND read_at < %s",
                (cutoff,),
            )
            return cursor.rowcount

    def get_preference(self, actor_id: ActorId) -> NotificationPreference:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT browser_enabled FROM notification_preferences WHERE actor_id=%s",
                (actor_id.value,),
            ).fetchone()
        return NotificationPreference(actor_id, bool(row[0]) if row is not None else False)

    def save_preference(self, preference: NotificationPreference) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO notification_preferences (actor_id,browser_enabled)
                VALUES (%s,%s) ON CONFLICT (actor_id) DO UPDATE
                SET browser_enabled=EXCLUDED.browser_enabled, updated_at=now()
                """,
                (preference.actor_id.value, preference.browser_enabled),
            )


def _actor_payload(actor: ActorSnapshot) -> dict[str, JsonValue]:
    return {"id": actor.id.value, "display_name": actor.display_name, "email": actor.email}


def _failure_payload(failure: AiJobFailure) -> dict[str, JsonValue]:
    return {
        "code": failure.code,
        "message": failure.message,
        "retryable": failure.retryable,
        "correlation_id": failure.correlation_id,
    }


def _resource_payload(resource: AiJobResultResource) -> dict[str, JsonValue]:
    return {"kind": resource.kind, "path": resource.path}


def _job_values(record: AiJobRecord) -> tuple[object, ...]:
    job = record.job
    return (
        job.id.value,
        job.requirement_id.value,
        job.operation.value,
        job.status.value,
        Jsonb(_actor_payload(job.created_by)),
        Jsonb(record.command.arguments),
        job.command_fingerprint,
        job.idempotency_key,
        job.attempt_count,
        job.started_at,
        job.completed_at,
        job.cancel_requested_at,
        job.retry_of_job_id.value if job.retry_of_job_id else None,
        Jsonb(_failure_payload(job.failure)) if job.failure else None,
        Jsonb([_resource_payload(item) for item in job.result_resources]),
        job.created_at,
        job.updated_at,
        job.origin.value,
        job.phase,
        job.completed_units,
        job.total_units,
        job.current_section_label,
    )


def record_from_row(row: tuple[object, ...]) -> AiJobRecord:
    actor = cast(dict[str, object], row[4])
    command = cast(dict[str, JsonValue], row[5])
    failure = cast(dict[str, object] | None, row[13])
    resources = cast(list[dict[str, object]], row[14])
    job = AiJob(
        AiJobId(str(row[0])),
        RequirementId(str(row[1])),
        AiJobOperation(str(row[2])),
        AiJobStatus(str(row[3])),
        ActorSnapshot(
            ActorId(str(actor["id"])),
            str(actor["display_name"]),
            str(actor["email"]) if actor.get("email") is not None else None,
        ),
        cast(datetime, row[17]),
        cast(datetime, row[18]),
        str(row[7]),
        str(row[6]),
        int(cast(int, row[8])),
        cast(datetime | None, row[9]),
        cast(datetime | None, row[10]),
        cast(datetime | None, row[11]),
        AiJobId(str(row[12])) if row[12] is not None else None,
        AiJobFailure(
            str(failure["code"]),
            str(failure["message"]),
            bool(failure["retryable"]),
            str(failure.get("correlation_id") or "legacy-unavailable"),
        )
        if failure is not None
        else None,
        tuple(AiJobResultResource(str(item["kind"]), str(item["path"])) for item in resources),
        origin=AiJobOrigin(str(row[19])) if len(row) > 19 else AiJobOrigin.USER,
        phase=str(row[20]) if len(row) > 20 and row[20] is not None else None,
        completed_units=int(cast(int, row[21])) if len(row) > 21 else 0,
        total_units=(int(cast(int, row[22])) if len(row) > 22 and row[22] is not None else None),
        current_section_label=(str(row[23]) if len(row) > 23 and row[23] is not None else None),
        version=int(cast(int, row[25])) if len(row) > 25 else 1,
        next_attempt_at=cast(datetime | None, row[26]) if len(row) > 26 else None,
    )
    return AiJobRecord(
        job,
        AiJobCommand(command),
        str(row[15]) if row[15] is not None else None,
        str(row[24]) if len(row) > 24 and row[24] is not None else None,
        cast(datetime | None, row[16]),
        inputs_pruned=len(row) > 27 and row[27] is not None,
    )


def _notification(row: tuple[object, ...]) -> ActorNotification:
    return ActorNotification(
        NotificationId(str(row[0])),
        ActorId(str(row[1])),
        AiJobId(str(row[2])) if row[2] is not None else None,
        NotificationKind(str(row[3])),
        str(row[4]),
        cast(datetime, row[6]),
        str(row[5]) if row[5] is not None else None,
        cast(datetime | None, row[7]),
    )
