"""Current publication impact and content-bound, attributed reconciliation."""

from collections.abc import Sequence
from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
    DocumentNotFoundError,
)
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidencePort
from smb_requirement_agent.application.ports.reference_publications import (
    ReferencePublicationStatePort,
)
from smb_requirement_agent.application.ports.source_dependencies import (
    SourceDependency,
    SourceDependencyPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.value_objects import IntentProposal
from smb_requirement_agent.domain.document.lineage import ImpactDecision, ImpactDecisionKind
from smb_requirement_agent.domain.document.reference import PublishedReference
from smb_requirement_agent.domain.identity.entities import ActorProfile
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


@dataclass(frozen=True)
class DependencyImpact:
    dependency: SourceDependency
    publication_current: bool
    publication_state: str
    needs_review: bool
    decisions: tuple[ImpactDecision, ...]


@dataclass(frozen=True)
class DependencyImpactPage:
    items: tuple[DependencyImpact, ...]
    next_offset: int | None


class SourceImpactReview:
    def __init__(
        self,
        index: SourceDependencyPort,
        documents: ReferencePublicationStatePort,
        authorization: RequirementAccessService,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        references: ReferenceEvidencePort,
    ) -> None:
        self._index, self._documents, self._authorization = index, documents, authorization
        self._transactions, self._clock, self._references = transactions, clock, references

    def _view(self, row: SourceDependency) -> DependencyImpact:
        document = self._documents.get(row.lineage.citation.document_id)
        state = document.publication_state if document else "unavailable"
        current = bool(
            document
            and document.published
            and document.published.publication_id == row.lineage.citation.publication_id
        )
        decisions = self._index.decisions(row.id)
        retained = bool(
            decisions
            and decisions[-1].publication_state == state
            and decisions[-1].decision is ImpactDecisionKind.RETAIN
        )
        return DependencyImpact(
            row, current, state, row.active and not current and not retained, decisions
        )

    def page(
        self,
        actor: ActorProfile,
        *,
        document_id: str | None = None,
        requirement_id: str | None = None,
        active_only: bool = False,
        query: str = "",
        offset: int = 0,
        limit: int = 20,
    ) -> DependencyImpactPage:
        with self._transactions.transaction():
            if document_id is not None:
                document = self._documents.get(document_id)
                if document is None:
                    raise DocumentNotFoundError("Document was not found.")
                if document.owner_id != actor.id.value:
                    raise AuthorizationDeniedError(
                        "Only the document owner can inspect its dependencies."
                    )
            if requirement_id is not None:
                self._authorization.require(
                    RequirementId(requirement_id), actor, RequirementPermission.MEMBER
                )
            rows = self._index.page(
                actor.id,
                document_id=document_id,
                requirement_id=requirement_id,
                active_only=active_only,
                query=query,
                offset=offset,
                limit=limit + 1,
            )
            return DependencyImpactPage(
                tuple(self._view(row) for row in rows[:limit]),
                offset + limit if len(rows) > limit else None,
            )

    def decide(
        self,
        dependency_id: str,
        actor: ActorProfile,
        publication_state: str,
        expected_version: int,
        decision: ImpactDecisionKind,
        reason: str,
        *,
        requirement_id: str,
    ) -> DependencyImpact:
        """Record a decision, only for content of the Requirement it is made through."""
        with self._transactions.transaction():
            row = self._index.get(dependency_id)
            if row is None or row.requirement_id != requirement_id:
                raise DocumentNotFoundError("Dependency was not found.")
            self._transactions.lock_requirement(RequirementId(row.requirement_id))
            self._authorization.require(
                RequirementId(row.requirement_id), actor, RequirementPermission.OWNER
            )
            self._documents.lock((row.lineage.citation.document_id,))
            row = self._index.get(dependency_id)
            if row is None or not row.active:
                raise ArtifactVersionConflictError(
                    "Affected content changed. Reload its dependencies."
                )
            view = self._view(row)
            if view.publication_current or view.publication_state != publication_state:
                raise ArtifactVersionConflictError(
                    "Publication changed. Reload its impact before deciding."
                )
            self._index.decide(
                ImpactDecision(
                    row.id,
                    publication_state,
                    decision,
                    reason.strip(),
                    actor.snapshot(),
                    self._clock.now(),
                    expected_version + 1,
                ),
                expected_version,
            )
            return self._view(row)

    def require_current(self, evidence: Sequence[PublishedReference]) -> None:
        self._references.require_current(evidence)

    def stale_proposals(self, proposals: Sequence[IntentProposal]) -> tuple[str, ...]:
        return self._references.stale_proposals(proposals)

    def stale_analysis(
        self, analysis: RequirementAnalysis, *, target_ids: Sequence[str] | None = None
    ) -> tuple[str, ...]:
        with self._transactions.transaction():
            rows = self._index.for_requirement(analysis.requirement_id.value)
            if not rows:
                return self._references.stale_analysis(analysis)
            # A generation checks its supplied parents, not the old descendants it
            # is replacing. Final review (None) still checks the entire backlog.
            rows = tuple(
                row
                for row in rows
                if target_ids is None
                or row.target_kind not in {"epic", "feature", "story"}
                or row.target_id in target_ids
            )
            self._documents.lock(tuple(sorted({r.lineage.citation.document_id for r in rows})))
            return tuple(
                dict.fromkeys(
                    row.target_id if row.target_kind == "proposal" else row.id
                    for row in rows
                    if self._view(row).needs_review
                )
            )
