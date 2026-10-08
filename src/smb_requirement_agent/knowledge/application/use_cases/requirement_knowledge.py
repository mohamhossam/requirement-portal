"""Build, screen, review, and reuse trusted requirement knowledge."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from typing import Any

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.analysis.domain.entities import (
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.analysis.domain.lineage import analysis_lineage
from smb_requirement_agent.analysis.domain.value_objects import (
    IntentProposalStatus,
)
from smb_requirement_agent.application.errors import (
    KnowledgeFindingNotFoundError,
    KnowledgeGenerationError,
    KnowledgeIndexPendingError,
    KnowledgeScreenConflictError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementPermission,
)
from smb_requirement_agent.identity.domain.entities import RequirementAccess
from smb_requirement_agent.jobs.domain.entities import AiJobOperation
from smb_requirement_agent.knowledge.application.ports.corpus_membership import CorpusMembershipPort
from smb_requirement_agent.knowledge.application.ports.knowledge_access import KnowledgeAccessPort
from smb_requirement_agent.knowledge.application.ports.requirement_knowledge import (
    KnowledgeEmbeddingPort,
    KnowledgeReview,
    KnowledgeScreenEnsureResult,
    KnowledgeScreenSchedulerPort,
    RequirementKnowledgeIndexPort,
    RequirementKnowledgeRepositoryPort,
    RequirementRelationshipClassifierPort,
)
from smb_requirement_agent.knowledge.domain.entities import (
    KnowledgeChunk,
    KnowledgeChunkId,
    KnowledgeFinding,
    KnowledgeFindingId,
    KnowledgeFindingStatus,
    KnowledgeScreen,
    KnowledgeScreenId,
    KnowledgeSourceKind,
    RelationshipEvidence,
)
from smb_requirement_agent.knowledge.domain.membership import CorpusMembership
from smb_requirement_agent.knowledge.domain.screening_errors import (
    KnowledgeFindingConflictError,
    KnowledgeReviewRequiredError,
    RequirementRetiredError,
)
from smb_requirement_agent.references.domain.bounded_text import bounded_knowledge_text
from smb_requirement_agent.requirements.application.ports.document_repository import (
    DocumentRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.errors import (
    DuplicateRequirementStateError,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import RequirementStatus
from smb_requirement_agent.shared_kernel.actors import (
    ActorProfile,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import (
    SourceLineage,
    merge_lineage,
)


class RequirementKnowledgeCorpus:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        analyses: RequirementAnalysisRepositoryPort,
        audits: AnalysisAuditRepositoryPort,
        access: AccessRepositoryPort,
        reviews: RequirementKnowledgeRepositoryPort,
        documents: DocumentRepositoryPort,
        *,
        membership: CorpusMembershipPort | None = None,
    ) -> None:
        self._requirements = requirements
        self._analyses = analyses
        self._audits = audits
        self._access = access
        self._reviews = reviews
        self._documents = documents
        # Who has been retired from the corpus (B3); None where no admin can retire anyone.
        self._membership = membership

    def retirement(self, requirement_id: RequirementId) -> CorpusMembership | None:
        """The Requirement's retirement when it is retired from the corpus now."""
        membership = self._membership.get(requirement_id) if self._membership else None
        return membership if membership is not None and membership.retired else None

    def in_corpus(self, requirement: Requirement) -> bool:
        """Takes part in screening, search and suggestions: not a duplicate, not retired."""
        return (
            requirement.status is not RequirementStatus.DUPLICATE
            and self.retirement(requirement.id) is None
        )

    def chunks(
        self, requirement: Requirement, *, screening_subject: bool = False
    ) -> tuple[KnowledgeChunk, ...]:
        access = self._access.get_requirement(requirement.id)
        owner = access.owner.actor if access is not None and access.owner is not None else None
        path = f"/requirements/{requirement.id.value}/capture"
        values: list[tuple[KnowledgeSourceKind, str, str, str, tuple[SourceLineage, ...]]] = [
            (KnowledgeSourceKind.SOURCE, "title", requirement.title.value, path, ()),
            (KnowledgeSourceKind.SOURCE, "business_need", requirement.description.value, path, ()),
        ]
        optional = (
            ("desired_outcome", requirement.desired_outcome),
            ("customer_context", requirement.customer_context),
        )
        values.extend(
            (KnowledgeSourceKind.SOURCE, field, item.value, path, ())
            for field, item in optional
            if item is not None
        )
        for field, entries in (
            ("channel", requirement.channels),
            ("system", requirement.systems),
            ("business_rule", requirement.business_rules),
            ("constraint", requirement.constraints),
        ):
            values.extend(
                (KnowledgeSourceKind.SOURCE, field, item.value, path, ()) for item in entries
            )
        values.extend(self._attachment_values(requirement))
        analysis = self._analyses.get_by_requirement_id(requirement.id)
        if analysis is not None:
            analysis_path = f"/requirements/{requirement.id.value}/clarify"
            values.extend(
                (
                    KnowledgeSourceKind.CLARIFICATION,
                    f"clarification:{item.kind.value}",
                    f"{item.subject}: {item.answer}",
                    analysis_path,
                    item.source_lineage,
                )
                for item in analysis.clarifications
                if item.answered_by is not None
                and (screening_subject or not item.source_suggestion_id or item.source_lineage)
            )
            values.extend(
                (
                    KnowledgeSourceKind.INTENT_DECISION,
                    f"intent:{item.kind.value}",
                    item.effective_statement or "",
                    analysis_path,
                    tuple(
                        SourceLineage(c, (f"proposal:{item.id.value}",))
                        for c in item.reference_evidence
                    ),
                )
                for item in analysis.intent_proposals
                if item.status in {IntentProposalStatus.ACCEPTED, IntentProposalStatus.EDITED}
            )
            unknown_legacy_origin = any(
                item.source_suggestion_id and not item.source_lineage
                for item in analysis.clarifications
            )
            if screening_subject or (analysis.is_human_confirmed and not unknown_legacy_origin):
                values.extend(
                    (*value, analysis_lineage(analysis))
                    for value in self._analysis_values(
                        analysis, analysis_path, KnowledgeSourceKind.CONFIRMED_ANALYSIS
                    )
                )
        for finding in self._reviews.list_related_findings(requirement.id):
            if (
                finding.status is KnowledgeFindingStatus.RESOLVED
                and finding.resolution_statement is not None
            ):
                values.append(
                    (
                        KnowledgeSourceKind.CONFLICT_RESOLUTION,
                        "conflict_resolution",
                        finding.resolution_statement,
                        f"/requirements/{finding.subject_requirement_id.value}/knowledge",
                        merge_lineage(*(item.source_lineage for item in finding.evidence)),
                    )
                )
        deduplicated: list[
            tuple[KnowledgeSourceKind, str, str, str, tuple[SourceLineage, ...]]
        ] = []
        seen: set[tuple[str, str]] = set()
        for kind, field, text, evidence_path, lineage in values:
            cleaned = text.strip()
            key = (field, cleaned.casefold())
            if not cleaned or key in seen:
                continue
            seen.add(key)
            deduplicated.append((kind, field, cleaned, evidence_path, lineage))
        return tuple(
            _chunk(requirement, kind, field, part, evidence_path, owner, ordinal, lineage)
            for kind, field, text, evidence_path, lineage in deduplicated
            for ordinal, part in enumerate(bounded_knowledge_text(text))
            if part.strip()
        )

    def _attachment_values(
        self, requirement: Requirement
    ) -> list[tuple[KnowledgeSourceKind, str, str, str, tuple[SourceLineage, ...]]]:
        """The included passages of the Requirement's own attachments (Knowledge Center B1).

        Each is the Requirement's own source, like a typed field, so it carries no lineage.
        Its field names the document and block, so two equal passages stay two citations.
        """
        values: list[tuple[KnowledgeSourceKind, str, str, str, tuple[SourceLineage, ...]]] = []
        documents = self._documents.list_for_requirement(requirement.id)
        for document in sorted(documents, key=lambda item: item.id.value):
            if not document.is_included or document.included_version_id is None:
                continue
            path = f"/documents/{document.id.value}"
            prefix = f"attachment:{document.id.value}"
            if document.version(document.included_version_id).extraction_version is None:
                # A legacy plain-text extraction has no blocks; analysis reads its text whole.
                text = document.version(document.included_version_id).extracted_text or ""
                values.append((KnowledgeSourceKind.ATTACHMENT, f"{prefix}:text", text, path, ()))
                continue
            values.extend(
                (KnowledgeSourceKind.ATTACHMENT, f"{prefix}:{block.id}", block.text, path, ())
                for block in document.included_blocks
                if block.text
            )
        return values

    def fingerprint(self, requirement_id: RequirementId) -> str:
        requirement = self._require(requirement_id)
        chunks = self.chunks(requirement, screening_subject=True)
        payload: list[Any] = [(item.source_kind.value, item.field, item.text) for item in chunks]
        conflicts = self.reference_conflicts(requirement_id)
        membership = self._membership.get(requirement_id) if self._membership else None
        if membership is not None:
            # A reinstated Requirement's earlier screen predates its return: it is stale.
            payload.append(("corpus", membership.state.value, membership.changed_at.isoformat()))
        return _hash_json((payload, conflicts)) if conflicts else _hash_json(payload)

    def reference_conflicts(self, requirement_id: RequirementId) -> tuple[str, ...]:
        analysis = self._analyses.get_by_requirement_id(requirement_id)
        return (
            tuple(
                p.id.value
                for p in analysis.intent_proposals
                if p.reference_evidence
                and p.reference_conflict
                and p.status is IntentProposalStatus.PENDING
            )
            if analysis
            else ()
        )

    def title(self, requirement_id: RequirementId) -> str:
        return self._require(requirement_id).title.value

    def version(self, requirement_id: RequirementId) -> int:
        return self._require(requirement_id).version.value

    def subject_text(self, requirement_id: RequirementId) -> str:
        requirement = self._require(requirement_id)
        return "\n".join(item.text for item in self.chunks(requirement, screening_subject=True))

    def current_analysis_chunks(self, requirement: Requirement) -> tuple[KnowledgeChunk, ...]:
        """Return only answerable analysis evidence, never uncertainty categories."""
        analysis = self._analyses.get_by_requirement_id(requirement.id)
        if analysis is None:
            return ()
        path = f"/requirements/{requirement.id.value}/clarify"
        access = self._access.get_requirement(requirement.id)
        owner = access.owner.actor if access is not None and access.owner is not None else None
        return tuple(
            _chunk(requirement, kind, field, text, path, owner, lineage=analysis_lineage(analysis))
            for kind, field, text, _ in self._analysis_values(
                analysis,
                path,
                KnowledgeSourceKind.CURRENT_ANALYSIS,
            )
        )

    def citations_current(self, evidence: tuple[RelationshipEvidence, ...]) -> bool:
        current = {
            chunk.id: chunk.fingerprint
            for requirement_id in {item.requirement_id for item in evidence}
            if (requirement := self._requirements.get(requirement_id)) is not None
            and self.in_corpus(requirement)
            for chunk in self.chunks(requirement)
        }
        return all(current.get(item.chunk_id) == item.fingerprint for item in evidence)

    def suggestion_citations_current(
        self,
        requirement_id: RequirementId,
        evidence: tuple[RelationshipEvidence, ...],
    ) -> bool:
        current: dict[KnowledgeChunkId, str] = {}
        for source_id in {item.requirement_id for item in evidence}:
            requirement = self._requirements.get(source_id)
            if requirement is None or not self.in_corpus(requirement):
                continue
            chunks = self.chunks(requirement)
            if requirement.id == requirement_id:
                chunks = (*chunks, *self.current_analysis_chunks(requirement))
            current.update({chunk.id: chunk.fingerprint for chunk in chunks})
        return all(current.get(item.chunk_id) == item.fingerprint for item in evidence)

    def sync_index(
        self,
        index: RequirementKnowledgeIndexPort,
        embeddings: KnowledgeEmbeddingPort,
        *,
        require_complete: bool = True,
    ) -> None:
        for requirement_id, change in index.pending_sources(100):
            chunks, fingerprint = self.index_source(requirement_id)
            vectors = embeddings.embed(tuple(item.text for item in chunks)) if chunks else ()
            if not index.replace_if_current(requirement_id, change, fingerprint, chunks, vectors):
                raise KnowledgeGenerationError(
                    "Knowledge source changed during indexing. Retry screening."
                )
        if require_complete and index.pending_sources(1):
            raise KnowledgeGenerationError(
                "Knowledge index catch-up is incomplete. Retry screening."
            )

    def index_source(self, requirement_id: RequirementId) -> tuple[tuple[KnowledgeChunk, ...], str]:
        requirement = self._require(requirement_id)
        chunks = self.chunks(requirement) if self.in_corpus(requirement) else ()
        return chunks, _hash_json([(item.id.value, item.fingerprint) for item in chunks])

    @staticmethod
    def _analysis_values(
        analysis: RequirementAnalysis,
        path: str,
        source_kind: KnowledgeSourceKind,
    ) -> list[tuple[KnowledgeSourceKind, str, str, str]]:
        values: list[tuple[KnowledgeSourceKind, str, str, str]] = []
        values.extend(
            (source_kind, "known_fact", item.statement, path) for item in analysis.known_facts
        )
        values.extend(
            (source_kind, "business_rule", item.statement, path) for item in analysis.business_rules
        )
        values.extend(
            (source_kind, "constraint", item.statement, path) for item in analysis.constraints
        )
        return values

    def _require(self, requirement_id: RequirementId) -> Requirement:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        return requirement


