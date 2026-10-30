"""Structured-output Story size estimator, and its local OpenAI-compatible variant."""

import httpx
from smb_kernel.diagnostics import DebugTrace, NullDebugTrace
from smb_kernel.llm.local_structured_output import (
    LocalStructuredOutputClient,
)
from smb_kernel.llm.structured_output import (
    StructuredOutputClient,
    StructuredOutputError,
)

from smb_requirement_agent.breakdown.application.errors import StoryEstimationError
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.estimate import EstimateSuggestion
from smb_requirement_agent.breakdown.domain.story.quality import StoryQualityEvidence
from smb_requirement_agent.breakdown.infrastructure.llm.prompts.story_estimate_prompt import (
    PROMPT_VERSION,
    STORY_ESTIMATE_SYSTEM_PROMPT,
    build_story_estimate_prompt,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.story_estimate_schema import (
    StoryEstimatesSchema,
)
from smb_requirement_agent.breakdown.infrastructure.llm.story_estimate_mapping import (
    LabelledStories,
    request_complete_estimates,
)


class StructuredStoryEstimatorAdapter:
    prompt_version = PROMPT_VERSION

    def __init__(self, client: StructuredOutputClient, provider_name: str) -> None:
        self._client = client
        self._provider_name = provider_name
        self.model = client.model

    def suggest(
        self, stories: tuple[UserStory, ...], *, evidence: StoryQualityEvidence
    ) -> tuple[EstimateSuggestion, ...]:
        def request(labelled: LabelledStories) -> StoryEstimatesSchema:
            try:
                return self._client.parse(
                    system_prompt=STORY_ESTIMATE_SYSTEM_PROMPT,
                    user_prompt=build_story_estimate_prompt(labelled, evidence=evidence),
                    schema_type=StoryEstimatesSchema,
                )
            except StructuredOutputError as exc:
                raise StoryEstimationError(
                    f"{self._provider_name} Story sizing failed: {exc}"
                ) from exc

        return request_complete_estimates(request, stories)


class LocalStoryEstimator(StructuredStoryEstimatorAdapter):
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str | None,
        context_window_tokens: int,
        max_output_tokens: int,
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
