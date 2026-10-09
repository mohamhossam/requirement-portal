"""Knowledge's OpenAI adapters: the shared structured adapters over the OpenAI transport."""

from __future__ import annotations

from openai import OpenAI

from smb_requirement_agent.infrastructure.llm.openai_transport import OPENAI, openai_transport
from smb_requirement_agent.knowledge.infrastructure.llm.requirement_knowledge_adapters import (
    StructuredClarificationAnswerSuggesterAdapter,
    StructuredRequirementRelationshipClassifierAdapter,
)


class OpenAIRequirementRelationshipClassifier(StructuredRequirementRelationshipClassifierAdapter):
    def __init__(self, client: OpenAI, *, model: str, timeout_seconds: float) -> None:
        super().__init__(openai_transport(client, model, timeout_seconds), OPENAI)


class OpenAIClarificationAnswerSuggester(StructuredClarificationAnswerSuggesterAdapter):
    def __init__(self, client: OpenAI, *, model: str, timeout_seconds: float) -> None:
        super().__init__(openai_transport(client, model, timeout_seconds), OPENAI)
