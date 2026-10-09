"""Analysis's reaction to a revised Requirement (ADR-0004, ADR-0103 §3).

An analysis is disposable AI output that no human approves, so a revised Requirement deletes
it; it is regenerated on demand. Its clarification questions are superseded, never deleted,
because people may have answered them.
"""

from __future__ import annotations

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.events import RequirementRevised


class DiscardAnalysis:
    """Handler for `RequirementRevised`."""

    def __init__(
        self,
        analyses: RequirementAnalysisRepositoryPort,
        audits: AnalysisAuditRepositoryPort,
    ) -> None:
        self._analyses = analyses
        self._audits = audits

    def on_requirement_revised(self, event: RequirementRevised) -> None:
        requirement_id = event.requirement_id
        self._analyses.delete_by_requirement_id(requirement_id)
        for question in self._audits.list_questions(requirement_id):
            updated = question.supersede()
            if updated != question:
                self._audits.save_question(updated)
