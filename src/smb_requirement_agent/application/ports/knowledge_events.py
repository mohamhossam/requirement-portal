"""Events the knowledge side publishes for requirement work to project (ADR-0099).

An event is written in the same transaction as the change it reports. Each
carries the subject's whole current state, so applying one is idempotent and a
consumer that missed some only needs the latest.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from smb_requirement_agent.domain.document.reference import ReferenceDocumentState
from smb_requirement_agent.domain.knowledge.historic import HistoricRequirementState

REFERENCE_DOCUMENT_CHANGED = "reference_document_changed"
ARCHITECTURE_RELEASE_ACTIVATED = "architecture_release_activated"
# A historic requirement was published, refreshed or withdrawn (ADR-0102). Its payload names
# the publication; the content is read a page at a time (ADR-0102, amendment 1).
HISTORIC_REQUIREMENT_CHANGED = "historic_requirement_changed"


@dataclass(frozen=True)
class KnowledgeEvent:
    seq: int
    kind: str
    subject_id: str
    payload: object
    created_at: datetime


class KnowledgeEventSourcePort(Protocol):
    """What a consumer reads: in process, the outbox itself; once split, the knowledge API."""

    def after(self, seq: int, limit: int) -> tuple[KnowledgeEvent, ...]:
        """Events after `seq`, oldest first."""
        ...


class KnowledgeStateDecoderPort(Protocol):
    """Turns an event's payload into the state it carries, refusing anything malformed.

    The codec is infrastructure (ADR-0103, PR 2). The knowledge-portal ACL decodes events
    itself once `references` moves (PR 15a), and this port goes.
    """

    def reference_document(self, payload: object) -> ReferenceDocumentState: ...

    def historic_requirement(self, payload: object) -> HistoricRequirementState: ...


class KnowledgeEventOutboxPort(KnowledgeEventSourcePort, Protocol):
    def append(self, kind: str, subject_id: str, payload: object) -> int:
        """Record an event inside the caller's transaction; returns its sequence number."""
        ...
