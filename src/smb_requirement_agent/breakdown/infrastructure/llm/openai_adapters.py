"""Breakdown's OpenAI adapters: the shared structured adapters over the OpenAI transport."""

from __future__ import annotations

from openai import OpenAI

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
from smb_requirement_agent.infrastructure.llm.openai_transport import OPENAI, openai_transport


class OpenAIEpicGenerator(StructuredEpicGeneratorAdapter):
    def __init__(
        self, client: OpenAI, *, model: str, timeout_seconds: float, max_output_tokens: int
    ) -> None:
        super().__init__(
            openai_transport(client, model, timeout_seconds, max_output_tokens), OPENAI
        )


class OpenAIFeatureGenerator(StructuredFeatureGeneratorAdapter):
    def __init__(
        self, client: OpenAI, *, model: str, timeout_seconds: float, max_output_tokens: int
    ) -> None:
        super().__init__(
            openai_transport(client, model, timeout_seconds, max_output_tokens), OPENAI
        )


class OpenAIStoryGenerator(StructuredStoryGeneratorAdapter):
    def __init__(
        self, client: OpenAI, *, model: str, timeout_seconds: float, max_output_tokens: int
    ) -> None:
        super().__init__(
            openai_transport(client, model, timeout_seconds, max_output_tokens), OPENAI
        )


class OpenAIStoryQualityEvaluator(StructuredStoryQualityEvaluatorAdapter):
    def __init__(
        self, client: OpenAI, *, model: str, timeout_seconds: float, max_output_tokens: int
    ) -> None:
        super().__init__(
            openai_transport(client, model, timeout_seconds, max_output_tokens), OPENAI
        )
