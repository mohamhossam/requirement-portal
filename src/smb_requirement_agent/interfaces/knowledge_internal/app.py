"""The knowledge service's /internal routes (ADR-0099).

Every route needs the `requirements` service token. The request and response
bodies are the shared contract values themselves: `ArchitectureQuery`,
`ArchitectureKnowledgeMatch`, `ReferenceEvidence` and `KnowledgeEvent`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query, Request
from pydantic import BaseModel, Field
from smb_kernel.http.service_auth import InternalRouteGuard, ServiceTokenVerifier

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.knowledge_events import KnowledgeEvent
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.error_handlers import register_error_handlers


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class PublishedResponse(BaseModel):
    has_published: bool


def _container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(_container)]


def create_knowledge_internal_app(
    container_factory: Callable[[], Container], requirements_token: str
) -> FastAPI:
    """The knowledge service's internal API over `container`, admitting only requirement work."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.container = container_factory()
        yield

    application = FastAPI(title="Knowledge service internal API", lifespan=lifespan)
    register_error_handlers(application)
    application.add_middleware(
        InternalRouteGuard, verifier=ServiceTokenVerifier({"requirements": requirements_token})
    )

    @application.post("/internal/architecture/match")
    def match(query: ArchitectureQuery, container: ContainerDep) -> ArchitectureKnowledgeMatch:
        return container.architecture_knowledge.match(query)

    @application.get("/internal/library/published")
    def published(container: ContainerDep) -> PublishedResponse:
        return PublishedResponse(has_published=container.reference_knowledge.has_published())

    @application.post("/internal/library/search")
    def search(body: SearchRequest, container: ContainerDep) -> list[ReferenceEvidence]:
        return list(container.reference_knowledge.search_evidence(body.query))

    @application.post("/internal/library/retrieve")
    def retrieve(body: SearchRequest, container: ContainerDep) -> list[ReferenceEvidence]:
        return list(container.reference_knowledge.retrieve(body.query))

    @application.get("/internal/events")
    def events(
        container: ContainerDep,
        after: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        return [_event(e) for e in container.knowledge_events.after(after, limit)]

    return application


def _event(event: KnowledgeEvent) -> dict[str, Any]:
    return {
        "seq": event.seq,
        "kind": event.kind,
        "subject_id": event.subject_id,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }
