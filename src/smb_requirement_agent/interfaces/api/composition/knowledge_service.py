"""Where requirement work's knowledge comes from: the knowledge service, or offline fakes.

With KNOWLEDGE_API_BASE_URL set, library search, architecture matching, the
event feed and the read-only views all come from the knowledge service over
its internal API (ADR-0099). Unset, deterministic fakes stand in: no library,
one empty catalogue version, and nothing for the viewers to show.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass

import httpx
from smb_kernel.http.client import InternalHttpClient
from smb_kernel.observability.metrics import MeteredTransport, Metrics
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.architecture_knowledge import ArchitectureKnowledgePort
from smb_requirement_agent.application.ports.backlog_export import BacklogExportPort
from smb_requirement_agent.application.ports.knowledge_events import KnowledgeEventSourcePort
from smb_requirement_agent.application.ports.knowledge_handoff import ChangeRequestInboxPort
from smb_requirement_agent.application.ports.knowledge_views import KnowledgeViewsPort
from smb_requirement_agent.application.ports.reference_grounding import ReferenceKnowledgePort
from smb_requirement_agent.application.use_cases.knowledge_handoff import DeliverApprovedBacklogs
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.documents.ingestion_loop import IngestionLoop
from smb_requirement_agent.infrastructure.knowledge_client import (
    FakeArchitectureKnowledge,
    FakeKnowledgeEvents,
    FakeKnowledgeViews,
    FakeReferenceKnowledge,
    HttpArchitectureKnowledge,
    HttpChangeRequestInbox,
    HttpKnowledgeEvents,
    HttpKnowledgeViews,
    HttpReferenceKnowledge,
)
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters


@dataclass(frozen=True)
class KnowledgeService:
    references: ReferenceKnowledgePort
    architecture: ArchitectureKnowledgePort
    events: KnowledgeEventSourcePort
    views: KnowledgeViewsPort
    # A remote feed is polled by the knowledge event worker; the offline one is read at start.
    remote: bool
    # Where approved backlogs are handed over (ADR-0101 Amendment 2); none offline, so
    # approvals queue nothing.
    change_requests: ChangeRequestInboxPort | None = None


def build_knowledge_service(
    settings: Settings, resources: ExitStack, metrics: Metrics
) -> KnowledgeService:
    url, token = settings.knowledge_service_url, settings.requirement_service_token
    if url is None or token is None:
        return KnowledgeService(
            FakeReferenceKnowledge(),
            FakeArchitectureKnowledge(),
            FakeKnowledgeEvents(),
            FakeKnowledgeViews(),
            remote=False,
        )
    http = resources.enter_context(
        httpx.Client(transport=MeteredTransport(metrics, "knowledge", httpx.HTTPTransport()))
    )
    client = InternalHttpClient(
        url,
        token,
        service="knowledge",
        http=http,
    )
    return KnowledgeService(
        HttpReferenceKnowledge(client),
        HttpArchitectureKnowledge(client),
        HttpKnowledgeEvents(client),
        HttpKnowledgeViews(client),
        remote=True,
        change_requests=HttpChangeRequestInbox(client),
    )


def build_backlog_handoff_worker(
    persistence: PersistenceAdapters,
    exporter: BacklogExportPort,
    inbox: ChangeRequestInboxPort,
    clock: ClockPort,
    metrics: Metrics,
) -> IngestionLoop:
    """The worker handing approved backlogs to the knowledge service (ADR-0101 Amendment 2).

    Each outcome is counted as a job: delivered, retry, skipped or failed.
    """
    deliver = DeliverApprovedBacklogs(
        persistence.backlog_handoffs,
        persistence.revision_repository,
        exporter,
        inbox,
        clock,
        record=lambda outcome, seconds: metrics.record_job(
            "approved_backlog_handoff", outcome, seconds
        ),
    )
    return IngestionLoop("approved-backlogs", (deliver.deliver_next,))
