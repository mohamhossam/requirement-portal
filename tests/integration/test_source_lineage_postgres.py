"""Persistent dependency projection, restart, rollback and concurrent owner review."""

import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from urllib.parse import quote

import psycopg
import pytest

from smb_requirement_agent.analysis.domain.value_objects import IntentProposalStatus
from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.domain.document.lineage import ImpactDecisionKind
from smb_requirement_agent.identity.domain.errors import AuthorizationDeniedError
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.composition.operations import build_projection_rebuild
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from tests.knowledge_doubles import PublishedLibrary, service_for, sync

DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture
def isolated_url() -> Iterator[str]:
    """A schema of its own: the local copy's event cursor starts at zero for this library."""
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute("select current_database()").fetchone()
        assert row and "test" in row[0]
    schema = f"source_lineage_{uuid.uuid4().hex}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
    separator = "&" if "?" in DATABASE_URL else "?"
    yield f"{DATABASE_URL}{separator}options={quote(f'-csearch_path={schema},public')}"
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_postgres_lineage_restart_rebuild_concurrency_and_rollback(isolated_url: str) -> None:
    url = isolated_url
    run_migrations(url)
    settings = Settings(
        llm_provider=LLMProvider.FAKE,
        persistence_provider=PersistenceProvider.POSTGRES,
        database_url=url,
    )
    owner = FAKE_ACTORS[0]
    # The policy belongs to someone else, who must never see the owner's private work.
    library = PublishedLibrary(owner_id=FAKE_ACTORS[1].id.value)
    (citation,) = library.publish(
        "Lineage policy", ("XGPON coverage is required for high-speed orders.",)
    )
    container = build_container(settings, knowledge_service=service_for(library))
    try:
        sync(container)
        requirement = container.create_requirement.execute(
            CreateRequirementInput("XGPON orders", "Order high-speed bundles through BCRM."), owner
        )
        analysis = container.analyze_requirement.execute(owner, requirement.id)
        proposal = next(p for p in analysis.intent_proposals if p.reference_evidence)
        container.analysis_collaboration.decide_intent_proposal(
            requirement.id,
            proposal.id,
            IntentProposalStatus.ACCEPTED,
            proposal.version,
            owner,
            rationale="Applies to rollout",
        )
        # Counted across the portfolio: the document's owner does not own the Requirement.
        assert container.internal_reads.citation_counts((citation.document_id, "unknown")) == {
            citation.document_id: 1,
            "unknown": 0,
        }
        library.withdraw(citation.document_id)
        sync(container)
        rows = container.source_impact.page(
            owner, requirement_id=requirement.id.value, active_only=True
        ).items
        assert rows and all(row.needs_review for row in rows)
        selected = rows[0]
        before = container.breakdown_repository.list_breakdown_revisions(requirement.id)
        # The index rolls back with a source mutation, including direct adapter writes.
        with pytest.raises(RuntimeError), container.transaction_manager.transaction():
            current_analysis = container.analysis_repository.get_by_requirement_id(requirement.id)
            assert current_analysis
            container.analysis_repository.save(
                replace(current_analysis, intent_proposals=(), version=current_analysis.version + 1)
            )
            raise RuntimeError("abort")
        assert (
            container.source_impact.page(
                owner, requirement_id=requirement.id.value, active_only=True
            ).items
            == rows
        )

        def decide() -> str:
            other = build_container(settings, knowledge_service=service_for(library))
            try:
                other.source_impact.decide(
                    selected.dependency.id,
                    owner,
                    selected.publication_state,
                    0,
                    ImpactDecisionKind.RETAIN,
                    "Retain for this rollout",
                    requirement_id=selected.dependency.requirement_id,
                )
                return "saved"
            except ArtifactVersionConflictError:
                return "conflict"
            finally:
                other.close_resources()

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(lambda _: decide(), range(2))) == ["conflict", "saved"]
        assert container.breakdown_repository.list_breakdown_revisions(requirement.id) == before
        build_projection_rebuild(url)()
        restarted = build_container(settings, knowledge_service=service_for(library))
        try:
            after = restarted.source_impact.page(
                owner, requirement_id=requirement.id.value, active_only=True
            ).items
            retained = next(row for row in after if row.dependency.id == selected.dependency.id)
            assert not retained.needs_review and len(retained.decisions) == 1
            assert retained.dependency.lineage == selected.dependency.lineage
            # The persisted copy still knows the document's owner after a restart: only
            # they may inspect it, and they see nothing of Requirements they cannot read.
            with pytest.raises(AuthorizationDeniedError):
                restarted.source_impact.page(owner, document_id=citation.document_id)
            assert (
                restarted.source_impact.page(FAKE_ACTORS[1], document_id=citation.document_id).items
                == ()
            )
        finally:
            restarted.close_resources()
    finally:
        container.close_resources()
