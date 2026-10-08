"""Focused OpenRouter adapters over the shared structured-generation behavior."""

from __future__ import annotations

from typing import TypedDict, Unpack

import httpx
from smb_kernel.diagnostics import DebugTrace, NullDebugTrace
from smb_kernel.llm.openrouter_structured_output import (
    OpenRouterStructuredOutputClient,
)

from smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer import (
    StructuredRequirementAnalyzerAdapter,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_epic_generator import (
    StructuredEpicGeneratorAdapter,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_feature_generator import (
    StructuredFeatureGeneratorAdapter,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_story_generator import (
    StructuredStoryGeneratorAdapter,
)
from smb_requirement_agent.breakdown.infrastructure.llm.local_story_quality_evaluator import (
    StructuredStoryQualityEvaluatorAdapter,
)
from smb_requirement_agent.knowledge.infrastructure.llm.requirement_knowledge_adapters import (
    StructuredClarificationAnswerSuggesterAdapter,
    StructuredRequirementRelationshipClassifierAdapter,
)


class OpenRouterAdapterSettings(TypedDict):
    http_client: httpx.Client
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float
    max_output_tokens: int
    data_collection: str
    debug_trace: DebugTrace | None


def _client(
    *,
    base_url: str,
    http_client: httpx.Client,
    api_key: str,
    model: str,
    timeout_seconds: float,
    max_output_tokens: int,
    data_collection: str,
    debug_trace: DebugTrace,
) -> OpenRouterStructuredOutputClient:
    return OpenRouterStructuredOutputClient(
        base_url=base_url,
        http_client=http_client,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
        data_collection=data_collection,
        debug_trace=debug_trace,
    )


class OpenRouterRequirementAnalyzer(StructuredRequirementAnalyzerAdapter):
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        data_collection: str,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        resolved_trace = debug_trace if debug_trace is not None else NullDebugTrace()
        super().__init__(
            client=_client(
                base_url=base_url,
                http_client=http_client,
                api_key=api_key,
                model=model,
                timeout_seconds=timeout_seconds,
                max_output_tokens=max_output_tokens,
                data_collection=data_collection,
                debug_trace=resolved_trace,
            ),
            provider_name="OpenRouter",
            vision_enabled=True,
            vision_error="The configured OpenRouter model does not accept image evidence.",
            debug_trace=resolved_trace,
        )


class OpenRouterEpicGenerator(StructuredEpicGeneratorAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(_client_from_settings(settings), "OpenRouter")


class OpenRouterFeatureGenerator(StructuredFeatureGeneratorAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(_client_from_settings(settings), "OpenRouter")


class OpenRouterStoryGenerator(StructuredStoryGeneratorAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(_client_from_settings(settings), "OpenRouter")


class OpenRouterStoryQualityEvaluator(StructuredStoryQualityEvaluatorAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(_client_from_settings(settings), "OpenRouter")


class OpenRouterRequirementRelationshipClassifier(
    StructuredRequirementRelationshipClassifierAdapter
):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(_client_from_settings(settings), "OpenRouter")


class OpenRouterClarificationAnswerSuggester(StructuredClarificationAnswerSuggesterAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(_client_from_settings(settings), "OpenRouter")


def _client_from_settings(
    settings: OpenRouterAdapterSettings,
) -> OpenRouterStructuredOutputClient:
    debug_trace = settings["debug_trace"]
    return _client(
        base_url=str(settings["base_url"]),
        http_client=settings["http_client"],
        api_key=str(settings["api_key"]),
        model=str(settings["model"]),
        timeout_seconds=float(settings["timeout_seconds"]),
        max_output_tokens=int(settings["max_output_tokens"]),
        data_collection=str(settings["data_collection"]),
        debug_trace=debug_trace if debug_trace is not None else NullDebugTrace(),
    )
