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
`docs/slices/production-hardening.md`, with its shared provider limits and platform-kernel 1.2.0.

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

Upgrade: none (first release). Contract-step migrations: none after `202610091200`.
