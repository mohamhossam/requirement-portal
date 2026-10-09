"""Breakdown's OpenRouter adapters: the shared structured adapters over the OpenRouter client."""

from __future__ import annotations

from typing import Unpack

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
from smb_requirement_agent.infrastructure.llm.openrouter_transport import (
    OpenRouterAdapterSettings,
    openrouter_client_from_settings,
)


class OpenRouterEpicGenerator(StructuredEpicGeneratorAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(openrouter_client_from_settings(settings), "OpenRouter")


class OpenRouterFeatureGenerator(StructuredFeatureGeneratorAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(openrouter_client_from_settings(settings), "OpenRouter")


class OpenRouterStoryGenerator(StructuredStoryGeneratorAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(openrouter_client_from_settings(settings), "OpenRouter")


class OpenRouterStoryQualityEvaluator(StructuredStoryQualityEvaluatorAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(openrouter_client_from_settings(settings), "OpenRouter")
