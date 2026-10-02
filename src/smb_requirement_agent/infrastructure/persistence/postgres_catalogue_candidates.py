"""Durable AI-proposed catalogue changes; decisions are conditional on being undecided."""

from __future__ import annotations

from dataclasses import replace

import psycopg
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter, ValidationError

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.catalogue_candidates import ExtractionRun
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateDecisionConflictError,
    CandidateStatus,
    CatalogueCandidate,
)
from smb_requirement_agent.infrastructure.persistence.postgres_connector import PostgresConnector

_CANDIDATE: TypeAdapter[CatalogueCandidate] = TypeAdapter(CatalogueCandidate)
_RUN: TypeAdapter[ExtractionRun] = TypeAdapter(ExtractionRun)


def _candidate(raw: object) -> CatalogueCandidate:
    try:
        return _CANDIDATE.validate_python(raw)
    except ValidationError as exc:
        raise PersistenceError("A stored catalogue suggestion is invalid.") from exc


class PostgresCatalogueCandidates:
    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def replace_proposals(
        self, run: ExtractionRun, candidates: tuple[CatalogueCandidate, ...]
    ) -> None:
        try:
            with self._connector.connection() as connection:
                connection.execute(
                    "DELETE FROM architecture_catalogue_candidates "
                    "WHERE release_id = %s AND document_version_id = %s AND status = 'proposed'",
                    (run.release_id, run.document_version_id),
                )
                for item in candidates:
                    connection.execute(
                        "INSERT INTO architecture_catalogue_candidates "
                        "(candidate_id, release_id, document_version_id, status, payload, "
                        "created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            item.id,
                            item.release_id,
                            item.document_version_id,
                            item.status.value,
                            Jsonb(_CANDIDATE.dump_python(item, mode="json")),
                            item.created_at,
                        ),
                    )
                connection.execute(
                    "INSERT INTO architecture_extraction_runs "
                    "(run_id, release_id, document_version_id, payload, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        run.id,
                        run.release_id,
                        run.document_version_id,
                        Jsonb(_RUN.dump_python(run, mode="json")),
                        run.created_at,
                    ),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Catalogue suggestions could not be saved.") from exc

    def runs(self, release_id: str) -> tuple[ExtractionRun, ...]:
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    "SELECT payload FROM architecture_extraction_runs WHERE release_id = %s "
                    "ORDER BY created_at",
                    (release_id,),
                ).fetchall()
            return tuple(_RUN.validate_python(row[0]) for row in rows)
        except (psycopg.Error, ValidationError) as exc:
            raise PersistenceError("Extraction runs could not be read.") from exc

    def list(self, release_id: str) -> tuple[CatalogueCandidate, ...]:
        try:
            with self._connector.connection() as connection:
                rows = connection.execute(
                    "SELECT payload FROM architecture_catalogue_candidates WHERE release_id = %s "
                    "ORDER BY created_at, candidate_id",
                    (release_id,),
                ).fetchall()
            return tuple(_candidate(row[0]) for row in rows)
        except psycopg.Error as exc:
            raise PersistenceError("Catalogue suggestions could not be read.") from exc

    def get(self, candidate_id: str) -> CatalogueCandidate | None:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "SELECT payload FROM architecture_catalogue_candidates WHERE candidate_id = %s",
                    (candidate_id,),
                ).fetchone()
            return None if row is None else _candidate(row[0])
        except psycopg.Error as exc:
            raise PersistenceError("Catalogue suggestion could not be read.") from exc

    def save_decision(self, candidate: CatalogueCandidate) -> None:
        try:
            with self._connector.connection() as connection:
                row = connection.execute(
                    "UPDATE architecture_catalogue_candidates SET status = %s, payload = %s "
                    "WHERE candidate_id = %s AND status = 'proposed' RETURNING candidate_id",
                    (
                        candidate.status.value,
                        Jsonb(_CANDIDATE.dump_python(candidate, mode="json")),
                        candidate.id,
                    ),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceError("Catalogue suggestion decision could not be saved.") from exc
        if row is None:
            raise CandidateDecisionConflictError("This suggestion was already decided.")

    def reopen(self, candidate_id: str) -> None:
        current = self.get(candidate_id)
        if current is None:
            return
        reopened = replace(
            current,
            status=CandidateStatus.PROPOSED,
            edited=False,
            decided_by=None,
            decided_at=None,
        )
        try:
            with self._connector.connection() as connection:
                connection.execute(
                    "UPDATE architecture_catalogue_candidates SET status = 'proposed', "
                    "payload = %s WHERE candidate_id = %s",
                    (Jsonb(_CANDIDATE.dump_python(reopened, mode="json")), candidate_id),
                )
        except psycopg.Error as exc:
            raise PersistenceError("Catalogue suggestion could not be reopened.") from exc
