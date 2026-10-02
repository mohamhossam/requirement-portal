"""Carry only recorded origins through the inputs actually supplied to generation."""

from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.value_objects import HumanClarification, IntentProposal
from smb_requirement_agent.domain.document.lineage import SourceLineage, merge_lineage


def input_lineage(
    clarifications: tuple[HumanClarification, ...], proposals: tuple[IntentProposal, ...]
) -> tuple[SourceLineage, ...]:
    return merge_lineage(
        tuple(
            item.through(
                "clarification:"
                + (answer.question_id.value if answer.question_id else answer.subject)
            )
            for answer in clarifications
            for item in answer.source_lineage
        ),
        tuple(
            SourceLineage(citation, (f"proposal:{proposal.id.value}",))
            for proposal in proposals
            if proposal.effective_statement is not None
            for citation in proposal.reference_evidence
        ),
    )


def analysis_lineage(analysis: RequirementAnalysis) -> tuple[SourceLineage, ...]:
    return merge_lineage(
        analysis.source_lineage,
        input_lineage(analysis.clarifications, analysis.intent_proposals),
    )


def generation_lineage(analysis: RequirementAnalysis) -> tuple[SourceLineage, ...]:
    source = f"analysis:{analysis.id.value if analysis.id else 'legacy'}:v{analysis.version}"
    return tuple(item.through(source) for item in analysis_lineage(analysis))
