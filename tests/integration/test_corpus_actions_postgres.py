"""Corpus actions against the real schema (Knowledge Center B3).

Retiring writes the membership row, whose trigger marks the Requirement for indexing again,
closes the findings that cite it in their payloads, and records the action; the reads count and
filter it. Reinstating flips the row back; bulk reindex bumps only the chosen sources.
"""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import quote

import psycopg
import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from tests.unit.workflow_helpers import drain_requirement_index

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NEED = "Business customers order XGPON bundles via BCRM."
START = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
AMINA, RAVI, OMAR = FAKE_ACTORS


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute("select current_database()").fetchone()
        assert row and "test" in row[0]
    schema = f"corpus_actions_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def _change(url: str, requirement_id: str) -> tuple[int, bool]:
    with psycopg.connect(url) as connection:
        row = connection.execute(
            "SELECT change_number, dirty FROM knowledge_source_changes WHERE requirement_id=%s",
            (requirement_id,),
        ).fetchone()
    assert row is not None
    return int(row[0]), bool(row[1])


def test_retire_reinstate_and_reindex(isolated_url: str) -> None:
    run_migrations(isolated_url)
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=isolated_url,
        ),
        clock=FixedClock(START),
    )
    try:
        canonical = container.create_requirement.execute(
            CreateRequirementInput("XGPON bundles", NEED), RAVI
        )
        candidate = container.create_requirement.execute(
            CreateRequirementInput("XGPON bundles for offices", NEED), AMINA
        )
        fingerprint = container.get_knowledge_review.execute(candidate.id).current_fingerprint
        drain_requirement_index(container)
        container.screen_requirement_knowledge.execute(AMINA, candidate.id, fingerprint)
        (finding,) = container.get_knowledge_review.execute(candidate.id).findings
        drain_requirement_index(container)
        settled, _ = _change(isolated_url, canonical.id.value)

        result = container.retire_from_corpus.execute(
            canonical.id.value, OMAR.id.value, OMAR.display_name, "Cancelled launch."
        )

        assert (result.closed_findings, result.notified) == (1, RAVI.display_name)
        changed, dirty = _change(isolated_url, canonical.id.value)
        assert changed > settled and dirty
        with psycopg.connect(isolated_url) as connection:
            membership = connection.execute(
                "SELECT state, reason, actor_id, actor_name FROM requirement_corpus_membership"
            ).fetchall()
            status = connection.execute(
                "SELECT payload->>'status' FROM requirement_knowledge_findings WHERE finding_id=%s",
                (finding.id.value,),
            ).fetchone()
            actions = connection.execute(
                "SELECT kind, requirement_ids, actor_name, reason FROM knowledge_corpus_actions"
            ).fetchall()
        assert membership == [("retired", "Cancelled launch.", OMAR.id.value, OMAR.display_name)]
        assert status == ("source_retired",)
        assert actions == [("retire", [canonical.id.value], OMAR.display_name, "Cancelled launch.")]
        drain_requirement_index(container)
        assert container.internal_reads.corpus_summary().retired == 1
        page = container.knowledge_portfolio.corpus(
            index_state=None,
            owner_id=None,
            text="",
            open_findings_only=False,
            not_screened_for_days=None,
            offset=0,
            limit=50,
            retired_only=True,
        )
        (row,) = page.items
        assert row.retired is not None
        assert (row.requirement_id, row.retired.by, row.retired.at) == (
            canonical.id.value,
            OMAR.display_name,
            START,
        )

        container.reinstate_to_corpus.execute(
            canonical.id.value, OMAR.id.value, OMAR.display_name, "Back on."
        )

        assert container.internal_reads.corpus_summary().retired == 0
        assert _change(isolated_url, canonical.id.value)[1] is True
        drain_requirement_index(container)
        before, _ = _change(isolated_url, candidate.id.value)
        reindexed = container.bulk_reindex.reindex(
            (candidate.id.value, "missing"), OMAR.id.value, OMAR.display_name, None
        )
        assert reindexed.requirements == 1
        assert _change(isolated_url, candidate.id.value) == (before + 1, True)
        assert container.bulk_reindex.retry_failed(OMAR.id.value, OMAR.display_name, None)
    finally:
        container.close_resources()
