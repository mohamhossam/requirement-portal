"""Attachments stored in the library move to their own table, intact (ADR-0099).

The real migrations run in a throwaway schema: everything up to the previous
head, then library rows written in the shape attachments had before, then the
moving migration. The shared test schema is never touched.
"""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import psycopg
import pytest
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.infrastructure.persistence import migration_runner
from smb_requirement_agent.infrastructure.persistence.moved_knowledge_tables import (
    DROP_EMPTY_MIGRATION,
)
from smb_requirement_agent.requirements.domain.document.attachment import (
    AttachmentFile,
    AttachmentUpload,
)
from smb_requirement_agent.requirements.domain.document.ingestion import IngestionStage
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
MOVING = "202610021000_requirement_attachment_ingestions.sql"
OWNER = ActorSnapshot(ActorId("fake-owner"), "Amina Owner", "amina.owner@example.test")
NOW = datetime(2026, 10, 2, 9, tzinfo=UTC)


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    schema = f"attachments_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    # public stays on the path for the vector extension's types.
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def _document(key: str, stage: IngestionStage) -> dict[str, Any]:
    """A library row's payload as the library stored it before the move.

    The library's own types left with the library (ADR-0099), so the stored
    shape is written out here: a library version was the attachment file
    record plus its number and extraction revisions.
    """
    file = AttachmentFile(
        str(uuid.uuid4()),
        "policy.txt",
        "text/plain",
        12,
        "a" * 64,
        NOW,
        OWNER,
        key,
        stage=stage,
        attempt=2,
        error="Scanner restarted." if stage is IngestionStage.FAILED else None,
    )
    version = TypeAdapter(AttachmentFile).dump_python(file, mode="json") | {
        "number": 1,
        "revisions": [],
    }
    return {
        "id": str(uuid.uuid4()),
        "title": "policy.txt",
        "owner": TypeAdapter(ActorSnapshot).dump_python(OWNER, mode="json"),
        "versions": [version],
        "version": 3,
        "publications": [],
        "published_id": None,
        "ownership_history": [],
    }


def _insert(connection: psycopg.Connection[Any], document: dict[str, Any], **extra: Any) -> None:
    connection.execute(
        "INSERT INTO library_documents (id, owner_id, version, published_id, payload) "
        "VALUES (%s,%s,%s,NULL,%s)",
        (document["id"], OWNER.id.value, document["version"], Jsonb(document | extra)),
    )
    version = document["versions"][0]
    connection.execute(
        "INSERT INTO library_submissions (owner_id, submission_key, document_id, version_id) "
        "VALUES (%s,%s,%s,%s)",
        (OWNER.id.value, version["idempotency_key"], document["id"], version["id"]),
    )


def test_attachment_rows_move_out_of_the_library_with_their_state(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path(migration_runner.MIGRATIONS)
    for path in real.glob("*.sql"):
        if path.name not in {MOVING, DROP_EMPTY_MIGRATION}:
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)
    migration_runner.run_migrations(isolated_url)

    library = _document("library-key", IngestionStage.QUEUED)
    attached = _document("attached-key", IngestionStage.QUEUED)
    stopped = _document("stopped-key", IngestionStage.FAILED)
    target = {"source_id": "req-1", "is_draft": False, "include_in_analysis": True}
    with psycopg.connect(isolated_url) as connection:
        _insert(connection, library)
        _insert(
            connection,
            attached,
            attachment_target=target,
            attached_document_id="doc-9",
        )
        _insert(
            connection,
            stopped,
            attachment_target=target | {"source_id": "draft-2", "is_draft": True},
            attachment_excluded=True,
        )

    shutil.copy(real / MOVING, tmp_path / MOVING)
    migration_runner.run_migrations(isolated_url)

    with psycopg.connect(isolated_url) as connection:
        rows = connection.execute(
            "SELECT id, source_id, is_draft, owner_id, submission_key, version, payload "
            "FROM requirement_attachment_ingestions ORDER BY submission_key"
        ).fetchall()
        library_ids = [r[0] for r in connection.execute("SELECT id FROM library_documents")]
        submissions = [
            r[0] for r in connection.execute("SELECT submission_key FROM library_submissions")
        ]

    assert library_ids == [library["id"]]
    assert submissions == ["library-key"]
    by_key = {row[4]: row for row in rows}
    assert set(by_key) == {"attached-key", "stopped-key"}

    moved = TypeAdapter(AttachmentUpload).validate_python(by_key["attached-key"][6])
    assert by_key["attached-key"][1:6] == ("req-1", False, "fake-owner", "attached-key", 3)
    assert moved.id == attached["id"] and moved.version == 3
    assert moved.attached_document_id == "doc-9" and not moved.excluded
    assert moved.target.source_id == "req-1" and moved.target.include_in_analysis
    assert moved.file.id == attached["versions"][0]["id"]
    assert (moved.file.stage, moved.file.attempt) == (IngestionStage.QUEUED, 2)

    excluded = TypeAdapter(AttachmentUpload).validate_python(by_key["stopped-key"][6])
    assert by_key["stopped-key"][1:3] == ("draft-2", True)
    assert excluded.excluded and excluded.attached_document_id is None
    assert excluded.file.stage is IngestionStage.FAILED
    assert excluded.file.error == "Scanner restarted."
