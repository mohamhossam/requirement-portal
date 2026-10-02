"""In-memory and PostgreSQL Feature quality snapshot adapters."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, cast

from psycopg.types.json import Jsonb

from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.story.quality import FeatureQualitySnapshot
from smb_requirement_agent.infrastructure.persistence.payload_fields import JsonObject
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    quality_assessment_from_payload,
    quality_assessment_to_payload,
)


class InMemoryStoryQualityRepository:
    def __init__(self) -> None:
        self._values: dict[FeatureId, FeatureQualitySnapshot] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._values,))

    def restore_state(self, state: Any) -> None:
        (self._values,) = deepcopy(state)

    def get(self, feature_id: FeatureId) -> FeatureQualitySnapshot | None:
        return self._values.get(feature_id)

    def save(self, snapshot: FeatureQualitySnapshot) -> None:
        self._values[snapshot.feature_id] = snapshot


class PostgresStoryQualityRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def get(self, feature_id: FeatureId) -> FeatureQualitySnapshot | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM feature_quality_snapshots WHERE feature_id=%s",
                (feature_id.value,),
            ).fetchone()
        return _from_payload(cast(JsonObject, row[0])) if row is not None else None

    def save(self, snapshot: FeatureQualitySnapshot) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO feature_quality_snapshots (feature_id,payload) VALUES (%s,%s)
                ON CONFLICT (feature_id) DO UPDATE
                SET payload=EXCLUDED.payload, updated_at=now()
                """,
                (snapshot.feature_id.value, Jsonb(_to_payload(snapshot))),
            )


def _to_payload(snapshot: FeatureQualitySnapshot) -> JsonObject:
    return {
        "feature_id": snapshot.feature_id.value,
        "source_fingerprint": snapshot.source_fingerprint,
        "generated_at": snapshot.generated_at.isoformat(),
        "assessments": [quality_assessment_to_payload(item) for item in snapshot.assessments],
    }


def _from_payload(payload: JsonObject) -> FeatureQualitySnapshot:
    raw = payload.get("assessments", [])
    if not isinstance(raw, list):
        raise TypeError("Quality snapshot assessments must be a list.")
    return FeatureQualitySnapshot(
        FeatureId(str(payload["feature_id"])),
        str(payload["source_fingerprint"]),
        tuple(quality_assessment_from_payload(cast(JsonObject, item)) for item in raw),
        datetime.fromisoformat(str(payload["generated_at"])),
    )
