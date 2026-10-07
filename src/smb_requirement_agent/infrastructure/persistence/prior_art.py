"""Each Requirement's latest prior-art check, and the judge's hourly budget (ADR-0102)."""

from __future__ import annotations

import copy
from datetime import datetime
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb

from smb_requirement_agent.domain.knowledge.historic import HistoricSourceKind
from smb_requirement_agent.domain.knowledge.prior_art import (
    PriorArtCheck,
    PriorArtEvidence,
    PriorArtMatch,
    PriorArtVerdict,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def _hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def _evidence(match: PriorArtMatch) -> list[dict[str, object]]:
    return [
        {
            "chunk_id": item.chunk_id,
            "source_kind": item.source_kind.value,
            "excerpt": item.excerpt,
            "context": item.context,
        }
        for item in match.evidence
    ]


def _evidence_from(value: object) -> tuple[PriorArtEvidence, ...]:
    items = cast(list[dict[str, object]], value)
    return tuple(
        PriorArtEvidence(
            str(item["chunk_id"]),
            HistoricSourceKind(str(item["source_kind"])),
            str(item["excerpt"]),
            cast(dict[str, object], item["context"]),
        )
        for item in items
    )


class InMemoryPriorArt:
    """Prior-art checks and the judge's budget, under the graph-wide lock."""

    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._checks: dict[RequirementId, PriorArtCheck] = {}
        self._windows: dict[datetime, int] = {}

    def snapshot_state(self) -> object:
        return copy.deepcopy((self._checks, self._windows))

    def restore_state(self, state: object) -> None:
        self._checks, self._windows = cast(
            tuple[dict[RequirementId, PriorArtCheck], dict[datetime, int]], state
        )

    def get(self, requirement_id: RequirementId) -> PriorArtCheck | None:
        with self._lock:
            return self._checks.get(requirement_id)

    def replace(self, check: PriorArtCheck) -> None:
        with self._lock:
            self._checks[check.requirement_id] = check

    def remove_requirement(self, requirement_id: RequirementId) -> None:
        with self._lock:
            self._checks.pop(requirement_id, None)

    def citation_counts(self, historic_ids: tuple[str, ...]) -> dict[str, int]:
        with self._lock:
            counts = dict.fromkeys(historic_ids, 0)
            for check in self._checks.values():
                for match in check.matches:
                    if match.historic_requirement_id in counts:
                        counts[match.historic_requirement_id] += 1
            return counts

    def citing(self, historic_id: str, offset: int, limit: int) -> tuple[RequirementId, ...]:
        with self._lock:
            found = sorted(
                (
                    check
                    for check in self._checks.values()
                    if any(m.historic_requirement_id == historic_id for m in check.matches)
                ),
                key=lambda check: (check.checked_at, check.requirement_id.value),
            )
            return tuple(check.requirement_id for check in found[offset : offset + limit])

    def spend(self, now: datetime) -> None:
        with self._lock:
            window = _hour(now)
            self._windows = {window: self._windows.get(window, 0) + 1}

    def remaining(self, now: datetime, hourly: int) -> int:
        with self._lock:
            return max(0, hourly - self._windows.get(_hour(now), 0))


class PostgresPriorArt:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def get(self, requirement_id: RequirementId) -> PriorArtCheck | None:
        with self._store.connection() as connection:
            head = connection.execute(
                "SELECT subject_fingerprint, corpus_version, embedding_identity, model, "
                "prompt_version, checked_at FROM requirement_prior_art WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
            if head is None:
                return None
            rows = connection.execute(
                "SELECT historic_requirement_id, publication, title, verdict, rationale, evidence "
                "FROM requirement_prior_art_matches WHERE requirement_id = %s ORDER BY rank",
                (requirement_id.value,),
            ).fetchall()
        return PriorArtCheck(
            requirement_id,
            str(head[0]),
            int(cast(int, head[1])),
            str(head[2]),
            Provenance(cast(datetime, head[5]), str(head[3]), str(head[4])),
            tuple(
                PriorArtMatch(
                    str(row[0]),
                    int(cast(int, row[1])),
                    str(row[2]),
                    PriorArtVerdict(str(row[3])),
                    str(row[4]),
                    _evidence_from(row[5]),
                )
                for row in rows
            ),
        )

    def replace(self, check: PriorArtCheck) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM requirement_prior_art WHERE requirement_id = %s",
                (check.requirement_id.value,),
            )
            connection.execute(
                "INSERT INTO requirement_prior_art (requirement_id, subject_fingerprint, "
                "corpus_version, embedding_identity, model, prompt_version, checked_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    check.requirement_id.value,
                    check.subject_fingerprint,
                    check.corpus_version,
                    check.embedding_identity,
                    check.provenance.model,
                    check.provenance.prompt_version,
                    check.provenance.generated_at,
                ),
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO requirement_prior_art_matches (requirement_id, "
                    "historic_requirement_id, rank, publication, title, verdict, rationale, "
                    "evidence) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        (
                            check.requirement_id.value,
                            match.historic_requirement_id,
                            rank,
                            match.publication,
                            match.title,
                            match.verdict.value,
                            match.rationale,
                            Jsonb(_evidence(match)),
                        )
                        for rank, match in enumerate(check.matches, start=1)
                    ],
                )

    def citation_counts(self, historic_ids: tuple[str, ...]) -> dict[str, int]:
        if not historic_ids:
            return {}
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT historic_requirement_id, count(*) FROM requirement_prior_art_matches "
                "WHERE historic_requirement_id = ANY(%s) GROUP BY historic_requirement_id",
                (list(historic_ids),),
            ).fetchall()
        found = {str(row[0]): int(cast(int, row[1])) for row in rows}
        return {historic_id: found.get(historic_id, 0) for historic_id in historic_ids}

    def citing(self, historic_id: str, offset: int, limit: int) -> tuple[RequirementId, ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT p.requirement_id FROM requirement_prior_art_matches m "
                "JOIN requirement_prior_art p USING (requirement_id) "
                "WHERE m.historic_requirement_id = %s "
                "ORDER BY p.checked_at, p.requirement_id OFFSET %s LIMIT %s",
                (historic_id, offset, limit),
            ).fetchall()
        return tuple(RequirementId(str(row[0])) for row in rows)

    def spend(self, now: datetime) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO prior_art_call_windows (window_start, calls) VALUES (%s, 1) "
                "ON CONFLICT (window_start) DO UPDATE SET calls = prior_art_call_windows.calls + 1",
                (_hour(now),),
            )
            connection.execute(
                "DELETE FROM prior_art_call_windows WHERE window_start < %s", (_hour(now),)
            )

    def remaining(self, now: datetime, hourly: int) -> int:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT calls FROM prior_art_call_windows WHERE window_start = %s", (_hour(now),)
            ).fetchone()
        return max(0, hourly - (int(cast(int, row[0])) if row else 0))
