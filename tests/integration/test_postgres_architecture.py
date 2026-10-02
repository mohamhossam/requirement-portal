"""Real pgvector release indexing and durable worker state."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.persistence.connector import (
    DirectPostgresConnector,
)

from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.application.ports.architecture_rag import EvidenceChunk
from smb_requirement_agent.application.ports.identity import Actor
from smb_requirement_agent.application.use_cases.architecture_index import BuildArchitectureIndex
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeConflictError,
    KnowledgeDocumentVersion,
    KnowledgeReleaseStatus,
)
from smb_requirement_agent.domain.architecture.samples import SampleRequirement
from smb_requirement_agent.infrastructure.architecture.catalogue_files import (
    CatalogueFileAdapter,
)
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.located_extractor import (
    LocatedDocumentExtractor,
)
from smb_requirement_agent.infrastructure.architecture.postgres_evidence_index import (
    PostgresEvidenceIndex,
)
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.persistence.architecture_mapping_stats import (
    PostgresArchitectureMappingStats,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentStorage,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_architecture_jobs import (
    PostgresArchitectureJobs,
)
from smb_requirement_agent.infrastructure.persistence.postgres_architecture_knowledge import (
    PostgresArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_sample_requirements import (
    PostgresSampleRequirements,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


def _fresh_draft(knowledge: ManageArchitectureKnowledge, actor: Actor) -> ArchitectureKnowledge:
    """Only one draft may exist; the shared test database may keep one from a failed run."""
    for release in knowledge.list_releases(actor):
        if release.status is KnowledgeReleaseStatus.DRAFT:
            knowledge.discard_draft(release.id, release.revision, actor)
    return knowledge.create_draft(actor, "Next version")


def test_pgvector_index_release_and_job_survive_repository_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    repository = PostgresArchitectureKnowledgeRepository(
        DirectPostgresConnector(DATABASE_URL), seed_knowledge()
    )
    index = PostgresEvidenceIndex(
        DirectPostgresConnector(DATABASE_URL), FakeEmbeddings(), FakeWordTokenizer()
    )
    knowledge = ManageArchitectureKnowledge(repository, CatalogueFileAdapter(), index, 10_000_000)
    actor = Actor("knowledge-editor", frozenset({"knowledge_maintainer"}))
    draft = _fresh_draft(knowledge, actor)
    built = BuildArchitectureIndex(
        knowledge,
        index,
        InMemoryDocumentStorage(),
        LocatedDocumentExtractor(SafeDocumentTextExtractor()),
        FakeWordTokenizer(),
    ).execute(draft.id, draft.revision, actor.id, fence=lambda: None)
    assert built.index_profile and built.index_hash and built.index_id
    indexed = index.retrieve(built.index_id, "BCRM assisted sales", 8)
    assert indexed and any(chunk.location == "system bcrm" for chunk in indexed)
    assert all(index.get(built.index_id, item.id) == item for item in indexed)
    own = index.system_chunk(built.index_id, "oracle-atg-bcc")
    assert own is not None and own.location == "system oracle-atg-bcc"
    assert "Used by: B2B BFF" in own.text
    assert index.system_chunk(built.index_id, "missing") is None
    published = knowledge.publish(
        draft.id, draft.revision, actor, datetime.now(UTC), "Reviewed architecture"
    )
    assert repository.active().id == published.id
    with pytest.raises(KnowledgeConflictError):
        repository.save(built, built.revision, actor.id, "stale_build")
    index.store(draft.id, uuid4().hex, (EvidenceChunk("late", "Old build", "line 1", "Old text"),))
    assert all(index.get(built.index_id, item.id) == item for item in indexed)

    job_id = uuid4().hex
    jobs = PostgresArchitectureJobs(DirectPostgresConnector(DATABASE_URL))
    jobs.enqueue(
        ArchitectureJob(
            job_id,
            ArchitectureJobKind.INDEX,
            draft.id,
            str(draft.revision),
            actor.id,
            ArchitectureJobStatus.QUEUED,
        )
    )
    claimed = jobs.claim(datetime.now(UTC))
    assert claimed is not None and claimed.id == job_id
    assert PostgresArchitectureJobs(DirectPostgresConnector(DATABASE_URL)).get(job_id) == claimed
    assert jobs.heartbeat(job_id, claimed.attempts, datetime.now(UTC))
    jobs.finish(job_id, claimed.attempts, ArchitectureJobStatus.SUCCEEDED, None)
    completed = PostgresArchitectureJobs(DirectPostgresConnector(DATABASE_URL)).get(job_id)
    assert completed is not None and completed.status is ArchitectureJobStatus.SUCCEEDED

    restarted = PostgresArchitectureKnowledgeRepository(
        DirectPostgresConnector(DATABASE_URL), seed_knowledge()
    )
    assert restarted.active().id == published.id
    knowledge.activate("smb-source-reference-v1", actor, "Restore seed after integration test")


def test_deselected_document_registry_survives_restart() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    repository = PostgresArchitectureKnowledgeRepository(
        DirectPostgresConnector(DATABASE_URL), seed_knowledge()
    )
    index = PostgresEvidenceIndex(
        DirectPostgresConnector(DATABASE_URL), FakeEmbeddings(), FakeWordTokenizer()
    )
    knowledge = ManageArchitectureKnowledge(repository, CatalogueFileAdapter(), index, 10_000_000)
    actor = Actor("maintainer", frozenset({"knowledge_maintainer"}))
    draft = _fresh_draft(knowledge, actor)
    version_id = uuid4().hex
    document = KnowledgeDocumentVersion(
        version_id,
        "Retained source",
        "source.txt",
        "text/plain",
        "en",
        "checksum",
        version_id,
        actor.id,
        datetime.now(UTC),
    )
    uploaded = draft.updated(documents=(document,))
    repository.save(uploaded, draft.revision, actor.id, "upload_document")
    selected = knowledge.select_documents(uploaded.id, uploaded.revision, actor, ())
    restarted = PostgresArchitectureKnowledgeRepository(
        DirectPostgresConnector(DATABASE_URL), seed_knowledge()
    )
    assert document in restarted.document_versions(True)
    assert document not in restarted.document_versions(False)

    knowledge.discard_draft(selected.id, selected.revision, actor)
    assert restarted.get(selected.id) is None
    assert [item.action for item in restarted.audit(selected.id)][-1] == "discard_draft"
    with pytest.raises(KnowledgeConflictError):
        restarted.delete_draft(repository.active().id, 1, actor.id)


def test_mapping_counts_query_runs_against_the_schema() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    counts = PostgresArchitectureMappingStats(DirectPostgresConnector(DATABASE_URL)).by_release()
    assert all(item.requirements <= item.features + item.stories for item in counts)


def test_sample_list_survives_restart_and_refuses_a_stale_save() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    repository = PostgresSampleRequirements(DirectPostgresConnector(DATABASE_URL))
    current = repository.load()
    updated = current.replaced(
        (SampleRequirement(uuid4().hex, "Bill partner orders"),), "maintainer", datetime.now(UTC)
    )
    repository.save(updated, current.revision)

    assert PostgresSampleRequirements(DirectPostgresConnector(DATABASE_URL)).load() == updated
    with pytest.raises(KnowledgeConflictError):
        repository.save(updated, current.revision)


def test_a_rebuild_reuses_cached_embeddings_across_instances() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)

    class Counting(FakeEmbeddings):
        calls: list[str] = []

        def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
            Counting.calls.extend(texts)
            return super().embed(texts)

    repository = PostgresArchitectureKnowledgeRepository(
        DirectPostgresConnector(DATABASE_URL), seed_knowledge()
    )
    marker = uuid4().hex
    chunks = (EvidenceChunk("c1", "Doc", "line 1", f"cached passage {marker}"),)
    for _ in range(2):
        PostgresEvidenceIndex(
            DirectPostgresConnector(DATABASE_URL), Counting(), FakeWordTokenizer()
        ).store(repository.active().id, uuid4().hex, chunks)

    assert Counting.calls == [f"cached passage {marker}"]
