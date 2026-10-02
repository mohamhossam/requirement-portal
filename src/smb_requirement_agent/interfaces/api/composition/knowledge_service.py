"""Where requirement work's knowledge comes from: this process, or the knowledge service.

With KNOWLEDGE_API_BASE_URL set, library search, architecture matching, the
event feed and the read-only views all come from the knowledge service over
its internal API (ADR-0099). Unset, the knowledge code still in this process
answers, and the views have nothing to show.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass

import httpx
from smb_kernel.http.client import InternalHttpClient
from smb_kernel.observability.metrics import MeteredTransport, Metrics

from smb_requirement_agent.application.ports.architecture_knowledge import ArchitectureKnowledgePort
from smb_requirement_agent.application.ports.knowledge_events import KnowledgeEventSourcePort
from smb_requirement_agent.application.ports.knowledge_views import KnowledgeViewsPort
from smb_requirement_agent.application.ports.reference_grounding import ReferenceKnowledgePort
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.knowledge_client import (
    FakeKnowledgeViews,
    HttpArchitectureKnowledge,
    HttpKnowledgeEvents,
    HttpKnowledgeViews,
    HttpReferenceKnowledge,
)


@dataclass(frozen=True)
class KnowledgeService:
    """The remote knowledge service's adapters; `None` where this process still answers."""

    references: ReferenceKnowledgePort | None
    architecture: ArchitectureKnowledgePort | None
    events: KnowledgeEventSourcePort | None
    views: KnowledgeViewsPort

    @property
    def remote(self) -> bool:
        return self.events is not None


def build_knowledge_service(
    settings: Settings, resources: ExitStack, metrics: Metrics
) -> KnowledgeService:
    if settings.knowledge_api_base_url is None or settings.requirement_service_token is None:
        return KnowledgeService(None, None, None, FakeKnowledgeViews())
    http = resources.enter_context(
        httpx.Client(transport=MeteredTransport(metrics, "knowledge", httpx.HTTPTransport()))
    )
    client = InternalHttpClient(
        settings.knowledge_api_base_url,
        settings.requirement_service_token,
        service="knowledge",
        http=http,
    )
    return KnowledgeService(
        HttpReferenceKnowledge(client),
        HttpArchitectureKnowledge(client),
        HttpKnowledgeEvents(client),
        HttpKnowledgeViews(client),
    )
