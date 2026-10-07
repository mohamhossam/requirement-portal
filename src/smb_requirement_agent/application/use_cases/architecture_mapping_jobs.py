"""Queue and run the mapping of a Requirement's backlog to systems (ADR-0099).

Mapping is requirement work: it writes the Requirement's Features and Stories.
It has its own queue, apart from the catalogue's jobs, and pins the release
that was active when it was asked for.
"""

from __future__ import annotations

from uuid import uuid4

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import ArchitectureMappingProfileChangedError
from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobRepositoryPort,
    ArchitectureJobStatus,
    MappingJobInput,
)
from smb_requirement_agent.application.ports.architecture_knowledge import (
    ActiveArchitectureReleasePort,
)
from smb_requirement_agent.application.ports.identity import Actor, require_reader
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
)
from smb_requirement_agent.application.use_cases.leased_jobs import (
    ArchitectureJobExecution,
    CommitFence,
    LeasedJobs,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class ArchitectureMappingJobs(LeasedJobs):
    def __init__(
        self,
        jobs: ArchitectureJobRepositoryPort,
        releases: ActiveArchitectureReleasePort,
        mapper: MapBreakdownArchitecture,
        execution: ArchitectureJobExecution,
        embedding_profile: str,
        reasoning_profile: str,
        clock: ClockPort,
    ) -> None:
        super().__init__(jobs, execution, clock)
        self._releases = releases
        self._mapper = mapper
        self._embedding_profile = embedding_profile
        self._reasoning_profile = reasoning_profile

    def get_for_actor(self, job_id: str, actor: Actor) -> ArchitectureJob:
        job = self.get(job_id)
        require_reader(actor)
        return job

    def start(self, requirement_id: RequirementId, actor: Actor) -> ArchitectureJob:
        return self._dispatch(self.enqueue(requirement_id, actor))

    def enqueue(self, requirement_id: RequirementId, actor: Actor) -> ArchitectureJob:
        require_reader(actor)
        # The worker re-checks membership when it runs; checking here too keeps
        # non-members from queueing work or probing which Requirements exist.
        self._mapper.authorize(_job_actor(actor.id), requirement_id)
        release_id = self._releases.active_release_id()
        fingerprint = self._mapper.input_fingerprint(requirement_id)
        return self._jobs.enqueue(
            ArchitectureJob(
                uuid4().hex,
                ArchitectureJobKind.MAPPING,
                requirement_id.value,
                MappingJobInput(
                    release_id, fingerprint, self._embedding_profile, self._reasoning_profile
                ).key,
                actor.id,
                ArchitectureJobStatus.QUEUED,
            )
        )

    def _run(self, job: ArchitectureJob, fence: CommitFence) -> None:
        mapped = MappingJobInput.from_key(job.fingerprint)
        if (
            mapped.embedding_profile != self._embedding_profile
            or mapped.reasoning_profile != self._reasoning_profile
        ):
            raise ArchitectureMappingProfileChangedError("The queued mapping profile changed.")
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