class ScreenRequirementKnowledge:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        corpus: RequirementKnowledgeCorpus,
        index: RequirementKnowledgeIndexPort,
        reviews: RequirementKnowledgeRepositoryPort,
        embeddings: KnowledgeEmbeddingPort,
        classifier: RequirementRelationshipClassifierPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        *,
        authorization: KnowledgeAccessPort,
    ) -> None:
        self._requirements = requirements
        self._corpus = corpus
        self._index = index
        self._reviews = reviews
        self._embeddings = embeddings
        self._classifier = classifier
        self._clock = clock
        self._transactions = transactions
        self._authorization = authorization

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, expected_fingerprint: str
    ) -> KnowledgeReview:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(requirement_id, expected_fingerprint)

    def execute_automatic(
        self, requirement_id: RequirementId, expected_fingerprint: str
    ) -> KnowledgeReview:
        with self._authorization.automatic_mutation(
            requirement_id, AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE
        ):
            return self._execute(requirement_id, expected_fingerprint)

    def _execute(self, requirement_id: RequirementId, expected_fingerprint: str) -> KnowledgeReview:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        if requirement.status is RequirementStatus.DUPLICATE:
            raise DuplicateRequirementStateError("Duplicate Requirements cannot be screened again.")
        if self._corpus.retirement(requirement_id) is not None:
            raise RequirementRetiredError(
                "This Requirement is retired from the knowledge corpus, so it is not screened."
            )
        current_fingerprint = self._corpus.fingerprint(requirement_id)
        if current_fingerprint != expected_fingerprint:
            return GetKnowledgeReview(self._corpus, self._reviews).execute(requirement_id)
        with self._transactions.external_call():
            require_index_current(self._index)
            subject_text = self._corpus.subject_text(requirement_id)
            query = self._embeddings.embed((bounded_knowledge_text(subject_text)[0],))
            if len(query) != 1:
                raise KnowledgeGenerationError("Embedding provider returned no query embedding.")
            matches = tuple(
                m
                for m in self._index.search(subject_text, query[0], requirement_id, 100)
                if not m.chunk.source_lineage
            )[:20]
            candidates = (
                self._classifier.classify(requirement, subject_text, matches) if matches else ()
            )
        chunks = {item.chunk.id.value: item.chunk for item in matches}
        screen_id = KnowledgeScreenId(str(uuid.uuid4()))
        findings: list[KnowledgeFinding] = []
        seen_requirements: set[RequirementId] = set()
        for candidate in candidates:
            if candidate.related_requirement_id in seen_requirements:
                raise KnowledgeGenerationError(
                    "Knowledge classifier returned multiple findings for one Requirement."
                )
            cited = [chunks.get(item) for item in candidate.cited_chunk_ids]
            if not cited or any(item is None for item in cited):
                raise KnowledgeGenerationError(
                    "Knowledge classifier cited evidence outside the supplied candidates."
                )
            resolved_chunks = tuple(item for item in cited if item is not None)
            if any(
                item.requirement_id != candidate.related_requirement_id for item in resolved_chunks
            ):
                raise KnowledgeGenerationError(
                    "Knowledge classifier mixed evidence from different Requirements."
                )
            related = self._requirements.get(candidate.related_requirement_id)
            if related is None or related.status is RequirementStatus.DUPLICATE:
                raise KnowledgeGenerationError(
                    "Knowledge classifier returned an invalid related Requirement."
                )
            if self._corpus.retirement(related.id) is not None:
                # Retired while this screen ran; its passages are on their way out of the index.
                continue
            seen_requirements.add(candidate.related_requirement_id)
            if self._current_pair_finding(requirement, related) is not None:
                continue
            findings.append(
                KnowledgeFinding(
                    KnowledgeFindingId(str(uuid.uuid4())),
                    screen_id,
                    requirement_id,
                    requirement.version.value,
                    related.id,
                    related.version.value,
                    candidate.kind,
                    candidate.rationale,
                    tuple(relationship_evidence(item) for item in resolved_chunks),
                )
            )
        now = self._clock.now()
        screen = KnowledgeScreen(
            screen_id,
            requirement_id,
            current_fingerprint,
            requirement.version.value,
            tuple(item.id for item in findings),
            Provenance(now, self._classifier.model, self._classifier.prompt_version),
        )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            for source_id in sorted(
                {finding.related_requirement_id for finding in findings},
                key=lambda item: item.value,
            ):
                if not self._transactions.try_lock_requirement(source_id):
                    raise KnowledgeFindingConflictError(
                        "A related Requirement is changing. Retry screening."
                    )
            if self._index.pending_sources(1):
                raise KnowledgeIndexPendingError(
                    "Requirement knowledge index changed during screening."
                )
            if self._corpus.fingerprint(
                requirement_id
            ) != current_fingerprint or not self._corpus.citations_current(
                tuple(citation for finding in findings for citation in finding.evidence)
            ):
                raise KnowledgeScreenConflictError(
                    "Knowledge changed during screening. Retry screening."
                )
            self._reviews.append_screen(screen, tuple(findings))
        return GetKnowledgeReview(self._corpus, self._reviews).execute(requirement_id)

    def _current_pair_finding(
        self, requirement: Requirement, related: Requirement
    ) -> KnowledgeFinding | None:
        pair = {requirement.id, related.id}
        return next(
            (
                finding
                for finding in self._reviews.list_related_findings(requirement.id)
                if {finding.subject_requirement_id, finding.related_requirement_id} == pair
                # Closed by a retirement, not decided: a screen after reinstatement judges anew.
                and finding.status is not KnowledgeFindingStatus.SOURCE_RETIRED
                and self._corpus.version(finding.subject_requirement_id) == finding.subject_version
                and self._corpus.version(finding.related_requirement_id) == finding.related_version
            ),
            None,
        )


