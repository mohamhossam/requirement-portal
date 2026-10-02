"""Queue and execute architecture work without binding requests to model latency."""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum
from uuid import uuid4

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import ArchitectureJobNotFoundError
from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobRepositoryPort,
    ArchitectureJobStatus,
    ExtractionJobInput,
    IndexJobInput,
    MappingJobInput,
)
from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.identity import (
    Actor,
    require_maintainer,
    require_reader,
)
from smb_requirement_agent.application.public_errors import describe_public_error
from smb_requirement_agent.application.use_cases.architecture_index import BuildArchitectureIndex
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    KnowledgeNotFoundError,
)
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
)
from smb_requirement_agent.application.use_cases.catalogue_candidates import (
    ProposeCatalogueChanges,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    KnowledgeConflictError,
    KnowledgeReleaseStatus,
)
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class ArchitectureJobLeaseLostError(Exception):
    """This attempt no longer holds its job's lease; another worker may own it."""


# Checked immediately before a job commits: raises when the attempt lost its lease.
CommitFence = Callable[[], None]


_LOGGER = logging.getLogger(__name__)


class ArchitectureJobExecution(Enum):
    """Where a started job runs; chosen once by the composition root."""

    # Run to completion inside the starting request: offline fake knowledge,
    # where no background poller is configured and jobs take milliseconds.
    INLINE = "inline"
    # Leave queued for a background `ArchitectureJobWorker` to claim.
    QUEUED = "queued"


class ArchitectureJobs:
    def __init__(
        self,
        jobs: ArchitectureJobRepositoryPort,
        knowledge: ArchitectureKnowledgeRepositoryPort,
        indexer: BuildArchitectureIndex,
        mapper: MapBreakdownArchitecture,
        proposer: ProposeCatalogueChanges,
        execution: ArchitectureJobExecution,
        reasoning_profile: str,
        clock: ClockPort,
    ) -> None:
        self._jobs = jobs
        self._knowledge = knowledge
        self._indexer = indexer
        self._mapper = mapper
        self._proposer = proposer
        self._execution = execution
        self._reasoning_profile = reasoning_profile
        self._clock = clock

    def get(self, job_id: str) -> ArchitectureJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise ArchitectureJobNotFoundError("Architecture job not found.")
        return job

    def get_for_actor(self, job_id: str, actor: Actor) -> ArchitectureJob:
        job = self.get(job_id)
        if job.kind is not ArchitectureJobKind.MAPPING:
            require_maintainer(actor)
        else:
            require_reader(actor)
        return job

    def _dispatch(self, job: ArchitectureJob) -> ArchitectureJob:
        if self._execution is ArchitectureJobExecution.INLINE:
            while job.status is ArchitectureJobStatus.QUEUED:
                if self.run_once() is None:
                    break
                job = self.get(job.id)
        # Read back rather than trust the copy: a claim may have ended the job meanwhile.
        return self.get(job.id)

    def start_build(self, release_id: str, revision: int, actor: Actor) -> ArchitectureJob:
        return self._dispatch(self.enqueue_build(release_id, revision, actor))

    def start_mapping(self, requirement_id: RequirementId, actor: Actor) -> ArchitectureJob:
        return self._dispatch(self.enqueue_mapping(requirement_id, actor))

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

    def enqueue_mapping(self, requirement_id: RequirementId, actor: Actor) -> ArchitectureJob:
        require_reader(actor)
        # The worker re-checks membership when it runs; checking here too keeps
        # non-members from queueing work or probing which Requirements exist.
        self._mapper.authorize(_job_actor(actor.id), requirement_id)
        release = self._knowledge.active()
        fingerprint = self._mapper.input_fingerprint(requirement_id)
        return self._jobs.enqueue(
            ArchitectureJob(
                uuid4().hex,
                ArchitectureJobKind.MAPPING,
                requirement_id.value,
                MappingJobInput(
                    release.id, fingerprint, self._indexer.profile, self._reasoning_profile
                ).key,
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

    def cancel(self, job_id: str, actor: Actor) -> ArchitectureJob:
        job = self.get(job_id)
        if job.actor_id != actor.id:
            require_maintainer(actor)
        return self._jobs.cancel(job_id)

    def retry(self, job_id: str, actor: Actor) -> ArchitectureJob:
        job = self.get(job_id)
        if job.actor_id != actor.id:
            require_maintainer(actor)
        return self._dispatch(self._jobs.retry(job_id))

    def claim_next(self) -> ArchitectureJob | None:
        """Lease the next runnable job; the caller keeps the lease renewed while it runs."""
        return self._jobs.claim(self._clock.now())

    def renew_lease(self, job: ArchitectureJob) -> bool:
        """Extend this attempt's lease; False once another attempt owns the job."""
        return self._jobs.heartbeat(job.id, job.attempts, self._clock.now())

    def run_once(self) -> ArchitectureJob | None:
        """Claim and run one job in the caller's thread (the inline execution mode)."""
        job = self.claim_next()
        return None if job is None else self.execute_claimed(job)

    def execute_claimed(self, job: ArchitectureJob) -> ArchitectureJob:
        """Run one claimed attempt and record how it ended.

        Results commit only after the lease is renewed inside the commit, so an
        attempt that lost its lease (and may have been reclaimed) never writes
        over the attempt that now owns the job, and never records its outcome.
        """

        def fence() -> None:
            if not self.renew_lease(job):
                raise ArchitectureJobLeaseLostError(
                    f"Architecture job {job.id} attempt {job.attempts} lost its lease."
                )

        try:
            self._run(job, fence)
        except ArchitectureJobLeaseLostError:
            _LOGGER.warning("Architecture job %s attempt %s lost its lease", job.id, job.attempts)
            return self.get(job.id)
        except Exception as exc:
            # The job boundary: every failure becomes a recorded, public outcome.
            _LOGGER.exception("Architecture job %s failed", job.id)
            status = ArchitectureJobStatus.FAILED
            error: str | None = describe_public_error(exc).code
        else:
            status = ArchitectureJobStatus.SUCCEEDED
            error = None
        self._jobs.finish(job.id, job.attempts, status, error)
        return self.get(job.id)

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
        mapped = MappingJobInput.from_key(job.fingerprint)
        if (
            mapped.embedding_profile != self._indexer.profile
            or mapped.reasoning_profile != self._reasoning_profile
        ):
            raise KnowledgeConflictError("The queued mapping profile changed.")
        self._mapper.execute(
            _job_actor(job.actor_id),
            RequirementId(job.subject_id),
            release_id=mapped.release_id,
            expected_fingerprint=mapped.input_fingerprint,
            fence=fence,
        )


def _job_actor(actor_id: str) -> ActorProfile:
    """The actor snapshot a job acts for: membership is checked by identity alone."""
    return ActorProfile(ActorId(actor_id), actor_id)
