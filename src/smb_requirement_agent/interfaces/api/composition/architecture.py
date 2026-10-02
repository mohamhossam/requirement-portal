"""Architecture knowledge: retrieval, reasoning, curation and the impact-mapping jobs."""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.documents.text_extractor import SafeDocumentTextExtractor
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ActiveArchitectureReleasePort,
    ArchitectureKnowledgePort,
)
from smb_requirement_agent.application.ports.architecture_rag import (
    ArchitectureReasonerPort,
    EmbeddingPort,
)
from smb_requirement_agent.application.ports.architecture_tokenizer import (
    ArchitectureTokenizerPort,
)
from smb_requirement_agent.application.ports.catalogue_extractor import CatalogueExtractorPort
from smb_requirement_agent.application.ports.requirement_knowledge import KnowledgeEmbeddingPort
from smb_requirement_agent.application.ports.system_matcher import SystemMatcherPort
from smb_requirement_agent.application.use_cases.architecture_documents import (
    ReadKnowledgeDocument,
    UploadKnowledgeDocument,
)
from smb_requirement_agent.application.use_cases.architecture_index import BuildArchitectureIndex
from smb_requirement_agent.application.use_cases.architecture_jobs import (
    ArchitectureJobExecution,
    ArchitectureJobs,
)
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
)
from smb_requirement_agent.application.use_cases.architecture_mapping_jobs import (
    ArchitectureMappingJobs,
)
from smb_requirement_agent.application.use_cases.architecture_preview import (
    PreviewArchitectureImpact,
)
from smb_requirement_agent.application.use_cases.catalogue_candidates import (
    DecideCatalogueCandidate,
    ProposeCatalogueChanges,
)
from smb_requirement_agent.application.use_cases.resolve_architecture_knowledge import (
    ResolveArchitectureKnowledge,
)
from smb_requirement_agent.infrastructure.architecture.catalogue_files import (
    CatalogueFileAdapter,
)
from smb_requirement_agent.infrastructure.architecture.catalogue_tables import (
    CatalogueTableReader,
    TableFirstCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.architecture.embeddings import ArchitectureEmbeddings
from smb_requirement_agent.infrastructure.architecture.located_extractor import (
    LocatedDocumentExtractor,
)
from smb_requirement_agent.infrastructure.architecture.tokenizer import ApproximateTokenizer
from smb_requirement_agent.infrastructure.architecture.yaml_knowledge import (
    YamlArchitectureKnowledge,
    default_knowledge_path,
)
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.jobs.architecture_job_worker import ArchitectureJobWorker
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters


@dataclass(frozen=True)
class ArchitectureRetrieval:
    """Chunking and embedding for architecture evidence; persistence indexes with it."""

    tokenizer: ArchitectureTokenizerPort
    embeddings: EmbeddingPort


@dataclass(frozen=True)
class ArchitectureKnowledgeWiring:
    reasoner: ArchitectureReasonerPort
    knowledge: ArchitectureKnowledgePort
    manage: ManageArchitectureKnowledge
    build_index: BuildArchitectureIndex
    preview_impact: PreviewArchitectureImpact
    upload_document: UploadKnowledgeDocument
    read_document: ReadKnowledgeDocument
    propose_changes: ProposeCatalogueChanges
    decide_candidates: DecideCatalogueCandidate
    job_execution: ArchitectureJobExecution


@dataclass(frozen=True)
class ArchitectureJobWiring:
    jobs: ArchitectureJobs
    mapping_jobs: ArchitectureMappingJobs
    # Present only when jobs are queued; inline jobs finish inside the request.
    worker: ArchitectureJobWorker | None
    mapping_worker: ArchitectureJobWorker | None


def build_architecture_retrieval(embeddings: KnowledgeEmbeddingPort) -> ArchitectureRetrieval:
    """Architecture evidence uses the application's configured embedding model."""
    return ArchitectureRetrieval(
        tokenizer=ApproximateTokenizer(), embeddings=ArchitectureEmbeddings(embeddings)
    )


def build_architecture_knowledge(
    settings: Settings,
    persistence: PersistenceAdapters,
    retrieval: ArchitectureRetrieval,
    reasoner: ArchitectureReasonerPort,
    override: ArchitectureKnowledgePort | None,
    catalogue_extractor: CatalogueExtractorPort,
    system_matcher: SystemMatcherPort,
    clock: ClockPort,
) -> ArchitectureKnowledgeWiring:
    manage = ManageArchitectureKnowledge(
        persistence.architecture_repository,
        CatalogueFileAdapter(),
        persistence.architecture_evidence_index,
        settings.document_max_file_bytes,
    )
    document_extractor = SafeDocumentTextExtractor()
    located_extractor = LocatedDocumentExtractor(document_extractor)
    return ArchitectureKnowledgeWiring(
        reasoner=reasoner,
        knowledge=override
        if override is not None
        else ResolveArchitectureKnowledge(
            persistence.architecture_repository,
            persistence.architecture_evidence_index,
            reasoner,
            YamlArchitectureKnowledge(default_knowledge_path()),
            persistence.organisation_repository,
        ),
        manage=manage,
        build_index=BuildArchitectureIndex(
            manage,
            persistence.architecture_evidence_index,
            persistence.knowledge_document_storage,
            located_extractor,
            retrieval.tokenizer,
        ),
        preview_impact=PreviewArchitectureImpact(
            manage, persistence.architecture_evidence_index, reasoner
        ),
        upload_document=UploadKnowledgeDocument(
            manage,
            persistence.architecture_repository,
            persistence.knowledge_document_storage,
            document_extractor,
            settings.document_max_file_bytes,
        ),
        read_document=ReadKnowledgeDocument(
            manage, persistence.knowledge_document_storage, located_extractor
        ),
        propose_changes=ProposeCatalogueChanges(
            manage,
            persistence.knowledge_document_storage,
            located_extractor,
            document_extractor,
            # Every provider reads catalogue tables exactly before its model (ADR-0093).
            TableFirstCatalogueExtractor(catalogue_extractor, CatalogueTableReader()),
            system_matcher,
            persistence.catalogue_candidates,
            clock,
        ),
        decide_candidates=DecideCatalogueCandidate(
            manage, persistence.architecture_repository, persistence.catalogue_candidates
        ),
        # Offline fake models complete jobs inside the starting request; real
        # models queue them for the background worker.
        job_execution=ArchitectureJobExecution.INLINE
        if settings.llm_provider is LLMProvider.FAKE
        else ArchitectureJobExecution.QUEUED,
    )


def build_architecture_jobs(
    settings: Settings,
    architecture: ArchitectureKnowledgeWiring,
    persistence: PersistenceAdapters,
    map_breakdown_architecture: MapBreakdownArchitecture,
    clock: ClockPort,
    current_release: ActiveArchitectureReleasePort,
) -> ArchitectureJobWiring:
    """Jobs need the breakdown mapper, so they are built once the backlog graph exists."""
    jobs = ArchitectureJobs(
        persistence.architecture_job_repository,
        persistence.architecture_repository,
        architecture.build_index,
        architecture.propose_changes,
        architecture.job_execution,
        clock,
    )
    mapping_jobs = ArchitectureMappingJobs(
        persistence.mapping_job_repository,
        current_release,
        map_breakdown_architecture,
        architecture.job_execution,
        architecture.build_index.profile,
        f"{architecture.reasoner.model}:architecture-impact-v1",
        clock,
    )
    queued = architecture.job_execution is ArchitectureJobExecution.QUEUED
    worker, mapping_worker = (
        (
            ArchitectureJobWorker(
                jobs,
                poll_interval_seconds=settings.ai_job_poll_interval_seconds,
                shutdown_grace_seconds=settings.ai_job_shutdown_grace_seconds,
            ),
            ArchitectureJobWorker(
                mapping_jobs,
                poll_interval_seconds=settings.ai_job_poll_interval_seconds,
                shutdown_grace_seconds=settings.ai_job_shutdown_grace_seconds,
                name="architecture-mapping-jobs",
            ),
        )
        if queued
        else (None, None)
    )
    return ArchitectureJobWiring(
        jobs=jobs, mapping_jobs=mapping_jobs, worker=worker, mapping_worker=mapping_worker
    )
