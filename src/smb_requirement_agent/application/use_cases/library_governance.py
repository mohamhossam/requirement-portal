"""Audited document handover and access-filtered reference dependency queries."""

from dataclasses import dataclass

from smb_requirement_agent.application.errors import (
    ActorNotFoundError,
    DocumentNotFoundError,
    DocumentVersionConflictError,
)
from smb_requirement_agent.application.ports.actor_directory import ActorDirectoryPort
from smb_requirement_agent.application.ports.clock import ClockPort
from smb_requirement_agent.application.ports.document_library import DocumentLibraryPort
from smb_requirement_agent.application.ports.source_dependencies import SourceDependencyPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.domain.analysis.value_objects import IntentProposalStatus
from smb_requirement_agent.domain.document.library import LibraryDocument, OwnershipTransfer
from smb_requirement_agent.domain.document.reference import PublishedReference
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError


@dataclass(frozen=True)
class LibraryDependency:
    requirement_id: str
    requirement_title: str
    analysis_id: str | None
    round_number: int | None
    current_analysis: bool
    proposal_id: str
    statement: str
    status: IntentProposalStatus
    citation: PublishedReference
    publication_current: bool


@dataclass(frozen=True)
class LibraryDependencyPage:
    items: tuple[LibraryDependency, ...]
    next_offset: int | None


class LibraryGovernance:
    def __init__(
        self,
        documents: DocumentLibraryPort,
        actors: ActorDirectoryPort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        index: SourceDependencyPort,
    ) -> None:
        self._index = index
        self._documents, self._actors = documents, actors
        self._transactions, self._clock = transactions, clock

    def _owned(self, document_id: str, actor: ActorProfile) -> LibraryDocument:
        document = self._documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError("Library document was not found.")
        if document.owner.id != actor.id:
            raise AuthorizationDeniedError("Only the document owner can manage its governance.")
        return document

    def history(self, document_id: str, actor: ActorProfile) -> tuple[OwnershipTransfer, ...]:
        return self._owned(document_id, actor).ownership_history

    def transfer(
        self, document_id: str, actor: ActorProfile, target_id: ActorId, expected: int, reason: str
    ) -> OwnershipTransfer:
        with self._transactions.transaction():
            document = self._owned(document_id, actor)
            if document.version != expected:
                raise DocumentVersionConflictError("Document changed. Reload before transferring.")
            target = self._actors.get(target_id)
            if target is None:
                raise ActorNotFoundError("Choose a known workspace user as the new owner.")
            change = OwnershipTransfer(
                document.owner,
                target.snapshot(),
                actor.snapshot(),
                self._clock.now(),
                reason.strip(),
            )
            self._documents.save(document.transfer(change), document.version)
            return change

    def dependencies(
        self, document_id: str, actor: ActorProfile, offset: int = 0, limit: int = 50
    ) -> LibraryDependencyPage:
        # A document owner's rights never confer access to another user's Requirement.
        with self._transactions.transaction():
            document = self._owned(document_id, actor)
            self._documents.lock_publications((document_id,))
            document = self._owned(document_id, actor)
            rows = self._index.page(
                actor.id,
                document_id=document_id,
                target_kind="proposal",
                offset=offset,
                limit=limit + 1,
            )
            return LibraryDependencyPage(
                tuple(
                    LibraryDependency(
                        row.requirement_id,
                        row.requirement_title,
                        row.analysis_id,
                        row.round_number,
                        row.current,
                        row.target_id,
                        row.statement,
                        IntentProposalStatus(row.status),
                        row.lineage.citation,
                        document.published_id == row.lineage.citation.publication_id,
                    )
                    for row in rows[:limit]
                ),
                offset + limit if len(rows) > limit else None,
            )
