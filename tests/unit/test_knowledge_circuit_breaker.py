"""Calls to the knowledge service pause after repeated failures, whichever client failed.

The everyday client and the patient one for historic content call the same
peer, so they share one circuit breaker (platform-kernel 1.2.0).
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any

import httpx
import pytest
from smb_kernel.errors import ServiceUnavailableError
from smb_kernel.observability.metrics import Metrics

from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition.references import build_knowledge_service
from smb_requirement_agent.references.application.ports.historic_corpus import ContentPart


def test_failures_through_one_client_pause_the_other(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.path)
        # A 500 is not retried, so each call fails at once.
        return httpx.Response(500, json={"detail": "down"})

    def transport(**_options: Any) -> httpx.BaseTransport:
        return httpx.MockTransport(handle)

    # The composition root sends through httpx.HTTPTransport; this test answers instead.
    monkeypatch.setattr(httpx, "HTTPTransport", transport)
    settings = Settings(
        llm_provider=LLMProvider.FAKE,
        knowledge_api_base_url="http://knowledge",
        requirement_service_token="r" * 40,
    )
    with ExitStack() as resources:
        service = build_knowledge_service(settings, resources, Metrics())
        for _ in range(5):
            with pytest.raises(ServiceUnavailableError):
                service.references.has_published()
        with pytest.raises(ServiceUnavailableError, match="paused"):
            service.historic_content.page("h-1", 1, ContentPart.PASSAGES, 0, 10)

    assert len(sent) == 5
