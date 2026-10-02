"""Durable sample requirement list: one serialised row, replaced under a revision check."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter, ValidationError
from smb_kernel.persistence.connector import PostgresConnector

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.domain.architecture.knowledge import KnowledgeConflictError
from smb_requirement_agent.domain.architecture.samples import SampleRequirementSet

_ADAPTER: TypeAdapter[SampleRequirementSet] = TypeAdapter(SampleRequirementSet)


def _samples(raw: object) -> SampleRequirementSet:
    try:
        return _ADAPTER.validate_python(raw)
    except ValidationError as exc:
        raise PersistenceError("Stored sample requirements are invalid.") from exc


class PostgresSampleRequirements:
    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def load(self) -> SampleRequirementSet:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT payload FROM architecture_sample_requirements WHERE set_id = 1"
                ).fetchone()
            return SampleRequirementSet() if row is None else _samples(row[0])
        except psycopg.Error as exc:
            raise PersistenceError("Sample requirements read failed.") from exc

    def save(self, updated: SampleRequirementSet, expected_revision: int) -> None:
        payload = Jsonb(_ADAPTER.dump_python(updated, mode="json"))
        try:
            with self._connector.connection() as connection:
                connection.execute(
                    "INSERT INTO architecture_sample_requirements (set_id, payload) "
                    "VALUES (1, %s) ON CONFLICT DO NOTHING",
                    (Jsonb(_ADAPTER.dump_python(SampleRequirementSet(), mode="json")),),
                )
                row = connection.execute(
                    "SELECT payload FROM architecture_sample_requirements "
                    "WHERE set_id = 1 FOR UPDATE"
                ).fetchone()
                if row is None:
                    raise PersistenceError("Sample requirements row is missing.")
                if _samples(row[0]).revision != expected_revision:
                    raise KnowledgeConflictError("The sample list changed; reload before saving.")
                connection.execute(
                    "UPDATE architecture_sample_requirements SET payload = %s, updated_at = now() "
                    "WHERE set_id = 1",
                    (payload,),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Sample requirements write failed.") from exc
