"""Analysis's OpenRouter adapters: the shared structured adapters over the OpenRouter client."""

from __future__ import annotations

import httpx
from smb_kernel.diagnostics import DebugTrace, NullDebugTrace

from smb_requirement_agent.analysis.infrastructure.llm.local_requirement_analyzer import (
    StructuredRequirementAnalyzerAdapter,
)
from smb_requirement_agent.infrastructure.llm.openrouter_transport import (
    openrouter_client,
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
            client=openrouter_client(
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
