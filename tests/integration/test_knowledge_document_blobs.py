"""Library and catalogue file bytes move to their own blob store (ADR-0099).

The real migrations run in a throwaway schema: up to the previous head, then
blobs for a library version, catalogue documents (registered, and listed only
by a draft release) and an attachment, then the moving migration.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import psycopg
import pytest
from psycopg.types.json import Jsonb
from smb_kernel.persistence.connector import DirectPostgresConnector

from smb_requirement_agent.application.errors import DocumentNotFoundError
from smb_requirement_agent.domain.document.value_objects import DocumentVersionId
from smb_requirement_agent.infrastructure.persistence import migration_runner
from smb_requirement_agent.infrastructure.persistence.moved_knowledge_tables import (
    DROP_EMPTY_MIGRATION,
)
from smb_requirement_agent.infrastructure.persistence.postgres_document_repository import (
    PostgresDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
MOVING = "202610021400_knowledge_document_blobs.sql"


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    schema = f"blobs_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def _blob(connection: psycopg.Connection[tuple[object, ...]], key: str, content: bytes) -> None:
    connection.execute(
        "INSERT INTO document_blobs (document_version_id, checksum_sha256, size_bytes, content) "
        "VALUES (%s, %s, %s, %s)",
        (key, hashlib.sha256(content).hexdigest(), len(content), content),
    )


def test_knowledge_blobs_move_and_requirement_blobs_stay(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path(migration_runner.MIGRATIONS)
    for path in real.glob("*.sql"):
        if path.name not in {MOVING, DROP_EMPTY_MIGRATION}:
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)
    migration_runner.run_migrations(isolated_url)
    with psycopg.connect(isolated_url) as connection:
        for key in ("library-v1", "catalogue-registered", "catalogue-draft-only", "attachment-1"):
            _blob(connection, key, f"bytes of {key}".encode())
        connection.execute(
            "INSERT INTO library_documents (id, owner_id, version, payload) VALUES (%s,%s,%s,%s)",
            ("lib-1", "owner", 1, Jsonb({"versions": [{"id": "library-v1"}]})),
        )
        connection.execute(
            "INSERT INTO architecture_knowledge_documents (version_id, payload) VALUES (%s, %s)",
            ("doc-v1", Jsonb({"id": "doc-v1", "storage_key": "catalogue-registered"})),
        )
        connection.execute(
            "INSERT INTO architecture_knowledge_releases (release_id, revision, payload, active) "
            "VALUES (%s, 1, %s, false)",
            (
                "draft-1",
                Jsonb({"documents": [{"id": "doc-v2", "storage_key": "catalogue-draft-only"}]}),
            ),
        )

    shutil.copy(real / MOVING, tmp_path / MOVING)
    migration_runner.run_migrations(isolated_url)

    with psycopg.connect(isolated_url) as connection:
        knowledge = {
            row[0]: (row[1], bytes(row[2]))
            for row in connection.execute(
                "SELECT document_version_id, checksum_sha256, content FROM knowledge_document_blobs"
            )
        }
        requirement = {
            row[0] for row in connection.execute("SELECT document_version_id FROM document_blobs")
        }
    assert set(knowledge) == {"library-v1", "catalogue-registered", "catalogue-draft-only"}
    for key, (checksum, content) in knowledge.items():
        assert content == f"bytes of {key}".encode()
        assert checksum == hashlib.sha256(content).hexdigest()
    assert requirement == {"attachment-1"}


def test_requirement_bytes_stay_in_their_own_store_and_only_it_reaches_sql() -> None:
    assert DATABASE_URL is not None
    migration_runner.run_migrations(DATABASE_URL)
    store = PostgresStore(
        DirectPostgresConnector(DATABASE_URL), lambda _id, _conn: None, lambda _c, _i: None
    )
    requirement = PostgresDocumentStorage(store)
    key = DocumentVersionId(uuid.uuid4().hex)
    with store.transaction():
        requirement.put(key, b"attachment bytes")
    assert requirement.get(key) == b"attachment bytes"
    with pytest.raises(DocumentNotFoundError):
        requirement.get(DocumentVersionId(uuid.uuid4().hex))
    # The knowledge blob store belongs to the knowledge service now (ADR-0099).
    for table in ("knowledge_document_blobs", "document_blobs; DROP"):
        with pytest.raises(ValueError, match="Unknown blob table"):
            PostgresDocumentStorage(store, table)
