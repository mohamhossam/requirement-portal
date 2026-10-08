"""Suggest answers to clarification questions from reviewed, cited requirement knowledge."""

from __future__ import annotations

import uuid

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    QuestionId,
)
from smb_requirement_agent.application.errors import (
    AnswerSuggestionNotFoundError,
    ClarificationQuestionNotFoundError,
    KnowledgeGenerationError,
    RequirementAnalysisConflictError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.knowledge_access import KnowledgeAccessPort
from smb_requirement_agent.application.ports.reference_grounding import ReferenceSearchPort
from smb_requirement_agent.application.ports.requirement_knowledge import (
    ClarificationAnswerSuggesterPort,
    KnowledgeEmbeddingPort,
    RequirementKnowledgeIndexPort,
    RequirementKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
    bounded_knowledge_text,
    question_fingerprint,
    relationship_evidence,
    require_index_current,
    suggestion_input_fingerprint,
)
from smb_requirement_agent.domain.knowledge.entities import (
    AnswerSuggestion,
    AnswerSuggestionId,
    AnswerSuggestionSet,
    AnswerSuggestionSetId,
)
from smb_requirement_agent.domain.knowledge.errors import (
    KnowledgeFindingConflictError,
)
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementPermission,
)
from smb_requirement_agent.jobs.domain.entities import AiJobOperation
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


