"""Relay release activations to requirement work while both run in one process (ADR-0099).

The catalogue repository writes an `architecture_release_activated` event in
the transaction that activates a release. Straight after that commits, this
wrapper drains the outbox into requirement work's local copy, so a review or a
mapping sees the new release at once. It drains after the write, never while
reading, so no requirement transaction ever waits on its own locks. Once the
catalogue has its own service this wrapper goes, and the copy catches up by
polling.
"""

from __future__ import annotations

from collections.abc import Callable

from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeAuditEvent,
    KnowledgeDocumentVersion,
)


class RelayingArchitectureKnowledgeRepository:
    def __init__(
        self, inner: ArchitectureKnowledgeRepositoryPort, relay: Callable[[], None]
    ) -> None:
        self._inner = inner
        self._relay = relay

    def activate(self, release_id: str, actor_id: str, rationale: str) -> None:
        self._inner.activate(release_id, actor_id, rationale)
        self._relay()

    def publish(
        self, release: ArchitectureKnowledge, expected_revision: int, rationale: str
    ) -> None:
        self._inner.publish(release, expected_revision, rationale)
        self._relay()

    def get(self, release_id: str) -> ArchitectureKnowledge | None:
        return self._inner.get(release_id)

    def list_all(self) -> tuple[ArchitectureKnowledge, ...]:
        return self._inner.list_all()

    def document_versions(self, include_drafts: bool) -> tuple[KnowledgeDocumentVersion, ...]:
        return self._inner.document_versions(include_drafts)

    def active(self) -> ArchitectureKnowledge:
        return self._inner.active()

    def save(
        self,
        release: ArchitectureKnowledge,
        expected_revision: int | None,
        actor_id: str,
        action: str,
    ) -> None:
        self._inner.save(release, expected_revision, actor_id, action)

    def audit(self, release_id: str) -> tuple[KnowledgeAuditEvent, ...]:
        return self._inner.audit(release_id)

    def delete_draft(self, release_id: str, expected_revision: int, actor_id: str) -> None:
        self._inner.delete_draft(release_id, expected_revision, actor_id)
