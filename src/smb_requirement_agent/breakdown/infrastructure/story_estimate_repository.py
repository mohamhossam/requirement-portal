"""In-memory and PostgreSQL adapters for a Feature's latest size suggestions.

Suggestions are AI output kept beside the Stories, like quality snapshots: they never
mark the requirement dirty, so they never become part of a revision (ADR-0121).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from psycopg.types.json import Jsonb

from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.estimate import FeatureEstimateSuggestions
from smb_requirement_agent.breakdown.infrastructure.backlog_codecs import (
    estimate_suggestions_from_payload,
    estimate_suggestions_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.payload_fields import JsonObject
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


class InMemoryStoryEstimateSuggestionRepository:
    def __init__(self) -> None:
        self._values: dict[FeatureId, FeatureEstimateSuggestions] = {}

    def snapshot_state(self) -> Any:
        return deepcopy((self._values,))

    def restore_state(self, state: Any) -> None:
        (self._values,) = deepcopy(state)

    def get(self, feature_id: FeatureId) -> FeatureEstimateSuggestions | None:
        return self._values.get(feature_id)

    def save(self, suggestions: FeatureEstimateSuggestions) -> None:
        self._values[suggestions.feature_id] = suggestions


class PostgresStoryEstimateSuggestionRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def get(self, feature_id: FeatureId) -> FeatureEstimateSuggestions | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM feature_estimate_suggestions WHERE feature_id=%s",
                (feature_id.value,),
            ).fetchone()
        return estimate_suggestions_from_payload(cast(JsonObject, row[0])) if row else None

    def save(self, suggestions: FeatureEstimateSuggestions) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO feature_estimate_suggestions (feature_id,payload) VALUES (%s,%s)
                ON CONFLICT (feature_id) DO UPDATE
                SET payload=EXCLUDED.payload, updated_at=now()
                """,
                (
                    suggestions.feature_id.value,
                    Jsonb(estimate_suggestions_to_payload(suggestions)),
                ),
            )
