"""The OpenAI transport every context's OpenAI adapters share.

Each context keeps its own adapters in its `infrastructure/llm/openai_adapters.py` (ADR-0103
Amendment 3); this module holds only what they share, so it imports no context.
"""

from __future__ import annotations

from openai import OpenAI
from smb_kernel.llm.openai_structured_output import (
    OpenAIStructuredOutputClient,
)

OPENAI = "OpenAI"


def openai_transport(
    client: OpenAI, model: str, timeout_seconds: float
) -> OpenAIStructuredOutputClient:
    return OpenAIStructuredOutputClient(client, model=model, timeout_seconds=timeout_seconds)
