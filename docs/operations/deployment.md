# Deployment

The reference deployment is `deploy/compose.production.yaml`. It runs the whole
platform on one host, every process in its own container: requirement work,
built from this repository, and the knowledge service, from the image
knowledge-portal publishes (ADR-0098, ADR-0099). Use it as it stands for a
single-host install, or as the specification to translate for Kubernetes or
another orchestrator. CI builds both images and starts this manifest, with the
knowledge service, on every push.

The Compose project is `requirement-platform`, so its containers, images and
volumes never collide with the earlier single-repository deployment
(`requirement-ai`) on the same host. Set `WEB_PORT` to publish the proxy on a
port other than 8080 while both run.

## Images and processes

| Image | Built from | Runs |
|---|---|---|
| `requirement-platform/api` | `deploy/api/Dockerfile` | Four processes, each chosen by the container command: the **API** (`python -m smb_requirement_agent.interfaces.api.serve`); the **worker** (`python -m smb_requirement_agent.interfaces.worker`); **migrate** (`python -m smb_requirement_agent.infrastructure.persistence.migrate`); and **maintenance** (`python -m smb_requirement_agent.interfaces.maintenance`). |
| `requirement-platform/web` | `deploy/web/Dockerfile` | nginx serving the built browser app, proxying `/api/` to the API, and `/knowledge-api/` and `/knowledge/` to the knowledge service. |
| `ghcr.io/mohamhossam/knowledge-api` | knowledge-portal's release workflow, pinned by `KNOWLEDGE_IMAGE_TAG` | The knowledge service's four processes: `knowledge-api`, `knowledge-worker`, `knowledge-migrate` and the one-off `knowledge-import`. |
| `ghcr.io/mohamhossam/knowledge-web` | the same release, same tag | `knowledge-web`: nginx serving the knowledge portal's browser app under `/knowledge/`. |

Both images run as non-root users on read-only root filesystems. The backend
image installs dependencies from `uv.lock` (`uv sync --locked --no-dev`).

- **API.** Runs with `API_BACKGROUND_WORKERS=false`, so it only serves HTTP.
  Scale it with `--scale api=N` behind the proxy.
- **Worker.** Runs every background worker: AI jobs, requirement indexing,
  attachment ingestion, architecture mapping jobs, and reading the knowledge
  service's events. Jobs are leased in PostgreSQL, so `--scale worker=N` is safe. The process exits
  non-zero when a worker stops being healthy, and the restart policy replaces it.
- **Migrate.** Runs to completion before the API and worker start. Migrations
  never run on application boot.
- **The knowledge service.** `knowledge-api` serves HTTP only, and
  `knowledge-worker` runs library ingestion and catalogue jobs; both scale like
  their requirement counterparts. `knowledge-migrate` runs its migrations first.
  It has its own database, `knowledge-postgres`, and shares ClamAV.
- **Web.** The only published port (8080, or `WEB_PORT`).
  - Put TLS termination in front of it.
  - The APIs, workers, both PostgreSQL servers, ClamAV and metrics ports stay on
    the private network.
  - `/internal` on either service answers 404 at the edge.
  - `/knowledge/` is the knowledge portal's browser app, served by
    `knowledge-web`. While that container is down, it answers 503 with a page
    saying the portal is not available, not a bare 502.
  - `CSP_IDENTITY_ORIGINS` reaches both apps: it is built into the `web`
    image, and `knowledge-web` reads it when it starts (its image is published
    once, so it cannot be built in). Set it in `deploy/.env` and restart
    `knowledge-web` when the issuer changes.
  - nginx passes its `$request_id` as `X-Request-ID`, so one ID links the edge
    log, the API's log line and any error body the browser receives.

## First install

The backend image installs `smb-platform-kernel` (ADR-0100) from its private repository.
Before any `build`, export a fine-grained, read-only token for `mohamhossam/platform-kernel`
as `KERNEL_READ_TOKEN`. Compose passes it to the build as a BuildKit secret, so it is never
stored in an image layer:

```bash
export KERNEL_READ_TOKEN=...   # Contents: read-only on platform-kernel
```

The knowledge service's image is private on ghcr.io. Sign in once with a token
that can read packages:

