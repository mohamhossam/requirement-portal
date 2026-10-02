"""FastAPI application assembly."""

import logging
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from time import perf_counter

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from smb_requirement_agent.infrastructure.observability.correlation import correlation_scope
from smb_requirement_agent.interfaces.api.body_limit import RequestBodyLimit
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.error_handlers import register_error_handlers
from smb_requirement_agent.interfaces.api.routes.activity import (
    activity_router,
    report_router,
    saved_view_router,
)
from smb_requirement_agent.interfaces.api.routes.analysis import router as analysis_router
from smb_requirement_agent.interfaces.api.routes.architecture import router as architecture_router
from smb_requirement_agent.interfaces.api.routes.architecture_knowledge import (
    job_router as architecture_job_router,
)
from smb_requirement_agent.interfaces.api.routes.architecture_knowledge import (
    router as architecture_knowledge_router,
)
from smb_requirement_agent.interfaces.api.routes.documents import router as documents_router
from smb_requirement_agent.interfaces.api.routes.epic import router as epic_router
from smb_requirement_agent.interfaces.api.routes.feature import router as feature_router
from smb_requirement_agent.interfaces.api.routes.governance import router as governance_router
from smb_requirement_agent.interfaces.api.routes.identity import (
    assignment_router as identity_assignment_router,
)
from smb_requirement_agent.interfaces.api.routes.identity import (
    public_router as public_identity_router,
)
from smb_requirement_agent.interfaces.api.routes.identity import (
    router as identity_router,
)
from smb_requirement_agent.interfaces.api.routes.jobs import (
    notification_router,
)
from smb_requirement_agent.interfaces.api.routes.jobs import (
    router as jobs_router,
)
from smb_requirement_agent.interfaces.api.routes.knowledge import router as knowledge_router
from smb_requirement_agent.interfaces.api.routes.library import router as library_router
from smb_requirement_agent.interfaces.api.routes.library import search_router
from smb_requirement_agent.interfaces.api.routes.organisation import (
    router as organisation_router,
)
from smb_requirement_agent.interfaces.api.routes.requirements import router as requirements_router
from smb_requirement_agent.interfaces.api.routes.review import router as review_router
from smb_requirement_agent.interfaces.api.routes.revisions import router as revisions_router
from smb_requirement_agent.interfaces.api.routes.story import router as story_router
from smb_requirement_agent.interfaces.runtime import (
    start_metrics,
    start_workers,
    stop_workers_and_close,
)

_REQUESTS = logging.getLogger("smb_requirement_agent.http")


def _route_template(request: Request) -> str:
    """The matched route's path template: a bounded metric label, free of identifiers."""
    route = request.scope.get("route")
    return str(getattr(route, "path", "unmatched"))


def create_app(container_factory: Callable[[], Container] = build_container) -> FastAPI:
    """Create one application whose complete lifecycle shares one object graph."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        container = container_factory()
        # An API replica deployed with API_BACKGROUND_WORKERS=false leaves jobs to
        # the separate worker process and must not report them as its own.
        workers = container.background_workers if container.settings.api_background_workers else {}
        application.state.container = container
        application.state.workers = workers
        application.state.accepting_requests = False
        stop_metrics = start_metrics(container)
        try:
            container.debug_trace.record(
                "application.started",
                settings=asdict(container.settings),
            )
            start_workers(workers)
            application.state.accepting_requests = True
            yield
        finally:
            application.state.accepting_requests = False
            stop_metrics()
            stop_workers_and_close(container, workers)

    application = FastAPI(
        title="SMB AI Requirement Breakdown Agent",
        lifespan=lifespan,
    )
    register_error_handlers(application)
    # Registered before the trace middleware, so it runs inside it: a refused
    # body still gets a correlation ID, a log line and a metric.
    application.add_middleware(RequestBodyLimit)

    @application.middleware("http")
    async def trace_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Trace one request without opening a database transaction around I/O."""
        supplied_id = request.headers.get("X-Request-ID", "").strip()
        correlation_id = (
            supplied_id
            if re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", supplied_id)
            else str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id
        container: Container = request.app.state.container
        trace = container.debug_trace
        started = perf_counter()
        with correlation_scope(correlation_id):
            trace.record(
                "http.request_started",
                method=request.method,
                path=request.url.path,
                query=request.url.query,
                correlation_id=correlation_id,
            )
            try:
                response: Response = await call_next(request)
            except Exception as exc:
                elapsed = perf_counter() - started
                container.metrics.record_http(
                    request.method, _route_template(request), 500, elapsed
                )
                trace.record(
                    "http.request_failed",
                    method=request.method,
                    path=request.url.path,
                    duration_ms=round(elapsed * 1000, 3),
                    error_type=type(exc).__name__,
                    error=str(exc),
                    correlation_id=correlation_id,
                )
                raise
            elapsed = perf_counter() - started
            route = _route_template(request)
            container.metrics.record_http(request.method, route, response.status_code, elapsed)
            # The route template, never the path: paths carry identifiers and
            # queries carry search text.
            _REQUESTS.info(
                "%s %s %s",
                request.method,
                route,
                response.status_code,
                extra={
                    "method": request.method,
                    "route": route,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 1),
                },
            )
            trace.record(
                "http.request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(elapsed * 1000, 3),
                correlation_id=correlation_id,
            )
        response.headers["X-Request-ID"] = correlation_id
        return response

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready")
    def ready(request: Request, response: Response) -> dict[str, object]:
        container = getattr(request.app.state, "container", None)
        workers = getattr(request.app.state, "workers", {})
        checks = {
            "accepting_requests": bool(getattr(request.app.state, "accepting_requests", False)),
            "persistence": container is not None and container.readiness_check(),
            **{name: worker.healthy for name, worker in workers.items()},
        }
        available = all(checks.values())
        response.status_code = 200 if available else 503
        return {"status": "ready" if available else "unavailable", "checks": checks}

    for router in (
        requirements_router,
        activity_router,
        report_router,
        saved_view_router,
        public_identity_router,
        identity_router,
        identity_assignment_router,
        jobs_router,
        notification_router,
        knowledge_router,
        library_router,
        search_router,
        documents_router,
        analysis_router,
        epic_router,
        feature_router,
        story_router,
        revisions_router,
        architecture_router,
        architecture_knowledge_router,
        architecture_job_router,
        organisation_router,
        review_router,
        governance_router,
    ):
        application.include_router(router)
    return application


app = create_app()
