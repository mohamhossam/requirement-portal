"""Isolated offline repository for versioned architecture knowledge."""

from datetime import UTC, datetime
from threading import RLock

from smb_requirement_agent.application.ports.knowledge_events import (
    ARCHITECTURE_RELEASE_ACTIVATED,
    KnowledgeEventOutboxPort,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeAuditEvent,
    KnowledgeConflictError,
    KnowledgeDocumentVersion,
    KnowledgeReleaseStatus,
)


class InMemoryArchitectureKnowledgeRepository:
    def __init__(
        self,
        initial: ArchitectureKnowledge,
        events: KnowledgeEventOutboxPort | None = None,
    ) -> None:
        self._lock = RLock()
        self._outbox = events
        self._releases = {initial.id: initial}
        self._documents = {item.id: item for item in initial.documents}
        self._published_documents = set(self._documents)
        self._active_id = initial.id
        self._events: list[KnowledgeAuditEvent] = []
        self._activated(initial.id)

    def _activated(self, release_id: str) -> None:
        """Report the new active release, as the PostgreSQL adapter does (ADR-0099)."""
        if self._outbox is not None:
            self._outbox.append(
                ARCHITECTURE_RELEASE_ACTIVATED, release_id, {"release_id": release_id}
            )

    def get(self, release_id: str) -> ArchitectureKnowledge | None:
        with self._lock:
            return self._releases.get(release_id)

    def list_all(self) -> tuple[ArchitectureKnowledge, ...]:
        with self._lock:
            return tuple(self._releases.values())

    def document_versions(self, include_drafts: bool) -> tuple[KnowledgeDocumentVersion, ...]:
        with self._lock:
            return tuple(
                item
                for key, item in self._documents.items()
                if include_drafts or key in self._published_documents
            )

    def active(self) -> ArchitectureKnowledge:
        with self._lock:
            return self._releases[self._active_id]

    def save(
        self,
        release: ArchitectureKnowledge,
        expected_revision: int | None,
        actor_id: str,
        action: str,
    ) -> None:
        with self._lock:
            current = self._releases.get(release.id)
            if (current.revision if current else None) != expected_revision:
                raise KnowledgeConflictError("The knowledge draft changed; reload before saving.")
            if current is not None and current.status is not KnowledgeReleaseStatus.DRAFT:
                raise KnowledgeConflictError("Published releases are immutable.")
            self._documents.update({item.id: item for item in release.documents})
            self._releases[release.id] = release
            self._events.append(
                KnowledgeAuditEvent(
                    release.id, actor_id, action, release.revision, None, datetime.now(UTC)
                )
            )

    def audit(self, release_id: str) -> tuple[KnowledgeAuditEvent, ...]:
        with self._lock:
            return tuple(item for item in self._events if item.release_id == release_id)

    def activate(self, release_id: str, actor_id: str, rationale: str) -> None:
        with self._lock:
            release = self._releases.get(release_id)
            if release is None or release.status is not KnowledgeReleaseStatus.PUBLISHED:
                raise KnowledgeConflictError("Only a published release can be activated.")
            self._active_id = release_id
            self._activated(release_id)
            self._events.append(
                KnowledgeAuditEvent(
                    release_id, actor_id, "activate", release.revision, rationale, datetime.now(UTC)
                )
            )

    def publish(
        self, release: ArchitectureKnowledge, expected_revision: int, rationale: str
    ) -> None:
        with self._lock:
            current = self._releases.get(release.id)
            if (
                current is None
                or current.revision != expected_revision
                or current.status is not KnowledgeReleaseStatus.DRAFT
            ):
                raise KnowledgeConflictError(
                    "The knowledge draft changed; reload before publishing."
                )
            if release.status is not KnowledgeReleaseStatus.PUBLISHED:
                raise KnowledgeConflictError("Only a published release can be activated.")
            self._documents.update({item.id: item for item in release.documents})
            self._releases[release.id] = release
            self._published_documents.update(item.id for item in release.documents)
            self._active_id = release.id
            self._activated(release.id)
            self._events.append(
                KnowledgeAuditEvent(
                    release.id,
                    release.published_by or "",
                    "publish",
                    release.revision,
                    rationale,
                    datetime.now(UTC),
                )
            )

    def delete_draft(self, release_id: str, expected_revision: int, actor_id: str) -> None:
        with self._lock:
            current = self._releases.get(release_id)
            if (
                current is None
                or current.status is not KnowledgeReleaseStatus.DRAFT
                or current.revision != expected_revision
            ):
                raise KnowledgeConflictError("The draft changed; reload before discarding it.")
            del self._releases[release_id]
            self._events.append(
                KnowledgeAuditEvent(
                    release_id, actor_id, "discard_draft", current.revision, None, datetime.now(UTC)
                )
            )
