"""Events the knowledge side publishes for requirement work to project (ADR-0099).

An event is written in the same transaction as the change it reports. Each
carries the subject's whole current state, so applying one is idempotent and a
consumer that missed some only needs the latest.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

REFERENCE_DOCUMENT_CHANGED = "reference_document_changed"
ARCHITECTURE_RELEASE_ACTIVATED = "architecture_release_activated"


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


class KnowledgeEventOutboxPort(KnowledgeEventSourcePort, Protocol):
    def append(self, kind: str, subject_id: str, payload: object) -> int:
        """Record an event inside the caller's transaction; returns its sequence number."""
        ...
