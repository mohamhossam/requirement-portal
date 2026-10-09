"""PostgreSQL repositories for the identity context (ADR-0103).

`requirement_access`, `draft_ownership` and `actor_profiles` rows, each a JSONB payload written
by `identity_payloads`.
"""

from __future__ import annotations

from psycopg.types.json import Jsonb

from smb_requirement_agent.identity.domain.entities import DraftOwnership, RequirementAccess
from smb_requirement_agent.identity.domain.errors import RequirementAccessConflictError
from smb_requirement_agent.identity.infrastructure.identity_payloads import (
    access_from_payload,
    access_to_payload,
    draft_ownership_from_payload,
    draft_ownership_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import _payload
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    actor_from_payload,
    actor_to_payload,
)
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresAccessRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def get_requirement(self, requirement_id: RequirementId) -> RequirementAccess | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_access WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return access_from_payload(_payload(row[0])) if row is not None else None

    def save_requirement(self, access: RequirementAccess) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "SELECT requirement_id FROM requirements WHERE requirement_id = %s FOR UPDATE",
                (access.requirement_id.value,),
            )
            row = connection.execute(
                "SELECT payload FROM requirement_access WHERE requirement_id = %s",
                (access.requirement_id.value,),
            ).fetchone()
            if row is not None:
                current = access_from_payload(_payload(row[0]))
                if (
                    access.version != current.version + 1
                    or access.changes[: len(current.changes)] != current.changes
                ):
                    raise RequirementAccessConflictError(
                        "Requirement access changed before this operation completed."
                    )
            connection.execute(
                """
                INSERT INTO requirement_access (requirement_id, payload) VALUES (%s, %s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
                """,
                (access.requirement_id.value, Jsonb(access_to_payload(access))),
            )
            self._store.mark_requirement_dirty(access.requirement_id)

    def get_draft_ownership(self, draft_id: RequirementId) -> DraftOwnership | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM draft_ownership WHERE draft_id = %s", (draft_id.value,)
            ).fetchone()
        return draft_ownership_from_payload(_payload(row[0])) if row is not None else None

    def save_draft_ownership(self, ownership: DraftOwnership) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "SELECT draft_id FROM requirement_drafts WHERE draft_id = %s FOR UPDATE",
                (ownership.draft_id.value,),
            )
            row = connection.execute(
                "SELECT payload FROM draft_ownership WHERE draft_id = %s",
                (ownership.draft_id.value,),
            ).fetchone()
            if row is not None:
                current = draft_ownership_from_payload(_payload(row[0]))
                if current.owner != ownership.owner:
                    raise RequirementAccessConflictError(
                        "Draft ownership changed before this operation completed."
                    )
            connection.execute(
                """
                INSERT INTO draft_ownership (draft_id, payload) VALUES (%s, %s)
                ON CONFLICT (draft_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
                """,
                (ownership.draft_id.value, Jsonb(draft_ownership_to_payload(ownership))),
            )

    def delete_draft_ownership(self, draft_id: RequirementId) -> None:
        with self._store.connection() as connection:
            connection.execute("DELETE FROM draft_ownership WHERE draft_id = %s", (draft_id.value,))


class PostgresActorDirectory:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def record(self, actor: ActorProfile) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO actor_profiles (actor_id, payload) VALUES (%s, %s)
                ON CONFLICT (actor_id) DO UPDATE
                SET payload = EXCLUDED.payload, last_seen_at = now()
                """,
                (actor.id.value, Jsonb(actor_to_payload(actor))),
            )

    def get(self, actor_id: ActorId) -> ActorProfile | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM actor_profiles WHERE actor_id = %s", (actor_id.value,)
            ).fetchone()
        return actor_from_payload(_payload(row[0])) if row is not None else None

    def search(self, query: str | None, limit: int) -> list[ActorProfile]:
        needle = f"%{(query or '').strip()}%"
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM actor_profiles
                WHERE %s = '%%' OR payload->>'display_name' ILIKE %s
                    OR COALESCE(payload->>'email', '') ILIKE %s
                ORDER BY lower(payload->>'display_name') LIMIT %s
                """,
                (needle, needle, needle, limit),
            ).fetchall()
        return [actor_from_payload(_payload(row[0])) for row in rows]
