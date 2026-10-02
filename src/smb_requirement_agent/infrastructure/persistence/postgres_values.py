"""PostgreSQL value decoding and aggregate identity lookups."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from psycopg import Connection

from smb_requirement_agent.application.errors import (
    PersistenceError,
)
from smb_requirement_agent.domain.epic.value_objects import EpicId
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.infrastructure.persistence.payload_fields import JsonObject

DbConnection = Connection[tuple[object, ...]]


def _payload(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise PersistenceError("Stored snapshot payload must be a JSON object.")
    return cast(JsonObject, value)


def _integer(value: object) -> int:
    if not isinstance(value, int):
        raise PersistenceError("Stored revision number must be an integer.")
    return value


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise PersistenceError("Stored revision timestamp must be a datetime.")
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise PersistenceError("Stored identifier must be text.")
    return value


def requirement_id_for_epic(epic_id: EpicId, connection: DbConnection) -> RequirementId | None:
    row = connection.execute(
        "SELECT requirement_id FROM epics WHERE epic_id = %s", (epic_id.value,)
    ).fetchone()
    return RequirementId(_string(row[0])) if row is not None else None


def requirement_id_for_feature(
    feature_id: FeatureId, connection: DbConnection
) -> RequirementId | None:
    row = connection.execute(
        """
        SELECT e.requirement_id FROM features f
        JOIN epics e ON e.epic_id = f.epic_id
        WHERE f.feature_id = %s
        """,
        (feature_id.value,),
    ).fetchone()
    return RequirementId(_string(row[0])) if row is not None else None