class SuggestClarificationAnswers:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        audits: AnalysisAuditRepositoryPort,
        access: AccessRepositoryPort,
        corpus: RequirementKnowledgeCorpus,
        index: RequirementKnowledgeIndexPort,
        reviews: RequirementKnowledgeRepositoryPort,
        embeddings: KnowledgeEmbeddingPort,
        suggester: ClarificationAnswerSuggesterPort,
        clock: ClockPort,
        transactions: TransactionManagerPort,
        references: ReferenceSearchPort,
        *,
        authorization: KnowledgeAccessPort,
    ) -> None:
        self._requirements = requirements
        self._audits = audits
        self._access = access
        self._authorization = authorization
        self._corpus = corpus
        self._index = index
        self._reviews = reviews
        self._embeddings = embeddings
        self._suggester = suggester
        self._clock = clock
        self._transactions = transactions
        self._references = references

    def execute(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        expected_version: int,
        actor: ActorProfile,
    ) -> AnswerSuggestionSet:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(
                requirement_id=requirement_id,
                question_id=question_id,
                expected_version=expected_version,
                actor=actor,
            )

    def _execute(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        expected_version: int,
        actor: ActorProfile,
    ) -> AnswerSuggestionSet:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        self._authorization.require(requirement_id, actor, RequirementPermission.MEMBER)
        return self._generate(requirement, question_id, expected_version)

    def execute_automatic(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        expected_version: int,
    ) -> AnswerSuggestionSet | None:
        with self._authorization.automatic_mutation(
            requirement_id, AiJobOperation.SUGGEST_CLARIFICATION_ANSWERS
        ):
            return self._execute_automatic(
                requirement_id=requirement_id,
                question_id=question_id,
                expected_version=expected_version,
            )

    def _execute_automatic(
        self,
        requirement_id: RequirementId,
        question_id: QuestionId,
        expected_version: int,
    ) -> AnswerSuggestionSet | None:
        """Generate system-scheduled suggestions through an explicit trusted path."""
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        try:
            return self._generate(requirement, question_id, expected_version)
        except (ClarificationQuestionNotFoundError, KnowledgeFindingConflictError):
            # A queued automatic job may become obsolete while a human resolves,
            # reclassifies, or replaces its question. That is a successful no-op,
            # not a provider failure requiring a retry.
            return None

    def _generate(
        self,
        requirement: Requirement,
        question_id: QuestionId,
        expected_version: int,
    ) -> AnswerSuggestionSet:
        requirement_id = requirement.id
        question = self._audits.get_question(requirement_id, question_id)
        if question is None or not question.is_active:
            raise ClarificationQuestionNotFoundError(
                f"Active clarification question {question_id.value!r} not found."
            )
        if question.version != expected_version:
            raise KnowledgeFindingConflictError(
                "The clarification question changed since it was loaded."
            )
        with self._transactions.external_call():
            require_index_current(self._index)
            query_text = (
                f"{requirement.title.value}\n{question.subject}\n{question.rationale or ''}"
            )
            vector = self._embeddings.embed((bounded_knowledge_text(query_text)[0],))
            if len(vector) != 1:
                raise KnowledgeGenerationError("Embedding provider returned no query embedding.")
            matches = tuple(
                m
                for m in self._index.search(query_text, vector[0], requirement_id, 100)
                if not m.chunk.source_lineage
            )[:20]
            current_analysis = self._corpus.current_analysis_chunks(requirement)
            references = self._references.retrieve(query_text)
            own_origins = {
                o.citation.document_id for c in current_analysis for o in c.source_lineage
            }
            references = tuple(r for r in references if r.citation.document_id not in own_origins)
            candidates = (
                self._suggester.suggest(
                    requirement, question, current_analysis, matches, references
                )
                if current_analysis or matches or references
                else ()
            )
        chunks = {
            item.id.value: item for item in (*current_analysis, *(match.chunk for match in matches))
        }
        suggestions: list[AnswerSuggestion] = []
        reference_citations = {f"reference:{i}": item.citation for i, item in enumerate(references)}
        normalized: set[str] = set()
        for candidate in candidates:
            if len(suggestions) == 3:
                break
            key = candidate.answer.strip().casefold()
            if not key or key in normalized:
                raise KnowledgeGenerationError(
                    "Answer suggester returned blank or duplicate suggestions."
                )
            if (
                not candidate.cited_chunk_ids
                or not candidate.rationale.strip()
                or len(set(candidate.cited_chunk_ids)) != len(candidate.cited_chunk_ids)
                or any(
                    item not in chunks and item not in reference_citations
                    for item in candidate.cited_chunk_ids
                )
            ):
                raise KnowledgeGenerationError(
                    "Answer suggester cited evidence outside the supplied candidates."
                )
            cited = [chunks[item] for item in candidate.cited_chunk_ids if item in chunks]
            normalized.add(key)
            suggestions.append(
                AnswerSuggestion(
                    AnswerSuggestionId(str(uuid.uuid4())),
                    candidate.answer,
                    candidate.rationale,
                    tuple(relationship_evidence(item) for item in cited if item is not None),
                    tuple(
                        reference_citations[item]
                        for item in candidate.cited_chunk_ids
                        if item in reference_citations
                    ),
                )
            )
        now = self._clock.now()
        result = AnswerSuggestionSet(
            AnswerSuggestionSetId(str(uuid.uuid4())),
            requirement_id,
            question_id,
            suggestion_input_fingerprint(question, current_analysis),
            tuple(suggestions),
            Provenance(now, self._suggester.model, self._suggester.prompt_version),
        )
        evidence = tuple(item for suggestion in result.suggestions for item in suggestion.evidence)
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._references.require_current(
                tuple(
                    c
                    for s in result.suggestions
                    for c in (
                        *s.reference_evidence,
                        *(o.citation for e in s.evidence for o in e.source_lineage),
                    )
                )
            )
            for source_id in sorted(
                {item.requirement_id for item in evidence}, key=lambda item: item.value
            ):
                if not self._transactions.try_lock_requirement(source_id):
                    raise KnowledgeFindingConflictError(
                        "A cited Requirement is changing. Retry suggestions."
                    )
            if (
                self._requirements.get(requirement_id) != requirement
                or self._audits.get_question(requirement_id, question_id) != question
                or self._corpus.current_analysis_chunks(requirement) != current_analysis
                or not self._corpus.suggestion_citations_current(requirement_id, evidence)
            ):
                raise KnowledgeFindingConflictError(
                    "Suggestion evidence changed during generation. Retry suggestions."
                )
            self._reviews.append_suggestion_set(result)
        return result

    def get_current(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> AnswerSuggestionSet | None:
        question = self._audits.get_question(requirement_id, question_id)
        if question is None or not question.is_active:
            return None
        result = self._reviews.latest_suggestion_set(requirement_id, question_id.value)
        if result is None:
            return None
        if result.question_fingerprint.startswith("dual-source-v2:"):
            requirement = self._requirements.get(requirement_id)
            if requirement is None or result.question_fingerprint != suggestion_input_fingerprint(
                question, self._corpus.current_analysis_chunks(requirement)
            ):
                return None
        elif result.question_fingerprint != question_fingerprint(question):
            return None
        evidence = tuple(
            evidence for suggestion in result.suggestions for evidence in suggestion.evidence
        )
        if not self._corpus.suggestion_citations_current(requirement_id, evidence):
            return None
        try:
            self._references.require_current(
                tuple(
                    c
                    for s in result.suggestions
                    for c in (
                        *s.reference_evidence,
                        *(o.citation for e in s.evidence for o in e.source_lineage),
                    )
                )
            )
        except RequirementAnalysisConflictError:
            return None
        return result

    def require_suggestion(
        self, requirement_id: RequirementId, question_id: QuestionId, suggestion_id: str
    ) -> AnswerSuggestion:
        result = self.get_current(requirement_id, question_id)
        if result is None or not any(item.id.value == suggestion_id for item in result.suggestions):
            raise AnswerSuggestionNotFoundError(
                "The selected answer suggestion is absent or stale. Refresh suggestions."
            )
        return next(item for item in result.suggestions if item.id.value == suggestion_id)

    def suggestion_provenance(
        self, requirement_id: RequirementId, question_id: QuestionId, suggestion_id: str
    ) -> tuple[SourceLineage, ...]:
        """The lineage an answer taken from this suggestion records.

        Implements analysis's `SuggestionProvenancePort`; the lineage was built in
        `AnalysisCollaboration` until ADR-0103 PR 10.
        """
        suggestion = self.require_suggestion(requirement_id, question_id, suggestion_id)
        return (
            *tuple(SourceLineage(c) for c in suggestion.reference_evidence),
            *(
                o.through(f"requirement:{e.requirement_id.value}:chunk:{e.chunk_id.value}")
                for e in suggestion.evidence
                for o in e.source_lineage
            ),
        )
