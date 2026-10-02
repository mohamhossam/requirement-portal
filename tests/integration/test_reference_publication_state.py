"""The local copy of the library's citable state, seeded and kept in PostgreSQL (ADR-0099)."""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from urllib.parse import quote

import psycopg
import pytest
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter
from smb_kernel.documents.scanner import OfflineDocumentScanner
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.persistence.connector import DirectPostgresConnector
from smb_kernel.time.fixed import FixedClock
from smb_kernel.time.system import SystemClock

from smb_requirement_agent.application.use_cases.document_library import (
    CHUNKING_POLICY,
    DocumentLibrary,
)
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.application.use_cases.reference_currency import (
    CurrentArchitectureRelease,
    ProjectKnowledgeEvents,
)
from smb_requirement_agent.domain.document.library import LibraryDocument, ReviewedPassage
from smb_requirement_agent.domain.document.reference import ReferenceDocumentState
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.persistence import migration_runner
from smb_requirement_agent.infrastructure.persistence.architecture_release_state import (
    PostgresArchitectureReleaseState,
)
from smb_requirement_agent.infrastructure.persistence.document_library import (
    InMemoryDocumentLibrary,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.infrastructure.persistence.knowledge_events import (
    PostgresKnowledgeEvents,
)
from smb_requirement_agent.infrastructure.persistence.postgres_architecture_knowledge import (
    PostgresArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.infrastructure.persistence.reference_publications import (
    PostgresReferencePublications,
)
from smb_requirement_agent.infrastructure.persistence.relaying_architecture_knowledge import (
    RelayingArchitectureKnowledgeRepository,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
SEEDING = "202610021200_knowledge_events_and_reference_state.sql"
OWNER = ActorProfile(ActorId("library-owner"), "Owner")


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    schema = f"reference_state_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def _published_documents() -> tuple[LibraryDocument, LibraryDocument, LibraryDocument]:
    """One published, one withdrawn and one never published, through the real library flow."""
    lock = RLock()
    repository = InMemoryDocumentLibrary(lock)
    storage = InMemoryDocumentStorage()
    transactions = InMemoryTransactionManager(lambda _: None, lock)
    transactions.enroll(repository, storage)
    clock = FixedClock(datetime(2026, 10, 2, tzinfo=UTC))
    service = DocumentLibrary(
        repository,
        storage,
        SafeDocumentTextExtractor(),
        OfflineDocumentScanner(),
        transactions,
        clock,
        100_000,
    )

    def publish(key: str, content: bytes) -> LibraryDocument:
        document = service.submit(
            "Eligibility", UploadDocumentInput("p.txt", "text/plain", content), key, OWNER
        )
        assert service.process_next()
        view = service.get(document.id, OWNER)
        source = view.versions[0]
        # The first block is included; the second is excluded, so it never appears.
        passages = tuple(
            ReviewedPassage(b.id, b.text or "", i != 1, "" if i != 1 else "Private")
            for i, b in enumerate(source.blocks)
        )
        reviewed = service.review(document.id, source.id, view.version, OWNER, passages, "Checked")
        revision = reviewed.versions[0].revisions[-1]
        approved = service.approve(
            document.id,
            source.id,
            revision.id,
            revision.fingerprint(source.id, CHUNKING_POLICY),
            reviewed.version,
            OWNER,
        )
        stored = repository.get(approved.id)
        assert stored is not None and stored.publications
        publication = stored.publications[-1]
        activated = stored.activate(publication.id, clock.now())
        activated = replace(activated, version=stored.version + 1)
        repository.save(activated, stored.version)
        return activated

    live = publish("live", b"XGPON coverage is required.\nPrivate appendix.\nThird line.")
    gone = publish("gone", b"Retired policy.\nIts appendix.")
    withdrawn = gone.withdraw(clock.now(), "Retired")
    withdrawn = replace(withdrawn, version=gone.version + 1)
    repository.save(withdrawn, gone.version)
    draft = service.submit(
        "Draft", UploadDocumentInput("d.txt", "text/plain", b"Draft."), "d", OWNER
    )
    stored_draft = repository.get(draft.id)
    assert stored_draft is not None
    return live, withdrawn, stored_draft


def test_the_seed_builds_exactly_the_state_the_library_publishes(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path(migration_runner.MIGRATIONS)
    for path in real.glob("*.sql"):
        if path.name != SEEDING:
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)
    migration_runner.run_migrations(isolated_url)
    documents = _published_documents()
    codec = TypeAdapter(LibraryDocument)
    with psycopg.connect(isolated_url) as connection:
        for document in documents:
            connection.execute(
                "INSERT INTO library_documents (id, owner_id, version, published_id, payload) "
                "VALUES (%s,%s,%s,%s,%s)",
                (
                    document.id,
                    document.owner.id.value,
                    document.version,
                    document.published_id,
                    Jsonb(codec.dump_python(document, mode="json")),
                ),
            )

    shutil.copy(real / SEEDING, tmp_path / SEEDING)
    migration_runner.run_migrations(isolated_url)

    with psycopg.connect(isolated_url) as connection:
        rows: dict[object, object] = dict(
            connection.execute(
                "SELECT document_id, payload FROM reference_publication_state"
            ).fetchall()
        )
    live, withdrawn, draft = documents
    assert live.citable_state().published is not None
    assert withdrawn.citable_state().published is None and draft.citable_state().published is None
    for document in documents:
        seeded = ReferenceDocumentState.from_payload(rows[document.id])
        assert seeded == document.citable_state()


def test_the_postgres_copy_keeps_the_newest_state_and_its_cursor() -> None:
    assert DATABASE_URL is not None
    migration_runner.run_migrations(DATABASE_URL)
    store = PostgresStore(
        DirectPostgresConnector(DATABASE_URL), lambda _id, _conn: None, lambda _c, _i: None
    )
    states = PostgresReferencePublications(store)
    state = ReferenceDocumentState(f"doc-{uuid.uuid4().hex}", "owner", "Policy", 3)
    with store.transaction():
        states.apply(10, state)
        states.apply(9, replace(state, title="Older"))
        states.lock((state.document_id,))
    assert states.get(state.document_id) == state
    with store.transaction():
        states.apply(11, replace(state, version=4))
    assert states.get(state.document_id) == replace(state, version=4)
    before = states.cursor()
    states.advance(before + 5)
    states.advance(before + 2)
    assert states.cursor() == before + 5


def test_an_activation_writes_its_event_and_the_relay_brings_the_copy_along() -> None:
    assert DATABASE_URL is not None
    migration_runner.run_migrations(DATABASE_URL)
    connector = DirectPostgresConnector(DATABASE_URL)
    store = PostgresStore(connector, lambda _id, _conn: None, lambda _c, _i: None)
    releases = PostgresArchitectureReleaseState(store)
    projector = ProjectKnowledgeEvents(
        PostgresKnowledgeEvents(store),
        PostgresReferencePublications(store),
        releases,
        store,
        SystemClock(),
    )
    repository = RelayingArchitectureKnowledgeRepository(
        PostgresArchitectureKnowledgeRepository(connector, seed_knowledge()), projector.drain
    )
    active = repository.active().id

    repository.activate(active, "maintainer", "Re-affirmed")

    with psycopg.connect(DATABASE_URL) as connection:
        kind, subject = connection.execute(
            "SELECT kind, subject_id FROM knowledge_events ORDER BY seq DESC LIMIT 1"
        ).fetchone() or (None, None)
    assert (kind, subject) == ("architecture_release_activated", active)
    assert CurrentArchitectureRelease(releases).active_release_id() == active


def test_the_migration_seeds_the_release_active_now(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path(migration_runner.MIGRATIONS)
    seeding = "202610021300_active_architecture_release.sql"
    for path in real.glob("*.sql"):
        if path.name != seeding:
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)
    migration_runner.run_migrations(isolated_url)
    with psycopg.connect(isolated_url) as connection:
        connection.execute(
            "INSERT INTO architecture_knowledge_releases (release_id, revision, payload, active) "
            "VALUES ('old', 1, '{}'::jsonb, false), ('live', 2, '{}'::jsonb, true)"
        )

    shutil.copy(real / seeding, tmp_path / seeding)
    migration_runner.run_migrations(isolated_url)

    with psycopg.connect(isolated_url) as connection:
        row = connection.execute(
            "SELECT release_id, seq FROM active_architecture_release"
        ).fetchone()
    assert row == ("live", 0)