class GetKnowledgeReview:
    def __init__(
        self, corpus: RequirementKnowledgeCorpus, reviews: RequirementKnowledgeRepositoryPort
    ) -> None:
        self._corpus = corpus
        self._reviews = reviews

    def execute(self, requirement_id: RequirementId) -> KnowledgeReview:
        fingerprint = self._corpus.fingerprint(requirement_id)
        screen = self._reviews.current_screen(requirement_id)
        findings = list(self._reviews.list_findings(screen.id.value) if screen is not None else ())
        known_ids = {item.id for item in findings}
        # An open finding stays in force while both Requirements are at the
        # versions it judged, whichever screen recorded it. Screening never
        # records a second finding for such a pair, so tying findings to the
        # latest screen would silently drop an undecided one on any re-screen.
        for item in self._reviews.list_related_findings(requirement_id):
            if item.id in known_ids or not item.actionable or not self._pair_current(item):
                continue
            findings.append(item)
            known_ids.add(item.id)
        versions_current = all(
            self._corpus.version(item.subject_requirement_id) == item.subject_version
            and self._corpus.version(item.related_requirement_id) == item.related_version
            for item in findings
        )
        return KnowledgeReview(
            screen,
            tuple(findings),
            fingerprint,
            versions_current,
            self._corpus.reference_conflicts(requirement_id),
            self._corpus.retirement(requirement_id),
        )

    def _pair_current(self, finding: KnowledgeFinding) -> bool:
        return (
            self._corpus.version(finding.subject_requirement_id) == finding.subject_version
            and self._corpus.version(finding.related_requirement_id) == finding.related_version
        )

    def require_ready(self, requirement_id: RequirementId) -> None:
        review = self.execute(requirement_id)
        if not review.ready:
            raise KnowledgeReviewRequiredError(
                "Complete the current requirement knowledge review before confirming analysis."
            )


