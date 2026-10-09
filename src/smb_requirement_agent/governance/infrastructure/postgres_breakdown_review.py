"""PostgreSQL repository for breakdown reviews (ADR-0103 PR 12; was postgres_repositories)."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
)
from smb_requirement_agent.governance.domain.review.entities import BreakdownReview
from smb_requirement_agent.governance.infrastructure.review_payloads import (
    review_from_payload,
    review_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import (
    _payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresBreakdownReviewRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def save(self, review: BreakdownReview) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """
                INSERT INTO breakdown_reviews (requirement_id, payload)
                VALUES (%s, %s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
                WHERE (breakdown_reviews.payload->>'version')::integer =
                          (EXCLUDED.payload->>'version')::integer - 1
                   OR breakdown_reviews.payload = EXCLUDED.payload
                """,
                (review.requirement_id.value, Jsonb(review_to_payload(review))),
            )
            if result.rowcount == 0:
                raise ArtifactVersionConflictError(
                    "Breakdown review changed before this mutation could be saved. Reload it."
                )
            self._store.mark_requirement_dirty(review.requirement_id)

    def get(self, requirement_id: RequirementId) -> BreakdownReview | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM breakdown_reviews WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return review_from_payload(_payload(row[0])) if row is not None else None
