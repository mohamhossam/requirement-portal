"""Paged drafts and documents against PostgreSQL (production hardening PR 13).

The same scenarios as the in-memory store, and no per-row lookups: ownership, owner
titles and eligibility are read with the page, not once per draft or document.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from urllib.parse import quote

import psycopg
import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.identity.infrastructure.postgres_identity import (
    PostgresAccessRepository,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.requirements.infrastructure.postgres_document_metadata import (
    PostgresDocumentRepository,
)
from tests.catalogue_scenarios import (
    OWNER,
    documents_page_with_owners_counts_and_privacy,
    drafts_page_by_owner_search_and_title,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


@pytest.fixture
def client() -> Iterator[TestClient]:
    assert DATABASE_URL is not None
    schema = f"catalogue_pages_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    url = f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    run_migrations(url)
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=url,
        )
    )
    try:
        with TestClient(create_app(lambda: container)) as test_client:
            yield test_client
    finally:
        container.close_resources()
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_drafts_page_by_owner_search_and_title(client: TestClient) -> None:
    drafts_page_by_owner_search_and_title(client)


def test_documents_page_with_owners_counts_and_privacy(client: TestClient) -> None:
    documents_page_with_owners_counts_and_privacy(client)


def test_a_page_reads_no_draft_or_document_one_by_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: both lists looked up each draft's ownership, and each draft's documents."""
    for n in range(4):
        draft = client.post(
            "/requirements/drafts", json={"title": f"Draft {n}"}, headers=OWNER
        ).json()["id"]
        client.post(
            f"/requirement-drafts/{draft}/attachments",
            data={"include_in_analysis": "false"},
            files={"file": (f"notes-{n}.txt", b"Notes", "text/plain")},
            headers=OWNER,
        )

    def one_by_one(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("A list read a row one by one.")

    monkeypatch.setattr(PostgresAccessRepository, "get_draft_ownership", one_by_one)
    monkeypatch.setattr(PostgresDocumentRepository, "list_for_draft", one_by_one)

    drafts = client.get("/requirements/drafts", headers=OWNER)
    documents = client.get("/documents", headers=OWNER)

    assert drafts.status_code == 200, drafts.text
    assert drafts.json()["total"] == 4
    assert documents.status_code == 200, documents.text
    assert documents.json()["total"] == 4
