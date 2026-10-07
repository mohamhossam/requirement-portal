"""Deterministic Story generator for offline operation and tests."""

from __future__ import annotations

from smb_requirement_agent.application.errors import StoryGenerationError
from smb_requirement_agent.application.ports.generation_guidance import (
    EMPTY_GENERATION_GUIDANCE,
    GenerationGuidance,
)
from smb_requirement_agent.application.ports.story_generator import StoryCandidate
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement

FAKE_MODEL = "fake"
FAKE_PROMPT_VERSION = "fake-story-v1"


def _candidate(action: str, value: str) -> StoryCandidate:
    return StoryCandidate(
        role="SMB customer",
        action=action,
        value=value,
        acceptance_criteria=[
            {
                "given": "the customer is eligible for the approved Feature",
                "when": action,
                "then": value,
            }
        ],
        model=FAKE_MODEL,
        prompt_version=FAKE_PROMPT_VERSION,
    )


class FakeStoryGenerator:
    def __init__(self) -> None:
        self.should_fail = False

    def _check(self) -> None:
        if self.should_fail:
            raise StoryGenerationError("Fake Story generation error")

    def generate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[StoryCandidate]:
        self._check()
        return [
            _candidate(
                f"use {feature.name.value} through the happy path",
                "the requested capability is completed successfully",
            ),
            _candidate(
                f"receive a clear outcome when {feature.name.value} cannot proceed",
                "I understand what must happen next",
            ),
        ]

    def regenerate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        story: UserStory,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> StoryCandidate:
        self._check()
        return _candidate(story.action.value, f"{story.value.value} with clarified criteria")

    def propose_split(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        story: UserStory,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[StoryCandidate]:
        self._check()
        return [
            _candidate(f"complete the happy path for {story.action.value}", story.value.value),
            _candidate(f"handle an exception for {story.action.value}", story.value.value),
        ]

    def propose_merge(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        stories: list[UserStory],
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> StoryCandidate:
        self._check()
        return _candidate(
            f"complete {feature.name.value} from start to finish",
            "the complete capability is available in one coherent flow",
        )
