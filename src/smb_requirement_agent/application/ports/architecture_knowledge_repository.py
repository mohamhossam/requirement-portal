"""Persistence boundary for administered architecture releases."""

from typing import Protocol

from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    KnowledgeAuditEvent,
    KnowledgeDocumentVersion,
)


class ArchitectureKnowledgeRepositoryPort(Protocol):
    def get(self, release_id: str) -> ArchitectureKnowledge | None: ...

    def list_all(self) -> tuple[ArchitectureKnowledge, ...]: ...

    def document_versions(self, include_drafts: bool) -> tuple[KnowledgeDocumentVersion, ...]: ...

    def active(self) -> ArchitectureKnowledge: ...

    def save(
        self,
        release: ArchitectureKnowledge,
        expected_revision: int | None,
        actor_id: str,
        action: str,
    ) -> None: ...

    def audit(self, release_id: str) -> tuple[KnowledgeAuditEvent, ...]: ...

    def activate(self, release_id: str, actor_id: str, rationale: str) -> None: ...

    def publish(
        self, release: ArchitectureKnowledge, expected_revision: int, rationale: str
    ) -> None: ...

    def delete_draft(self, release_id: str, expected_revision: int, actor_id: str) -> None:
        """Delete a draft still at ``expected_revision`` with its indexes and suggestions.

        Raises ``KnowledgeConflictError`` when it changed, was published or is gone.
        """
        ...
