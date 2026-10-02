"""Queue and execute catalogue work (index builds, document reading) off the request path.

Mapping a Requirement's backlog is requirement work with its own queue
(`architecture_mapping_jobs`, ADR-0099).
"""

from __future__ import annotations

from uuid import uuid4

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobRepositoryPort,
    ArchitectureJobStatus,
    ExtractionJobInput,
    IndexJobInput,
)
from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.identity import Actor, require_maintainer
from smb_requirement_agent.application.use_cases.architecture_index import BuildArchitectureIndex
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    KnowledgeNotFoundError,
)
from smb_requirement_agent.application.use_cases.catalogue_candidates import (
    ProposeCatalogueChanges,
)
from smb_requirement_agent.application.use_cases.leased_jobs import (
    ArchitectureJobExecution as ArchitectureJobExecution,
)
from smb_requirement_agent.application.use_cases.leased_jobs import (
    ArchitectureJobLeaseLostError as ArchitectureJobLeaseLostError,
)
from smb_requirement_agent.application.use_cases.leased_jobs import (
    CommitFence,
    LeasedJobs,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    KnowledgeConflictError,
    KnowledgeReleaseStatus,
)


class ArchitectureJobs(LeasedJobs):
    def __init__(
        self,
        jobs: ArchitectureJobRepositoryPort,
        knowledge: ArchitectureKnowledgeRepositoryPort,
        indexer: BuildArchitectureIndex,
        proposer: ProposeCatalogueChanges,
        execution: ArchitectureJobExecution,
        clock: ClockPort,
    ) -> None:
        super().__init__(jobs, execution, clock)
        self._knowledge = knowledge
        self._indexer = indexer
        self._proposer = proposer

    def get_for_actor(self, job_id: str, actor: Actor) -> ArchitectureJob:
        job = self.get(job_id)
        require_maintainer(actor)
        return job

    def start_build(self, release_id: str, revision: int, actor: Actor) -> ArchitectureJob:
        return self._dispatch(self.enqueue_build(release_id, revision, actor))

    def start_extraction(self, release_id: str, version_id: str, actor: Actor) -> ArchitectureJob:
        """Read one draft document for catalogue suggestions; repeat requests share one job."""
        version = self._proposer.document(release_id, version_id, actor)
        return self._dispatch(
            self._jobs.enqueue(
                ArchitectureJob(
                    uuid4().hex,
                    ArchitectureJobKind.EXTRACTION,
                    release_id,
                    ExtractionJobInput(version.id, self._proposer.profile).key,
                    actor.id,
                    ArchitectureJobStatus.QUEUED,
                )
            )
        )

    def enqueue_build(self, release_id: str, revision: int, actor: Actor) -> ArchitectureJob:
        require_maintainer(actor)
        release = self._knowledge.get(release_id)
        if (
            release is None
            or release.status is not KnowledgeReleaseStatus.DRAFT
            or release.revision != revision
        ):
            raise KnowledgeConflictError("The draft changed; reload before building.")
        return self._jobs.enqueue(
            ArchitectureJob(
                uuid4().hex,
                ArchitectureJobKind.INDEX,
                release_id,
                IndexJobInput(revision, self._indexer.profile).key,
                actor.id,
                ArchitectureJobStatus.QUEUED,
            )
        )

    def extractions(self, release_id: str, actor: Actor) -> tuple[tuple[str, ArchitectureJob], ...]:
        """The latest reading job for each document still in the draft."""
        require_maintainer(actor)
        release = self._knowledge.get(release_id)
        if release is None:
            raise KnowledgeNotFoundError(f"Architecture release {release_id!r} not found.")
        documents = {item.id for item in release.documents}
        latest: dict[str, ArchitectureJob] = {}
        for job in self._jobs.for_subject(ArchitectureJobKind.EXTRACTION, release_id):
            version_id = ExtractionJobInput.from_key(job.fingerprint).document_version_id
            if version_id in documents:
                latest[version_id] = job
        return tuple(latest.items())

    def latest_build(self, release_id: str, actor: Actor) -> ArchitectureJob | None:
        """The most recent evidence-index build for a release, whatever its state."""
        require_maintainer(actor)
        if self._knowledge.get(release_id) is None:
            raise KnowledgeNotFoundError(f"Architecture release {release_id!r} not found.")
        builds = self._jobs.for_subject(ArchitectureJobKind.INDEX, release_id)
        return builds[-1] if builds else None

    def _run(self, job: ArchitectureJob, fence: CommitFence) -> None:
        if job.kind is ArchitectureJobKind.INDEX:
            built = IndexJobInput.from_key(job.fingerprint)
            if built.embedding_profile != self._indexer.profile:
                raise KnowledgeConflictError("The queued embedding profile changed.")
            self._indexer.execute(job.subject_id, built.revision, job.actor_id, fence=fence)
            return
        if job.kind is ArchitectureJobKind.EXTRACTION:
            extraction = ExtractionJobInput.from_key(job.fingerprint)
            if extraction.extraction_profile != self._proposer.profile:
                raise KnowledgeConflictError("The configured extraction model changed.")
            self._proposer.execute(job.subject_id, extraction.document_version_id, fence)
            return
        raise KnowledgeConflictError(f"Catalogue jobs do not run {job.kind} work.")
