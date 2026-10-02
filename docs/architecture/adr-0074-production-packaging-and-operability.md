# ADR 0074 — Production packaging and operability

## Status

Accepted.

## Context

The review found no deployable artefact. There were no images, the frontend had
no production server, and there was no manifest. Operational visibility was
also missing:

- The only structured record was the opt-in debug trace, which carries
  requirement text and so must stay off in production.
- Nothing measured requests, provider calls or jobs.
- Nothing bounded how many paid provider calls one user could trigger.
- Sequentially numbered migrations had already collided (`018`).

## Decision

- **One backend image, several processes.** `deploy/api/Dockerfile` builds
  from `uv.lock`. The container command chooses the API
  (`interfaces.api.serve`), worker, migrate or maintenance process. One image
  keeps every process on the same code and dependencies. `deploy/web/Dockerfile`
  serves the built app from unprivileged nginx. nginx proxies `/api/`, adds the
  headers a `<meta>` policy cannot carry (`frame-ancestors`), and sets
  `X-Request-ID` at the edge.
- **Reference manifest.** `deploy/compose.production.yaml` defines:
  - PostgreSQL and ClamAV;
  - a one-shot `migrate` that the API and worker wait for;
  - a profile-gated `maintenance`;
  - an HTTP-only API with a `/ready` healthcheck;
  - a separate worker;
  - the web proxy as the only published port.

  Every container runs read-only and non-root. CI builds both images and starts
  the manifest on every push.
- **Logs.** `infrastructure/observability/logging.py` configures stdout in the
  format set by `LOG_FORMAT` (`text` or `json`). A context-variable correlation
  ID, set per request by the middleware and per job by the worker, appears on
  every record. The API logs one line per request by route template, never by
  concrete path or query.
- **Metrics.** `infrastructure/observability/metrics.py` holds Prometheus
  instruments on a registry owned by the container. They count HTTP requests by
  route template, provider requests and AI job attempts. Provider requests are
  measured by a metered `httpx`/`httpx2` transport on every provider client the
  composition root builds. That covers every adapter without changing one. The
  exporter listens on its own port (`METRICS_PORT`), never behind the proxy.
- **Cost guard.** `ProviderCallRateLimit` (application) caps provider-calling
  operations per actor per minute (`PROVIDER_RATE_LIMIT_PER_MINUTE`). It is
  enforced by the `limit_provider_calls` dependency on every such route, and
  refused as `ProviderRateLimitExceededError` → 429 with `Retry-After`. An
  architecture test pins the set of limited routes and requires every
  `GenerationRequest` route to be in it.
  **Amended by the third review remediation:**
  - The limit also covers routes that queue automatic provider work, such
    as creating, promoting or editing a Requirement (each queues a
    knowledge screen). That was an unmetered path to spend.
  - The same work found three routes that called a model directly
    without the limit: clarification resolution (it re-analyses) and the
    two Story quality reads (they run the evaluator).
  - The architecture test now also walks each route's dependency graph.
    Any route that can reach a provider port or a job scheduler must be
    limited, or listed with the reason it calls none on that path.
- **Migrations** after `026` are named `YYYYMMDDHHMM_description.sql`, enforced
  by a test. They sort after every legacy number, so runner order is unchanged.

## Consequences

- An operator can build, install, upgrade, probe, scrape and read logs without
  reading the code (`docs/operations/deployment.md`).
- The limit is per API process. N replicas allow N times the limit. An exact
  global ceiling belongs at a gateway, or in a durable counter if it becomes a
  requirement.
- The requirement index worker re-embeds the changed text after any edit to
  the knowledge corpus, including edits through unlimited routes such as
  saving a draft answer. That spend is bounded to the changed chunks and
  by the input limits. It is recorded in AGENTS.md §19.
- Provider metrics are measured at the HTTP layer: calls, outcomes and latency.
  **Amended by the second review remediation:** the same transport now reads
  the provider-reported `usage` from each response body, and exports
  `smb_provider_tokens_total{provider, model, direction}`. That makes spend
  something you can alert on without touching an adapter. Every provider
  call is non-streaming, so the transport reads the body and the client
  reuses it.
- The web image bakes in `CSP_IDENTITY_ORIGINS`, so changing the OIDC issuer
  means rebuilding the web image.

## Alternatives Considered

- **Serve the frontend from FastAPI.** Rejected. It couples frontend releases
  to API replicas, and every static request would pass through Python.
- **Metrics on the API port.** Rejected. It exposes operational data to anyone
  who can reach the proxy, unless every proxy remembers to block it.
- **A metering decorator per LLM port.** Rejected. It would need nine
  decorators with different signatures, where one transport per client covers
  every provider.
- **A global spend ceiling in PostgreSQL.** Deferred. The per-actor limit
  covers the realistic failure (a loop or script). A durable counter would add
  a write to every provider call.
