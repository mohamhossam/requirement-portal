"""Knowledge's OpenRouter adapters: the shared structured adapters over the OpenRouter client."""

from __future__ import annotations

from typing import Unpack

from smb_requirement_agent.infrastructure.llm.openrouter_transport import (
    OpenRouterAdapterSettings,
    openrouter_client_from_settings,
)
from smb_requirement_agent.knowledge.infrastructure.llm.requirement_knowledge_adapters import (
    StructuredClarificationAnswerSuggesterAdapter,
    StructuredRequirementRelationshipClassifierAdapter,
)


class OpenRouterRequirementRelationshipClassifier(
    StructuredRequirementRelationshipClassifierAdapter
):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(openrouter_client_from_settings(settings), "OpenRouter")


class OpenRouterClarificationAnswerSuggester(StructuredClarificationAnswerSuggesterAdapter):
    def __init__(self, **settings: Unpack[OpenRouterAdapterSettings]) -> None:
        super().__init__(openrouter_client_from_settings(settings), "OpenRouter")
