"""Prior art in PostgreSQL (Knowledge Center E2, ADR-0102).

The check is kept apart from findings, filtered by what is still published, counted per
historic requirement for the knowledge portal, and gone with its Requirement. Prior-art
jobs are claimed after everything else, and the hourly budget is shared by every worker.
"""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import quote

import psycopg
import pytest

from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.jobs.domain.entities import AiJobOperation
from smb_requirement_agent.knowledge.domain.prior_art import PriorArtStatus
from tests.knowledge_doubles import PublishedLibrary, container_with_library
from tests.unit.knowledge.test_prior_art import _create, _drain, _publish_xgpon

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


@pytest.fixture
def isolated_url() -> Iterator[str]:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute("select current_database()").fetchone()
        assert row and "test" in row[0]
    schema = f"prior_art_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def served(isolated_url: str) -> Iterator[tuple[Container, PublishedLibrary, str]]:
    run_migrations(isolated_url)
    container, library = container_with_library(
        Settings(
            llm_provider=LLMProvider.FAKE,
            persistence_provider=PersistenceProvider.POSTGRES,
            database_url=isolated_url,
            prior_art_enabled=True,
        )
    )
    yield container, library, isolated_url
    container.close_resources()


def test_prior_art_round_trips_and_stays_apart_from_findings(
    served: tuple[Container, PublishedLibrary, str],
) -> None:
    container, library, url = served
    historic_id = _publish_xgpon(container, library)
    requirement = _create(
        container,
        "XGPON fibre bundles for small offices",
        "Sales agents order XGPON fibre bundles for small offices through BCRM.",
    )
    ran = _drain(container)
    assert ran[-1] is AiJobOperation.SCREEN_PRIOR_ART
    view = container.get_prior_art.execute(requirement.id)
    assert view.status is PriorArtStatus.CURRENT and view.check is not None
    (match,) = view.check.matches
    assert match.historic_requirement_id == historic_id and match.evidence[0].excerpt
    assert container.prior_art_store.citation_counts((historic_id, "other")) == {
        historic_id: 1,
        "other": 0,
    }
    assert container.prior_art_store.citing(historic_id, 0, 10) == (requirement.id,)
    # Nothing was written where findings are counted.
    with psycopg.connect(url) as connection:
        findings = connection.execute(
            "SELECT count(*) FROM requirement_knowledge_findings"
        ).fetchone()
    assert findings == (0,)
    # The budget is shared by every worker through the database.
    now = datetime.now(UTC)
    assert container.prior_art_store.remaining(now, 60) == 59
    container.prior_art_store.spend(now)
    assert container.prior_art_store.remaining(now, 60) == 58
    # A withdrawal hides the match; the Requirement's removal takes its check with it.
    library.withdraw_historic(historic_id)
    container.historic_projection.drain()
    # It was the only one, so there is no historic knowledge left to show.
    view = container.get_prior_art.execute(requirement.id)
    assert view.status is PriorArtStatus.NO_HISTORIC_KNOWLEDGE and view.check is None
    with psycopg.connect(url) as connection:
        connection.execute("DELETE FROM requirement_prior_art_matches")
        connection.execute(
            "DELETE FROM requirement_prior_art WHERE requirement_id = %s",
            (requirement.id.value,),
        )
    assert container.prior_art_store.get(requirement.id) is None
