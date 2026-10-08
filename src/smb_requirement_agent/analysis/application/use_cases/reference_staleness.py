"""Whether the references an analysis and its proposals cite are still current (ADR-0103 PR 15a).

Analysis's half of the old `ReferenceCurrency`: `stale_analysis` and `stale_proposals` are typed in
analysis's vocabulary, so they are analysis's. They run on references' publication-currency
primitives inside one transaction, locking the cited documents in the same order as before:
an analysis's origins, then its proposals'.
"""

from collections.abc import Sequence

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.lineage import analysis_lineage
from smb_requirement_agent.analysis.domain.value_objects import (
    IntentProposal,
    IntentProposalStatus,
)
from smb_requirement_agent.application.ports.reference_grounding import PublicationCurrencyPort
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.shared_kernel.citation import PublishedReference


class AnalysisReferenceCurrency:
    """Analysis's `ReferenceEvidencePort` over references' publication currency."""

    def __init__(
        self, currency: PublicationCurrencyPort, transactions: TransactionManagerPort
    ) -> None:
        self._currency = currency
        self._transactions = transactions

    def require_current(self, evidence: Sequence[PublishedReference]) -> None:
        self._currency.require_current(evidence)

    def stale_analysis(
        self, analysis: RequirementAnalysis, *, target_ids: Sequence[str] | None = None
    ) -> tuple[str, ...]:
        with self._transactions.transaction():
            origins = analysis_lineage(analysis)
            self._currency.lock_documents(
                tuple(sorted({item.citation.document_id for item in origins}))
            )
            return (
                *self.stale_proposals(analysis.intent_proposals),
                *(
                    item.citation.publication_id
                    for item in origins
                    if not self._currency.is_current(item.citation)
                ),
            )

    def stale_proposals(self, proposals: Sequence[IntentProposal]) -> tuple[str, ...]:
        with self._transactions.transaction():
            self._currency.lock_documents(
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
                and any(not self._currency.is_current(c) for c in p.reference_evidence)
            )
