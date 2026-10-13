# Changelog

Each release has a `## vX.Y.Z` section, written before the tag is pushed. The release workflow
(`.github/workflows/release.yml`, ADR-0108) refuses a tag without one and publishes the section as
the GitHub release notes. The tag must match `version` in `pyproject.toml` and
`frontend/package.json`.

Under each heading, list what changed for whoever deploys, then any upgrade step. Name every
contract-step migration (WORKSPACE.md, "Migrations"), because rolling back past one means
restoring a backup.

## Unreleased

- **A figure the owner gave in an answer no longer fails analysis.** The check that refuses
  numeric targets the model invents (ADR-0025) now also counts the owner's clarification answers
  and accepted or edited intent decisions as support, not only the requirement and its documents.
  Resolving a question answered with "1000 max for off-net calls" used to fail with "The service
  could not complete the request". No migration.
- **Publishing approved backlogs to Azure DevOps (Slice 12, ADR-0112).** Off by default
  (`ADO_PUBLISHER=none`). To turn it on, set `ADO_PUBLISHER=azure_devops`, `ADO_ORGANIZATION_URL`,
  `ADO_PROJECT` and `ADO_PERSONAL_ACCESS_TOKEN` (or `_FILE`), a token with Work Items read and
  write. `ADO_SQUAD_AREA_PATHS` sends each squad's Features to its board. No migration.
- **Safe republish to Azure DevOps (Slice 13, ADR-0113).** Publishing again updates the items
  already sent instead of duplicating them, and Retry continues a publication that stopped
  part-way. Migration `202610101200_backlog_publications` (expand only: a new table).

- **Product impact in analysis (ontology plan Phase 4, ADR-0115, ADR-0116).** With a knowledge
  portal linked, analysis asks it where the requirement sits (a new offering or a change to one),
  and the owner accepts, overrides or marks the verdict unknown before confirming. Breakdown
  follows the decided impact (prompts `feature-v6` and `story-v6`), review flags an undecided
  verdict, capability gaps and weak links, and publication records the verdict. Needs
  knowledge-portal v0.3.0 or later; an older one assesses nothing and blocks nothing.
  `PRODUCT_VERDICT_VALIDATED` (default `false`) stops calling the verdict a suggestion once the
  live gate has passed. No migration: the impact is stored in the analysis snapshot.
- **Decided verdicts sent back as precedents (ontology plan Phase 5).** Each accepted,
  overridden or unknown product impact is queued with the decision and delivered to the knowledge
  portal's `POST /internal/architecture/precedents`, retried until it answers. Assessments now
  carry the requirement's id, so its own decision is never its precedent. Needs knowledge-portal
  v0.4.0 or later; an older one answers 404, which is retried for about two days. Migration
  `202610111200_precedent_handoffs` (expand only: a new table).
- **What a closed Epic delivered (ontology plan Phase 7).** When an Epic this service published is
  closed or removed in Azure DevOps, its service hook
  (`POST /api/integrations/azure-devops/work-items`) queues it once per event. A worker reads its
  Features' states and sends what was delivered, what was predicted and the catalogue changes that
  implies to the knowledge portal's `POST /internal/change-requests/deliveries`, retried until it
  answers. Off until `ADO_HOOK_SECRET` (24+ characters, or `_FILE`) is set and the subscription is
  added in Azure DevOps (`docs/operations/deployment.md`, "Azure DevOps service hook"). Needs
  knowledge-portal v0.5.0 or later. Migration `202610111800_delivery_closures` (expand only: a new
  table and an index on `backlog_publications`).
- **A drafted offering for a new offering (ontology plan Phase 9).** When the knowledge portal
  suggests a new offering in a family or a new product line, it drafts the offering and its
  journey; the product impact card shows the draft, and the approved backlog sends it back
  unchanged while the decided verdict is a new offering. Export schema 1.6 adds
  `product_impact` (the decided verdict, its offering and release, and the draft) to the
  approved-backlog export and the JSON download; a knowledge portal older than v0.6.0 ignores
  it. Needs knowledge-portal v0.6.0 for the draft. No migration.
- **Production mode on one machine against the local Keycloak.** Two optional overlays,
  `deploy/keycloak/compose.local.yaml` and `deploy/compose.local-oidc.yaml`, run the Docker stack
  with `APP_ENV=production` and OIDC sign-in through `https://keycloak.localhost:8443`
  (`docs/operations/keycloak-login.md`, "Production mode on one machine"). Not for a shared
  deployment. `.gitattributes` now checks shell scripts out with LF line endings: on Windows, a
  CRLF checkout left the web container restarting with "not found". No migration.

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
- **Governance.**
  - `SECURITY.md`: report vulnerabilities privately through GitHub.
  - `CODEOWNERS` and a pull request template.
  - Four accepted risks recorded in ADR-0111: tokens in `sessionStorage`, the silent-renewal
    iframe, workspace-wide read access, and English only.
  - The repository has no licence yet.

Upgrade: none (first release). Contract-step migrations: none after `202610091200`.
