"""Persistent dependency projection, restart, rollback and concurrent owner review."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import psycopg
import pytest

from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.document_library import CHUNKING_POLICY
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.domain.analysis.value_objects import IntentProposalStatus
from smb_requirement_agent.domain.document.library import ReviewedPassage
from smb_requirement_agent.domain.document.lineage import ImpactDecisionKind
from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.documents.library_worker import ClamAvDocumentScanner
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.composition.operations import build_projection_rebuild
from smb_requirement_agent.interfaces.api.container import build_container


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured"
)
def test_postgres_lineage_restart_rebuild_concurrency_and_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(url) as connection:
        row = connection.execute("select current_database()").fetchone()
        assert row and "test" in row[0]
    run_migrations(url)
    with psycopg.connect(url) as connection:
        connection.execute(
            "TRUNCATE library_chunks, library_embedding_cache, "
            "library_submissions, library_documents CASCADE"
        )
    settings = Settings(
        llm_provider=LLMProvider.FAKE,
        persistence_provider=PersistenceProvider.POSTGRES,
        database_url=url,
    )
    monkeypatch.setattr(ClamAvDocumentScanner, "scan", lambda _self, _content: True)
    container = build_container(settings)
    owner = FAKE_ACTORS[0]
    try:
        import uuid

        library = container.document_library
        uploaded = library.submit(
            "Lineage policy",
            UploadDocumentInput(
                "policy.txt", "text/plain", b"XGPON coverage is required for high-speed orders."
            ),
            str(uuid.uuid4()),
            owner,
        )
        assert library.process_next()
        doc = library.get(uploaded.id, owner)
        source = doc.versions[0]
        reviewed = library.review(
            doc.id,
            source.id,
            doc.version,
            owner,
            tuple(ReviewedPassage(b.id, b.text or "", True, "") for b in source.blocks),
            "Reviewed synthetic fixture",
        )
        revision = reviewed.versions[0].revisions[-1]
        library.approve(
            doc.id,
            source.id,
            revision.id,
            revision.fingerprint(source.id, CHUNKING_POLICY),
            reviewed.version,
            owner,
        )
        assert container.reference_knowledge.index_next()
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
        current = library.get(doc.id, owner)
        library.withdraw(doc.id, current.version, owner, "Superseded")
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
            other = build_container(settings)
            try:
                other.source_impact.decide(
                    selected.dependency.id,
                    owner,
                    selected.publication_state,
                    0,
                    ImpactDecisionKind.RETAIN,
                    "Retain for this rollout",
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
        restarted = build_container(settings)
        try:
            after = restarted.source_impact.page(
                owner, requirement_id=requirement.id.value, active_only=True
            ).items
            retained = next(row for row in after if row.dependency.id == selected.dependency.id)
            assert not retained.needs_review and len(retained.decisions) == 1
            assert retained.dependency.lineage == selected.dependency.lineage
            latest = restarted.document_library.get(doc.id, owner)
            restarted.library_governance.transfer(
                doc.id, owner, FAKE_ACTORS[1].id, latest.version, "Test handover"
            )
            assert restarted.source_impact.page(FAKE_ACTORS[1], document_id=doc.id).items == ()
        finally:
            restarted.close_resources()
    finally:
        container.close_resources()
