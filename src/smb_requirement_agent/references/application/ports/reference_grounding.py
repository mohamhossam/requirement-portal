"""Reference evidence and current-publication validation boundaries.

The applicability-proposal ports are analysis's, in `reference_analysis.py` (ADR-0103 PR 10).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from smb_requirement_agent.shared_kernel.citation import PublishedReference


@dataclass(frozen=True)
class ReferenceEvidence:
    """Exact citable passage plus bounded, non-authoritative retrieval context."""

    citation: PublishedReference
    context_text: str
    context_locations: tuple[str, ...]


class CitationCurrencyPort(Protocol):
    """Whether cited publications are still current, answered from the local copy."""

    def require_current(self, evidence: Sequence[PublishedReference]) -> None: ...


class PublicationCurrencyPort(CitationCurrencyPort, Protocol):
    """The primitives a staleness check needs, inside the caller's transaction.

    Analysis's reference currency (`AnalysisReferenceCurrency`) is built on these (ADR-0103
    PR 15a): lock the cited documents' local state, then ask whether each citation is current.
    """

    def lock_documents(self, document_ids: tuple[str, ...]) -> None: ...

    def is_current(self, citation: PublishedReference) -> bool: ...


class ReferenceReviewPort(Protocol):
    def overdue_reviews(self, document_ids: Sequence[str], today: date) -> dict[str, date]:
        """The cited documents the library says are past their review date, with that date.

        Knowledge Center D: an overdue document is flagged beside its citations, never
        withheld from them.
        """
        ...


class ReferenceSearchPort(CitationCurrencyPort, Protocol):
    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]: ...


class ReferenceKnowledgePort(Protocol):
    """What requirement work reads from the shared reference library (ADR-0099).

    Everything crosses as this application's own values (`ReferenceEvidence`,
    `PublishedReference`), never the library's chunks, so the library can move to
    its own service behind an HTTP adapter. Whether a citation is still current
    is answered locally, by `CitationCurrencyPort`.
    """

    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]: ...

    def has_published(self) -> bool: ...

    def search_evidence(self, query: str) -> tuple[ReferenceEvidence, ...]:
        """Every ranked hit for `query`, unbudgeted, each with its citation and context."""
        ...