```bash
echo "$GHCR_READ_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
```

Compose reads its own variables from the shell or from `deploy/.env`
(git-ignored). Generate each secret, for example with `openssl rand -hex 32`:

```bash
# deploy/.env
POSTGRES_PASSWORD=...              # requirement work's database
KNOWLEDGE_POSTGRES_PASSWORD=...    # the knowledge service's database
REQUIREMENT_SERVICE_TOKEN=...      # 32+ characters; requirement work presents it
KNOWLEDGE_SERVICE_TOKEN=...        # 32+ characters; the knowledge service presents it
KNOWLEDGE_IMAGE_TAG=v0.1.0         # a knowledge-portal release
CSP_IDENTITY_ORIGINS=https://login.example.com   # the OIDC issuer origin
```

```bash
cp deploy/production.env.example deploy/production.env   # fill in every blank; git-ignored
cp deploy/knowledge.env.example deploy/knowledge.env     # fill in every blank; git-ignored
docker compose -f deploy/compose.production.yaml pull knowledge-api knowledge-web
docker compose -f deploy/compose.production.yaml build
docker compose -f deploy/compose.production.yaml run --rm maintenance
docker compose -f deploy/compose.production.yaml up -d
```

`run --rm maintenance` applies migrations first (it depends on `migrate`), then
rebuilds the derived projections and records the maintenance marker. `/ready`
refuses traffic until that marker exists. On an empty database it takes
seconds.

`CSP_IDENTITY_ORIGINS` is built into the page's Content-Security-Policy. If it
is missing, the browser blocks the OIDC sign-in and token calls. Rebuild the web
image when the issuer changes.

## Moving knowledge from an earlier system

