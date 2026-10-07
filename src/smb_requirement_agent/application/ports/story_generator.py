"""Provider-independent Story generation port."""

from __future__ import annotations

from typing import Protocol, TypedDict

from smb_requirement_agent.application.ports.generation_guidance import (
    EMPTY_GENERATION_GUIDANCE,
    GenerationGuidance,
)
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


class AcceptanceCriterionCandidate(TypedDict):
    given: str
    when: str
    then: str


class StoryCandidate(TypedDict):
    role: str
    action: str
    value: str
    acceptance_criteria: list[AcceptanceCriterionCandidate]
    model: str
    prompt_version: str


class StoryGeneratorPort(Protocol):
    def generate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[StoryCandidate]: ...

    def regenerate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        story: UserStory,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> StoryCandidate: ...

    def propose_split(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        story: UserStory,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[StoryCandidate]: ...

    def propose_merge(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        stories: list[UserStory],
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> StoryCandidate: ...
