"""PostgreSQL connection ownership and explicit units of work."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import psycopg
from psycopg.errors import RaiseException
from smb_kernel.persistence.connector import PostgresConnector

from smb_requirement_agent.application.errors import DuplicateRequirementError, PersistenceError
from smb_requirement_agent.application.ports.external_work import check_external_result
from smb_requirement_agent.infrastructure.persistence.migration_runner import (
    latest_packaged_migration,
)
from smb_requirement_agent.infrastructure.persistence.postgres_values import DbConnection
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

# The maintenance backfill a ready database must have completed after migrating.
REQUIRED_MAINTENANCE_MARKER = "activity-worklist-v2"


class PostgresStore:
    """Own connections, atomic commits, checkpoints, and derived projection refreshes."""

    def __init__(
        self,
        connector: PostgresConnector,
        checkpoint: Callable[[RequirementId, DbConnection], None],
        refresh_projections: Callable[[DbConnection, tuple[RequirementId, ...]], None],
    ) -> None:
        self._connector = connector
        self._checkpoint = checkpoint
        self._refresh_projections = refresh_projections
        self._connection_var: ContextVar[DbConnection | None] = ContextVar(
            "postgres_connection", default=None
        )
        self._dirty_var: ContextVar[set[str] | None] = ContextVar(
            "postgres_dirty_requirements", default=None
        )
        self._rollback_var: ContextVar[bool] = ContextVar("postgres_rollback_only", default=False)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._connection_var.get() is not None:
            try:
                yield
            except BaseException:
                self.mark_rollback_only()
                raise
            return
        try:
            connection = self._connector.acquire()
            connection_token = self._connection_var.set(connection)
            dirty_token = self._dirty_var.set(set())
            rollback_token = self._rollback_var.set(False)
            try:
                yield
                current = self._connection_var.get()
                if current is None:
                    raise PersistenceError("PostgreSQL unit of work lost its connection.")
                if self._rollback_var.get():
                    current.rollback()
                else:
                    self._flush(current)
                    current.commit()
            finally:
                current = self._connection_var.get()
                if current is not None:
                    # Releasing rolls back any uncommitted work after a rejected result.
                    self._connector.release(current)
                self._rollback_var.reset(rollback_token)
                self._dirty_var.reset(dirty_token)
                self._connection_var.reset(connection_token)
        except (DuplicateRequirementError, RaiseException):
            raise
        except psycopg.Error as exc:
            raise PersistenceError("PostgreSQL operation failed.") from exc

    def _flush(self, connection: DbConnection) -> None:
        authoritative = set(self._dirty_var.get() or ())
        dirty = set(authoritative)
        if dirty:
            rows = connection.execute(
                "SELECT DISTINCT dependent_requirement_id FROM requirement_knowledge_dependencies "
                "WHERE source_requirement_id=ANY(%s)",
                (list(dirty),),
            ).fetchall()
            dirty.update(str(row[0]) for row in rows)
        # Finish every authoritative revision before reading any derived projection.
        for raw_id in sorted(authoritative):
            self._checkpoint(RequirementId(raw_id), connection)
        if dirty:
            self._refresh_projections(
                connection, tuple(RequirementId(raw_id) for raw_id in sorted(dirty))
            )

    def mark_rollback_only(self) -> None:
        self._rollback_var.set(True)

    def in_unit_of_work(self) -> bool:
        # external_call() clears the connection while the provider runs.
        return self._connection_var.get() is not None

    def readiness(self) -> bool:
        """Bounded database checks, without schema changes or paid provider calls."""
        try:
            with self._connector.connection(timeout_seconds=2) as connection:
                connection.execute("SET LOCAL statement_timeout = '2000ms'")
                row = connection.execute(
                    "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version=%s) "
                    "AND EXISTS (SELECT 1 FROM maintenance_markers WHERE name=%s)",
                    (latest_packaged_migration(), REQUIRED_MAINTENANCE_MARKER),
                ).fetchone()
                return row is not None and bool(row[0])
        except psycopg.Error:
            return False

    def lock_requirement(self, requirement_id: RequirementId) -> None:
        if self._connection_var.get() is None:
            raise RuntimeError("Requirement locks require an active PostgreSQL transaction.")
        with self._connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (requirement_id.value,),
            )

    @contextmanager
    def external_call(self) -> Iterator[None]:
        """Suspend the unit of work completely while external work is running.

        Progress and cache reads must use independent, short connections. They
        must never restart a transaction on the suspended commit connection.
        """
        connection = self._connection_var.get()
        if connection is None:
            yield
            return
        if self._dirty_var.get():
            raise RuntimeError("External providers cannot run after a transaction has written.")
        connection.commit()
        self._connector.release(connection)
        connection_token = self._connection_var.set(None)
        dirty_token = self._dirty_var.set(None)
        rollback_token = self._rollback_var.set(False)
        try:
            yield
        finally:
            self._rollback_var.reset(rollback_token)
            self._dirty_var.reset(dirty_token)
            self._connection_var.reset(connection_token)
            # A failed provider call must propagate without reconnecting and
            # potentially replacing that failure with a database exception.
            self._connection_var.set(None)
        self._connection_var.set(self._connector.acquire())
        check_external_result()

    def try_lock_requirement(self, requirement_id: RequirementId) -> bool:
        if self._connection_var.get() is None:
            raise RuntimeError("Requirement locks require an active PostgreSQL transaction.")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0))",
                (requirement_id.value,),
            ).fetchone()
        return row is not None and bool(row[0])

    @contextmanager
    def _connection(self) -> Iterator[DbConnection]:
        active = self._connection_var.get()
        if active is not None:
            yield active
            return
        with self.transaction():
            connection = self._connection_var.get()
            if connection is None:  # pragma: no cover - transaction invariant
                raise PersistenceError("PostgreSQL transaction did not provide a connection.")
            yield connection

    @contextmanager
    def connection(self) -> Iterator[DbConnection]:
        """Share the active unit-of-work connection with sibling adapters."""
        with self._connection() as connection:
            yield connection

    def _mark(self, requirement_id: RequirementId) -> None:
        dirty = self._dirty_var.get()
        if dirty is not None:
            dirty.add(requirement_id.value)

    def mark_requirement_dirty(self, requirement_id: RequirementId) -> None:
        """Enroll a sibling adapter's business-state change in this unit of work."""
        self._mark(requirement_id)
