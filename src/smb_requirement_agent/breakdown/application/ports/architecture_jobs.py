"""Durable work queue for mapping a Requirement's backlog to the architecture catalogue."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from smb_requirement_agent.application.errors import PersistenceError

_KEY_SEPARATOR = "|"

# The public code a failed attempt records, from the catalogue the composition root supplies.
FailureCode = Callable[[Exception], str]


class ArchitectureJobKind(StrEnum):
    MAPPING = "mapping"


class ArchitectureJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class MappingJobInput:
    """What a mapping was queued against; any change makes the result stale."""

    release_id: str
    input_fingerprint: str
    embedding_profile: str
    reasoning_profile: str

    @property
    def key(self) -> str:
        return _KEY_SEPARATOR.join(
            (
                self.release_id,
                self.input_fingerprint,
                self.embedding_profile,
                self.reasoning_profile,
            )
        )

    @classmethod
    def from_key(cls, key: str) -> MappingJobInput:
        # The reasoning profile is last and may itself contain the separator.
        parts = key.split(_KEY_SEPARATOR, 3)
        if len(parts) != 4 or not all(parts):
            raise PersistenceError("Stored architecture mapping job input is malformed.")
        return cls(*parts)


@dataclass(frozen=True)
class ArchitectureJob:
    id: str
    kind: ArchitectureJobKind
    subject_id: str
    # The job input's key: jobs with the same kind, subject and key are one job.
    fingerprint: str
    actor_id: str
    status: ArchitectureJobStatus
    attempts: int = 0
    error_category: str | None = None
    lease_until: datetime | None = None


class ArchitectureJobRepositoryPort(Protocol):
    def enqueue(self, job: ArchitectureJob) -> ArchitectureJob: ...

    def get(self, job_id: str) -> ArchitectureJob | None: ...

    def for_subject(
        self, kind: ArchitectureJobKind, subject_id: str
    ) -> tuple[ArchitectureJob, ...]:
        """Jobs of one kind for one subject, least recently changed first."""
        ...

    def claim(self, now: datetime) -> ArchitectureJob | None: ...

    def heartbeat(self, job_id: str, attempt: int, now: datetime) -> bool: ...

    def finish(
        self,
        job_id: str,
        attempt: int,
        status: ArchitectureJobStatus,
        error_category: str | None,
    ) -> None: ...

    def cancel(self, job_id: str) -> ArchitectureJob: ...

    def retry(self, job_id: str) -> ArchitectureJob: ...
