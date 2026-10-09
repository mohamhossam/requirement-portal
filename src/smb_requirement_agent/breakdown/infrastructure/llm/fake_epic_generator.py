"""Deterministic Epic generator for tests and credential-free runs."""

from __future__ import annotations

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.breakdown.application.errors import EpicGenerationError
from smb_requirement_agent.breakdown.application.ports.epic_generator import EpicCandidate
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement

FAKE_MODEL = "fake"
FAKE_PROMPT_VERSION = "fake-epic-v1"


class FakeEpicGenerator:
    """Returns a canned candidate derived from the requirement title."""

    def __init__(self) -> None:
        self.should_fail = False

    def generate(self, requirement: Requirement, analysis: RequirementAnalysis) -> EpicCandidate:
        if self.should_fail:
            raise EpicGenerationError("Fake generation error")
        return EpicCandidate(
            name=f"Epic for {requirement.title.value}",
            outcome="A measurable business outcome for the requirement.",
            business_case="A one-sentence justification for the Epic.",
            model=FAKE_MODEL,
            prompt_version=FAKE_PROMPT_VERSION,
        )
