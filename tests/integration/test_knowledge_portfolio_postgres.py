"""The corpus browser's queries and the nudge record against the real schema (B2).

Corpus rows join `requirements` to their access snapshots for the owner's display name and
count only findings in force; finding rows join both Requirements and the latest nudge. A
nudge's notifications carry no AI job, which the schema now allows.
"""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import psycopg
import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.ports.knowledge_portfolio import (
    FindingAge,
    IndexState,
    PersonName,
)
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.domain.jobs.entities import NotificationKind
from smb_requirement_agent.domain.knowledge.errors import KnowledgeFindingConflictError
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.container import build_container
from tests.unit.workflow_helpers import drain_requirement_index

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NEED = "Business customers order XGPON bundles via BCRM."
START = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
AMINA, RAVI, OMAR = FAKE_ACTORS


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute("select current_database()").fetchone()
        assert row and "test" in row[0]
    schema = f"knowledge_portfolio_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_corpus_findings_and_nudges(isolated_url: str) -> None:
    run_migrations(isolated_url)
    clock = FixedClock(START)
    container = build_container(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=isolated_url,
        ),
        clock=clock,
    )

    def corpus(**filters: object) -> list[str]:
        arguments: dict[str, object] = {
            "index_state": None,
            "owner_id": None,
            "text": "",
            "open_findings_only": False,
            "not_screened_for_days": None,
            "offset": 0,
            "limit": 50,
        }
        arguments.update(filters)
        page = container.knowledge_portfolio.corpus(**arguments)  # type: ignore[arg-type]
        return [item.title for item in page.items]

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
        container.create_requirement.execute(CreateRequirementInput("Archive_1", "Old."), RAVI)

        page = container.knowledge_portfolio.corpus(
            index_state=None,
            owner_id=None,
            text="",
            open_findings_only=False,
            not_screened_for_days=None,
            offset=0,
            limit=50,
        )
        assert [item.title for item in page.items] == [
            "Archive_1",
            "XGPON bundles",
            "XGPON bundles for offices",
        ]
        archive, first, second = page.items
        assert archive.index_state is IndexState.WAITING
        assert first.owner == PersonName(RAVI.id.value, RAVI.display_name)
        assert (first.open_findings, second.open_findings) == (1, 1)
        assert (first.last_screened_at, second.last_screened_at) == (None, START)
        assert corpus(owner_id=RAVI.id.value) == ["Archive_1", "XGPON bundles"]
        # LIKE wildcards are matched literally.
        assert corpus(text="e_1") == ["Archive_1"]
        assert corpus(text="%") == []
        assert corpus(open_findings_only=True) == ["XGPON bundles", "XGPON bundles for offices"]
        assert corpus(index_state=IndexState.WAITING) == ["Archive_1"]
        assert corpus(index_state=IndexState.CURRENT) == [
            "XGPON bundles",
            "XGPON bundles for offices",
        ]
        assert corpus(limit=1, offset=1) == ["XGPON bundles"]

        (row,) = container.knowledge_portfolio.findings(
            kind=None, age=None, owner_id=RAVI.id.value, offset=0, limit=50
        ).items
        assert (row.subject.requirement_id, row.related.requirement_id) == (
            candidate.id.value,
            canonical.id.value,
        )
        assert row.subject.owner == PersonName(AMINA.id.value, AMINA.display_name)
        assert row.rationale and row.last_nudge is None

        result = container.nudge_finding_owners.execute(
            row.finding_id, OMAR.id.value, OMAR.display_name
        )
        assert set(result.recipients) == {AMINA.display_name, RAVI.display_name}
        (notification,) = [
            item
            for item in container.notification_repository.list_for_actor(RAVI.id)
            if item.kind is NotificationKind.KNOWLEDGE_FINDINGS_NUDGE
        ]
        assert notification.job_id is None
        assert notification.resource_path == f"/requirements/{canonical.id.value}/knowledge"
        with psycopg.connect(isolated_url) as connection:
            record = connection.execute(
                "SELECT actor_id, actor_name, nudged_at, recipients FROM knowledge_finding_nudges"
            ).fetchall()
        assert len(record) == 1
        assert record[0][:3] == (OMAR.id.value, OMAR.display_name, START)
        assert set(record[0][3]) == {AMINA.id.value, RAVI.id.value}

        clock.set(START + timedelta(days=3))
        with pytest.raises(KnowledgeFindingConflictError, match="again from 13 Oct 2026"):
            container.nudge_finding_owners.execute(row.finding_id, OMAR.id.value, OMAR.display_name)

        clock.set(START + timedelta(days=31))
        (aged,) = container.knowledge_portfolio.findings(
            kind=None, age=FindingAge.OVER_30_DAYS, owner_id=None, offset=0, limit=50
        ).items
        assert aged.last_nudge is not None
        assert (aged.last_nudge.at, aged.last_nudge.by) == (START, OMAR.display_name)
        assert aged.next_nudge_at is None
        assert not container.knowledge_portfolio.findings(
            kind=None, age=FindingAge.UNDER_7_DAYS, owner_id=None, offset=0, limit=50
        ).items
        assert corpus(not_screened_for_days=40) == ["Archive_1", "XGPON bundles"]
    finally:
        container.close_resources()
