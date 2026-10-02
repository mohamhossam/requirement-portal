"""Attachment uploads: optimistic writes and independently leased scanning (ADR-0099)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import DocumentVersionConflictError
from smb_requirement_agent.domain.document.attachment import AttachmentUpload
from smb_requirement_agent.domain.document.ingestion import IngestionStage
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession

MAX_ATTEMPTS = 3


def claimable(upload: AttachmentUpload, now: datetime) -> bool:
    file = upload.file
    return file.stage is IngestionStage.QUEUED or (
        file.stage in {IngestionStage.SCANNING, IngestionStage.EXTRACTING}
        and file.lease_until is not None
        and file.lease_until <= now
    )


def claimed(
    upload: AttachmentUpload, now: datetime, until: datetime, token: str
) -> AttachmentUpload:
    if not claimable(upload, now):
        raise DocumentVersionConflictError("Upload is no longer available for processing.")
    file = upload.file
    if file.attempt >= MAX_ATTEMPTS:
        return upload.update_file(
            replace(
                file,
                stage=IngestionStage.FAILED,
                lease_token=None,
                lease_until=None,
                error="Processing attempts exhausted. The owner can explicitly retry.",
            )
        )
    return upload.update_file(
        replace(
            file,
            stage=IngestionStage.SCANNING,
            lease_token=token,
            lease_until=until,
            attempt=file.attempt + 1,
            error=None,
        )
    )


def _pending(upload: AttachmentUpload) -> bool:
    return upload.attached_document_id is None and upload.file.stage is IngestionStage.READY


class InMemoryAttachmentIngestions:
    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self._uploads: dict[str, AttachmentUpload] = {}

    def snapshot_state(self) -> object:
        return dict(self._uploads)

    def restore_state(self, state: object) -> None:
        self._uploads = cast(dict[str, AttachmentUpload], state)

    def add(self, upload: AttachmentUpload) -> None:
        with self._lock:
            if upload.id in self._uploads or self.find_submission(
                upload.file.uploaded_by.id.value, upload.file.idempotency_key
            ):
                raise DocumentVersionConflictError("This upload was already submitted. Reload it.")
            self._uploads[upload.id] = upload

    def get(self, upload_id: str) -> AttachmentUpload | None:
        with self._lock:
            return self._uploads.get(upload_id)

    def save(self, upload: AttachmentUpload, expected_version: int) -> None:
        with self._lock:
            previous = self._uploads.get(upload.id)
            if previous is None or previous.version != expected_version:
                raise DocumentVersionConflictError("Upload changed. Reload before retrying.")
            if upload.version != expected_version + 1:
                raise DocumentVersionConflictError("Upload revision must advance exactly once.")
            self._uploads[upload.id] = upload

    def find_submission(self, actor_id: str, key: str) -> AttachmentUpload | None:
        with self._lock:
            return next(
                (
                    u
                    for u in self._uploads.values()
                    if u.file.uploaded_by.id.value == actor_id and u.file.idempotency_key == key
                ),
                None,
            )

    def list_for(self, source_id: str, is_draft: bool) -> tuple[AttachmentUpload, ...]:
        with self._lock:
            return tuple(
                u
                for u in sorted(self._uploads.values(), key=lambda u: u.id)
                if u.target.source_id == source_id and u.target.is_draft == is_draft
            )

    def claim(self, now: datetime, until: datetime, token: str) -> AttachmentUpload | None:
        with self._lock:
            source = next(
                (
                    u
                    for u in sorted(self._uploads.values(), key=lambda u: u.id)
                    if claimable(u, now)
                ),
                None,
            )
            if source is None:
                return None
            upload = claimed(source, now, until, token)
            self.save(upload, source.version)
            return upload

    def pending_finalization(self) -> AttachmentUpload | None:
        with self._lock:
            return next(
                (u for u in sorted(self._uploads.values(), key=lambda u: u.id) if _pending(u)),
                None,
            )


class PostgresAttachmentIngestions:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store
        self._codec = TypeAdapter(AttachmentUpload)

    def _dump(self, upload: AttachmentUpload) -> Jsonb:
        return Jsonb(self._codec.dump_python(upload, mode="json"))

    def add(self, upload: AttachmentUpload) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """INSERT INTO requirement_attachment_ingestions
                (id, source_id, is_draft, owner_id, submission_key, version, payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (
                    upload.id,
                    upload.target.source_id,
                    upload.target.is_draft,
                    upload.file.uploaded_by.id.value,
                    upload.file.idempotency_key,
                    upload.version,
                    self._dump(upload),
                ),
            )
            if result.rowcount != 1:
                raise DocumentVersionConflictError("This upload was already submitted. Reload it.")

    def get(self, upload_id: str) -> AttachmentUpload | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_attachment_ingestions WHERE id=%s", (upload_id,)
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None

    def save(self, upload: AttachmentUpload, expected_version: int) -> None:
        if upload.version != expected_version + 1:
            raise DocumentVersionConflictError("Upload revision must advance exactly once.")
        with self._store.connection() as connection:
            result = connection.execute(
                """UPDATE requirement_attachment_ingestions SET version=%s, payload=%s
                WHERE id=%s AND version=%s""",
                (upload.version, self._dump(upload), upload.id, expected_version),
            )
            if result.rowcount != 1:
                raise DocumentVersionConflictError("Upload changed. Reload before retrying.")

    def find_submission(self, actor_id: str, key: str) -> AttachmentUpload | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """SELECT payload FROM requirement_attachment_ingestions
                WHERE owner_id=%s AND submission_key=%s""",
                (actor_id, key),
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None

    def list_for(self, source_id: str, is_draft: bool) -> tuple[AttachmentUpload, ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """SELECT payload FROM requirement_attachment_ingestions
                WHERE source_id=%s AND is_draft=%s ORDER BY id""",
                (source_id, is_draft),
            ).fetchall()
        return tuple(self._codec.validate_python(row[0]) for row in rows)

    def claim(self, now: datetime, until: datetime, token: str) -> AttachmentUpload | None:
        with self._store.transaction(), self._store.connection() as connection:
            row = connection.execute(
                """SELECT payload FROM requirement_attachment_ingestions
                WHERE payload->'file'->>'stage'='queued'
                OR (payload->'file'->>'stage' IN ('scanning','extracting')
                AND (payload->'file'->>'lease_until')::timestamptz <= %s)
                ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1""",
                (now,),
            ).fetchone()
            if not row:
                return None
            previous = self._codec.validate_python(row[0])
            upload = claimed(previous, now, until, token)
            self.save(upload, previous.version)
            return upload

    def pending_finalization(self) -> AttachmentUpload | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """SELECT payload FROM requirement_attachment_ingestions
                WHERE payload->'file'->>'stage'='ready_for_review'
                AND payload->>'attached_document_id' IS NULL
                ORDER BY id LIMIT 1"""
            ).fetchone()
        return self._codec.validate_python(row[0]) if row else None
