# ADR 0110 — Optional tracing: requests, jobs, SQL and calls, with trace context only for peers

## Status

Accepted 2026-10-10 (production hardening PR 14). The owner chose where the mechanism lives
(platform-kernel 1.3.0), which calls carry trace context (the knowledge portal only), and a
bundled tracing backend. It extends ADR-0074's logs and metrics.

## Context

Logs and metrics say that something was slow, not where. One request can read and write
PostgreSQL several times and call the knowledge portal; one AI job calls a model provider and
the portal many times. Following that path took matching correlation IDs across log lines by
hand, and stopped at the portal's edge.

There was also a latent fault. FastAPI 0.142 has built-in telemetry that configures itself
from `OTEL_EXPORTER_OTLP_*`. An operator who set those variables would have found the API
failing to start, because the OpenTelemetry SDK was not installed. And had it been installed,
FastAPI's own spans would have recorded raw paths, query strings and exception messages.

## Decision

- **Off by default.** Tracing runs only when `OTEL_EXPORTER_OTLP_ENDPOINT` names a collector.
  With it unset, the process records nothing and sends no trace context, and log lines are
  unchanged.
- **The mechanism is the kernel's** (ADR-0100), in platform-kernel 1.3.0 and its `tracing` extra.
  - `configure_tracing` builds a `Tracing` per process: an SDK provider exporting over OTLP/HTTP.
    It installs no global provider, so tests and processes share none.
  - `TracedTransport` and `TracedTransport2` give each outbound call a client span.
  - `Tracing.request_span`, `Tracing.span` and `Tracing.instrument_connection` cover requests,
    named units of work and SQL.
  - The JSON log formatter adds `trace_id` and `span_id`.
- **What is traced:**
  - **Requests.** Each API request, except the probes, is one server span opened by the request
    middleware and named by the route template.
  - **Jobs.** Each AI job attempt is one span, `ai_job <operation>`.
  - **SQL.** Every statement on a pooled connection is traced, through the pool's `configure`
    hook.
  - **Outbound calls.** Every call to the knowledge portal, a model provider (including OpenAI,
    whose SDK uses `httpx2`) and the identity provider is traced.
- **What is never recorded:** a path, query string, header or body; SQL parameter values;
  exception messages. A failure records its type only. This is the logging rule (operational
  telemetry never carries requirement text or provider payloads) applied to spans.
- **FastAPI's built-in telemetry is switched off** (`telemetry={... "auto_configure": False}`).
  This removes the startup fault and the raw-path spans.
- **Trace context goes to peers only.**
  - The knowledge portal's client sends `traceparent`, and only when a portal is connected.
  - Model providers and the identity provider are never sent it, so a trace ID never leaves
    the platform.
  - The edge drops a browser's `traceparent` and `tracestate`, so the API starts each request's
    trace and a browser cannot force sampling.
  - The API continues a trace the knowledge portal sends on an internal call.
- **Sampling.** `OTEL_TRACES_SAMPLER_ARG` (default 1) keeps that share of new traces, and a
  sampled parent is always followed. A client span with no parent (a background loop's poll
  query) starts no trace, so polling never floods the backend.
- **A bundled backend.** The monitoring overlay adds an OpenTelemetry Collector and Grafana Tempo,
  with a Grafana data source, and points `api` and `worker` at the collector. Any other OTLP
  endpoint works in its place.

## Consequences

- **One trace per unit of work.** A slow request or job shows its SQL and calls in one trace,
  and continues into the knowledge portal when that portal traces too.
- **Two more pinned images** in the monitoring overlay. Tempo keeps 72 hours by default
  (`TEMPO_RETENTION`).
- **Every process installs the SDK**, since the kernel's `tracing` extra is a dependency. A
  process with tracing off pays a context lookup per span site, and exports nothing.
- **Outside any trace.** Ingestion and indexing loops run outside a request or job, so their
  work is traced only when it happens inside one. Their failures stay in logs and metrics.

## Alternatives Considered

- **OpenTelemetry's auto-instrumentation for FastAPI and httpx.**
  - It records paths and queries.
  - It would send `traceparent` to every host, model and identity providers included.
  - It misses OpenAI's `httpx2` client.
  - It is configured through global state.
- **Tracing in this repository only.** Rejected by the owner: correlation, logging and the
  internal client already live in the kernel (ADR-0100), and the knowledge portal needs the
  same mechanism.
- **Sending traces to any OTLP endpoint without a bundled backend.** Rejected by the owner, who
  wanted a deployment to see traces with no other service. The endpoint stays configurable.
