"""Local OpenAI-compatible semantic INVEST evaluator."""

import httpx

from smb_requirement_agent.application.errors import StoryQualityEvaluationError
from smb_requirement_agent.application.ports.story_quality_evaluator import (
    EMPTY_QUALITY_EVIDENCE,
    StoryQualityEvidence,
)
from smb_requirement_agent.domain.story.entities import UserStory
from smb_requirement_agent.domain.story.quality import InvestCriterion, ValidationFinding
from smb_requirement_agent.infrastructure.diagnostics import DebugTrace, NullDebugTrace
from smb_requirement_agent.infrastructure.llm.local_structured_output import (
    LocalStructuredOutputClient,
)
from smb_requirement_agent.infrastructure.llm.prompts.story_quality_prompt import (
    PROMPT_VERSION,
    STORY_QUALITY_SYSTEM_PROMPT,
    build_story_quality_prompt,
)
from smb_requirement_agent.infrastructure.llm.schemas.story_quality_schema import (
    StoryQualitySchema,
)
from smb_requirement_agent.infrastructure.llm.story_quality_mapping import (
    request_complete_quality_findings,
)
from smb_requirement_agent.infrastructure.llm.structured_output import (
    StructuredOutputClient,
    StructuredOutputError,
)


class StructuredStoryQualityEvaluatorAdapter:
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        client: StructuredOutputClient,
        provider_name: str,
    ) -> None:
        self._client = client
        self._provider_name = provider_name
        self.model = client.model

    def evaluate(
        self,
        story: UserStory,
        siblings: tuple[UserStory, ...],
        criteria: tuple[InvestCriterion, ...],
        *,
        evidence: StoryQualityEvidence = EMPTY_QUALITY_EVIDENCE,
    ) -> tuple[ValidationFinding, ...]:
        def request_schema(
            requested: tuple[InvestCriterion, ...],
        ) -> StoryQualitySchema:
            try:
                return self._client.parse(
                    system_prompt=STORY_QUALITY_SYSTEM_PROMPT,
                    user_prompt=build_story_quality_prompt(
                        story, siblings, requested, evidence=evidence
                    ),
                    schema_type=StoryQualitySchema,
                )
            except StructuredOutputError as exc:
                raise StoryQualityEvaluationError(
                    f"{self._provider_name} Story quality evaluation failed: {exc}"
                ) from exc

        return request_complete_quality_findings(request_schema, criteria)


class LocalStoryQualityEvaluator(StructuredStoryQualityEvaluatorAdapter):
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
