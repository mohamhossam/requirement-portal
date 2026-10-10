"""Optional tracing (ADR-0110): built once per process from settings, off without an endpoint."""

from __future__ import annotations

from contextlib import ExitStack

import httpx
from smb_kernel.observability.tracing import TracedTransport
from smb_kernel.observability.tracing_setup import NO_TRACING, Tracing, configure_tracing

from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.release import APPLICATION_VERSION, SERVICE_NAME

# Identity-provider calls (JWKS, service tokens) give up after this long.
IDENTITY_TIMEOUT_SECONDS = 10


def build_tracing(settings: Settings, resources: ExitStack) -> Tracing:
    """Export spans to OTEL_EXPORTER_OTLP_ENDPOINT, flushing them when `resources` closes."""
    if settings.tracing_endpoint is None:
        return NO_TRACING
    tracing = configure_tracing(
        settings.tracing_endpoint,
        service=SERVICE_NAME,
        version=APPLICATION_VERSION,
        sample_ratio=settings.tracing_sample_ratio,
    )
    resources.callback(tracing.shutdown)
    return tracing


def identity_client(tracing: Tracing) -> httpx.Client:
    """A client for the OIDC issuer: traced, but never sent the trace context."""
    return httpx.Client(
        timeout=IDENTITY_TIMEOUT_SECONDS,
        transport=TracedTransport(
            httpx.HTTPTransport(), tracer_provider=tracing.tracer_provider, peer="identity"
        ),
    )
