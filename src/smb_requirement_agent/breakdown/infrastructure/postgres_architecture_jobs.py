"""PostgreSQL worker queue with atomic leasing."""

from __future__ import annotations

from datetime import datetime

import psycopg
from smb_kernel.persistence.connector import PostgresConnector

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.breakdown.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.infrastructure.persistence.database_errors import database_error
from smb_requirement_agent.references.domain.architecture.knowledge import KnowledgeConflictError


class PostgresArchitectureJobs:
    """Requirement work's mapping queue; the catalogue's jobs left with it (ADR-0099)."""

    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector
        self._table = "requirement_mapping_jobs"

    @staticmethod
    def _job(row: tuple[object, ...]) -> ArchitectureJob:
        if not isinstance(row[6], int):
            raise PersistenceError("Stored architecture job attempt count is invalid.")
        try:
            kind = ArchitectureJobKind(str(row[1]))
            status = ArchitectureJobStatus(str(row[5]))
        except ValueError as exc:
            raise PersistenceError("Stored architecture job kind or status is invalid.") from exc
        return ArchitectureJob(
            str(row[0]),
            kind,
            str(row[2]),
            str(row[3]),
            str(row[4]),
            status,
            row[6],
            str(row[7]) if row[7] is not None else None,
            row[8] if isinstance(row[8], datetime) else None,
        )

    def enqueue(self, job: ArchitectureJob) -> ArchitectureJob:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    f"INSERT INTO {self._table} "  # noqa: S608 - constant table name
                    "(job_id, kind, subject_id, fingerprint, actor_id, status) "
                    "VALUES (%s, %s, %s, %s, %s, 'queued') "
                    "ON CONFLICT (kind, subject_id, fingerprint) DO UPDATE SET "
                    # Asking again for a failed or cancelled job starts it afresh;
                    # a job already queued, running or done is returned as it is.
                    f"attempts = CASE WHEN {self._table}.status IN ('failed', 'cancelled') "
                    f"THEN 0 ELSE {self._table}.attempts END, "
                    f"error_category = CASE WHEN {self._table}.status IN "
                    f"('failed', 'cancelled') THEN NULL ELSE {self._table}.error_category END, "
                    f"status = CASE WHEN {self._table}.status IN ('failed', 'cancelled') "
                    f"THEN 'queued' ELSE {self._table}.status END, "
                    "updated_at = now() "
                    "RETURNING job_id, kind, subject_id, fingerprint, actor_id, status, "
                    "attempts, error_category, lease_until",
                    (job.id, job.kind.value, job.subject_id, job.fingerprint, job.actor_id),
                ).fetchone()
            if row is None:
                raise PersistenceError("Architecture job upsert returned no row.")
            return self._job(row)
        except psycopg.Error as exc:
            raise database_error(exc, "Architecture job could not be queued.") from exc

    def for_subject(
        self, kind: ArchitectureJobKind, subject_id: str
    ) -> tuple[ArchitectureJob, ...]:
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    "SELECT job_id, kind, subject_id, fingerprint, actor_id, status, attempts, "  # noqa: S608 - constant table name
                    f"error_category, lease_until FROM {self._table} "
                    "WHERE kind = %s AND subject_id = %s ORDER BY updated_at, created_at",
                    (kind.value, subject_id),
                ).fetchall()
            return tuple(self._job(row) for row in rows)
        except psycopg.Error as exc:
            raise database_error(exc, "Architecture jobs could not be listed.") from exc

    def get(self, job_id: str) -> ArchitectureJob | None:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT job_id, kind, subject_id, fingerprint, actor_id, status, attempts, "  # noqa: S608 - constant table name
                    f"error_category, lease_until FROM {self._table} WHERE job_id = %s",
                    (job_id,),
                ).fetchone()
            return self._job(row) if row else None
        except psycopg.Error as exc:
            raise database_error(exc, "Architecture job read failed.") from exc

    def claim(self, now: datetime) -> ArchitectureJob | None:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    f"""
                    WITH candidate AS (
                      SELECT job_id FROM {self._table}
                      WHERE attempts < 3 AND (status = 'queued' OR
                        (status = 'running' AND lease_until < %s))
                      ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
                    )
                    UPDATE {self._table} j
                    SET status = 'running', attempts = attempts + 1,
                        lease_until = %s + interval '5 minutes', updated_at = now()
                    FROM candidate WHERE j.job_id = candidate.job_id
                    RETURNING j.job_id, j.kind, j.subject_id, j.fingerprint, j.actor_id,
                              j.status, j.attempts, j.error_category, j.lease_until
                    """,  # noqa: S608 - constant table name
                    (now, now),
                ).fetchone()
                if row is None:
                    connection.execute(
                        f"UPDATE {self._table} SET status = 'failed', "  # noqa: S608 - constant table name
                        "error_category = 'attempts_exhausted', lease_until = NULL, "
                        "updated_at = now() WHERE attempts >= 3 AND "
                        "(status = 'queued' OR (status = 'running' AND lease_until < %s))",
                        (now,),
                    )
            return self._job(row) if row else None
        except psycopg.Error as exc:
            raise database_error(exc, "Architecture job claim failed.") from exc

    def heartbeat(self, job_id: str, attempt: int, now: datetime) -> bool:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    f"UPDATE {self._table} SET lease_until = %s + interval '5 minutes', "  # noqa: S608 - constant table name
                    "updated_at = now() WHERE job_id = %s AND attempts = %s "
                    "AND status = 'running' RETURNING job_id",
                    (now, job_id, attempt),
                ).fetchone()
            return row is not None
        except psycopg.Error as exc:
            raise database_error(exc, "Architecture job heartbeat failed.") from exc

    def finish(
        self,
        job_id: str,
        attempt: int,
        status: ArchitectureJobStatus,
        error_category: str | None,
    ) -> None:
        try:
            with self._connector.connection() as connection:
                connection.execute(
                    f"UPDATE {self._table} SET status = %s, error_category = %s, "  # noqa: S608 - constant table name
                    "lease_until = NULL, updated_at = now() "
                    "WHERE job_id = %s AND attempts = %s AND status = 'running'",
                    (status.value, error_category, job_id, attempt),
                )
        except psycopg.Error as exc:
            raise database_error(exc, "Architecture job completion failed.") from exc

    def cancel(self, job_id: str) -> ArchitectureJob:
        return self._transition(
            job_id, ArchitectureJobStatus.QUEUED, ArchitectureJobStatus.CANCELLED
        )

    def retry(self, job_id: str) -> ArchitectureJob:
        return self._transition(job_id, ArchitectureJobStatus.FAILED, ArchitectureJobStatus.QUEUED)

    def _transition(
        self,
        job_id: str,
        from_status: ArchitectureJobStatus,
        to_status: ArchitectureJobStatus,
    ) -> ArchitectureJob:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    f"UPDATE {self._table} SET status = %s, attempts = 0, "  # noqa: S608 - constant table name
                    "error_category = NULL, lease_until = NULL, updated_at = now() "
                    "WHERE job_id = %s AND status = %s "
                    "RETURNING job_id, kind, subject_id, fingerprint, actor_id, status, "
                    "attempts, error_category, lease_until",
                    (to_status.value, job_id, from_status.value),
                ).fetchone()
            if row is None:
                raise KnowledgeConflictError(f"Only a {from_status} job can be changed.")
            return self._job(row)
        except psycopg.Error as exc:
            raise database_error(exc, "Architecture job state update failed.") from exc
