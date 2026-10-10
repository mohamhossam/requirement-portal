# Changelog

Each release has a `## vX.Y.Z` section, written before the tag is pushed. The release workflow
(`.github/workflows/release.yml`, ADR-0108) refuses a tag without one and publishes the section as
the GitHub release notes. The tag must match `version` in `pyproject.toml` and
`frontend/package.json`.

Under each heading, list what changed for whoever deploys, then any upgrade step. Name every
contract-step migration (WORKSPACE.md, "Migrations"), because rolling back past one means
restoring a backup.

## v0.1.0

The first published release: the pilot candidate, closing the pilot gate of
`docs/slices/production-hardening.md`, with its shared provider limits and platform-kernel 1.3.0.

- **Production configuration fails closed.**
  - The production manifest always runs `APP_ENV=production` with OIDC sign-in.
  - A fake model, the debug trace or non-JSON logs refuse to start.
  - The API documentation is not served at the edge.
- **Analysis survives a knowledge-portal outage.** It is kept and marked "references not
  checked".
- **AI jobs retry transient outages with backoff.**
  - The waits are `AI_JOB_RETRY_FIRST_SECONDS` and `AI_JOB_RETRY_MAX_SECONDS`.
  - Exhausted jobs are labelled in metrics.
- **Model-backed work runs only as a durable job (ADR-0105).**
  - The synchronous provider routes are removed.
  - The edge's `/api/` timeout is 60 seconds.
  - Architecture mapping runs through the job routes and needs Requirement membership only.
- **Probes and shutdown.**
  - `/ready` answers within 2.5 seconds on its own threads.
  - In-flight requests get 25 seconds on a stop.
  - `web` has a healthcheck.
- **The browser keeps working through a token renewal.**
  - Requests abandoned by a sign-out or identity switch are silent.
  - A crash or a redeployed page shows a way out (ADR-0109).
- **Releases, backups, upgrade and rollback (ADR-0108).**
  - Signed images, with SBOMs, are published to `ghcr.io` by tag.
  - `/health` reports the version.
  - A `backup` service is added.
  - Migrations follow an expand/contract policy.
- **Shared provider limits, a daily token budget, and edge limits (ADR-0106).**
  - The per-person provider rate limit holds across API replicas.
  - `PROVIDER_DAILY_TOKEN_BUDGET` pauses new AI work until 00:00 UTC once spent
    (`provider_budget_exhausted`, 429). Queued jobs wait.
  - nginx limits each client address (`EDGE_RATE_PER_SECOND`, `EDGE_BURST`).
  - A deployment behind a TLS proxy must set `TRUSTED_PROXY_CIDR`.
- **Platform-kernel 1.2.0.**
  - **Sign-in.** A person's token must be an access token issued to `OIDC_CLIENT_ID`. Other
    clients are accepted only when listed in `OIDC_AUTHORIZED_PARTIES`.
  - **Clock difference.** `OIDC_LEEWAY_SECONDS` (60) of clock difference is tolerated.
  - **Issuer outages.** A brief issuer outage no longer fails sign-ins: the last good signing
    keys keep being served (ADR-0018 amendment).
  - **OpenAI.** Each reply is capped at `OPENAI_MAX_OUTPUT_TOKENS` (8192).
  - **Migrations.** A migration waits at most 10 seconds for a table lock, and concurrent
    `migrate` runs take turns.
  - **Knowledge service.** Calls pause for 30 seconds after 5 failures in a row.
- **Database sessions are bounded (ADR-0074 amendment).**
  - Pooled connections run with a 30s statement timeout, a 5s lock timeout and a 60s
    idle-transaction timeout (`DATABASE_*_TIMEOUT_SECONDS`).
  - A busy database answers 503 `database_busy`, and AI jobs retry it.
  - PostgreSQL starts with `max_connections=${POSTGRES_MAX_CONNECTIONS:-200}`; size it with
    `deployment.md`.
  - Pool use is exported as `smb_db_pool_connections`.
- **Alerting, SLOs and runbooks.**
  - The monitoring overlay adds:
    - Alertmanager, sending to `ALERTMANAGER_RECEIVER` (`none`, `webhook` or `slack`) at
      `ALERTMANAGER_URL`;
    - a PostgreSQL exporter;
    - a host exporter.
  - 18 alerts, each with a runbook in `docs/operations/alerts.md` and unit tests run by CI.
  - Proposed objectives in `docs/operations/slos.md`, for the owner to confirm.
  - New metrics: `smb_build_info`, `smb_ready`, the AI job queue (`smb_ai_jobs_queued`,
    `smb_ai_job_oldest_queued_age_seconds`), `smb_provider_spend_blocked_total`, and the
    process, Python and garbage-collector series.
