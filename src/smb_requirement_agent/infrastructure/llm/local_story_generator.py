"""Local OpenAI-compatible Story adapter."""

from __future__ import annotations

import logging

import httpx

from smb_requirement_agent.application.errors import StoryGenerationError
from smb_requirement_agent.application.ports.generation_guidance import (
    EMPTY_GENERATION_GUIDANCE,
    GenerationGuidance,
)
from smb_requirement_agent.application.ports.story_generator import StoryCandidate
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.infrastructure.diagnostics import DebugTrace, NullDebugTrace
from smb_requirement_agent.infrastructure.llm.candidate_mappers import to_story_candidates
from smb_requirement_agent.infrastructure.llm.local_structured_output import (
    LocalStructuredOutputClient,
)
from smb_requirement_agent.infrastructure.llm.prompts.story_prompt import (
    PROMPT_VERSION,
    SPLIT_OPERATION,
    SPLIT_RETRY_OPERATION,
    STORY_SYSTEM_PROMPT,
    build_story_user_prompt,
)
from smb_requirement_agent.infrastructure.llm.schemas.story_schema import StorySetSchema
from smb_requirement_agent.infrastructure.llm.structured_output import (
    StructuredOutputClient,
    StructuredOutputError,
)

logger = logging.getLogger("smb_requirement_agent.llm.local_story")


class StructuredStoryGeneratorAdapter:
    """Provider-labelled Story generation over a structured-output client."""

    def __init__(self, client: StructuredOutputClient, provider_name: str) -> None:
        self._client = client
        self._provider_name = provider_name

    def generate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[StoryCandidate]:
        return self._call(
            "generate a complete ordered Story set",
            requirement,
            analysis,
            epic,
            feature,
            [],
            guidance,
        )

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
        return self._one(
            self._call(
                "regenerate exactly one improved Story",
                requirement,
                analysis,
                epic,
                feature,
                [story],
                guidance,
            )
        )

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
        candidates = self._call(
            SPLIT_OPERATION,
            requirement,
            analysis,
            epic,
            feature,
            [story],
            guidance,
        )
        if len(candidates) >= 2:
            return candidates
        logger.warning(
            "%s model %s returned %d split candidate(s); retrying once.",
            self._provider_name,
            self._client.model,
            len(candidates),
        )
        candidates = self._call(
            SPLIT_RETRY_OPERATION,
            requirement,
            analysis,
            epic,
            feature,
            [story],
            guidance,
        )
        if len(candidates) < 2:
            raise StoryGenerationError(
                f"{self._provider_name} returned fewer than two split candidates after one "
                "corrective retry."
            )
        return candidates

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
        return self._one(
            self._call(
                "merge the sources into exactly one Story",
                requirement,
                analysis,
                epic,
                feature,
                stories,
                guidance,
            )
        )

    @staticmethod
    def _one(candidates: list[StoryCandidate]) -> StoryCandidate:
        if len(candidates) != 1:
            raise StoryGenerationError("Provider did not return exactly one Story.")
        return candidates[0]

    def _call(
        self,
        operation: str,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        feature: Feature,
        sources: list[UserStory],
        guidance: GenerationGuidance,
    ) -> list[StoryCandidate]:
        try:
            parsed = self._client.parse(
                system_prompt=STORY_SYSTEM_PROMPT,
                user_prompt=_user_prompt(
                    operation, requirement, analysis, epic, feature, sources, guidance
                ),
                schema_type=StorySetSchema,
            )
        except StructuredOutputError as exc:
            raise StoryGenerationError(
                f"{self._provider_name} Story generation failed: {exc}"
            ) from exc
        return to_story_candidates(parsed, model=self._client.model, prompt_version=PROMPT_VERSION)


class LocalStoryGenerator(StructuredStoryGeneratorAdapter):
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str | None,
        context_window_tokens: int = 8192,
        max_output_tokens: int = 4096,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        super().__init__(
            LocalStructuredOutputClient(
                base_url=base_url,
                http_client=http_client,
                model=model,
                timeout_seconds=timeout_seconds,
                reasoning_effort=reasoning_effort,
                context_window_tokens=context_window_tokens,
                max_output_tokens=max_output_tokens,
                debug_trace=debug_trace if debug_trace is not None else NullDebugTrace(),
            ),
            "Local LLM",
        )


def _user_prompt(
    operation: str,
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
    feature: Feature,
    sources: list[UserStory],
    guidance: GenerationGuidance,
) -> str:
    return build_story_user_prompt(
        operation=operation,
        title=requirement.title.value,
        description=requirement.description.value,
        known_facts=[item.statement for item in analysis.known_facts],
        constraints=[item.statement for item in analysis.constraints]
        + list(analysis.accepted_constraints),
        business_rules=[item.statement for item in analysis.business_rules]
        + list(analysis.accepted_business_rules),
        assumptions=[item.statement for item in analysis.assumptions],
        open_questions=[item.question for item in analysis.open_questions],
        clarifications=[f"{item.subject}: {item.answer}" for item in analysis.clarifications],
        epic_name=epic.name.value,
        epic_outcome=epic.outcome.value,
        feature_name=feature.name.value,
        feature_outcome=feature.outcome.value,
        source_stories=sources,
        desired_outcome=analysis.effective_desired_outcome(),
        guidance=guidance,
    )
