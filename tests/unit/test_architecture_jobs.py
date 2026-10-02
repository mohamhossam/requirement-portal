"""Lease recovery and authorization boundaries for architecture jobs."""

import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from smb_kernel.identity.ports import IdentityCredential

from smb_requirement_agent.application.errors import AuthenticationRequiredError, PersistenceError
from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
    IndexJobInput,
    MappingJobInput,
)
from smb_requirement_agent.application.use_cases.architecture_jobs import (
    ArchitectureJobExecution,
    ArchitectureJobs,
)
from smb_requirement_agent.application.use_cases.identity_access import ResolveCurrentActor
from smb_requirement_agent.domain.architecture.knowledge import KnowledgeConflictError
from smb_requirement_agent.domain.identity.entities import ActorProfile
from smb_requirement_agent.infrastructure.jobs.architecture_job_worker import ArchitectureJobWorker
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_jobs import (
    InMemoryArchitectureJobs,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.main import create_app

INDEX = ArchitectureJobKind.INDEX
SUCCEEDED = ArchitectureJobStatus.SUCCEEDED


def test_expired_lease_is_reclaimed_without_old_worker_overwrite() -> None:
    jobs = InMemoryArchitectureJobs()
    now = datetime(2026, 9, 23, tzinfo=UTC)
    jobs.enqueue(
        ArchitectureJob("job-1", INDEX, "release", "1", "actor", ArchitectureJobStatus.QUEUED)
    )
    first = jobs.claim(now)
    assert first is not None and first.attempts == 1
    assert jobs.heartbeat(first.id, first.attempts, now + timedelta(minutes=4))
    assert jobs.claim(now + timedelta(minutes=6)) is None
    second = jobs.claim(now + timedelta(minutes=10))
    assert second is not None and second.attempts == 2
    jobs.finish(first.id, first.attempts, SUCCEEDED, None)
    assert jobs.get(first.id) == second
    jobs.finish(second.id, second.attempts, SUCCEEDED, None)
    completed = jobs.get(second.id)
    assert completed is not None and completed.status is SUCCEEDED


def test_three_expired_attempts_fail_and_explicit_retry_resets() -> None:
    jobs = InMemoryArchitectureJobs()
    now = datetime(2026, 9, 23, tzinfo=UTC)
    jobs.enqueue(
        ArchitectureJob("job-2", INDEX, "release", "1", "actor", ArchitectureJobStatus.QUEUED)
    )
    for attempt in range(3):
        claimed = jobs.claim(now + timedelta(minutes=6 * attempt))
        assert claimed is not None and claimed.attempts == attempt + 1
    assert jobs.claim(now + timedelta(minutes=18)) is None
    failed = jobs.get("job-2")
    assert failed is not None and failed.error_category == "attempts_exhausted"
    assert jobs.retry("job-2").status is ArchitectureJobStatus.QUEUED


def test_anonymous_data_requests_are_denied_but_health_remains_public(
    container: Container,
) -> None:
    class RejectIdentity:
        def authenticate(self, credential: IdentityCredential) -> ActorProfile:
            del credential
            raise AuthenticationRequiredError("A bearer token is required.")

    identity = RejectIdentity()
    rejected = replace(
        container,
        identity_provider=identity,
        resolve_current_actor=ResolveCurrentActor(identity, container.actor_directory),
    )
    with TestClient(create_app(lambda: rejected)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/identity/me").status_code == 401
        assert client.get("/architecture-knowledge/releases/active").status_code == 401


def test_job_input_keys_round_trip_and_match_previously_queued_jobs() -> None:
    index = IndexJobInput(3, "embedding:tokenizer:located-v1:window-v1")
    mapping = MappingJobInput("release-7", "abc123", "embedding-profile", "model|impact-v1")

    assert IndexJobInput.from_key(index.key) == index
    assert MappingJobInput.from_key(mapping.key) == mapping
    # Keys are the durable idempotency value, so the stored format must not drift.
    assert index.key == "3|embedding:tokenizer:located-v1:window-v1"
    assert mapping.key == "release-7|abc123|embedding-profile|model|impact-v1"


@pytest.mark.parametrize("key", ["", "3", "three|profile", "3|"])
def test_malformed_index_job_input_is_a_persistence_failure(key: str) -> None:
    with pytest.raises(PersistenceError, match="index job input"):
        IndexJobInput.from_key(key)


@pytest.mark.parametrize(
    "key", ["", "release|fingerprint|embedding", "release||embedding|reasoning"]
)
def test_malformed_mapping_job_input_is_a_persistence_failure(key: str) -> None:
    with pytest.raises(PersistenceError, match="mapping job input"):
        MappingJobInput.from_key(key)


class SteppingClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class RecordingIndexer:
    """Stands in for the index build: runs `before_commit`, then the fence, then writes."""

    profile = "embedding-profile"

    def __init__(self) -> None:
        self.stored = False
        self.failure: Exception | None = None
        self.before_commit: Callable[[], None] = lambda: None

    def execute(
        self, release_id: str, revision: int, actor_id: str, *, fence: Callable[[], None]
    ) -> None:
        if self.failure is not None:
            raise self.failure
        self.before_commit()
        fence()
        self.stored = True


def _index_jobs() -> tuple[
    ArchitectureJobs, InMemoryArchitectureJobs, RecordingIndexer, SteppingClock
]:
    repository = InMemoryArchitectureJobs()
    indexer = RecordingIndexer()
    clock = SteppingClock(datetime(2026, 9, 24, tzinfo=UTC))
    repository.enqueue(
        ArchitectureJob(
            "job-3",
            INDEX,
            "release",
            IndexJobInput(1, indexer.profile).key,
            "actor",
            ArchitectureJobStatus.QUEUED,
        )
    )
    jobs = ArchitectureJobs(
        repository,
        cast(Any, None),
        cast(Any, indexer),
        cast(Any, None),
        cast(Any, None),
        ArchitectureJobExecution.QUEUED,
        "reasoning-profile",
        clock,
    )
    return jobs, repository, indexer, clock


def test_an_attempt_that_lost_its_lease_neither_writes_nor_records_an_outcome() -> None:
    jobs, repository, indexer, clock = _index_jobs()
    stale = jobs.claim_next()
    assert stale is not None

    def reclaimed_meanwhile() -> None:
        # The stale attempt stalled past its lease; another worker took the job.
        clock.current += timedelta(minutes=10)
        assert repository.claim(clock.now()) is not None

    indexer.before_commit = reclaimed_meanwhile

    jobs.execute_claimed(stale)

    assert indexer.stored is False
    current = repository.get("job-3")
    assert current is not None
    assert (current.status, current.attempts) == (ArchitectureJobStatus.RUNNING, 2)


def test_an_attempt_holding_its_lease_writes_and_succeeds() -> None:
    jobs, repository, indexer, _ = _index_jobs()
    claimed = jobs.claim_next()
    assert claimed is not None

    finished = jobs.execute_claimed(claimed)

    assert indexer.stored is True
    assert finished.status is SUCCEEDED


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (KnowledgeConflictError("The draft changed."), "architecture_knowledge_conflict"),
        (RuntimeError("password=secret"), "internal"),
    ],
)
def test_failures_are_recorded_as_public_error_codes(failure: Exception, code: str) -> None:
    jobs, repository, indexer, _ = _index_jobs()
    indexer.failure = failure
    claimed = jobs.claim_next()
    assert claimed is not None

    failed = jobs.execute_claimed(claimed)

    assert failed.status is ArchitectureJobStatus.FAILED
    assert failed.error_category == code


class SlowJobs:
    """One claimed job that runs until the worker has renewed its lease three times."""

    def __init__(self) -> None:
        self.job: ArchitectureJob | None = ArchitectureJob(
            "job-4", INDEX, "release", "1", "actor", ArchitectureJobStatus.RUNNING, attempts=1
        )
        self.renewals = 0
        self.renewed = threading.Event()

    def claim_next(self) -> ArchitectureJob | None:
        job, self.job = self.job, None
        return job

    def renew_lease(self, job: ArchitectureJob) -> bool:
        self.renewals += 1
        if self.renewals >= 3:
            self.renewed.set()
        return True

    def execute_claimed(self, job: ArchitectureJob) -> ArchitectureJob:
        assert self.renewed.wait(timeout=2)
        return replace(job, status=SUCCEEDED)


def test_the_worker_keeps_a_running_jobs_lease_renewed() -> None:
    jobs = SlowJobs()
    worker = ArchitectureJobWorker(
        cast(ArchitectureJobs, jobs),
        poll_interval_seconds=0.01,
        shutdown_grace_seconds=2,
        lease_renewal_seconds=0.01,
    )

    worker.start()
    assert jobs.renewed.wait(timeout=2)
    assert worker.stop() is True
    assert jobs.renewals >= 3
