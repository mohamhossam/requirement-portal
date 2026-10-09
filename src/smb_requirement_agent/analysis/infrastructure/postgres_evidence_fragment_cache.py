"""Durable PostgreSQL cache for successful evidence packet analysis."""

from collections.abc import Sequence
from datetime import datetime

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.application.ports.requirement_evidence_analyzer import (
    EvidenceFragmentCacheEntry,
    EvidenceFragmentCachePort,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession

_CANDIDATE = TypeAdapter(RequirementAnalysisCandidate)


class PostgresEvidenceFragmentCache(EvidenceFragmentCachePort):
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def get(self, key: str) -> EvidenceFragmentCacheEntry | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload,generated_at FROM analysis_evidence_fragments WHERE cache_key=%s",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return EvidenceFragmentCacheEntry(
            _CANDIDATE.validate_python(row[0]),
            row[1] if isinstance(row[1], datetime) else datetime.fromisoformat(str(row[1])),
        )

    def put(self, key: str, value: EvidenceFragmentCacheEntry) -> None:
        self.put_many(((key, value),))

    def put_many(self, values: Sequence[tuple[str, EvidenceFragmentCacheEntry]]) -> None:
        rows = [
            (
                key,
                Jsonb(_CANDIDATE.dump_python(value.candidate, mode="json")),
                value.generated_at,
            )
            for key, value in values
        ]
        if not rows:
            return
        with self._store.connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO analysis_evidence_fragments (cache_key,payload,generated_at)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (cache_key) DO NOTHING
                    """,
                    rows,
                )
