"""Persistence and leasing boundaries for durable AI work."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from smb_requirement_agent.jobs.domain.entities import AiJob, AiJobId, AiJobOperation
from smb_requirement_agent.shared_kernel.actors import ActorId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


@dataclass(frozen=True)
class AiJobCommand:
    arguments: dict[str, JsonValue]


@dataclass(frozen=True)
class AiJobRecord:
    job: AiJob
    command: AiJobCommand
    worker_id: str | None = None
    attempt_token: str | None = None
    lease_until: datetime | None = None


class AiJobRepositoryPort(Protocol):
    def add(self, record: AiJobRecord) -> None: ...

    def save(self, job: AiJob) -> None: ...

    def save_fenced(
        self,
        job: AiJob,
        worker_id: str,
        attempt_token: str,
        now: datetime,
    ) -> bool:
        """Save only for the live attempt; a job that no longer holds one releases the lease."""
        ...

    def report_progress_fenced(
        self,
        job: AiJob,
        worker_id: str,
        attempt_token: str,
        now: datetime,
    ) -> bool:
        """Update progress fields only while the execution lease remains live."""
        ...

    def get(self, job_id: AiJobId) -> AiJobRecord | None: ...

    def get_by_idempotency(self, actor_id: ActorId, key: str) -> AiJobRecord | None: ...

    def bind_idempotency(
        self,
        job_id: AiJobId,
        actor_id: ActorId,
        key: str,
        command_fingerprint: str,
    ) -> None: ...

    def find_active_equivalent(
        self, requirement_id: RequirementId, command_fingerprint: str
    ) -> AiJobRecord | None: ...

    def reserve_automatic(self, record: AiJobRecord) -> tuple[AiJobRecord, bool]:
        """Atomically return an existing equivalent attempt or add this automatic job."""
        ...

    def list_for_requirement(
        self,
        requirement_id: RequirementId,
        *,
        active_only: bool = False,
        limit: int | None = None,
    ) -> list[AiJobRecord]:
        """Newest first; `limit` keeps only the newest rows, None keeps all."""
        ...


@dataclass(frozen=True)
class AiJobBacklog:
    """Jobs waiting to be claimed: how many per operation, and since when the oldest could be.

    A job waiting out a retry's backoff counts as queued, but its wait starts when
    its next attempt is due, so backoff is not mistaken for a stuck queue.
    """

    queued: Mapping[str, int]
    oldest_claimable_since: datetime | None


class AiJobBacklogPort(Protocol):
    def backlog(self, now: datetime) -> AiJobBacklog: ...


class AiJobQueuePort(Protocol):
    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_until: datetime,
        blocked_operations: tuple[AiJobOperation, ...] = (),
    ) -> AiJobRecord | None: ...

    def heartbeat(
        self,
        job_id: AiJobId,
        worker_id: str,
        attempt_token: str,
        now: datetime,
        lease_until: datetime,
    ) -> bool: ...

    def release(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> None: ...

    def fence_attempt(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> bool: ...


class AiJobWorkerPort(Protocol):
    @property
    def healthy(self) -> bool: ...

    def start(self) -> None: ...

    def stop(self) -> bool: ...

    def wait_until_stopped(self) -> None: ...