A new install starts with an empty library and the knowledge service's initial
catalogue; skip this section. To carry over an earlier system's library and
catalogues, restore its database backup into this platform's requirements
database first (the earlier system's own database is never written). Then:

```bash
docker compose -f deploy/compose.production.yaml run --rm maintenance
docker compose -f deploy/compose.production.yaml run --rm knowledge-import
```

`maintenance` runs requirement work's migrations, which move attachments out of
the library tables. `knowledge-import` copies the library, the architecture and
squad catalogues and their blobs into the knowledge database, keeping every id,
then compares every table (`--verify`). It is safe to repeat. Run it before the
APIs and workers start.

## Dropping the moved knowledge tables

A fresh install never keeps the library, catalogue and event tables the
knowledge service now owns: requirement work's earlier migrations still create
them, and its last migration drops them again while every one is empty. Nothing
here reads or writes them.

A database moved from an earlier system keeps them all while any holds rows, so
`knowledge-import` can copy them. Once it has finished, drop them, with the
platform stopped:

```bash
docker compose -f deploy/compose.production.yaml run --rm drop-knowledge-tables
```

It checks every table first and drops all of them or none. An empty table is
dropped. A table holding rows is dropped only when the knowledge database holds
an identical copy (the same row count and content checksum); otherwise the
command lists what would be lost, drops nothing and exits non-zero. Tables
already gone are skipped, so it is safe to repeat. To see the report without
dropping anything:

```bash
docker compose -f deploy/compose.production.yaml run --rm drop-knowledge-tables --dry-run
```

## Knowledge admins

Only actors with the `knowledge_admin` role open the knowledge portal, and only
they see the link to it in requirement work. Everyone else keeps the read-only
passage and evidence views.

- **Keycloak** (`deploy/keycloak/`): add the person to the `knowledge-admins`
  group. The realm puts realm roles in each access token's `roles` claim
  (`OIDC_ROLES_CLAIM`, default `roles`), for both browser clients:
  `requirement-spa` (audience `requirement-api`) and `knowledge-spa` (audience
  `knowledge-api`, signing in under `/knowledge/`). Set `KNOWLEDGE_APP_ORIGIN`
  when the portal is served from another origin than requirement work.
- **Another identity provider:** issue `knowledge_admin` in the claim
  `OIDC_ROLES_CLAIM` names, and register a second public client for the portal.
- **Offline (fake identity):** Amina Owner and Ravi Reviewer are knowledge
  admins in both portals; Omar Observer is not.

Architecture mapping in requirement work checks two more roles, also granted by
group in the Keycloak realm:

| Group | Roles | Allows |
|---|---|---|
| `knowledge-readers` | `knowledge_reader` | Starting and reading architecture mapping jobs on Requirements the person works on |
| `knowledge-maintainers` | `knowledge_reader`, `knowledge_maintainer` | Also cancelling and retrying other people's mapping jobs |

Without `knowledge_reader`, a signed-in member cannot map a Requirement's
architecture. Offline, Amina Owner has both roles, Ravi Reviewer is a reader,
and Omar Observer has neither.

## Model files

The backend image holds no configuration files, and its root filesystem is
read-only. The manifest bind-mounts one host directory, read-only, into
every backend container (`api`, `worker`, `migrate`, `maintenance`,
`retention`):

| Host directory | Default | Mounted at | Setting that names the file |
|---|---|---|---|
| `LLM_CONFIG_DIR` | `config/` | `/app/config` | `LLM_CONFIG_PATH=/app/config/llm.yaml`, only when you use model profiles |
| `KNOWLEDGE_LLM_CONFIG_DIR` | `config/` | `/app/config` in the knowledge containers | the same, in `deploy/knowledge.env` |

- **Model profiles.** The default mounts the repository's `config/`. To keep
  your own profiles outside the checkout, set `LLM_CONFIG_DIR`. Setting
  `LLM_CONFIG_PATH` selects the profiles, and `LLM_PROVIDER` is then ignored;
  the profiles' API keys go in `production.env`.

`LLM_CONFIG_DIR` is read by Compose, not by the application: put it in
`deploy/.env` with `POSTGRES_PASSWORD`, or export it in the shell that runs `docker compose`, and use absolute paths (a relative path resolves from
`deploy/`). A directory that does not exist stops the start with a mount
error. The containers run as uid 10001, so the files must be readable by that
user. Restart the backend containers after replacing a file. Changing the
embedding model also means building and publishing the architecture catalogue
again: mapping refuses an index built with another model (ADR-0082).

```bash
export LLM_CONFIG_DIR=/etc/requirement-ai               # optional; holds llm.yaml
```

## Upgrades

```bash
docker compose -f deploy/compose.production.yaml build
docker compose -f deploy/compose.production.yaml up -d
```

To move to a knowledge-portal release, change `KNOWLEDGE_IMAGE_TAG` and
`pull knowledge-api knowledge-web` first. `up` re-runs `migrate` and `knowledge-migrate`
before recreating the APIs and workers. Run
`maintenance` again only when a release's notes require it, and follow
`production-readiness-maintenance.md`: stop the API and every worker first, and
never run it against live traffic.

New migrations are named `YYYYMMDDHHMM_description.sql` (UTC); see
`WORKSPACE.md`.

## Retention

Read notifications are deleted after `NOTIFICATION_RETENTION_DAYS` (default 90)
by an online command. It is safe to run with the API and workers live.
Schedule it, for example daily:

```bash
docker compose -f deploy/compose.production.yaml run --rm retention
```

AI jobs are never deleted: they are the activity feed's record of AI work
(ADR-0079). The browser's job and notification lists are bounded to the
newest 100, so their cost does not grow with a workspace's age.

## Health

| Probe | Meaning |
|---|---|
| `GET /api/health` | The process is serving HTTP. |
| `GET /api/ready` | The API accepts requests, the schema is at the newest packaged migration, the maintenance marker exists, and (when the API runs them) its background workers are healthy. The compose healthcheck uses it. |
| `GET /knowledge-api/ready` | The same for the knowledge service; `web` waits for both. |

## Logs

Set `LOG_FORMAT=json` (the manifest does) for one JSON object per line on
stdout. Fields:

- `timestamp`, `level`, `logger` and `message`;
- `correlation_id`: the request's `X-Request-ID`, or `job:<id>` inside an AI
  job;
- event fields:
  - `smb_requirement_agent.http` logs one line per request, with `method`,
    `route`, `status` and `duration_ms`;
  - `smb_requirement_agent.ai_jobs.worker` logs one line per job attempt, with
    `job_id`, `operation`, `status` and `duration_ms`.

`route` is the path template (`/requirements/{requirement_id}`), never the
concrete path, and query strings are never logged. Operational logs contain no
requirement text or provider payloads. Those appear only in the opt-in debug
trace (`DEBUG_TRACE_ENABLED`), which must stay off in production.

## Metrics

Each API and worker container serves Prometheus metrics on `:9464/metrics`
(`METRICS_PORT`, `METRICS_HOST`). The exporter is a separate listener, so it can
never be reached through the proxy. Scrape each container.

| Metric | Labels | Meaning |
|---|---|---|
| `smb_http_requests_total` | `method`, `route`, `status` | Requests by route template; unknown paths share `route="unmatched"`. |
| `smb_http_request_duration_seconds` | `method`, `route` | Request latency. |
| `smb_provider_requests_total` | `provider`, `operation`, `outcome` | Every HTTP request to an AI provider. `operation` is `generation`, `embeddings` or `other`; `outcome` is `2xx`/`4xx`/`5xx`/`error`. |
| `smb_provider_request_duration_seconds` | `provider`, `operation` | Provider latency, to the end of the response body. |
| `smb_provider_tokens_total` | `provider`, `model`, `direction` | Tokens the provider reported consuming (`usage` in its response); `direction` is `input` or `output`. Multiply by your price per token for spend. |
| `smb_ai_jobs_total` | `operation`, `status` | Job attempts by resulting status. |
| `smb_ai_job_duration_seconds` | `operation` | Job attempt duration. |

Suggested alerts:
- a rising rate of `smb_provider_requests_total` with `outcome` of `4xx` or
  `error` (quota, authentication or outage);
- `smb_ai_jobs_total{status="failed"}`;
- the rate of `smb_provider_tokens_total` against a daily token budget, which
  is the direct spend signal;
- `status="429"` in `smb_http_requests_total` (the rate limit is biting);
- `smb_http_request_duration_seconds` p95 on generation routes.

### Monitoring add-on (Prometheus and Grafana)

`deploy/compose.monitoring.yaml` is an optional overlay that collects and
shows these metrics. It adds two containers:

- **Prometheus** scrapes every `api`, `worker`, `knowledge-api` and
  `knowledge-worker` container through Docker's DNS, so `--scale` needs no
  configuration change. The dashboard shows requirement work. It evaluates the alerts
  above (`deploy/monitoring/prometheus/alerts.yml`) and keeps 15 days of data
  (`PROMETHEUS_RETENTION`). It is not published.
- **Grafana** opens on the provisioned **Requirement AI — overview**
  dashboard: API traffic and slow routes, provider requests, latency and
  tokens by model, and AI job outcomes. It is published on
  `127.0.0.1:3000` only (`GRAFANA_PORT`); sign in as `admin`.

```bash
export GRAFANA_ADMIN_PASSWORD=...        # used when Grafana first creates its database
docker compose -f deploy/compose.production.yaml -f deploy/compose.monitoring.yaml up -d
```

Pass both `-f` files to every command for these containers (`ps`, `logs`,
`down`). The dashboard and data source are read-only in the UI: change
`deploy/monitoring/` and restart Grafana. Grafana runs on a read-only root with its plugin
preinstaller off, so it uses the plugins in the pinned image and never updates them online.
`tests/architecture/test_monitoring_metrics.py`
fails when a panel or alert names a metric the application does not export,
and CI starts the overlay and checks that all four exporters are scraped.

Before relying on it in production:

- **Alert delivery.** Firing alerts are visible in Grafana (Alerting > Alert
  rules) and Prometheus, but nothing is sent until you add an Alertmanager or
  point Prometheus at an existing one.
- **Thresholds.** Set `DailyTokenBudgetExceeded` to your own daily budget and
  tune the others to your traffic.
- **Access.** Put Grafana behind TLS and your identity provider before
  exposing it beyond the host.
- **An existing stack.** If your organization already runs Prometheus, skip
  the overlay: scrape `:9464` on each `api` and `worker` container and import
  `deploy/monitoring/grafana/dashboards/requirement-ai.json`.

## Rate limiting

`PROVIDER_RATE_LIMIT_PER_MINUTE` caps how many provider-calling operations one
actor may start per minute. They include:
- generation, analysis and clarification resolution;
- AI jobs, knowledge search, Story quality checks, architecture mapping and
  index builds;
- the actions that queue automatic provider work: creating, promoting or
  editing a Requirement, asking a clarification question, and deciding
  knowledge findings or intent proposals.

`tests/architecture/test_provider_rate_limit.py` lists the routes. Refusals
return 429 with `Retry-After` and code `provider_rate_limited`. Size the limit
for the busiest author: bulk-creating Requirements counts one call per
Requirement.

The count is kept per API process. With `N` API replicas an actor can reach `N`
times the limit. Enforce an exact global ceiling at a gateway if you need one.

## Internal API

The knowledge service reads a few things from this service over `/internal`
(ADR-0099):
- a document's dependents and impact, for its owner;
- mapping counts per catalogue release;
- actor details for ownership transfers.

- **Off by default.** Every `/internal` path answers 404 until
  `KNOWLEDGE_SERVICE_TOKEN` is set. The reference deployment sets it, from `deploy/.env`.
- **Turning it on.** Set it to a random secret of 32 characters or more, and give the same
  value to the knowledge service. The manifest passes both tokens to both services. Requests must then carry `Authorization: Bearer <token>`;
  no user sign-in is involved.
- **Never public.** The bundled nginx answers 404 for `/api/internal` and
  `/knowledge-api/internal` whatever the tokens hold, and the CI deployment job checks both.

## Reaching the knowledge service

This service reads from the knowledge service over its internal API (ADR-0099): library search
and retrieval, architecture matching, the knowledge event feed, and the read-only viewers'
passages and evidence.

- **Configure both or neither:** `KNOWLEDGE_API_BASE_URL` (for example
  `http://knowledge-api:8000`) and `REQUIREMENT_SERVICE_TOKEN`, the secret this service
  presents. It is 32+ characters, and the knowledge service holds the same value. Startup
  refuses one without the other.
- **Neither set (development only):** deterministic fakes stand in, with no library, one
  empty catalogue version (`offline-catalogue`), and nothing for the viewers to show.
  `APP_ENV=production` refuses to start this way.
- **Gone from this service:** the library, the architecture and squad catalogues, their
  routes (`/library/*`, `/architecture-knowledge/*`, `/organisation/*`, `/jobs/*`,
  `/knowledge/search`) and their worker. They live in the knowledge portal. A Requirement's
  source impact is read and decided under `/requirements/{id}/source-impact`; the old
  `/library/requirements/{id}/source-impact` and `/library/source-impact/{id}/decisions`
  paths are gone.
- **Architecture mapping jobs** are read, cancelled and retried under
  `/requirements/{id}/architecture-mapping/jobs/{job_id}`.
- **`KNOWLEDGE_EVALUATION_APPROVED`** is no longer read here. The knowledge service holds that
  production gate for the models that do the matching.
- **Catalogue version names:** the local copy of the active catalogue release now records
  its name too (`202610021500_active_release_name.sql`). The read-only views read
  `GET /architecture/active-release`.

## Image updates

- **Pinning.** Base and service images are pinned by digest. Dependabot opens
  weekly pull requests to move the pins.
- **Scanning.** CI scans both images with Trivy and fails on fixable HIGH or
  CRITICAL vulnerabilities.
- **Patches.** The web image applies Alpine security updates at build time.

Rebuild and redeploy when those pull requests merge, even if no application
code changed (ADR-0077).

## Not included

- **TLS termination.** Put a load balancer or reverse proxy in front of `web`.
- **The model servers.** Point `LLM_PROVIDER` (or the model profiles) at the
  models you run or subscribe to. Architecture mapping uses the same knowledge
  model and embedding as the rest of the application.
- **OCR and office previews.** The image omits the optional `document-ocr` extra
  (docling) and LibreOffice. Extend the image if you need
  `LIBRARY_OCR_ARTIFACTS_PATH` or `DOCUMENT_OFFICE_PREVIEW_EXECUTABLE`.
- **Backups.** Back up the `postgres_data` and `knowledge_postgres_data`
  volumes, or use managed PostgreSQL servers and point each service's
  `DATABASE_URL` at its own.

- **Identity.** `deploy/keycloak/` is a development identity provider, not a
  production one.
