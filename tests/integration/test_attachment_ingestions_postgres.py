"""The PostgreSQL attachment repository: idempotent submission, leases and exhaustion."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from smb_kernel.documents.model import DocumentEvidenceBlock, EvidenceBlockKind
from smb_kernel.persistence.connector import DirectPostgresConnector

from smb_requirement_agent.application.errors import DocumentVersionConflictError
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.requirements.domain.document.attachment import (
    AttachmentFile,
    AttachmentTarget,
    AttachmentUpload,
)
from smb_requirement_agent.requirements.domain.document.ingestion import IngestionStage
from smb_requirement_agent.requirements.infrastructure.attachment_ingestions import (
    PostgresAttachmentIngestions,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
OWNER = ActorSnapshot(ActorId("fake-owner"), "Amina Owner", None)
NOW = datetime(2026, 10, 2, 9, tzinfo=UTC)


@pytest.fixture
def repository() -> Iterator[PostgresAttachmentIngestions]:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("TRUNCATE requirement_attachment_ingestions")
    yield PostgresAttachmentIngestions(
        PostgresStore(
            DirectPostgresConnector(DATABASE_URL), lambda _id, _conn: None, lambda _c, _i: None
        )
    )


def _upload(key: str, source: str = "req-1") -> AttachmentUpload:
    file = AttachmentFile(str(uuid.uuid4()), "a.txt", "text/plain", 3, "b" * 64, NOW, OWNER, key)
    return AttachmentUpload(str(uuid.uuid4()), AttachmentTarget(source, False, True), OWNER, file)


def test_submission_keys_are_unique_per_owner_and_reload(
    repository: PostgresAttachmentIngestions,
) -> None:
    first = _upload("key-1")
    repository.add(first)
    assert repository.find_submission("fake-owner", "key-1") == first
    assert repository.get(first.id) == first
    with pytest.raises(DocumentVersionConflictError):
        repository.add(_upload("key-1"))
    repository.add(_upload("key-2", source="req-2"))
    assert [u.id for u in repository.list_for("req-1", False)] == [first.id]
    assert repository.list_for("req-1", True) == ()


def test_saves_are_optimistic(repository: PostgresAttachmentIngestions) -> None:
    upload = _upload("key-1")
    repository.add(upload)
    excluded = replace(upload, excluded=True, version=2)
    repository.save(excluded, 1)
    with pytest.raises(DocumentVersionConflictError):
        repository.save(excluded, 1)


def test_claims_lease_and_retire_exhausted_attempts(
    repository: PostgresAttachmentIngestions,
) -> None:
    upload = _upload("key-1")
    repository.add(upload)
    claimed = repository.claim(NOW, NOW + timedelta(minutes=11), "token-1")
    assert claimed is not None
    assert (claimed.file.stage, claimed.file.attempt) == (IngestionStage.SCANNING, 1)
    assert claimed.file.lease_token == "token-1"
    # A live lease is not reclaimed; an expired one is, up to three attempts.
    assert repository.claim(NOW + timedelta(minutes=5), NOW, "token-2") is None
    later = NOW + timedelta(minutes=12)
    for attempt, token in ((2, "token-2"), (3, "token-3")):
        reclaimed = repository.claim(later, later + timedelta(minutes=11), token)
        assert reclaimed is not None and reclaimed.file.attempt == attempt
        later += timedelta(minutes=12)
    exhausted = repository.claim(later, later + timedelta(minutes=11), "token-4")
    assert exhausted is not None
    assert exhausted.file.stage is IngestionStage.FAILED and exhausted.file.lease_token is None
    assert repository.claim(later, later, "token-5") is None


def test_only_extracted_unattached_uploads_await_finalization(
    repository: PostgresAttachmentIngestions,
) -> None:
    upload = _upload("key-1")
    repository.add(upload)
    assert repository.pending_finalization() is None
    block = DocumentEvidenceBlock("b1", EvidenceBlockKind.PARAGRAPH, 1, (), "P1", "c" * 64, "hi")
    ready = upload.update_file(replace(upload.file, stage=IngestionStage.READY, blocks=(block,)))
    repository.save(ready, 1)
    assert repository.pending_finalization() == ready
    attached = replace(ready, attached_document_id="doc-1", version=ready.version + 1)
    repository.save(attached, ready.version)
    assert repository.pending_finalization() is None
