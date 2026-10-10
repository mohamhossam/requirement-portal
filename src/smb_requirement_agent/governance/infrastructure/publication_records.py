"""Publication records in memory and in PostgreSQL (Slice 13).

A save advances the stored record by exactly one version, or inserts the first one; a
writer that lost a race gets `ArtifactVersionConflictError` instead of overwriting.
"""

from __future__ import annotations

from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.governance.domain.publication.entities import BacklogPublication
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

_CONFLICT = "The publication record changed while it was being saved. Reload and try again."
_CODEC: TypeAdapter[BacklogPublication] = TypeAdapter(BacklogPublication)


def publication_to_payload(publication: BacklogPublication) -> dict[str, object]:
    return cast(dict[str, object], _CODEC.dump_python(publication, mode="json"))


def publication_from_payload(payload: object) -> BacklogPublication:
    return _CODEC.validate_python(payload)


class InMemoryPublicationRecords:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._records: dict[str, BacklogPublication] = {}

    def snapshot_state(self) -> object:
        return dict(self._records)

    def restore_state(self, state: object) -> None:
        self._records = cast(dict[str, BacklogPublication], state)

    def get(self, requirement_id: RequirementId) -> BacklogPublication | None:
        with self._lock:
            return self._records.get(requirement_id.value)

    def save(self, publication: BacklogPublication) -> None:
        with self._lock:
            stored = self._records.get(publication.requirement_id.value)
            if stored is not None and stored.version != publication.version - 1:
                raise ArtifactVersionConflictError(_CONFLICT)
            self._records[publication.requirement_id.value] = publication


class PostgresPublicationRecords:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def get(self, requirement_id: RequirementId) -> BacklogPublication | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM backlog_publications WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return publication_from_payload(row[0]) if row is not None else None

    def save(self, publication: BacklogPublication) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """
                INSERT INTO backlog_publications (requirement_id, target_key, version, payload)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET target_key = EXCLUDED.target_key, version = EXCLUDED.version,
                    payload = EXCLUDED.payload, updated_at = now()
                WHERE backlog_publications.version = EXCLUDED.version - 1
                """,
                (
                    publication.requirement_id.value,
                    publication.target_key,
                    publication.version,
                    Jsonb(publication_to_payload(publication)),
                ),
            )
            if result.rowcount != 1:
                raise ArtifactVersionConflictError(_CONFLICT)
