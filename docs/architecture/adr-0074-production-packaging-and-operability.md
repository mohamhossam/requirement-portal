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

## Amendment — The manifest fails closed (2026-10-09)

Slice `production-hardening` (PR 1). The text above stays as accepted; where it differs, this
amendment governs.

`APP_ENV` and `IDENTITY_PROVIDER` used to come only from `deploy/production.env`. Both default to
development, so a settings file missing those two lines booted the reference manifest with
header-based development personas, and the demo published that on every network interface.

- **The manifest pins production.** `deploy/compose.production.yaml` sets `APP_ENV=production`
  and `IDENTITY_PROVIDER=oidc` in the backend environment, which overrides the settings file.
  A missing line now fails the boot on the missing OIDC settings instead of opening the stack.
- **The demo is an overlay.** `deploy/compose.demo.yaml` restores the development personas for a
  local demo and CI, and publishes `web` on `127.0.0.1` only.
- **Production refuses development conveniences.** With `APP_ENV=production` the settings refuse
  `LLM_PROVIDER=fake`, `DEBUG_TRACE_ENABLED=true` and any `LOG_FORMAT` other than `json`. The
  deployment preflight refuses the same fake model and debug trace under any `APP_ENV`.
- **The edge hides the API documentation.** `/api/docs`, `/api/redoc` and `/api/openapi.json`
  answer 404 at the bundled nginx, as `/api/internal` does. They stay available to a developer
  calling the API directly.
- **CI boots the manifest in production.** OIDC discovery is lazy, so the API boots, reports
  ready and refuses an unauthenticated request with a placeholder HTTPS issuer; the deployment
  job checks that, and that fake identity or the fake model is refused.

## Amendment — Bounded database sessions and a sized connection ceiling (2026-10-09)

Production hardening PR 3 (`docs/slices/production-hardening.md`), on platform-kernel 1.2.0's
pool `configure` hook and `stats()`.

**Before this amendment**
- A pooled session had no limits. A slow query, or a lock wait behind a long transaction, held a
  pool connection and its request for as long as it took.
- A forgotten open transaction held its locks indefinitely.
- PostgreSQL ran with its default connection ceiling, which nothing related to the pools.

**Decision**
- **Session limits.** Every pooled connection, in the API and the worker, gets a
  `statement_timeout` (30s), a `lock_timeout` (5s) and an `idle_in_transaction_session_timeout`
  (60s) when it is opened. Each can be configured with a `DATABASE_*_TIMEOUT_SECONDS` setting.
  - The lock timeout also bounds the Requirement advisory locks.
  - One-shot commands keep direct connections without limits.
- **A busy database is a 503.** Every adapter translates a cancelled statement (SQLSTATE 57014) or
  an abandoned lock wait (55P03) into `DatabaseBusyError`, through one helper.
  - The API answers it with 503 `database_busy`.
  - AI jobs retry it with backoff (ADR-0020).
  - Other database failures stay 500 `persistence`, including an idle transaction that lost its
    session, since that is a defect in the code holding it.
- **A sized ceiling.** The manifest starts PostgreSQL with
  `max_connections=${POSTGRES_MAX_CONNECTIONS:-200}`, and `deployment.md` gives the sizing
  formula.
- **Pool metrics.** Each process reports `smb_db_pool_connections` (by state),
  `smb_db_pool_max_connections` and `smb_db_pool_requests_waiting` from the pool on every scrape.

**Consequences**
- A request stuck behind a lock fails in seconds and says so, instead of holding a connection.
- A legitimate statement longer than 30 seconds in the API or worker needs a higher
  `DATABASE_STATEMENT_TIMEOUT_SECONDS`, or a move to a one-shot command.
