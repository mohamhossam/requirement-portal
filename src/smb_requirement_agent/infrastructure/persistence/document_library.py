"""Library metadata adapters, optimistic writes and independently leased ingestion."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import DocumentVersionConflictError
from smb_requirement_agent.domain.document.library import IngestionStage, LibraryDocument
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession


def claimable(document: LibraryDocument, now: datetime) -> bool:
    return any(
        v.stage is IngestionStage.QUEUED
        or (
            v.stage in {IngestionStage.SCANNING, IngestionStage.EXTRACTING}
            and v.lease_until is not None
            and v.lease_until <= now
        )
        for v in document.versions
    )


def claimed(
    document: LibraryDocument, now: datetime, until: datetime, token: str
) -> LibraryDocument:
    for v in document.versions:
        if v.stage is IngestionStage.QUEUED or (
            v.stage in {IngestionStage.SCANNING, IngestionStage.EXTRACTING}
            and v.lease_until is not None
            and v.lease_until <= now
        ):
            if v.attempt >= 3:
                return document.update_file(
                    replace(
                        v,
                        stage=IngestionStage.FAILED,
                        lease_token=None,
                        lease_until=None,
                        error="Processing attempts exhausted. The owner can explicitly retry.",
                    )
                )
            return document.update_file(
                replace(
                    v,
                    stage=IngestionStage.SCANNING,
                    lease_token=token,
                    lease_until=until,
                    attempt=v.attempt + 1,
                    error=None,
                )
            )
    raise DocumentVersionConflictError("Document is no longer available for processing.")


class InMemoryDocumentLibrary:
    def has_incompatible_publication(self, identities: tuple[str, ...]) -> bool:
        with self._lock:
            return any(
                p.id == d.published_id and p.index_identity not in identities
                for d in self._documents.values()
                for p in d.publications
            )

    def has_published(self) -> bool:
        with self._lock:
            return any(d.published_id is not None for d in self._documents.values())

    def lock_publications(self, document_ids: tuple[str, ...]) -> None:
        # The surrounding application transaction owns the same graph-wide RLock.
        with self._lock:
            pass

    def pending_publication(self, now: datetime) -> LibraryDocument | None:
        with self._lock:
            return next(
                (
                    d
                    for d in self._documents.values()
                    if d.publications
                    and d.publications[-1].withdrawn_at is None
                    and d.publications[-1].activated_at is None
                    and d.publications[-1].built_at is None
                    and d.publications[-1].indexing_attempts < 3
                    and (
                        d.publications[-1].index_lease_until is None
                        or d.publications[-1].index_lease_until <= now
                    )
                ),
                None,
            )

    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._documents: dict[str, LibraryDocument] = {}

    def snapshot_state(self) -> object:
        return dict(self._documents)

    def restore_state(self, state: object) -> None:
        self._documents = cast(dict[str, LibraryDocument], state)

    def add(self, document: LibraryDocument) -> None:
        with self._lock:
            if document.id in self._documents or any(
                self.find_submission(document.owner.id.value, v.idempotency_key)
                for v in document.versions
            ):
                raise DocumentVersionConflictError("This upload was already submitted. Reload it.")
            self._documents[document.id] = document

    def get(self, document_id: str) -> LibraryDocument | None:
        with self._lock:
            return self._documents.get(document_id)

    def save(self, document: LibraryDocument, expected_version: int) -> None:
        with self._lock:
            previous = self._documents.get(document.id)
            if previous is None or previous.version != expected_version:
                raise DocumentVersionConflictError("Document changed. Reload before retrying.")
            if document.version != expected_version + 1:
                raise DocumentVersionConflictError("Document revision must advance exactly once.")
            self._documents[document.id] = document

    def list_visible(self, actor_id: str, offset: int, limit: int) -> tuple[LibraryDocument, ...]:
        with self._lock:
            return tuple(
                d
                for d in sorted(self._documents.values(), key=lambda d: d.id)
                if d.owner.id.value == actor_id or d.published_id
            )[offset : offset + limit]

    def find_submission(self, actor_id: str, key: str) -> LibraryDocument | None:
        with self._lock:
            return next(
                (
                    d
                    for d in self._documents.values()
                    if any(
                        v.uploaded_by.id.value == actor_id and v.idempotency_key == key
                        for v in d.versions
                    )
                ),
                None,
            )

    def claim(self, now: datetime, until: datetime, token: str) -> LibraryDocument | None:
        with self._lock:
            source = next((d for d in self._documents.values() if claimable(d, now)), None)
            if source is None:
                return None
            document = claimed(source, now, until, token)
            self.save(document, source.version)
            return document


class PostgresDocumentLibrary:
    def has_incompatible_publication(self, identities: tuple[str, ...]) -> bool:
        with self._store.connection() as connection:
            row = connection.execute(
                """SELECT EXISTS(SELECT 1 FROM library_documents d,
                jsonb_array_elements(d.payload->'publications') p
                WHERE p->>'id'=d.published_id
                AND (p->>'index_identity' IS NULL OR NOT (p->>'index_identity'=ANY(%s))))""",
                (list(identities),),
            ).fetchone()
        return bool(row and row[0])

    def has_published(self) -> bool:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM library_documents WHERE published_id IS NOT NULL)"
            ).fetchone()
        return bool(row and row[0])

    def lock_publications(self, document_ids: tuple[str, ...]) -> None:
        if document_ids:
            with self._store.connection() as connection:
                connection.execute(
                    "SELECT id FROM library_documents WHERE id=ANY(%s) ORDER BY id FOR SHARE",
                    (list(document_ids),),
                ).fetchall()

    def pending_publication(self, now: datetime) -> LibraryDocument | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """SELECT payload FROM library_documents
                WHERE payload->'publications'->-1->>'withdrawn_at' IS NULL
                AND payload->'publications'->-1->>'activated_at' IS NULL
                AND payload->'publications'->-1->>'built_at' IS NULL
                AND COALESCE((payload->'publications'->-1->>'indexing_attempts')::integer,0) < 3
                AND (payload->'publications'->-1->>'index_lease_until' IS NULL
                     OR (payload->'publications'->-1->>'index_lease_until')::timestamptz <= %s)
                AND jsonb_array_length(payload->'publications') > 0
                ORDER BY id LIMIT 1""",
                (now,),
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None

    def __init__(self, store: PostgresSession) -> None:
        self._store = store
        self._codec = TypeAdapter(LibraryDocument)

    def add(self, document: LibraryDocument) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """INSERT INTO library_documents (id, owner_id, version, published_id, payload)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (
                    document.id,
                    document.owner.id.value,
                    document.version,
                    document.published_id,
                    Jsonb(self._codec.dump_python(document, mode="json")),
                ),
            )
            if result.rowcount != 1:
                raise DocumentVersionConflictError("This upload already exists. Reload it.")
            self._submissions(document)

    def _submissions(self, document: LibraryDocument) -> None:
        with self._store.connection() as connection:
            for v in document.versions:
                result = connection.execute(
                    """INSERT INTO library_submissions
                    (owner_id, submission_key, document_id, version_id)
                    VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (v.uploaded_by.id.value, v.idempotency_key, document.id, v.id),
                )
                if result.rowcount != 1:
                    row = connection.execute(
                        "SELECT version_id FROM library_submissions "
                        "WHERE owner_id=%s AND submission_key=%s",
                        (v.uploaded_by.id.value, v.idempotency_key),
                    ).fetchone()
                    if row is None or str(row[0]) != v.id:
                        raise DocumentVersionConflictError("Submission key has already been used.")

    def get(self, document_id: str) -> LibraryDocument | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM library_documents WHERE id=%s", (document_id,)
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None

    def save(self, document: LibraryDocument, expected_version: int) -> None:
        if document.version != expected_version + 1:
            raise DocumentVersionConflictError("Document revision must advance exactly once.")
        with self._store.connection() as connection:
            result = connection.execute(
                """UPDATE library_documents SET version=%s, published_id=%s, payload=%s, owner_id=%s
                WHERE id=%s AND version=%s""",
                (
                    document.version,
                    document.published_id,
                    Jsonb(self._codec.dump_python(document, mode="json")),
                    document.owner.id.value,
                    document.id,
                    expected_version,
                ),
            )
            if result.rowcount != 1:
                raise DocumentVersionConflictError("Document changed. Reload before retrying.")
            self._submissions(document)

    def list_visible(self, actor_id: str, offset: int, limit: int) -> tuple[LibraryDocument, ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """SELECT payload FROM library_documents
                WHERE (owner_id=%s OR published_id IS NOT NULL)
                ORDER BY id OFFSET %s LIMIT %s""",
                (actor_id, offset, limit),
            ).fetchall()
        return tuple(self._codec.validate_python(row[0]) for row in rows)

    def find_submission(self, actor_id: str, key: str) -> LibraryDocument | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """SELECT d.payload FROM library_documents d
                JOIN library_submissions s ON d.id=s.document_id
                WHERE s.owner_id=%s AND s.submission_key=%s""",
                (actor_id, key),
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None

    def claim(self, now: datetime, until: datetime, token: str) -> LibraryDocument | None:
        with self._store.transaction(), self._store.connection() as connection:
            row = connection.execute(
                """SELECT payload FROM library_documents d WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(d.payload->'versions') v
                WHERE v->>'stage'='queued' OR (v->>'stage' IN ('scanning','extracting')
                AND (v->>'lease_until')::timestamptz <= %s))
                ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1""",
                (now,),
            ).fetchone()
            if not row:
                return None
            previous = self._codec.validate_python(row[0])
            document = claimed(previous, now, until, token)
            self.save(document, previous.version)
            return document
