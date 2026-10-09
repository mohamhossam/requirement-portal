"""The local copy of the library's citable state, seeded and kept in PostgreSQL (ADR-0099)."""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

import psycopg
import pytest
from psycopg.types.json import Jsonb
from smb_kernel.persistence.connector import DirectPostgresConnector
from smb_kernel.time.system import SystemClock

from smb_requirement_agent.infrastructure.persistence import migration_runner
from smb_requirement_agent.infrastructure.persistence.moved_knowledge_tables import (
    DROP_EMPTY_MIGRATION,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.references.application.errors import CitationNotCurrentError
from smb_requirement_agent.references.application.ports.architecture_knowledge import ActiveRelease
from smb_requirement_agent.references.application.use_cases.reference_currency import (
    CurrentArchitectureRelease,
    ProjectKnowledgeEvents,
    ReferenceCurrency,
)
from smb_requirement_agent.references.domain.reference import (
    CurrentPublication,
    ReferenceDocumentState,
)
from smb_requirement_agent.references.infrastructure.architecture_release_state import (
    PostgresArchitectureReleaseState,
)
from smb_requirement_agent.references.infrastructure.knowledge_payloads import (
    PayloadKnowledgeStateDecoder,
    reference_document_state_from_payload,
)
from smb_requirement_agent.references.infrastructure.reference_publications import (
    PostgresReferencePublications,
)
from tests.knowledge_doubles import PublishedLibrary

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
SEEDING = "202610021200_knowledge_events_and_reference_state.sql"


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


def _legacy_document(
    document_id: str,
    *,
    published: bool = True,
    withdrawn: bool = False,
) -> dict[str, object]:
    """A `library_documents` payload as the in-process library stored it before the split.

    Only the fields the seeding migration reads. Block 2 is excluded from review,
    and block 1 has a second included passage that the seed must not pick.
    """
    version = {
        "id": f"{document_id}-v1",
        "number": 1,
        "blocks": [
            {"id": "b1", "label": "Line 1"},
            {"id": "b2", "label": "Line 2"},
            {"id": "b3", "label": "Line 3"},
        ],
        "revisions": [
            {
                "id": f"{document_id}-r1",
                "passages": [
                    {"block_id": "b1", "text": "XGPON coverage is required.", "included": True},
                    {"block_id": "b2", "text": "Private appendix.", "included": False},
                    {"block_id": "b3", "text": "Third line.", "included": True},
                    {"block_id": "b1", "text": "A later duplicate.", "included": True},
                ],
            }
        ],
    }
    publication = {
        "id": f"{document_id}-p1",
        "fingerprint": "f" * 64,
        "version_id": version["id"],
        "revision_id": f"{document_id}-r1",
        "withdrawn_at": "2026-10-02T00:00:00Z" if withdrawn else None,
    }
    return {
        "owner": {"id": {"value": "library-owner"}},
        "title": "Eligibility",
        "versions": [version],
        "publications": [publication] if published else [],
        "published_id": publication["id"] if published else None,
    }


def _expected(document_id: str, version: int, *, live: bool) -> ReferenceDocumentState:
    """What `LibraryDocument.citable_state()` gave for the payload above."""
    publication = CurrentPublication(
        f"{document_id}-p1",
        "f" * 64,
        f"{document_id}-v1",
        1,
        f"{document_id}-r1",
        (("b1", "Line 1"), ("b2", "Line 2"), ("b3", "Line 3")),
        (("b1", "XGPON coverage is required."), ("b3", "Third line.")),
    )
    return ReferenceDocumentState(
        document_id, "library-owner", "Eligibility", version, publication if live else None
    )


def test_the_seed_builds_exactly_the_state_the_library_published(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path(migration_runner.MIGRATIONS)
    for path in real.glob("*.sql"):
        if path.name not in {SEEDING, DROP_EMPTY_MIGRATION}:
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(migration_runner, "MIGRATIONS", tmp_path)
    migration_runner.run_migrations(isolated_url)
    documents = {
        "live": (_legacy_document("live"), 3),
        "gone": (_legacy_document("gone", withdrawn=True), 4),
        "draft": (_legacy_document("draft", published=False), 1),
    }
    with psycopg.connect(isolated_url) as connection:
        for document_id, (payload, version) in documents.items():
            connection.execute(
                "INSERT INTO library_documents (id, owner_id, version, published_id, payload) "
                "VALUES (%s,%s,%s,%s,%s)",
                (document_id, "library-owner", version, payload["published_id"], Jsonb(payload)),
            )

    shutil.copy(real / SEEDING, tmp_path / SEEDING)
    migration_runner.run_migrations(isolated_url)

    with psycopg.connect(isolated_url) as connection:
        rows: dict[object, object] = dict(
            connection.execute(
                "SELECT document_id, payload FROM reference_publication_state"
            ).fetchall()
        )
    assert reference_document_state_from_payload(rows["live"]) == _expected("live", 3, live=True)
    assert reference_document_state_from_payload(rows["gone"]) == _expected("gone", 4, live=False)
    assert reference_document_state_from_payload(rows["draft"]) == _expected("draft", 1, live=False)


def test_the_postgres_copy_keeps_the_newest_state_and_its_cursor(isolated_url: str) -> None:
    migration_runner.run_migrations(isolated_url)
    store = PostgresStore(
        DirectPostgresConnector(isolated_url), lambda _id, _conn: None, lambda _c, _i: None
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


def test_the_knowledge_service_feed_brings_the_postgres_copy_along(isolated_url: str) -> None:
    """Publications, withdrawals and activations reach the copy only through the feed."""
    migration_runner.run_migrations(isolated_url)
    store = PostgresStore(
        DirectPostgresConnector(isolated_url), lambda _id, _conn: None, lambda _c, _i: None
    )
    states = PostgresReferencePublications(store)
    releases = PostgresArchitectureReleaseState(store)
    library = PublishedLibrary()
    projector = ProjectKnowledgeEvents(
        library, states, releases, store, SystemClock(), decoder=PayloadKnowledgeStateDecoder()
    )
    currency = ReferenceCurrency(states, store)
    (citation,) = library.publish("Eligibility", ("XGPON coverage is required.",))
    library.activate_release("release-2", "Q4 catalogue")

    projector.drain()

    currency.require_current((citation,))
    assert CurrentArchitectureRelease(releases).active_release() == ActiveRelease(
        "release-2", "Q4 catalogue"
    )
    library.withdraw(citation.document_id)
    projector.drain()
    with pytest.raises(CitationNotCurrentError, match="withdrawn or replaced"):
        currency.require_current((citation,))
    state = states.get(citation.document_id)
    assert state is not None and state.published is None
    assert states.cursor() == len(library.after(0, 1000))
    # Caught up: a restarted copy resumes where it stopped, with nothing left to apply.
    assert not ProjectKnowledgeEvents(
        library,
        PostgresReferencePublications(store),
        releases,
        store,
        SystemClock(),
        decoder=PayloadKnowledgeStateDecoder(),
    ).project_next()


def test_the_migration_seeds_the_release_active_now(
    isolated_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path(migration_runner.MIGRATIONS)
    seeding = "202610021300_active_architecture_release.sql"
    for path in real.glob("*.sql"):
        if path.name not in {seeding, DROP_EMPTY_MIGRATION}:
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


def test_the_local_copy_keeps_the_version_s_name(isolated_url: str) -> None:
    migration_runner.run_migrations(isolated_url)
    store = PostgresStore(DirectPostgresConnector(isolated_url), lambda *_: None, lambda *_: None)
    releases = PostgresArchitectureReleaseState(store)

    releases.apply(5, ActiveRelease("named-release", "Q4 catalogue"))
    releases.apply(4, ActiveRelease("older-release"))

    assert PostgresArchitectureReleaseState(store).active_release() == ActiveRelease(
        "named-release", "Q4 catalogue"
    )
    releases.apply(6, ActiveRelease("unnamed-release"))
    assert releases.active_release() == ActiveRelease("unnamed-release", None)
