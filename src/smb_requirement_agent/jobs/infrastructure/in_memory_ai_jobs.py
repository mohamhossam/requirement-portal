"""Thread-safe offline AI job queue and actor notification adapter."""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Any

from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobRecord
from smb_requirement_agent.jobs.domain.entities import (
    ActorNotification,
    AiJob,
    AiJobId,
    AiJobOperation,
    AiJobOrigin,
    AiJobStatus,
    NotificationId,
    NotificationPreference,
)
from smb_requirement_agent.jobs.domain.errors import AiJobConflictError
from smb_requirement_agent.shared_kernel.actors import ActorId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class InMemoryAiJobStore:
    def __init__(self, lock: RLock) -> None:
        self._jobs: dict[AiJobId, AiJobRecord] = {}
        self._idempotency: dict[tuple[ActorId, str], tuple[AiJobId, str]] = {}
        self._leases: dict[AiJobId, tuple[str, str, datetime]] = {}
        self._notifications: dict[NotificationId, ActorNotification] = {}
        self._preferences: dict[ActorId, NotificationPreference] = {}
        self._lock = lock

    def snapshot_state(self) -> Any:
        return deepcopy(
            (
                self._jobs,
                self._idempotency,
                self._leases,
                self._notifications,
                self._preferences,
            )
        )

    def restore_state(self, state: Any) -> None:
        (
            self._jobs,
            self._idempotency,
            self._leases,
            self._notifications,
            self._preferences,
        ) = deepcopy(state)

    def add(self, record: AiJobRecord) -> None:
        with self._lock:
            duplicate = self.get_by_idempotency(
                record.job.created_by.id, record.job.idempotency_key
            )
            if duplicate is not None:
                raise AiJobConflictError("The Idempotency-Key already exists.")
            self._jobs[record.job.id] = record
            self._idempotency[(record.job.created_by.id, record.job.idempotency_key)] = (
                record.job.id,
                record.job.command_fingerprint,
            )

    def save(self, job: AiJob) -> None:
        with self._lock:
            current = self._jobs.get(job.id)
            if current is None:
                raise AiJobConflictError(f"AI job {job.id.value!r} does not exist.")
            if current.job != job and current.job.version + 1 != job.version:
                raise AiJobConflictError("AI job changed before this mutation could be saved.")
            self._jobs[job.id] = AiJobRecord(
                job,
                current.command,
                None if job.status.terminal else current.worker_id,
                None if job.status.terminal else current.attempt_token,
                None if job.status.terminal else current.lease_until,
            )
            if job.status.terminal:
                self._leases.pop(job.id, None)

    def save_fenced(
        self,
        job: AiJob,
        worker_id: str,
        attempt_token: str,
        now: datetime,
    ) -> bool:
        with self._lock:
            lease = self._leases.get(job.id)
            if (
                lease is None
                or lease[0] != worker_id
                or lease[1] != attempt_token
                or lease[2] <= now
            ):
                return False
            current = self._jobs.get(job.id)
            if current is None or job.version != current.job.version + 1:
                return False
            ends_attempt = not job.status.holds_attempt
            self._jobs[job.id] = AiJobRecord(
                job,
                current.command,
                None if ends_attempt else current.worker_id,
                None if ends_attempt else current.attempt_token,
                None if ends_attempt else current.lease_until,
            )
            if ends_attempt:
                self._leases.pop(job.id, None)
            return True

    def report_progress_fenced(
        self,
        job: AiJob,
        worker_id: str,
        attempt_token: str,
        now: datetime,
    ) -> bool:
        with self._lock:
            lease = self._leases.get(job.id)
            current = self._jobs.get(job.id)
            if (
                lease is None
                or current is None
                or lease[0] != worker_id
                or lease[1] != attempt_token
                or lease[2] <= now
                or current.job.status is not AiJobStatus.RUNNING
                or job.version != current.job.version + 1
            ):
                return False
            progress = replace(
                current.job,
                phase=job.phase,
                completed_units=job.completed_units,
                total_units=job.total_units,
                current_section_label=job.current_section_label,
                updated_at=job.updated_at,
                version=job.version,
            )
            self._jobs[job.id] = AiJobRecord(
                progress,
                current.command,
                current.worker_id,
                current.attempt_token,
                current.lease_until,
            )
            return True

    def get(self, job_id: AiJobId) -> AiJobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_by_idempotency(self, actor_id: ActorId, key: str) -> AiJobRecord | None:
        with self._lock:
            binding = self._idempotency.get((actor_id, key))
            return self._jobs.get(binding[0]) if binding is not None else None

    def bind_idempotency(
        self,
        job_id: AiJobId,
        actor_id: ActorId,
        key: str,
        command_fingerprint: str,
    ) -> None:
        with self._lock:
            existing = self._idempotency.get((actor_id, key))
            binding = (job_id, command_fingerprint)
            if existing is not None and existing != binding:
                raise AiJobConflictError("The Idempotency-Key already exists.")
            self._idempotency[(actor_id, key)] = binding

    def find_active_equivalent(
        self, requirement_id: RequirementId, command_fingerprint: str
    ) -> AiJobRecord | None:
        with self._lock:
            return next(
                (
                    item
                    for item in self._jobs.values()
                    if item.job.requirement_id == requirement_id
                    and item.job.command_fingerprint == command_fingerprint
                    and not item.job.status.terminal
                ),
                None,
            )

    def reserve_automatic(self, record: AiJobRecord) -> tuple[AiJobRecord, bool]:
        with self._lock:
            matches = [
                item
                for item in self._jobs.values()
                if item.job.requirement_id == record.job.requirement_id
                and item.job.command_fingerprint == record.job.command_fingerprint
            ]
            active = next(
                (item for item in matches if not item.job.status.terminal),
                None,
            )
            existing = active or max(
                matches,
                key=lambda item: (item.job.created_at, item.job.id.value),
                default=None,
            )
            if existing is not None:
                return existing, False
            self.add(record)
            return record, True

    def list_for_requirement(
        self,
        requirement_id: RequirementId,
        *,
        active_only: bool = False,
        limit: int | None = None,
    ) -> list[AiJobRecord]:
        with self._lock:
            result = [
                item
                for item in self._jobs.values()
                if item.job.requirement_id == requirement_id
                and (not active_only or not item.job.status.terminal)
            ]
        newest = sorted(result, key=lambda item: item.job.created_at, reverse=True)
        return newest if limit is None else newest[:limit]

    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_until: datetime,
        blocked_operations: tuple[AiJobOperation, ...] = (),
    ) -> AiJobRecord | None:
        with self._lock:
            running_requirements = {
                item.job.requirement_id
                for item in self._jobs.values()
                if item.job.status in {AiJobStatus.RUNNING, AiJobStatus.CANCELLATION_REQUESTED}
                and item.job.id in self._leases
                and self._leases[item.job.id][2] > now
            }
            # A job waiting out a transient outage holds its Requirement's later jobs.
            waiting_requirements = {
                item.job.requirement_id
                for item in self._jobs.values()
                if item.job.status is AiJobStatus.QUEUED
                and item.job.next_attempt_at is not None
                and item.job.next_attempt_at > now
            }
            candidates = sorted(
                self._jobs.values(),
                key=lambda item: (
                    0 if item.job.origin is AiJobOrigin.USER else 1,
                    # Prior art waits behind everything else (Knowledge Center E2).
                    1 if item.job.operation is AiJobOperation.SCREEN_PRIOR_ART else 0,
                    item.job.created_at,
                ),
            )
            for record in candidates:
                job = record.job
                if (
                    job.operation in blocked_operations
                    and job.status is not AiJobStatus.CANCELLATION_REQUESTED
                ):
                    continue
                expired = job.status in {
                    AiJobStatus.RUNNING,
                    AiJobStatus.CANCELLATION_REQUESTED,
                } and (job.id not in self._leases or self._leases[job.id][2] <= now)
                if not expired and job.status is not AiJobStatus.QUEUED:
                    continue
                if job.requirement_id in running_requirements and not expired:
                    continue
                if not expired and job.requirement_id in waiting_requirements:
                    continue
                if expired and job.status is AiJobStatus.CANCELLATION_REQUESTED:
                    token = str(uuid.uuid4())
                    self._leases[job.id] = (worker_id, token, lease_until)
                    return AiJobRecord(record.job, record.command, worker_id, token, lease_until)
                queued = replace(job, status=AiJobStatus.QUEUED) if expired else job
                claimed = queued.claim(now)
                token = str(uuid.uuid4())
                updated = AiJobRecord(claimed, record.command, worker_id, token, lease_until)
                self._jobs[job.id] = updated
                self._leases[job.id] = (worker_id, token, lease_until)
                return updated
        return None

    def heartbeat(
        self,
        job_id: AiJobId,
        worker_id: str,
        attempt_token: str,
        now: datetime,
        lease_until: datetime,
    ) -> bool:
        with self._lock:
            lease = self._leases.get(job_id)
            if (
                lease is None
                or lease[0] != worker_id
                or lease[1] != attempt_token
                or lease[2] <= now
            ):
                return False
            self._leases[job_id] = (worker_id, attempt_token, lease_until)
            return True

    def release(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> None:
        with self._lock:
            lease = self._leases.get(job_id)
            if lease is not None and lease[:2] == (worker_id, attempt_token):
                self._leases.pop(job_id, None)

    def fence_attempt(self, job_id: AiJobId, worker_id: str, attempt_token: str) -> bool:
        with self._lock:
            lease = self._leases.get(job_id)
            if lease is None or lease[:2] != (worker_id, attempt_token):
                return False
            self._leases.pop(job_id, None)
            record = self._jobs.get(job_id)
            if record is not None:
                self._jobs[job_id] = AiJobRecord(record.job, record.command)
            return True

    def add_notification(self, notification: ActorNotification) -> None:
        with self._lock:
            self._notifications[notification.id] = notification

    # NotificationRepositoryPort uses concise names. These dispatch according
    # to the argument type so one adapter can back both jobs and notifications.
    def add_notification_record(self, notification: ActorNotification) -> None:
        self.add_notification(notification)

    def get_notification(self, notification_id: NotificationId) -> ActorNotification | None:
        with self._lock:
            return self._notifications.get(notification_id)

    def save_notification(self, notification: ActorNotification) -> None:
        with self._lock:
            if notification.id not in self._notifications:
                raise AiJobConflictError("Notification does not exist.")
            self._notifications[notification.id] = notification

    def list_notifications(
        self, actor_id: ActorId, *, unread_only: bool = False, limit: int | None = None
    ) -> list[ActorNotification]:
        with self._lock:
            result = [
                item
                for item in self._notifications.values()
                if item.recipient_id == actor_id and (not unread_only or item.read_at is None)
            ]
        newest = sorted(result, key=lambda item: item.created_at, reverse=True)
        return newest if limit is None else newest[:limit]

    def delete_read_notifications_before(self, cutoff: datetime) -> int:
        with self._lock:
            expired = [
                key
                for key, item in self._notifications.items()
                if item.read_at is not None and item.read_at < cutoff
            ]
            for key in expired:
                del self._notifications[key]
        return len(expired)

    def get_preference(self, actor_id: ActorId) -> NotificationPreference:
        with self._lock:
            return self._preferences.get(actor_id, NotificationPreference(actor_id))

    def save_preference(self, preference: NotificationPreference) -> None:
        with self._lock:
            self._preferences[preference.actor_id] = preference


class InMemoryNotificationRepository:
    def __init__(self, store: InMemoryAiJobStore) -> None:
        self._store = store

    def add(self, notification: ActorNotification) -> None:
        self._store.add_notification_record(notification)

    def get(self, notification_id: NotificationId) -> ActorNotification | None:
        return self._store.get_notification(notification_id)

    def save(self, notification: ActorNotification) -> None:
        self._store.save_notification(notification)

    def list_for_actor(
        self, actor_id: ActorId, *, unread_only: bool = False, limit: int | None = None
    ) -> list[ActorNotification]:
        return self._store.list_notifications(actor_id, unread_only=unread_only, limit=limit)

    def delete_read_before(self, cutoff: datetime) -> int:
        return self._store.delete_read_notifications_before(cutoff)

    def get_preference(self, actor_id: ActorId) -> NotificationPreference:
        return self._store.get_preference(actor_id)

    def save_preference(self, preference: NotificationPreference) -> None:
        self._store.save_preference(preference)
