"""OpenAI adapters over the shared structured-generation behavior.

Each focused operation reuses the provider-neutral `Structured…Adapter` that the
local and OpenRouter providers use; only the transport differs. Before this,
OpenAI had its own copy of every adapter, and the analysis copy had silently
fallen behind the shared one (question-review reconciliation and uncertainty
repair never reached OpenAI users).
"""

from __future__ import annotations

from openai import OpenAI
from smb_kernel.diagnostics import DebugTrace, NullDebugTrace
from smb_kernel.llm.openai_structured_output import (
    OpenAIStructuredOutputClient,
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

PROVIDER_NAME = "OpenAI"


def _transport(client: OpenAI, model: str, timeout_seconds: float) -> OpenAIStructuredOutputClient:
    return OpenAIStructuredOutputClient(client, model=model, timeout_seconds=timeout_seconds)


class OpenAIRequirementAnalyzer(StructuredRequirementAnalyzerAdapter):
    def __init__(
        self,
        client: OpenAI,
        *,
        model: str,
        timeout_seconds: float,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        resolved_trace = debug_trace if debug_trace is not None else NullDebugTrace()
        super().__init__(
            client=_transport(client, model, timeout_seconds),
            provider_name=PROVIDER_NAME,
            vision_enabled=True,
            vision_error="The configured OpenAI model does not accept image evidence.",
            debug_trace=resolved_trace,
        )


class OpenAIEpicGenerator(StructuredEpicGeneratorAdapter):
    def __init__(self, client: OpenAI, *, model: str, timeout_seconds: float) -> None:
        super().__init__(_transport(client, model, timeout_seconds), PROVIDER_NAME)


class OpenAIFeatureGenerator(StructuredFeatureGeneratorAdapter):
    def __init__(self, client: OpenAI, *, model: str, timeout_seconds: float) -> None:
        super().__init__(_transport(client, model, timeout_seconds), PROVIDER_NAME)


class OpenAIStoryGenerator(StructuredStoryGeneratorAdapter):
    def __init__(self, client: OpenAI, *, model: str, timeout_seconds: float) -> None:
        super().__init__(_transport(client, model, timeout_seconds), PROVIDER_NAME)


class OpenAIStoryQualityEvaluator(StructuredStoryQualityEvaluatorAdapter):
    def __init__(self, client: OpenAI, *, model: str, timeout_seconds: float) -> None:
        super().__init__(_transport(client, model, timeout_seconds), PROVIDER_NAME)


class OpenAIRequirementRelationshipClassifier(StructuredRequirementRelationshipClassifierAdapter):
    def __init__(self, client: OpenAI, *, model: str, timeout_seconds: float) -> None:
        super().__init__(_transport(client, model, timeout_seconds), PROVIDER_NAME)


class OpenAIClarificationAnswerSuggester(StructuredClarificationAnswerSuggesterAdapter):
    def __init__(self, client: OpenAI, *, model: str, timeout_seconds: float) -> None:
        super().__init__(_transport(client, model, timeout_seconds), PROVIDER_NAME)
