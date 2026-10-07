"""Deterministic Feature generator for tests and credential-free runs."""

from __future__ import annotations

from smb_requirement_agent.application.errors import FeatureGenerationError
from smb_requirement_agent.application.ports.feature_generator import FeatureCandidate
from smb_requirement_agent.application.ports.generation_guidance import (
    EMPTY_GENERATION_GUIDANCE,
    GenerationGuidance,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement

FAKE_MODEL = "fake"
FAKE_PROMPT_VERSION = "fake-feature-v1"


class FakeFeatureGenerator:
    """Returns a canned two-Feature set.

    Two rather than one, so tests can prove that editing or approving one
    Feature leaves its siblings alone.
    """

    def __init__(self) -> None:
        self.should_fail = False

    def generate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[FeatureCandidate]:
        if self.should_fail:
            raise FeatureGenerationError("Fake generation error")
        return [
            FeatureCandidate(
                name=f"{epic.name.value} - ordering",
                outcome="Customers can place the order in channel.",
                delivery_drop="mvp",
                splitting_pattern="journey_stage",
                splitting_rationale="Lead-to-Order is a distinct journey stage.",
                model=FAKE_MODEL,
                prompt_version=FAKE_PROMPT_VERSION,
            ),
            FeatureCandidate(
                name=f"{epic.name.value} - fulfilment",
                outcome="Orders are provisioned and activated.",
                delivery_drop="later",
                splitting_pattern="component_system",
                splitting_rationale="Provisioning is a separate system boundary.",
                model=FAKE_MODEL,
                prompt_version=FAKE_PROMPT_VERSION,
            ),
        ]