class EnsureKnowledgeScreen:
    """Lazily schedule one current screen for an authorized Requirement team member."""

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        authorization: KnowledgeAccessPort,
        scheduler: KnowledgeScreenSchedulerPort,
    ) -> None:
        self._requirements = requirements
        self._authorization = authorization
        self._scheduler = scheduler

    def execute(
        self, requirement_id: RequirementId, actor: ActorProfile
    ) -> KnowledgeScreenEnsureResult:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        if requirement.status is RequirementStatus.DUPLICATE:
            raise DuplicateRequirementStateError(
                "A duplicate Requirement cannot start a new knowledge screen."
            )
        self._authorization.require(requirement_id, actor, RequirementPermission.MEMBER)
        return self._scheduler.ensure(requirement_id)


class DecideKnowledgeFinding:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        access: AccessRepositoryPort,
        reviews: RequirementKnowledgeRepositoryPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        scheduler: KnowledgeScreenSchedulerPort,
        *,
        authorization: KnowledgeAccessPort,
        membership: CorpusMembershipPort | None = None,
    ) -> None:
        self._requirements = requirements
        self._access = access
        self._authorization = authorization
        self._reviews = reviews
        self._clock = clock
        self._transactions = transactions
        self._scheduler = scheduler
        self._membership = membership

    def execute(
        self,
        requirement_id: RequirementId,
        finding_id: KnowledgeFindingId,
        decision: str,
        expected_version: int,
        actor: ActorProfile,
        text: str | None = None,
    ) -> KnowledgeFinding:
        finding = self._reviews.get_finding(finding_id)
        if finding is None or requirement_id not in (
            finding.subject_requirement_id,
            finding.related_requirement_id,
        ):
            raise KnowledgeFindingNotFoundError(
                f"Knowledge finding {finding_id.value!r} not found."
            )
        if decision == "distinct":
            return self.distinct(finding_id, text or "", expected_version, actor)
        if decision == "duplicate":
            return self.duplicate(finding_id, expected_version, actor)
        if decision == "propose_resolution":
            return self.propose_resolution(finding_id, text or "", expected_version, actor)
        if decision == "accept_resolution":
            return self.accept_resolution(finding_id, expected_version, actor)
        raise KnowledgeFindingConflictError(f"Unsupported knowledge decision {decision!r}.")

    def distinct(
        self,
        finding_id: KnowledgeFindingId,
        rationale: str,
        expected_version: int,
        actor: ActorProfile,
    ) -> KnowledgeFinding:
        finding = self._require_current(finding_id)
        self._authorization.require(
            finding.subject_requirement_id, actor, RequirementPermission.OWNER
        )
        updated = finding.mark_distinct(actor, rationale, self._clock.now(), expected_version)
        with self._transactions.transaction():
            self._lock_findings(finding)
            self._reviews.save_finding(updated, expected_version)
        return updated

    def duplicate(
        self, finding_id: KnowledgeFindingId, expected_version: int, actor: ActorProfile
    ) -> KnowledgeFinding:
        finding = self._require_current(finding_id)
        self._authorization.require(
            finding.subject_requirement_id, actor, RequirementPermission.OWNER
        )
        requirement = self._require_requirement(finding.subject_requirement_id)
        canonical = self._require_requirement(finding.related_requirement_id)
        if canonical.status is RequirementStatus.DUPLICATE:
            raise KnowledgeFindingConflictError(
                "The selected canonical Requirement is a duplicate."
            )
        if self._membership is not None:
            retired = self._membership.get(canonical.id)
            if retired is not None and retired.retired:
                raise KnowledgeFindingConflictError(
                    "The selected canonical Requirement is retired from the knowledge corpus."
                )
        now = self._clock.now()
        updated = finding.mark_duplicate(actor, now, expected_version)
        with self._transactions.transaction():
            self._lock_findings(finding)
            self._requirements.save(requirement.close_as_duplicate(canonical.id, now))
            self._reviews.save_finding(updated, expected_version)
        return updated

    def propose_resolution(
        self,
        finding_id: KnowledgeFindingId,
        statement: str,
        expected_version: int,
        actor: ActorProfile,
    ) -> KnowledgeFinding:
        finding = self._require_current(finding_id)
        self._require_either_owner(finding, actor)
        updated = finding.propose_resolution(actor, statement, self._clock.now(), expected_version)
        with self._transactions.transaction():
            self._lock_findings(finding)
            self._reviews.save_finding(updated, expected_version)
        return updated

    def accept_resolution(
        self, finding_id: KnowledgeFindingId, expected_version: int, actor: ActorProfile
    ) -> KnowledgeFinding:
        finding = self._require_current(finding_id)
        subject = self._subject_access(finding)
        related = self._related_access(finding)
        if subject.owner is None or related.owner is None:
            raise KnowledgeFindingConflictError(
                "Both Requirements must have current owners before resolving a contradiction."
            )
        self._require_either_owner(finding, actor)
        updated = finding.accept_resolution(
            actor,
            (subject.owner.actor.id, related.owner.actor.id),
            self._clock.now(),
            expected_version,
        )
        with self._transactions.transaction():
            self._lock_findings(finding)
            self._reviews.save_finding(updated, expected_version)
            if updated.status is KnowledgeFindingStatus.RESOLVED:
                self._scheduler.schedule(updated.subject_requirement_id)
        return updated

    def _lock_findings(self, finding: KnowledgeFinding) -> None:
        for requirement_id in sorted(
            {finding.subject_requirement_id, finding.related_requirement_id},
            key=lambda item: item.value,
        ):
            self._transactions.lock_requirement(requirement_id)

    def _require_current(self, finding_id: KnowledgeFindingId) -> KnowledgeFinding:
        finding = self._reviews.get_finding(finding_id)
        if finding is None:
            raise KnowledgeFindingNotFoundError(
                f"Knowledge finding {finding_id.value!r} not found."
            )
        subject = self._require_requirement(finding.subject_requirement_id)
        related = self._require_requirement(finding.related_requirement_id)
        if (
            subject.version.value != finding.subject_version
            or related.version.value != finding.related_version
        ):
            raise KnowledgeFindingConflictError(
                "A linked Requirement changed; run a new knowledge screen before deciding."
            )
        return finding

    def _require_either_owner(self, finding: KnowledgeFinding, actor: ActorProfile) -> None:
        self._authorization.require_owner_of_either(
            finding.subject_requirement_id, finding.related_requirement_id, actor
        )

    def _subject_access(self, finding: KnowledgeFinding) -> RequirementAccess:
        return self._access.get_requirement(finding.subject_requirement_id) or RequirementAccess(
            finding.subject_requirement_id
        )

    def _related_access(self, finding: KnowledgeFinding) -> RequirementAccess:
        return self._access.get_requirement(finding.related_requirement_id) or RequirementAccess(
            finding.related_requirement_id
        )

    def _require_requirement(self, requirement_id: RequirementId) -> Requirement:
        value = self._requirements.get(requirement_id)
        if value is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        return value


