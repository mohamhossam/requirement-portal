"""Requirement work's local copy of the reference library's citable state (ADR-0099)."""

from typing import Protocol

from smb_requirement_agent.references.domain.reference import ReferenceDocumentState


class ReferencePublicationStatePort(Protocol):
    def lock(self, document_ids: tuple[str, ...]) -> None:
        """Hold these documents' state steady until the caller's transaction ends."""
        ...

    def get(self, document_id: str) -> ReferenceDocumentState | None: ...

    def apply(self, seq: int, state: ReferenceDocumentState) -> None:
        """Store `state` unless a newer event for the same document was already applied."""
        ...

    def cursor(self) -> int:
        """The last library event this copy has read."""
        ...

    def advance(self, seq: int) -> None: ...
