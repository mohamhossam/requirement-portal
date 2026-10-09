"""An answer taken from a suggestion records the suggestion's lineage (ADR-0103 PR 10).

The lineage was built in AnalysisCollaboration; it is now the screening context's answer to
analysis's SuggestionProvenancePort. This pins both kinds of evidence a suggestion can cite.
"""

from __future__ import annotations

from smb_requirement_agent.analysis.domain.value_objects import QuestionId
from smb_requirement_agent.knowledge.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.knowledge.domain.entities import (
    AnswerSuggestion,
    AnswerSuggestionId,
    KnowledgeChunkId,
    RelationshipEvidence,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


def _citation(document_id: str) -> PublishedReference:
    return PublishedReference(
        document_id,
        "Policy",
        "file",
        1,
        "rev",
        "pub",
        "a" * 64,
        "block",
        "Line 1",
        "Coverage required.",
        0,
        18,
        "b" * 64,
    )


class _Suggestions(SuggestClarificationAnswers):
    """Only the provenance method under test; the stored suggestion is supplied directly."""

    def __init__(self, suggestion: AnswerSuggestion) -> None:
        self._suggestion = suggestion
        self.asked: list[tuple[RequirementId, QuestionId, str]] = []

    def require_suggestion(
        self, requirement_id: RequirementId, question_id: QuestionId, suggestion_id: str
    ) -> AnswerSuggestion:
        self.asked.append((requirement_id, question_id, suggestion_id))
        return self._suggestion


def test_provenance_lists_references_then_each_chunk_lineage_through_its_chunk() -> None:
    reference = _citation("reference-doc")
    chunk_origin = SourceLineage(_citation("chunk-doc"), ("upload",))
    related = RequirementId("related-requirement")
    evidence = RelationshipEvidence(
        KnowledgeChunkId("chunk-7"),
        related,
        "business_need",
        "Use BCRM.",
        "/requirements/related-requirement/capture",
        "chunk-fingerprint",
        (chunk_origin,),
    )
    suggestion = AnswerSuggestion(
        AnswerSuggestionId("suggestion-1"),
        "Use BCRM.",
        "Confirmed by related evidence.",
        (evidence,),
        (reference,),
    )
    suggestions = _Suggestions(suggestion)
    subject = RequirementId("subject-requirement")
    question = QuestionId("question-1")

    lineage = suggestions.suggestion_provenance(subject, question, "suggestion-1")

    assert lineage == (
        SourceLineage(reference),
        SourceLineage(
            chunk_origin.citation,
            ("upload", "requirement:related-requirement:chunk:chunk-7"),
        ),
    )
    assert suggestions.asked == [(subject, question, "suggestion-1")]
