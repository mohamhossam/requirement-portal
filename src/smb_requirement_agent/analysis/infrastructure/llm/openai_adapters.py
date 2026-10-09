"""Analysis's OpenAI adapters: the shared structured adapters over the OpenAI transport."""

from __future__ import annotations

from openai import OpenAI
from smb_kernel.diagnostics import DebugTrace, NullDebugTrace

from smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer import (
    StructuredRequirementAnalyzerAdapter,
)
from smb_requirement_agent.infrastructure.llm.openai_transport import OPENAI, openai_transport


class OpenAIRequirementAnalyzer(StructuredRequirementAnalyzerAdapter):
    def __init__(
        self,
        client: OpenAI,
        *,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        resolved_trace = debug_trace if debug_trace is not None else NullDebugTrace()
        super().__init__(
            client=openai_transport(client, model, timeout_seconds, max_output_tokens),
            provider_name=OPENAI,
            vision_enabled=True,
            vision_error="The configured OpenAI model does not accept image evidence.",
            debug_trace=resolved_trace,
        )
