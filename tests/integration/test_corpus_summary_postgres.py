"""The corpus summary's queries against the real schema (A′).

Requirements and duplicates are counted from `requirements`; findings in force are joined
to their screens and both Requirements' versions; a failed source is a progress row that
stopped retrying on the source change still pending.
"""

import os
import uuid
from collections.abc import Iterator
from urllib.parse import quote

import psycopg
import pytest

from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.internal_reads import OpenFindingAges
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.container import build_container
from tests.unit.workflow_helpers import drain_requirement_index

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NEED = "Business customers order XGPON bundles via BCRM."


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute("select current_database()").fetchone()
        assert row and "test" in row[0]
    schema = f"corpus_summary_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_counts_findings_in_force_and_failed_sources(isolated_url: str) -> None:
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
        assert container.internal_reads.corpus_summary().requirements == 0
        canonical = container.create_requirement.execute(
            CreateRequirementInput("XGPON bundles", NEED), owner
        )
        candidate = container.create_requirement.execute(
            CreateRequirementInput("XGPON bundles", NEED), owner
        )
        fingerprint = container.get_knowledge_review.execute(candidate.id).current_fingerprint
        drain_requirement_index(container)
        container.screen_requirement_knowledge.execute(owner, candidate.id, fingerprint)

        summary = container.internal_reads.corpus_summary()
        assert (summary.requirements, summary.duplicates, summary.current) == (2, 0, 2)
        assert (summary.waiting, summary.failed) == (0, 0)
        assert summary.open_findings == OpenFindingAges(1, 0, 0)

        # A changed source whose progress stopped retrying on that change is failed.
        stored = container.requirement_repository.get(canonical.id)
        assert stored is not None
        container.requirement_repository.save(
            stored.update(stored.title, stored.description, updated_at=container.clock.now())
        )
        with psycopg.connect(isolated_url) as connection:
            row = connection.execute(
                "SELECT change_number FROM knowledge_source_changes WHERE requirement_id=%s",
                (canonical.id.value,),
            ).fetchone()
            assert row is not None
            connection.execute(
                "INSERT INTO requirement_index_progress(identity,source_id,payload) "
                "VALUES (%s,%s,%s::jsonb) ON CONFLICT (identity,source_id) "
                "DO UPDATE SET payload=EXCLUDED.payload,token=NULL,lease_until=NULL",
                (
                    container.requirement_indexer.identity,
                    canonical.id.value,
                    f'{{"source_change": {row[0]}, "failures": 3}}',
                ),
            )

        summary = container.internal_reads.corpus_summary()
        assert (summary.requirements, summary.current, summary.waiting, summary.failed) == (
            2,
            1,
            0,
            1,
        )
        # The canonical Requirement moved on, so the finding is no longer in force.
        assert summary.open_findings == OpenFindingAges(0, 0, 0)
    finally:
        container.close_resources()
