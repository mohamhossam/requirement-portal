"""Durable organisation catalogue: one serialised aggregate plus an audit trail."""

from __future__ import annotations

from collections.abc import Callable

import psycopg
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter, ValidationError
from smb_kernel.persistence.connector import PostgresConnector
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.domain.organisation.catalogue import (
    OrganisationAuditEvent,
    OrganisationCatalogue,
)
from smb_requirement_agent.infrastructure.persistence.postgres_values import _datetime

_ADAPTER: TypeAdapter[OrganisationCatalogue] = TypeAdapter(OrganisationCatalogue)


def _catalogue(raw: object) -> OrganisationCatalogue:
    try:
        return _ADAPTER.validate_python(raw)
    except ValidationError as exc:
        raise PersistenceError("Stored organisation catalogue is invalid.") from exc


class PostgresOrganisationRepository:
    def __init__(self, connector: PostgresConnector, clock: ClockPort) -> None:
        self._connector = connector
        self._clock = clock

    def load(self) -> OrganisationCatalogue:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT payload FROM organisation_catalogue WHERE catalogue_id = 1"
                ).fetchone()
            return OrganisationCatalogue() if row is None else _catalogue(row[0])
        except psycopg.Error as exc:
            raise PersistenceError("Organisation catalogue read failed.") from exc

    def change(
        self,
        change: Callable[[OrganisationCatalogue], OrganisationCatalogue],
        actor_id: str,
        action: str,
        subject_id: str,
    ) -> OrganisationCatalogue:
        try:
            with self._connector.connection() as connection:
                connection.execute(
                    "INSERT INTO organisation_catalogue (catalogue_id, payload) "
                    "VALUES (1, %s) ON CONFLICT DO NOTHING",
                    (Jsonb(_ADAPTER.dump_python(OrganisationCatalogue(), mode="json")),),
                )
                row = connection.execute(
                    "SELECT payload FROM organisation_catalogue WHERE catalogue_id = 1 FOR UPDATE"
                ).fetchone()
                if row is None:
                    raise PersistenceError("Organisation catalogue row is missing.")
                updated = change(_catalogue(row[0]))
                connection.execute(
                    "UPDATE organisation_catalogue SET payload = %s, updated_at = now() "
                    "WHERE catalogue_id = 1",
                    (Jsonb(_ADAPTER.dump_python(updated, mode="json")),),
                )
                connection.execute(
                    "INSERT INTO organisation_audit (actor_id, action, subject_id, created_at) "
                    "VALUES (%s, %s, %s, %s)",
                    (actor_id, action, subject_id, self._clock.now()),
                )
            return updated
        except psycopg.Error as exc:
            raise PersistenceError("Organisation catalogue write failed.") from exc

    def audit(self, limit: int) -> tuple[OrganisationAuditEvent, ...]:
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    "SELECT actor_id, action, subject_id, created_at FROM organisation_audit "
                    "ORDER BY audit_id DESC LIMIT %s",
                    (limit,),
                ).fetchall()
            return tuple(
                OrganisationAuditEvent(str(row[0]), str(row[1]), str(row[2]), _datetime(row[3]))
                for row in rows
            )
        except psycopg.Error as exc:
            raise PersistenceError("Organisation audit read failed.") from exc
