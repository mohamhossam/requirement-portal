"""Deterministic offline architecture queue."""

from dataclasses import replace
from datetime import datetime, timedelta

from smb_requirement_agent.breakdown.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.references.domain.architecture.knowledge import KnowledgeConflictError


class InMemoryArchitectureJobs:
    def __init__(self) -> None:
        self._jobs: dict[str, ArchitectureJob] = {}

    def enqueue(self, job: ArchitectureJob) -> ArchitectureJob:
        existing = next(
            (
                item
                for item in self._jobs.values()
                if (item.kind, item.subject_id, item.fingerprint)
                == (job.kind, job.subject_id, job.fingerprint)
            ),
            None,
        )
        if existing is None:
            self._jobs[job.id] = job
            return job
        if existing.status in {ArchitectureJobStatus.FAILED, ArchitectureJobStatus.CANCELLED}:
            # Asking again for a failed or cancelled job starts it afresh.
            existing = replace(
                existing,
                status=ArchitectureJobStatus.QUEUED,
                attempts=0,
                error_category=None,
                lease_until=None,
            )
            # Re-inserted so listings see it as the most recently changed job.
            del self._jobs[existing.id]
            self._jobs[existing.id] = existing
        return existing

    def for_subject(
        self, kind: ArchitectureJobKind, subject_id: str
    ) -> tuple[ArchitectureJob, ...]:
        return tuple(
            job for job in self._jobs.values() if (job.kind, job.subject_id) == (kind, subject_id)
        )

    def get(self, job_id: str) -> ArchitectureJob | None:
        return self._jobs.get(job_id)

    def claim(self, now: datetime) -> ArchitectureJob | None:
        for job in self._jobs.values():
            if job.status is ArchitectureJobStatus.QUEUED or (
                job.status is ArchitectureJobStatus.RUNNING
                and job.lease_until is not None
                and job.lease_until < now
            ):
                if job.attempts >= 3:
                    self.finish(
                        job.id, job.attempts, ArchitectureJobStatus.FAILED, "attempts_exhausted"
                    )
                    continue
                claimed = replace(
                    job,
                    status=ArchitectureJobStatus.RUNNING,
                    attempts=job.attempts + 1,
                    lease_until=now + timedelta(minutes=5),
                )
                self._jobs[job.id] = claimed
                return claimed
        return None

    def heartbeat(self, job_id: str, attempt: int, now: datetime) -> bool:
        job = self._jobs[job_id]
        if job.status is not ArchitectureJobStatus.RUNNING or job.attempts != attempt:
            return False
        self._jobs[job_id] = replace(job, lease_until=now + timedelta(minutes=5))
        return True

    def finish(
        self,
        job_id: str,
        attempt: int,
        status: ArchitectureJobStatus,
        error_category: str | None,
    ) -> None:
        job = self._jobs[job_id]
        if job.attempts != attempt:
            return
        self._jobs[job_id] = replace(
            job, status=status, error_category=error_category, lease_until=None
        )

    def cancel(self, job_id: str) -> ArchitectureJob:
        job = self._jobs[job_id]
        if job.status is not ArchitectureJobStatus.QUEUED:
            raise KnowledgeConflictError("Only a queued job can be cancelled.")
        self.finish(job_id, job.attempts, ArchitectureJobStatus.CANCELLED, None)
        return self._jobs[job_id]

    def retry(self, job_id: str) -> ArchitectureJob:
        job = self._jobs[job_id]
        if job.status is not ArchitectureJobStatus.FAILED:
            raise KnowledgeConflictError("Only a failed job can be retried.")
        retried = replace(job, status=ArchitectureJobStatus.QUEUED, attempts=0, error_category=None)
        self._jobs[job_id] = retried
        return retried