- **Containers and the edge are hardened.**
  - Every container rotates its logs and has memory, CPU and process limits
    (`API_MEM_LIMIT`, `WORKER_MEM_LIMIT`, `POSTGRES_MEM_LIMIT`, `CLAMAV_MEM_LIMIT`).
  - `clamav` and `worker` have healthchecks.
  - Secrets can be read from files (`NAME_FILE`; `docs/operations/secrets.md`, with rotation
    steps), including a new `DATABASE_PASSWORD`.
  - `DATABASE_URL` can name a managed PostgreSQL as a Compose variable.
  - The edge forwards the browser's scheme only from `TRUSTED_PROXY_CIDR` and sends HSTS over
    HTTPS.
  - The API trusts forwarded headers only from the deployment's fixed subnet
    (`REQUIREMENT_SUBNET`).
  - Logs carry exception types and correlation IDs, never messages.
  - A job heartbeat rides out a brief database failure while its lease lasts.
- **Supply chain.**
  - CI scans every commit for secrets (gitleaks), and CodeQL analyses the backend, the frontend
    and the workflows.
  - Every Monday, the latest release's images are scanned again for new vulnerabilities
    (`deployment.md`, "Releases and upgrades").
  - The optional Keycloak stack pins its images by digest, restarts with the host, and now pulls
    Keycloak from Docker Hub (`keycloak/keycloak`) rather than quay.io.
  - `docs/operations/identity-provider.md` describes the two clients and the token and session
    lifetimes.
- **The browser copes with a slow or failing API, and says when it fails.**
  - Requests give up after 30 seconds, or 2 minutes for uploads and downloads. A page nobody
    shows any more stops its requests.
  - Error messages and failure notices show the request's reference (its correlation ID), to
    quote to support.
  - Browsers report crashes to `POST /api/client-errors`, by kind only, counted as
    `smb_client_errors_total`. The edge limits each address to 1 report a second.
  - One `web` image serves every deployment. `CSP_IDENTITY_ORIGINS`, `KNOWLEDGE_PORTAL_URL` and
    `KNOWLEDGE_PORTAL_ROLE` are read when the container starts, which refuses to start under OIDC
    without an issuer origin.
  - The frontend declares Node 24 (`engines`, `.nvmrc`).
- **Long lists are paged, and old job inputs are cleared.**
  - `GET /documents` and `GET /requirements/drafts` answer a page (`offset`, `limit`, `total`,
    `has_more`) with search and sort, instead of a bare list. Documents also carry their
    owner's title, the counts per state and the owners to filter by. The Documents page loads
    more on request.
  - The `retention` command also clears the stored inputs of AI jobs that succeeded or were
    cancelled more than `AI_JOB_PAYLOAD_RETENTION_DAYS` (90) ago. Job rows and history stay;
    such a job can no longer be retried (`ai_job_inputs_pruned`, 409). Knowledge screens keep
    their inputs (ADR-0079 amendment).
  - Each run also reports the document blobs' count and size, and how many nothing refers to.
    It deletes none.
- **Optional tracing (ADR-0110), with platform-kernel 1.3.0.**
  - Set `OTEL_EXPORTER_OTLP_ENDPOINT` to export OpenTelemetry traces over OTLP/HTTP. Unset (the
    default), nothing is traced. Each traced unit has one trace:
    - an API request, named by its route;
    - an AI job attempt.
  - Each trace holds that unit's SQL statements and its calls to the knowledge portal, model
    providers and the identity provider.
  - No path, query string, body, SQL value or exception message is recorded.
  - Only the knowledge portal is sent `traceparent`. The edge drops one a browser sends.
  - `OTEL_TRACES_SAMPLER_ARG` keeps a share of new traces (default all).
  - JSON log lines carry `trace_id` and `span_id` inside a kept trace.
  - The monitoring overlay adds an OpenTelemetry Collector and Grafana Tempo
    (`TEMPO_RETENTION`, 72h), with a Grafana data source.
  - FastAPI's own telemetry is off, so `OTEL_*` variables can no longer stop the API starting.
- **The browser is easier to find your way in.**
  - An address that matches no page says so, with a link to the dashboard, instead of showing
    the dashboard under a wrong address.
  - A new page takes keyboard focus, so a screen reader starts at its content. Choosing an item
    that changes the address within a page leaves focus where it is.
  - Links to Azure DevOps work items are shown only for `https:` addresses.
  - Remembering the last requirement no longer fails a save in private browsing, and
    downloads keep their file long enough for Firefox and Safari.

Upgrade: none (first release). Contract-step migrations: none after `202610091200`.
