"""Commit-time refresh of PostgreSQL read projections."""

from __future__ import annotations

import httpx as httpx

from smb_requirement_agent.analysis.infrastructure.postgres_analysis import (
    PostgresAnalysisAuditRepository,
    PostgresAnalysisRepository,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    GetKnowledgeReview,
    RequirementKnowledgeCorpus,
)
from smb_requirement_agent.governance.infrastructure.postgres_revisions import (
    PostgresRevisionRepository,
)
from smb_requirement_agent.identity.infrastructure.postgres_identity import PostgresAccessRepository
from smb_requirement_agent.infrastructure.persistence.corpus_membership import (
    PostgresCorpusMembership,
)
from smb_requirement_agent.infrastructure.persistence.postgres_requirement_knowledge import (
    PostgresRequirementKnowledgeStore,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import (
    PostgresCommitSession,
)
from smb_requirement_agent.infrastructure.persistence.postgres_values import DbConnection
from smb_requirement_agent.infrastructure.persistence.source_dependencies import (
    PostgresSourceDependencies,
)
from smb_requirement_agent.jobs.infrastructure.postgres_ai_jobs import PostgresAiJobStore
from smb_requirement_agent.reporting.application.use_cases.dependency_projection import (
    DependencyProjection,
)
from smb_requirement_agent.reporting.infrastructure.postgres_activity import (
    PostgresProjectedActivity,
)
from smb_requirement_agent.reporting.infrastructure.postgres_activity_reader import (
    PostgresActivityReadAdapter,
)
from smb_requirement_agent.reporting.infrastructure.postgres_activity_sources import (
    PostgresActivitySources,
)
from smb_requirement_agent.reporting.infrastructure.postgres_snapshots import (
    PostgresSnapshotReader,
)
from smb_requirement_agent.reporting.infrastructure.postgres_worklist import (
    PostgresWorklistProjectionMaintainer,
)
from smb_requirement_agent.requirements.infrastructure.postgres_document_repository import (
    PostgresDocumentRepository,
)
from smb_requirement_agent.requirements.infrastructure.postgres_requirements import (
    PostgresRequirementRepository,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def refresh_postgres_projections(
    connection: DbConnection, requirement_ids: tuple[RequirementId, ...]
) -> None:
    """Compose a projection graph over the commit connection, with no deferred wiring."""

    session = PostgresCommitSession(connection)
    snapshots = PostgresSnapshotReader(session)
    revisions = PostgresRevisionRepository(session)
    audit = PostgresAnalysisAuditRepository(session)
    knowledge = PostgresRequirementKnowledgeStore(session)
    corpus = RequirementKnowledgeCorpus(
        PostgresRequirementRepository(session),
        PostgresAnalysisRepository(session),
        audit,
        PostgresAccessRepository(session),
        knowledge,
        PostgresDocumentRepository(session),
        membership=PostgresCorpusMembership(session),
    )
    sources = PostgresActivitySources(session, snapshots, revisions)
    activity = PostgresProjectedActivity(
        session,
        PostgresActivityReadAdapter(sources, PostgresAiJobStore(session), knowledge, audit),
    )
    projection = PostgresWorklistProjectionMaintainer(
        session,
        snapshots,
        GetKnowledgeReview(corpus, knowledge),
        activity,
        activity,
    )
    dependencies = DependencyProjection(snapshots, PostgresSourceDependencies(session))
    for requirement_id in requirement_ids:
        projection.refresh(requirement_id)
        dependencies.refresh(requirement_id)
