"""PostgreSQL follows a Requirement's attachments into its knowledge index (Knowledge Center B1).

The trigger on source_documents marks the Requirement changed whenever a row is written,
so an upload, an exclusion and a removal each reach the index through the ordinary
indexer, without the use cases knowing about knowledge at all.
"""

import os
import uuid
from collections.abc import Iterator
from urllib.parse import quote

import psycopg
import pytest

from smb_requirement_agent.domain.knowledge.entities import KnowledgeSourceKind
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.llm.fake_requirement_knowledge import (
    FakeKnowledgeEmbedding,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.requirements.application.use_cases.requirement_drafts import (
    RequirementDraftInput,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.workflow_helpers import drain_requirement_index

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
BRD = b"# Need\n\nBusiness customers order XGPON fibre bundles through BCRM.\n"


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute("select current_database()").fetchone()
        assert row and "test" in row[0]
    schema = f"attachment_sources_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def _change(url: str, requirement_id: RequirementId) -> tuple[int, bool]:
    with psycopg.connect(url) as connection:
        row = connection.execute(
            "SELECT change_number, dirty FROM knowledge_source_changes WHERE requirement_id=%s",
            (requirement_id.value,),
        ).fetchone()
    assert row is not None
    return int(row[0]), bool(row[1])


def _attachment_texts(container: Container, requirement_id: RequirementId) -> list[str]:
    (query,) = FakeKnowledgeEmbedding().embed(("XGPON",))
    return [
        match.chunk.text
        for match in container.knowledge_index.search("XGPON", query, None, 100)
        if match.chunk.requirement_id == requirement_id
        and match.chunk.source_kind is KnowledgeSourceKind.ATTACHMENT
    ]


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_attachment_writes_mark_the_requirement_and_reach_the_index(isolated_url: str) -> None:
    run_migrations(isolated_url)
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=isolated_url,
        )
    )
    owner = FAKE_ACTORS[0]
    try:
        requirement = container.create_requirement.execute(
            CreateRequirementInput("Fibre for offices", "See the attached need."), owner
        )
        drain_requirement_index(container)
        settled, dirty = _change(isolated_url, requirement.id)
        assert dirty is False
        assert _attachment_texts(container, requirement.id) == []

        document = container.upload_document.for_requirement(
            requirement.id,
            UploadDocumentInput("brd.md", "text/markdown", BRD, include_in_analysis=True),
            owner,
        )

        uploaded, dirty = _change(isolated_url, requirement.id)
        assert uploaded > settled and dirty is True
        drain_requirement_index(container)
        assert any("XGPON" in text for text in _attachment_texts(container, requirement.id))

        excluded = container.set_document_inclusion.execute(
            owner, requirement.id, document.id, False, document.version_number
        )

        assert _change(isolated_url, requirement.id) > (uploaded, False)
        drain_requirement_index(container)
        assert _attachment_texts(container, requirement.id) == []

        container.set_document_inclusion.execute(
            owner, requirement.id, document.id, True, excluded.version_number
        )
        drain_requirement_index(container)
        assert _attachment_texts(container, requirement.id)
        included = container.document_repository.get(document.id)
        assert included is not None
        container.remove_document.execute(
            owner, requirement.id, document.id, included.version_number
        )
        drain_requirement_index(container)
        assert _attachment_texts(container, requirement.id) == []
    finally:
        container.close_resources()


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_a_draft_attachment_joins_the_index_when_its_draft_is_promoted(isolated_url: str) -> None:
    run_migrations(isolated_url)
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=isolated_url,
        )
    )
    owner = FAKE_ACTORS[0]
    try:
        draft = container.create_requirement_draft.execute(
            RequirementDraftInput(title="Fibre for offices"), owner
        )
        # A draft's document has no Requirement, so there is nothing to mark yet.
        container.upload_document.for_draft(
            draft.id,
            UploadDocumentInput("brd.md", "text/markdown", BRD, include_in_analysis=True),
            owner,
        )
        current = container.get_requirement_draft.execute(draft.id, owner)

        requirement = container.promote_requirement_draft.execute(
            draft.id, current.version.value, owner
        )

        drain_requirement_index(container)
        assert any("XGPON" in text for text in _attachment_texts(container, requirement.id))
    finally:
        container.close_resources()
