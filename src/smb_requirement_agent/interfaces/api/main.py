"""FastAPI application assembly."""

import logging
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import ExitStack, asynccontextmanager
from dataclasses import asdict
from time import perf_counter

import anyio
import anyio.to_thread
from fastapi import FastAPI, Request, Response
from smb_kernel.http.body_limit import BodyLimits, RequestBodyLimit
from smb_kernel.http.service_auth import INTERNAL_PREFIX, InternalRouteGuard
from smb_kernel.observability.correlation import correlation_scope
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp, Receive, Scope, Send

from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition.identity import build_internal_verifier
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.error_handlers import register_error_handlers
from smb_requirement_agent.interfaces.api.routes.activity import (
    activity_router,
    report_router,
    saved_view_router,
)
from smb_requirement_agent.interfaces.api.routes.analysis import router as analysis_router
from smb_requirement_agent.interfaces.api.routes.architecture import router as architecture_router
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
from smb_requirement_agent.interfaces.api.routes.internal import router as internal_router
from smb_requirement_agent.interfaces.api.routes.jobs import (
    notification_router,
)
from smb_requirement_agent.interfaces.api.routes.jobs import (
    router as jobs_router,
)
from smb_requirement_agent.interfaces.api.routes.knowledge import router as knowledge_router
from smb_requirement_agent.interfaces.api.routes.knowledge_views import (
    router as knowledge_views_router,
)
from smb_requirement_agent.interfaces.api.routes.requirements import router as requirements_router
from smb_requirement_agent.interfaces.api.routes.review import router as review_router
from smb_requirement_agent.interfaces.api.routes.revisions import router as revisions_router
from smb_requirement_agent.interfaces.api.routes.source_impact import router as source_impact_router
from smb_requirement_agent.interfaces.api.routes.story import router as story_router
from smb_requirement_agent.interfaces.runtime import (
    APPLICATION_VERSION,
    start_metrics,
    start_workers,
    stop_workers_and_close,
)

_REQUESTS = logging.getLogger("smb_requirement_agent.http")
# A readiness probe answers within this, or reports the database unavailable.
READINESS_TIMEOUT_SECONDS = 2.5


def _route_template(request: Request) -> str:
    """The matched route's path template: a bounded metric label, free of identifiers."""
    route = request.scope.get("route")
    return str(getattr(route, "path", "unmatched"))


class InternalAccess:
    """Service access to /internal (ADR-0099, ADR-0104), configured per deployment.

    With neither KNOWLEDGE_SERVICE_TOKEN nor KNOWLEDGE_SERVICE_CLIENT_ID the
    internal API is not served: every /internal path answers 404. With either,
    the kernel's guard admits only the knowledge service, naming the caller
    "knowledge".
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self._key: tuple[object, ...] | None = None
        self._guard: InternalRouteGuard | None = None
        self._resources = ExitStack()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path: str = scope.get("path", "")
        internal = path == INTERNAL_PREFIX or path.startswith(INTERNAL_PREFIX + "/")
        if scope["type"] != "http" or not internal:
            await self._app(scope, receive, send)
            return
        guard = self._guard_for(scope["app"].state.container.settings)
        if guard is None:
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": b'{"detail":"Not Found"}'})
            return
        await guard(scope, receive, send)

    def _guard_for(self, settings: Settings) -> InternalRouteGuard | None:
        key = (
            settings.knowledge_service_token,
            settings.knowledge_service_client_id,
            settings.oidc_issuer_url,
            settings.oidc_allowed_algorithms,
        )
        if key != self._key:
            self._resources.close()
            self._resources = ExitStack()
            verifier = build_internal_verifier(settings, self._resources)
            self._guard = None if verifier is None else InternalRouteGuard(self._app, verifier)
            self._key = key
        return self._guard


def _body_limits(scope: Scope) -> BodyLimits:
    """The request and per-file ceilings, read from this app's settings per request."""
    settings = scope["app"].state.container.settings
    return BodyLimits(
        request_max_body_bytes=settings.request_max_body_bytes,
        document_max_file_bytes=settings.document_max_file_bytes,
    )


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
        # Probes get their own two threads, so a pool saturated by requests never
        # makes a healthy process look dead to its orchestrator.
        application.state.probe_threads = anyio.CapacityLimiter(2)
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
        version=APPLICATION_VERSION,
        lifespan=lifespan,
    )
    register_error_handlers(application)
    # Registered before the trace middleware, so it runs inside it: a refused
    # body still gets a correlation ID, a log line and a metric.
    application.add_middleware(RequestBodyLimit, limits=_body_limits)
    application.add_middleware(InternalAccess)

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

    # Both probes run on the event loop, never in the request thread pool.
    @application.get("/health")
    async def health() -> dict[str, str]:
        # The release a deployment runs, for checking an upgrade or rollback landed.
        return {"status": "ok", "version": APPLICATION_VERSION}

    @application.get("/ready")
    async def ready(request: Request, response: Response) -> dict[str, object]:
        container = getattr(request.app.state, "container", None)
        workers = getattr(request.app.state, "workers", {})
        persistence = False
        if container is not None:
            # The check bounds its own database wait; this bounds the whole probe.
            with anyio.move_on_after(READINESS_TIMEOUT_SECONDS):
                persistence = await anyio.to_thread.run_sync(
                    container.readiness_check,
                    abandon_on_cancel=True,
                    limiter=getattr(request.app.state, "probe_threads", None),
                )
        checks = {
            "accepting_requests": bool(getattr(request.app.state, "accepting_requests", False)),
            "persistence": persistence,
            **{name: worker.healthy for name, worker in workers.items()},
        }
        available = all(checks.values())
        if container is not None:
            container.metrics.set_ready(available)
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
        knowledge_views_router,
        source_impact_router,
        documents_router,
        analysis_router,
        epic_router,
        feature_router,
        story_router,
        revisions_router,
        architecture_router,
        review_router,
        governance_router,
    ):
        application.include_router(router)
    application.include_router(internal_router, include_in_schema=False)
    return application


app = create_app()