def question_fingerprint(question: ClarificationQuestion) -> str:
    return _hash_json(
        {
            "id": question.id.value,
            "kind": question.kind.value,
            "subject": question.subject,
            "rationale": question.rationale,
        }
    )


def suggestion_input_fingerprint(
    question: ClarificationQuestion,
    current_analysis: tuple[KnowledgeChunk, ...],
) -> str:
    return "dual-source-v2:" + _hash_json(
        {
            "question": question_fingerprint(question),
            "current_analysis": [(item.id.value, item.fingerprint) for item in current_analysis],
        }
    )


def require_index_current(index: RequirementKnowledgeIndexPort) -> None:
    if index.pending_sources(1):
        raise KnowledgeIndexPendingError(
            "Requirement knowledge is being indexed. Try again when ready."
        )


def _chunk(
    requirement: Requirement,
    kind: KnowledgeSourceKind,
    field: str,
    text: str,
    evidence_path: str,
    owner: ActorSnapshot | None,
    ordinal: int = 0,
    lineage: tuple[SourceLineage, ...] = (),
) -> KnowledgeChunk:
    fingerprint = hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()
    if lineage:
        fingerprint = _hash_json((fingerprint, [asdict(item) for item in lineage]))
    raw_id = (
        f"{requirement.id.value}:{requirement.version.value}:{kind.value}:{field}:{fingerprint}"
    )
    if ordinal:
        raw_id += f":part:{ordinal}"
    chunk_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
    return KnowledgeChunk(
        KnowledgeChunkId(chunk_id),
        requirement.id,
        requirement.version.value,
        kind,
        field,
        text,
        fingerprint,
        evidence_path,
        owner,
        lineage,
    )


def relationship_evidence(chunk: KnowledgeChunk) -> RelationshipEvidence:
    return RelationshipEvidence(
        chunk.id,
        chunk.requirement_id,
        chunk.field,
        chunk.text,
        chunk.evidence_path,
        chunk.fingerprint,
        chunk.source_lineage,
    )


def _hash_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
