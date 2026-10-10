"""Where requirement work's knowledge comes from: the knowledge portal, or nothing.

With KNOWLEDGE_API_BASE_URL set, library search, architecture matching, the
event feed and the read-only views all come from the knowledge portal over
its internal API (ADR-0099). Unset, in development and in production alike
(ADR-0104), deterministic stand-ins answer as an unconnected portal would: no
library, one empty catalogue version, and nothing for the viewers to show.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack, closing
from dataclasses import dataclass
from time import monotonic

import httpx
from smb_kernel.http.client import CircuitBreaker, InternalHttpClient
from smb_kernel.http.client_credentials import ClientCredentialsTokenSource
from smb_kernel.observability.metrics import MeteredTransport, Metrics
from smb_kernel.observability.tracing import TracedTransport
from smb_kernel.observability.tracing_setup import Tracing
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.governance.application.ports.backlog_export import BacklogExportPort
from smb_requirement_agent.governance.application.use_cases.knowledge_handoff import (
    DeliverApprovedBacklogs,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.documents.ingestion_loop import IngestionLoop
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters
from smb_requirement_agent.interfaces.api.composition.tracing import identity_client
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgePort,
)
from smb_requirement_agent.references.application.ports.historic_corpus import (
    HistoricContentSourcePort,
)
from smb_requirement_agent.references.application.ports.knowledge_events import (
    KnowledgeEventSourcePort,
)
from smb_requirement_agent.references.application.ports.knowledge_handoff import (
    ChangeRequestInboxPort,
)
from smb_requirement_agent.references.application.ports.knowledge_views import KnowledgeViewsPort
from smb_requirement_agent.references.application.ports.reference_grounding import (
    ReferenceKnowledgePort,
)
from smb_requirement_agent.references.infrastructure.knowledge_client import (
    FakeArchitectureKnowledge,
    FakeHistoricContent,
    FakeKnowledgeEvents,
    FakeKnowledgeViews,
    FakeReferenceKnowledge,
    HttpArchitectureKnowledge,
    HttpChangeRequestInbox,
    HttpHistoricContent,
    HttpKnowledgeEvents,
    HttpKnowledgeViews,
    HttpReferenceKnowledge,
)

# Seconds to wait for a page of a historic requirement's content (≤200 entries).
HISTORIC_PAGE_TIMEOUT = 60.0


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
    # A published historic requirement's content, read a page at a time (ADR-0102).
    historic_content: HistoricContentSourcePort = FakeHistoricContent()


def build_knowledge_service(
    settings: Settings, resources: ExitStack, metrics: Metrics, tracing: Tracing
) -> KnowledgeService:
    url = settings.knowledge_service_url
    if url is None:
        return KnowledgeService(
            FakeReferenceKnowledge(),
            FakeArchitectureKnowledge(),
            FakeKnowledgeEvents(),
            FakeKnowledgeViews(),
            remote=False,
        )
    # The one peer sent the trace context, so a request's trace continues in the
    # knowledge portal (ADR-0110). With no portal connected nothing is sent at all.
    http = resources.enter_context(
        httpx.Client(
            transport=TracedTransport(
                MeteredTransport(metrics, "knowledge", httpx.HTTPTransport()),
                tracer_provider=tracing.tracer_provider,
                peer="knowledge",
                propagate=True,
            )
        )
    )
    token = _service_token(settings, resources, tracing, settings.requirement_service_token or "")
    # One breaker for the one peer: either client's failures pause both.
    breaker = CircuitBreaker()
    client = InternalHttpClient(url, token, service="knowledge", http=http, breaker=breaker)
    # A page of historic content can be large; it gets its own, more patient client.
    patient = InternalHttpClient(
        url,
        token,
        service="knowledge",
        http=http,
        timeout_seconds=HISTORIC_PAGE_TIMEOUT,
        breaker=breaker,
    )
    return KnowledgeService(
        HttpReferenceKnowledge(client),
        HttpArchitectureKnowledge(client),
        HttpKnowledgeEvents(client),
        HttpKnowledgeViews(client),
        remote=True,
        change_requests=HttpChangeRequestInbox(client),
        historic_content=HttpHistoricContent(patient),
    )


def _service_token(
    settings: Settings, resources: ExitStack, tracing: Tracing, shared: str
) -> str | Callable[[], str]:
    """How this service proves itself to the knowledge service (ADR-0099, ADR-0104).

    With its own client at the OIDC issuer, the issuer grants it short-lived
    tokens and this service holds no secret of the knowledge service's;
    otherwise it presents the shared token, `shared`.
    """
    client_id = settings.requirement_service_client_id
    secret = settings.requirement_service_client_secret
    if client_id is not None and secret is not None:
        return resources.enter_context(
            closing(
                ClientCredentialsTokenSource(
                    settings.oidc_issuer_url,
                    client_id,
                    secret,
                    client=identity_client(tracing),
                )
            )
        )
    return shared


def build_backlog_handoff_worker(
    persistence: PersistenceAdapters,
    exporter: BacklogExportPort,
    inbox: ChangeRequestInboxPort,
    clock: ClockPort,
    metrics: Metrics,
    grace_seconds: float,
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
    return IngestionLoop(
        "approved-backlogs",
        (deliver.deliver_next,),
        failed=metrics.record_ingestion_failure,
        shutdown_grace_seconds=grace_seconds,
        monotonic_seconds=monotonic,
    )
