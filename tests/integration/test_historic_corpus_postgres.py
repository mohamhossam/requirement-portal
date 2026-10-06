"""The historic corpus in PostgreSQL (Knowledge Center E2, ADR-0102).

Requirement work's copy of the historic requirements keeps its own cursor, reads each
publication a page at a time, and makes it searchable in one update once every chunk is
embedded. A withdrawal removes it from search in the same transaction that records it.
"""

import os
import uuid
from collections.abc import Iterator
from urllib.parse import quote

import psycopg
import pytest

from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.container import Container
from tests.knowledge_doubles import (
    PublishedLibrary,
    container_with_library,
    index_historic,
    sync,
    work_item,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute("select current_database()").fetchone()
        assert row and "test" in row[0]
    schema = f"historic_corpus_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def served(isolated_url: str) -> tuple[Container, PublishedLibrary, str]:
    run_migrations(isolated_url)
    container, library = container_with_library(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=isolated_url,
        )
    )
    return container, library, isolated_url


def _search(container: Container, text: str) -> list[str]:
    identity = container.historic_indexer.identity
    vector = container.historic_indexer._embeddings.embed((text,))[0]  # noqa: SLF001
    return [
        m.chunk.historic_id for m in container.historic_corpus.search(text, vector, identity, 20)
    ]


def _rows(url: str, sql: str) -> list[tuple[object, ...]]:
    with psycopg.connect(url) as connection:
        return [tuple(row) for row in connection.execute(sql).fetchall()]


def test_the_historic_copy_is_projected_indexed_and_withdrawn(
    served: tuple[Container, PublishedLibrary, str],
) -> None:
    container, library, url = served
    backlog = (
        work_item(48213, "epic", "XGPON fibre bundles"),
        work_item(48216, "user_story", "Choose a bundle", parent_id=48213, description="Covered."),
    )
    kept = library.publish_historic(
        "XGPON bundles", [f"XGPON fibre passage {n}." for n in range(230)], backlog
    )
    gone = library.publish_historic("Gulf roaming", ["Roaming packs for the Gulf."])
    sync(container)
    assert _rows(url, "SELECT consumer, seq FROM knowledge_event_cursors ORDER BY consumer") == [
        ("historic_requirements", len(library._events)),  # noqa: SLF001
        ("reference_publications", len(library._events)),  # noqa: SLF001
    ]
    assert container.historic_corpus.version() == 0
    # A page is read and kept, but nothing is searchable yet.
    assert container.historic_indexer.process_next()
    assert _rows(url, "SELECT count(*) FROM historic_content_staging") == [(200,)]
    assert not container.historic_corpus.has_content(container.historic_indexer.identity)
    index_historic(container)
    assert container.historic_corpus.version() == 2
    assert _rows(url, "SELECT count(*) FROM historic_content_staging") == [(0,)]
    assert kept in _search(container, "XGPON fibre") and gone in _search(container, "Roaming")
    # Lexical search asks for any word, so a long subject still finds a short passage.
    assert gone in _search(container, "Prepaid customers want roaming packs when they travel")

    library.withdraw_historic(gone)
    sync(container)
    assert gone not in _search(container, "Roaming packs")
    assert _rows(
        url,
        f"SELECT count(*) FROM historic_knowledge_chunks WHERE historic_requirement_id = '{gone}'",
    ) == [(0,)]
    standing = container.historic_corpus.standing((kept, gone))
    assert standing[kept].published and not standing[gone].published

    # A new publication is read beside the old one, which stays searchable until it takes over.
    library.publish_historic(
        "XGPON bundles",
        [f"XGPON fibre passage {n}." for n in range(230)] + ["Static IP on request."],
        backlog,
        historic_id=kept,
    )
    sync(container)
    container.historic_indexer.process_next()
    assert kept in _search(container, "XGPON fibre")
    index_historic(container)
    assert container.historic_corpus.version() == 3
    seqs = _rows(
        url,
        "SELECT DISTINCT seq FROM historic_knowledge_chunks "
        f"WHERE historic_requirement_id = '{kept}'",
    )
    assert len(seqs) == 1, "only the searchable publication's chunks are kept"
    assert kept in _search(container, "Static IP on request")
