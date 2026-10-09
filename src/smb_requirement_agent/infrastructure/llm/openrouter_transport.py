"""The OpenRouter client every context's OpenRouter adapters share.

Each context keeps its own adapters in its `infrastructure/llm/openrouter_adapters.py` (ADR-0103
Amendment 3); this module holds only what they share, so it imports no context.
"""

from __future__ import annotations

from typing import TypedDict

import httpx
from smb_kernel.diagnostics import DebugTrace, NullDebugTrace
from smb_kernel.llm.openrouter_structured_output import (
    OpenRouterStructuredOutputClient,
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


def openrouter_client(
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


def openrouter_client_from_settings(
    settings: OpenRouterAdapterSettings,
) -> OpenRouterStructuredOutputClient:
    debug_trace = settings["debug_trace"]
    return openrouter_client(
        base_url=str(settings["base_url"]),
        http_client=settings["http_client"],
        api_key=str(settings["api_key"]),
        model=str(settings["model"]),
        timeout_seconds=float(settings["timeout_seconds"]),
        max_output_tokens=int(settings["max_output_tokens"]),
        data_collection=str(settings["data_collection"]),
        debug_trace=debug_trace if debug_trace is not None else NullDebugTrace(),
    )
