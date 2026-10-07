"""Whether the references requirement work relies on are still current (ADR-0099).

Answered from requirement work's local copy of the library's citable state,
never by reading the library. The copy's rows are locked for the caller's
transaction, so a withdrawal is serialised against the work that checks it.
"""

from collections.abc import Sequence
from datetime import date, timedelta

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    PersistenceError,
    RequirementAnalysisConflictError,
)
from smb_requirement_agent.application.ports.architecture_knowledge import (
    ActiveRelease,
    ArchitectureReleaseStatePort,
)
from smb_requirement_agent.application.ports.knowledge_events import (
    ARCHITECTURE_RELEASE_ACTIVATED,
    REFERENCE_DOCUMENT_CHANGED,
    KnowledgeEventSourcePort,
    KnowledgeStateDecoderPort,
)
from smb_requirement_agent.application.ports.reference_grounding import (
    ReferenceEvidence,
    ReferenceEvidencePort,
    ReferenceKnowledgePort,
)
from smb_requirement_agent.application.ports.reference_publications import (
    ReferencePublicationStatePort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.knowledge_event_cursor import contiguous_reach
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.lineage import analysis_lineage
from smb_requirement_agent.domain.analysis.value_objects import (
    IntentProposal,
    IntentProposalStatus,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference


class ReferenceCurrency:
    def __init__(
        self, states: ReferencePublicationStatePort, transactions: TransactionManagerPort
    ) -> None:
        self._states = states
        self._transactions = transactions

    def _current(self, citation: PublishedReference) -> bool:
        state = self._states.get(citation.document_id)
        return state is not None and state.cites(citation)

    def require_current(self, evidence: Sequence[PublishedReference]) -> None:
        with self._transactions.transaction():
            self._states.lock(tuple(sorted({c.document_id for c in evidence})))
            if any(not self._current(c) for c in evidence):
                raise RequirementAnalysisConflictError(
                    "A cited reference was withdrawn or replaced. "
                    "Re-analyse and reconcile its applicability before continuing."
                )

    def overdue_reviews(self, document_ids: Sequence[str], today: date) -> dict[str, date]:
        overdue: dict[str, date] = {}
        with self._transactions.transaction():
            for document_id in sorted(set(document_ids)):
                state = self._states.get(document_id)
                if state is not None and state.review_due_on and state.review_overdue(today):
                    overdue[document_id] = state.review_due_on
        return overdue

    def stale_analysis(
        self, analysis: RequirementAnalysis, *, target_ids: Sequence[str] | None = None
    ) -> tuple[str, ...]:
        with self._transactions.transaction():
            origins = analysis_lineage(analysis)
            self._states.lock(tuple(sorted({item.citation.document_id for item in origins})))
            return (
                *self.stale_proposals(analysis.intent_proposals),
                *(
                    item.citation.publication_id
                    for item in origins
                    if not self._current(item.citation)
                ),
            )

    def stale_proposals(self, proposals: Sequence[IntentProposal]) -> tuple[str, ...]:
        with self._transactions.transaction():
            self._states.lock(
                tuple(
                    sorted(
                        {
                            c.document_id
                            for p in proposals
                            if p.status is not IntentProposalStatus.REJECTED
                            for c in p.reference_evidence
                        }
                    )
                )
            )
            return tuple(
                p.id.value
                for p in proposals
                if p.status is not IntentProposalStatus.REJECTED
                and any(not self._current(c) for c in p.reference_evidence)
            )


class CurrentReferences:
    """Library retrieval with local currency checks: one `ReferenceSearchPort`."""

    def __init__(self, knowledge: ReferenceKnowledgePort, currency: ReferenceEvidencePort) -> None:
        self._knowledge = knowledge
        self._currency = currency

    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]:
        return self._knowledge.retrieve(query)

    def require_current(self, evidence: Sequence[PublishedReference]) -> None:
        self._currency.require_current(evidence)

    def stale_analysis(
        self, analysis: RequirementAnalysis, *, target_ids: Sequence[str] | None = None
    ) -> tuple[str, ...]:
        return self._currency.stale_analysis(analysis, target_ids=target_ids)

    def stale_proposals(self, proposals: Sequence[IntentProposal]) -> tuple[str, ...]:
        return self._currency.stale_proposals(proposals)


class ProjectKnowledgeEvents:
    """Bring the local copy up to date with the library's events, a batch at a time.

    Every visible event is applied (each carries its document's whole state, and a
    newer one always wins); the cursor moves as `contiguous_reach` allows.
    """

    def __init__(
        self,
        outbox: KnowledgeEventSourcePort,
        states: ReferencePublicationStatePort,
        releases: ArchitectureReleaseStatePort,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        batch: int = 100,
        gap_grace: timedelta = timedelta(seconds=60),
        *,
        decoder: KnowledgeStateDecoderPort,
    ) -> None:
        self._outbox = outbox
        self._decoder = decoder
        self._states = states
        self._releases = releases
        self._transactions = transactions
        self._clock = clock
        self._batch = batch
        self._gap_grace = gap_grace

    def project_next(self) -> bool:
        with self._transactions.transaction():
            cursor = self._states.cursor()
            events = self._outbox.after(cursor, self._batch)
            for event in events:
                if event.kind == REFERENCE_DOCUMENT_CHANGED:
                    self._states.apply(event.seq, self._decoder.reference_document(event.payload))
                elif event.kind == ARCHITECTURE_RELEASE_ACTIVATED:
                    self._releases.apply(event.seq, _release(event.payload))
            reached = contiguous_reach(cursor, events, self._clock.now(), self._gap_grace)
            if reached > cursor:
                self._states.advance(reached)
            return reached > cursor

    def drain(self) -> None:
        """Project until caught up, or until the cursor waits at an in-flight gap."""
        for _ in range(1000):
            if not self.project_next():
                return


class CurrentArchitectureRelease:
    """The active catalogue release, as requirement work's local copy records it."""

    def __init__(self, releases: ArchitectureReleaseStatePort) -> None:
        self._releases = releases

    def active_release_id(self) -> str:
        release_id = self._releases.active_release_id()
        if release_id is None:
            raise PersistenceError("No active architecture release is known yet.")
        return release_id

    def active_release(self) -> ActiveRelease | None:
        """The release in use with its name, or nothing before the first activation arrives."""
        return self._releases.active_release()


def _release(payload: object) -> ActiveRelease:
    """An activation: the release id, and its name once the knowledge side sends one."""
    if isinstance(payload, dict) and isinstance(payload.get("release_id"), str):
        name = payload.get("name")
        return ActiveRelease(str(payload["release_id"]), name if isinstance(name, str) else None)
    raise PersistenceError("Architecture release event is malformed.")
