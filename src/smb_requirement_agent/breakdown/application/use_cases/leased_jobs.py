"""Run leased background jobs: dispatch, claim, renew, and record how each attempt ended.

The catalogue's jobs (index, extraction) and requirement work's mapping jobs
each have their own queue and service (ADR-0099). Both run attempts the same
way, which lives here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.breakdown.application.errors import ArchitectureJobNotFoundError
from smb_requirement_agent.breakdown.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobRepositoryPort,
    ArchitectureJobStatus,
    FailureCode,
)
from smb_requirement_agent.identity.application.ports.identity import Actor, require_maintainer


class ArchitectureJobLeaseLostError(Exception):
    """This attempt no longer holds its job's lease; another worker may own it."""


# Checked immediately before a job commits: raises when the attempt lost its lease.
CommitFence = Callable[[], None]


class ArchitectureJobExecution(Enum):
    """Where a started job runs; chosen once by the composition root."""

    # Run to completion inside the starting request: offline fake knowledge,
    # where no background poller is configured and jobs take milliseconds.
    INLINE = "inline"
    # Leave queued for a background `ArchitectureJobWorker` to claim.
    QUEUED = "queued"


_LOGGER = logging.getLogger(__name__)


class LeasedJobs:
    """A queue's attempts: subclasses say what one attempt does in `_run`."""

    def __init__(
        self,
        jobs: ArchitectureJobRepositoryPort,
        execution: ArchitectureJobExecution,
        clock: ClockPort,
        failure_code: FailureCode,
    ) -> None:
        self._jobs = jobs
        self._execution = execution
        self._clock = clock
        self._failure_code = failure_code

    def owns(self, job_id: str) -> bool:
        return self._jobs.get(job_id) is not None

    def get(self, job_id: str) -> ArchitectureJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise ArchitectureJobNotFoundError("Architecture job not found.")
        return job

    def _dispatch(self, job: ArchitectureJob) -> ArchitectureJob:
        if self._execution is ArchitectureJobExecution.INLINE:
            while job.status is ArchitectureJobStatus.QUEUED:
                if self.run_once() is None:
                    break
                job = self.get(job.id)
        # Read back rather than trust the copy: a claim may have ended the job meanwhile.
        return self.get(job.id)

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
            error: str | None = self._failure_code(exc)
        else:
            status = ArchitectureJobStatus.SUCCEEDED
            error = None
        self._jobs.finish(job.id, job.attempts, status, error)
        return self.get(job.id)

    def _run(self, job: ArchitectureJob, fence: CommitFence) -> None:
        raise NotImplementedError
