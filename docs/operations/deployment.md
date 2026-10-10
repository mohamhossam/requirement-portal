# Deployment

The reference deployment is `deploy/compose.production.yaml`. It runs requirement work on one
host, every process in its own container: a release's published images, pulled by tag, or a
build from this repository (ADR-0108, "Releases and upgrades"). Use it as it stands for a
single-host install, or as the specification to translate for Kubernetes or another
orchestrator.

The knowledge portal deploys on its own, from knowledge-portal's repository and the images its
releases publish (ADR-0104). Requirement work runs without it; "Connecting the knowledge portal"
links the two. CI builds both images and starts this manifest beside the knowledge portal's
pinned release, on every push.

The manifest always runs in production mode: it sets `APP_ENV=production` and
`IDENTITY_PROVIDER=oidc` itself, so a line missing from `production.env` cannot
open the stack to the development personas. With `APP_ENV=production` the API,
worker and one-shot commands also refuse `LLM_PROVIDER=fake`,
`DEBUG_TRACE_ENABLED=true` and any `LOG_FORMAT` other than `json`, naming the
setting. `deploy/compose.demo.yaml` is the local demo overlay (development
personas, published on `127.0.0.1` only); never deploy with it.

The Compose project is `requirement-platform`, so its containers, images and
volumes never collide with the earlier single-repository deployment
(`requirement-ai`) on the same host. Set `WEB_PORT` to publish the proxy on a
port other than 8080 while both run.

## Images and processes

A release publishes them as `ghcr.io/mohamhossam/requirement-api` and
`ghcr.io/mohamhossam/requirement-web-production`; a local build names them as below.

| Image | Built from | Runs |
|---|---|---|
| `requirement-platform/api` | `deploy/api/Dockerfile` | Four processes, each chosen by the container command: the **API** (`python -m smb_requirement_agent.interfaces.api.serve`); the **worker** (`python -m smb_requirement_agent.interfaces.worker`); **migrate** (`python -m smb_requirement_agent.infrastructure.persistence.migrate`); and **maintenance** (`python -m smb_requirement_agent.interfaces.maintenance`). |
| `requirement-platform/web` | `deploy/web/Dockerfile` | nginx serving the built browser app and proxying `/api/` to the API. At start it writes this deployment's issuer origins and knowledge-portal link into the page (`CSP_IDENTITY_ORIGINS`, `KNOWLEDGE_PORTAL_URL`, `KNOWLEDGE_PORTAL_ROLE`), so one image serves every deployment. |

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
- **Web.** The only published port (8080, or `WEB_PORT`).
  - Put TLS termination in front of it.
  - The API, worker, PostgreSQL, ClamAV and metrics ports stay on the private
    network.
  - `/internal` answers 404 at the edge, and so does the API's generated
    documentation (`/api/docs`, `/api/redoc`, `/api/openapi.json`).
  - `/knowledge-api/` answers 404, and `/knowledge/` redirects old bookmarks to
    the knowledge portal's own address for one release (see "Connecting the
    knowledge portal").
  - `CSP_IDENTITY_ORIGINS` names the OIDC issuer for the page's Content-Security-Policy. The
    `web` container reads it when it starts, so set it in `deploy/.env`.
  - nginx passes its `$request_id` as `X-Request-ID`, so one ID links the edge
    log, the API's log line and any error body the browser receives.
  - The scheme the browser used reaches the API as `X-Forwarded-Proto`. The edge believes it only
    from the TLS proxy (`TRUSTED_PROXY_CIDR`). It sends `Strict-Transport-Security` (one year)
    only over HTTPS.
  - The API believes `X-Forwarded-*` only from the deployment's own network, a fixed subnet
    (`REQUIREMENT_SUBNET`, default `172.30.80.0/24`). A peer on another network, such as the
    knowledge portal on `compose.peer.yaml`'s network, cannot set them.
    - Change the subnet if it overlaps a network on the host.
    - A deployment that existed before this subnet must run `docker compose down` once (volumes
      are kept) so the network is recreated.

### Limits, health and logs

Every container rotates its log: five files of 10 MB each. Each one has memory, CPU and process
limits, so one runaway container cannot starve the host.

| Container | Memory | CPUs | Processes |
|---|---|---|---|
| `api` | `API_MEM_LIMIT` (2g) | 2 | 512 |
| `worker` | `WORKER_MEM_LIMIT` (3g); document extraction runs inside it | 2 | 1024 |
| `postgres` | `POSTGRES_MEM_LIMIT` (2g) | 2 | 512 |
| `clamav` | `CLAMAV_MEM_LIMIT` (4g); clamd holds its signatures twice while reloading | 1 | 256 |
| `web` | 256m | 1 | 128 |
| `migrate`, `maintenance`, `retention`, `backup` | 1g | 1 | 256 (128 for `backup`) |

- The memory limits are Compose variables; set them in `deploy/.env`.
- Docker refuses a CPU limit above the host's CPU count, so the host needs at least 2 CPUs.
- A container that reaches its limit is stopped by the kernel and restarted by Compose.
  `ProcessMemoryHigh` warns at 80% of the API's and worker's defaults; change its thresholds in
  `alerts.yml` with the limits.

Healthchecks:
- `api`: `/ready`.
- `worker`: its exporter reports `smb_ready 1`, meaning every background worker is running.
- `clamav`: `clamdcheck.sh`, allowing 10 minutes for the first signature download.
- `postgres`: `pg_isready`.
- `web`: nginx serves the app.

## First install

The backend image installs `smb-platform-kernel` (ADR-0100) from its private repository.
Before any `build`, export a fine-grained, read-only token for `mohamhossam/platform-kernel`
as `KERNEL_READ_TOKEN`. Compose passes it to the build as a BuildKit secret, so it is never
stored in an image layer:

```bash
export KERNEL_READ_TOKEN=...   # Contents: read-only on platform-kernel
```

Compose reads its own variables from the shell or from `deploy/.env`
(git-ignored). Every secret, how it can be read from a file instead (`NAME_FILE`), and how to
rotate it, is in `secrets.md`. Generate each secret, for example with `openssl rand -hex 32`:

```bash
# deploy/.env
POSTGRES_PASSWORD=...              # requirement work's database
CSP_IDENTITY_ORIGINS=https://login.example.com   # the OIDC issuer origin
KNOWLEDGE_PORTAL_URL=https://knowledge.example.com/knowledge/   # optional; ends in /
```

```bash
cp deploy/production.env.example deploy/production.env   # fill in every blank; git-ignored
docker compose -f deploy/compose.production.yaml build
docker compose -f deploy/compose.production.yaml run --rm maintenance
docker compose -f deploy/compose.production.yaml up -d
```

To install a release instead of building, name its images in `deploy/.env` (see "Releases and
upgrades") and replace `build` with `pull`, adding `--no-build` to `run` and `up`. No
`KERNEL_READ_TOKEN` is needed then.

`run --rm maintenance` applies migrations first (it depends on `migrate`), then
rebuilds the derived projections and records the maintenance marker. `/ready`
refuses traffic until that marker exists. On an empty database it takes
seconds.

`CSP_IDENTITY_ORIGINS` goes into the page's Content-Security-Policy. Without it the browser
would block the OIDC sign-in and token calls, so the `web` container refuses to start under
OIDC when it is empty. The container writes it, with `KNOWLEDGE_PORTAL_URL` and
`KNOWLEDGE_PORTAL_ROLE`, into the page each time it starts (`deploy/web/render-index.sh`), so
one `web` image serves every deployment. Restart `web` after changing any of them; nothing needs
rebuilding.

Before opening the edge to users, run the preflight with the deployment's
settings. It exits 2, naming the setting, while identity is not OIDC or the fake
model or the debug trace is configured:

```bash
docker compose -f deploy/compose.production.yaml run --rm api \
  python -m smb_requirement_agent.interfaces.deployment_preflight
```

## Knowledge tables left behind

Requirement work's earlier migrations create the library, catalogue and event tables the
knowledge portal owns. The last two drop them again while every one is empty, and stop the
upgrade if any is left (ADR-0104). A fresh install, or one whose tables were already moved,
never sees this.

An upgrade that stops with "Knowledge tables still hold rows" changes nothing: the upgrade
runs in one transaction. Those rows were never copied to the knowledge portal. The commands
that move them were removed with this check, so use the last versions that have them:

1. With knowledge-portal `v0.2.0`'s image, copy the rows into the knowledge portal's
   database and compare every table:
   `knowledge-portal import --source-database-url postgresql://…/requirements --verify`.
2. Back up the requirements database.
3. With requirement-portal at commit `d3ee708`, drop the tables. It drops all of them or
   none, and a table holding rows only when the knowledge database holds an identical copy:
   `docker compose -f deploy/compose.production.yaml run --rm drop-knowledge-tables
   --knowledge-database-url=postgresql://…/smb_knowledge`.
4. Upgrade again.

## Knowledge admins

Only actors with the `knowledge_admin` role open the knowledge portal, and only
they see the link to it in requirement work. Everyone else keeps the read-only
passage and evidence views.

- **Keycloak:** the knowledge portal defines its client, audience, roles and groups in its own
  repository (`deploy/keycloak/`) and adds them to the shared realm (ADR-0104); this realm
  file holds only requirement work's. Add the person to the `knowledge-admins` group there.
  `requirement-spa` puts realm roles in each access token's `roles` claim
  (`OIDC_ROLES_CLAIM`, default `roles`), so the link follows the same group.
- **Another identity provider:** issue `knowledge_admin` in the claim
  `OIDC_ROLES_CLAIM` names.
- **Offline (fake identity):** Amina Owner and Ravi Reviewer are knowledge
  admins in both portals; Omar Observer is not.

`KNOWLEDGE_PORTAL_ROLE` (in `deploy/.env`, read when `web` starts) names another role for the
link, or, set empty, shows it to everyone signed in and leaves the decision to the portal.

Any member of a Requirement may map its architecture; anyone signed in may read
the mapping jobs (ADR-0104 amendment, 2026-10-09). One role of requirement work's
own is granted by group in the Keycloak realm:

| Group | Role | Allows |
|---|---|---|
| `architecture-maintainers` | `architecture_maintainer` | Cancelling and retrying other people's mapping jobs |

The knowledge portal's `knowledge_reader` and `knowledge_maintainer` grant
nothing here. The earlier `architecture_reader` role and `architecture-readers`
group are no longer checked; a realm imported before this can keep or delete
them. Offline, Amina Owner is a maintainer.

## Model files

The backend image holds no configuration files, and its root filesystem is
read-only. The manifest bind-mounts one host directory, read-only, into
every backend container (`api`, `worker`, `migrate`, `maintenance`,
`retention`):

| Host directory | Default | Mounted at | Setting that names the file |
|---|---|---|---|
| `LLM_CONFIG_DIR` | `config/` | `/app/config` | `LLM_CONFIG_PATH=/app/config/llm.yaml`, only when you use model profiles |

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

## Releases and upgrades

A release is a tag `vX.Y.Z` with a section in `CHANGELOG.md` (ADR-0108). Its workflow,
`.github/workflows/release.yml`, first runs every CI gate on the tagged commit. It refuses a
tag that differs from `pyproject.toml` or `frontend/package.json`. Then it builds each image
once and publishes it:

| Image | For |
|---|---|
| `ghcr.io/mohamhossam/requirement-api:vX.Y.Z` | Every deployment: the API, worker and one-shot commands |
| `ghcr.io/mohamhossam/requirement-web-production:vX.Y.Z` | Every deployment. Its Content-Security-Policy and links come from the container's `CSP_IDENTITY_ORIGINS`, `KNOWLEDGE_PORTAL_URL` and `KNOWLEDGE_PORTAL_ROLE` when it starts. |

Each image is:
- scanned by Trivy, which refuses fixable HIGH or CRITICAL findings;
- signed with cosign (keyless, through GitHub's OIDC identity);
- published with an SPDX SBOM, attested to the image and attached to the GitHub release.

The release notes name both digests. `GET /api/health` reports the version a deployment runs.

A clean scan at release time does not stay clean: new vulnerabilities are published for packages
an image already ships. Every Monday, `.github/workflows/rescan.yml` scans the latest release's
two images again with the same Trivy rules (run it by hand from the Actions tab at any time).
- **Green:** nothing to do.
- **Red:** a fix exists for a HIGH or CRITICAL finding in what the release ships. The run's log
  names the package. Cut a patch release (`vX.Y.Z+1`), whose fresh build picks up the fixed
  package, and upgrade to it. GitHub emails the repository's owner when a scheduled run fails.

Run a release by naming it in `deploy/.env`:

```bash
# deploy/.env
REQUIREMENT_API_IMAGE=ghcr.io/mohamhossam/requirement-api
REQUIREMENT_WEB_IMAGE=ghcr.io/mohamhossam/requirement-web-production
IMAGE_TAG=v0.1.0
```

Optionally verify the signature first:

```bash
cosign verify ghcr.io/mohamhossam/requirement-api:$IMAGE_TAG \
  --certificate-identity-regexp 'https://github.com/mohamhossam/requirement-portal/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

A version bump changes `frontend/openapi.json`, whose `info.version` comes from the package.
Regenerate it in the bump commit: `python scripts/dump_openapi.py`.

### Upgrade

1. **Read the notes.** Check the new release's `CHANGELOG.md` section for upgrade steps, a
   required `maintenance` run, and contract-step migrations.
2. **Back up.** Run `docker compose -f deploy/compose.production.yaml run --rm backup`, then
   copy the new dump off the host (`backup-restore.md`).
3. **Pull.** Set `IMAGE_TAG` to the new release and run
   `docker compose -f deploy/compose.production.yaml pull`.
4. **Start.** Run `docker compose -f deploy/compose.production.yaml up -d --no-build`.
   `migrate` runs to completion before the API and worker are recreated. Then check that
   `/api/health` names the new version and `/api/ready` answers 200.

   A second `migrate` started meanwhile waits for the first, then finds nothing left to do.
   A migration waits at most 10 seconds for a table lock held by live traffic, then fails.
   The run is one transaction, so the database is left as it was. Run `up -d` again at a
   quieter moment.

Run `maintenance` only when a release's notes require it, and follow
`production-readiness-maintenance.md`: stop the API and every worker first, and never run it
against live traffic.

A deployment that builds from source runs `build` and then `up -d` at the release's tag instead
of `pull`.

### Rollback

- **No contract step since the previous release** (the usual case). Set `IMAGE_TAG` back to the
  previous release, then `pull` and `up -d --no-build`.
  - The newer release's migrations stay applied. They only added to the schema, so the previous
    release runs on it.
  - `/ready` checks only that the previous release's own newest migration is applied.
- **A contract step in between.** The previous release may read what that step removed, so
  redeploying it is not enough.
  - Stop the stack and restore the backup taken in step 2 of the upgrade
    (`backup-restore.md`). Then start the previous release.
  - Anything written since that backup is lost. Rolling forward with a fix is often the better
    choice.

New migrations are named `YYYYMMDDHHMM_description.sql` (UTC). They expand the schema unless
marked as a contract step; see `WORKSPACE.md`, "Migrations".

### Moving to a separate knowledge portal

Releases before ADR-0104's cutover ran the knowledge portal in this manifest, as `knowledge-*`
containers behind this edge. This release removes them. Before upgrading:

1. Stand up the knowledge portal from its own repository, `v0.2.0` or later, restoring this
   deployment's knowledge database into it (knowledge-portal's `docs/operations/deployment.md`,
   "Moving over from requirement-portal's deployment"). Add its sign-in entities to the realm
   with its `deploy/keycloak/apply.py`. People sign in to it again once.
2. Set `KNOWLEDGE_API_BASE_URL` in `production.env` and move the two service tokens there
   from `deploy/.env` (see "Connecting the knowledge portal"). Set `KNOWLEDGE_PORTAL_URL` in
   `deploy/.env` to the portal's address.
3. Upgrade, removing the old containers:

   ```bash
   docker compose -f deploy/compose.production.yaml -f deploy/compose.peer.yaml up -d --build --remove-orphans
   ```

4. Keep the old `requirement-platform_knowledge_postgres_data` volume, and a backup of it,
   until the knowledge portal has run cleanly; then remove it with `docker volume rm`.

Keycloak keeps the knowledge portal's client, roles and groups it already holds: removing them
from this realm file changes only new realms.

## Backups

`docker compose -f deploy/compose.production.yaml run --rm backup` dumps the database into the
`backups` volume. It runs online. Dumps older than `BACKUP_RETENTION_DAYS` (a Compose variable,
default 14) are removed after each successful run. Schedule it, copy each dump off the host, and
restore by the steps in `backup-restore.md`, which also states the proposed RPO and RTO.

## Database connections and limits

**Session limits.** Every pooled connection, in the API and the worker, runs under three limits:

| Setting | Default | What happens past it |
|---|---|---|
| `DATABASE_STATEMENT_TIMEOUT_SECONDS` | 30 | The statement is cancelled. |
| `DATABASE_LOCK_TIMEOUT_SECONDS` | 5 | The wait for a row, table or Requirement lock is abandoned. |
| `DATABASE_IDLE_TRANSACTION_TIMEOUT_SECONDS` | 60 | A transaction left open and idle loses its session, so its locks are released. |

- A cancelled statement or abandoned lock wait answers 503 `database_busy`. An AI job retries it
  with backoff, like a provider outage.
- One-shot commands (`migrate`, `maintenance`, `retention`, `backup`) use direct connections
  without these limits.

**The connection ceiling.** PostgreSQL accepts at most `POSTGRES_MAX_CONNECTIONS` connections
(a Compose variable, default 200). Size it as follows:

```text
POSTGRES_MAX_CONNECTIONS >= (API containers + worker containers) × DATABASE_POOL_MAX_SIZE
                            + 5   one-shot commands (migrate, maintenance, retention, backup) and psql
                            + 3   PostgreSQL's reserved superuser connections
                            + monitoring (one per exporter)
```

- With the defaults (one API, one worker, a pool of 20), 48 are needed.
- Raise it before adding replicas. Each connection costs PostgreSQL memory, so keep pools no
  larger than the concurrent work needs.
- A managed PostgreSQL sets its own ceiling; size against that.

**A managed PostgreSQL.** Set `DATABASE_URL` as a Compose variable, in the shell or
`deploy/.env` rather than `production.env`. It replaces the bundled database for the API,
worker and one-shot commands. Require TLS in the URL:

```bash
# deploy/.env
DATABASE_URL=postgresql://smb@db.example.com:5432/smb_requirements?sslmode=verify-full
```

Put the password in the URL, or keep it out of the URL: set `DATABASE_PASSWORD_FILE` in
`production.env` and mount the file (`secrets.md`).

- Without `DATABASE_URL`, the bundled database is used with `sslmode=${DATABASE_SSLMODE:-prefer}`.
- The bundled `postgres` container still starts, unused. The `backup` service and the PostgreSQL
  exporter still point at it, so use the provider's backups and metrics instead, or point them at
  the managed server in an override.
- The database needs the `vector` extension (pgvector).
- `smb_db_pool_connections` shows each process's pool in use.

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
| `GET /api/health` | The process is serving HTTP. It also reports the running release's `version`. |
| `GET /api/ready` | The API accepts requests, the schema is at the newest packaged migration, the maintenance marker exists, and (when the API runs them) its background workers are healthy. The compose healthcheck uses it. |

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
| `smb_db_pool_connections` | `state` | The process's database pool: connections `in_use` and `idle`, read on each scrape. With `smb_db_pool_max_connections` and `smb_db_pool_requests_waiting`. |
| `smb_build_info` | `service`, `version` | Always 1; names the release each process runs. |
| `smb_ready` | — | 1 when the process's latest readiness check passed: the API's `/ready`, the worker's health loop. |
| `smb_ai_jobs_queued` | `operation` | AI jobs waiting to be claimed, sampled every 15 seconds. Every process reports the same queue; take `max()`. |
| `smb_ai_job_oldest_queued_age_seconds` | — | How long the oldest claimable job has waited. A job in retry backoff waits from when it is due. |
| `smb_provider_spend_blocked_total` | `action` | Work held back because today's token budget is spent: `start` (refused) or `claim` (skipped by a worker). |
| `smb_client_errors_total` | `kind` | Failures browsers reported (`POST /api/client-errors`): `render` (a page crashed), `chunk_load` (a page's code was gone after a redeploy), `uncaught_error` and `unhandled_rejection`. Only the kind is sent, never a message. A browser reports each kind once per page load. |

The process, Python and garbage-collector series every Prometheus client exports
(`process_resident_memory_bytes`, `python_gc_*`, …) are there too.

The alerts, their thresholds and their runbooks are in `deploy/monitoring/prometheus/alerts.yml`
and `alerts.md`; the objectives they guard are in `slos.md`.

### Monitoring add-on (Prometheus, Alertmanager and Grafana)

`deploy/compose.monitoring.yaml` is an optional overlay that collects these metrics, alerts on
them and shows them. It adds five containers.

- **Prometheus**
  - It scrapes every `api` and `worker` container through Docker's DNS, so `--scale` needs no
    configuration change. The knowledge portal's exporters belong to its own deployment.
  - It also scrapes the two exporters below, and Alertmanager.
  - It evaluates the alerts in `deploy/monitoring/prometheus/alerts.yml`. Each one has a runbook in
    `alerts.md`, and `slos.md` says which ones guard an objective.
  - It keeps 15 days of data (`PROMETHEUS_RETENTION`) and is not published.
- **Alertmanager** sends warning and critical alerts to one receiver. Info alerts are only shown.
  It is not published.
- **postgres-exporter** reports PostgreSQL's connections, `max_connections` and database size.
  It reads them as the application's user, with the same password the API and worker use.
- **node-exporter** reports the host's disks, memory and CPU through a read-only view of its root.
- **Grafana** opens on the provisioned **Requirement AI — overview** dashboard: API traffic and
  slow routes, provider requests, latency and tokens by model, and AI job outcomes. It is
  published on `127.0.0.1:3000` only (`GRAFANA_PORT`); sign in as `admin`.

```bash
export GRAFANA_ADMIN_PASSWORD=...        # used when Grafana first creates its database
export ALERTMANAGER_RECEIVER=webhook     # none (the default), webhook or slack
export ALERTMANAGER_URL=https://...      # the webhook, or the Slack incoming-webhook URL
docker compose -f deploy/compose.production.yaml -f deploy/compose.monitoring.yaml up -d
```

**Alert delivery** is set by two Compose variables.

| Variable | Meaning |
|---|---|
| `ALERTMANAGER_RECEIVER` | `none` (default): alerts are only shown in Alertmanager, Grafana and Prometheus. `webhook`: each notification is POSTed as Alertmanager's JSON. `slack`: posted to a Slack incoming webhook, with each alert's runbook link. |
| `ALERTMANAGER_URL` | The receiver's URL, required for `webhook` and `slack`. It is written to a file only Alertmanager can read, and the configuration names that file, never the URL. |

- Alertmanager refuses to start with a receiver but no URL.
- `deploy/monitoring/alertmanager/entrypoint.sh` renders the configuration. Edit it for another
  kind of receiver, such as email.
- An alert for a container that cannot be scraped suppresses that container's other warnings.

Pass both `-f` files to every command for these containers (`ps`, `logs`, `down`). The dashboard
and data source are read-only in the UI: change `deploy/monitoring/` and restart Grafana. Grafana
runs on a read-only root with its plugin preinstaller off, so it uses the plugins in the pinned
image and never updates them online.

**Checks**
- `tests/architecture/test_monitoring_metrics.py` fails when:
  - a panel or alert reads a series that is neither one of the application's instruments nor an
    allow-listed exporter metric;
  - an alert has no runbook section.
- CI starts the overlay and checks that all five targets are scraped and PostgreSQL is reached.
- CI also runs `promtool check config`, the alert unit tests (`promtool test rules
  alerts.test.yml`, including a forced readiness failure), and `amtool check-config` for every
  receiver.

**Before relying on it in production**
- **Receiver.** Set `ALERTMANAGER_RECEIVER` and `ALERTMANAGER_URL`, then send a test alert:
  `docker compose ... exec alertmanager amtool alert add Test severity=warning
  --alertmanager.url=http://127.0.0.1:9093`.
- **Thresholds.** Set `DailyTokenBudgetExceeded` to your own daily budget and `ProcessMemoryHigh`
  below the containers' memory limit. Tune the others to your traffic, keeping `alerts.test.yml`
  passing.
- **Access.** Put Grafana behind TLS and your identity provider before exposing it beyond the
  host.
- **An existing stack.** If your organization already runs Prometheus, skip the overlay:
  - scrape `:9464` on each `api` and `worker` container;
  - load `alerts.yml`;
  - import `deploy/monitoring/grafana/dashboards/requirement-ai.json`.

## Rate limiting

Three limits protect the deployment (ADR-0106).

**Per actor, per minute.** `PROVIDER_RATE_LIMIT_PER_MINUTE` caps how many provider-calling
operations one actor may start per minute. They include:
- AI jobs, which cover generation, analysis and clarification resolution, Story quality checks
  and reviews;
- knowledge search, architecture mapping and index builds;
- the actions that queue automatic provider work: creating, promoting or editing a Requirement,
  asking a clarification question, and deciding knowledge findings or intent proposals.

`tests/architecture/test_provider_rate_limit.py` lists the routes. Refusals return 429 with
`Retry-After` and code `provider_rate_limited`. Size the limit for the busiest author:
bulk-creating Requirements counts one call per Requirement.

With PostgreSQL the count is shared by every API process: one row per counted call in
`provider_calls`, checked under a per-actor lock. The ceiling holds however many API replicas run.
The in-memory store used offline counts per process.

**Per day, in tokens.** `PROVIDER_DAILY_TOKEN_BUDGET` caps the tokens the model providers may
spend per UTC day, across every process. Spend is what the providers report in each response,
recorded in `provider_token_spend`; `smb_provider_tokens_total` shows the same counts as a metric.
Once the day's budget is spent:
- new AI jobs, and retries of old ones, are refused with 429, code `provider_budget_exhausted`,
  and `Retry-After` until 00:00 UTC;
- workers stop claiming queued AI jobs, so they wait and run after the reset;
- editing Requirements keeps working. Indexing and the knowledge service's own work are counted
  but not paused.

Calls already in flight finish, so a day can overshoot by them. 0, the default, records spend
without limiting it.

**Per client address, at the edge.** nginx limits each client address on `/api/` to
`EDGE_RATE_PER_SECOND` requests a second (default 50), with bursts of `EDGE_BURST` (default 100).
Impact preview is held to 2 a second (bursts of 5). Browser error reports
(`/api/client-errors`), which need no sign-in, are held to 1 a second (bursts of 10) with bodies of
1 KB at most. Refusals are 429, code `edge_rate_limited`, in the API's error shape, with
`Retry-After`. The API's own 429s pass through unchanged. These are
Compose variables, set in `deploy/.env`.

The edge sees the TLS proxy in front of it, not the browser, unless it trusts that proxy to name
the client. Set `TRUSTED_PROXY_CIDR` to the proxy's address or range, and have the proxy send
`X-Forwarded-For`. Otherwise every request counts as the proxy's address and the limit applies
to everyone together.

The default, `127.0.0.1/32`, trusts no one. People behind one corporate NAT share an address:
raise the limit if a whole office reaches it.

## Internal API

The knowledge service reads a few things from this service over `/internal`
(ADR-0099):
- a document's dependents and impact, for its owner;
- mapping counts per catalogue release;
- actor details for ownership transfers.

- **Off by default.** Every `/internal` path answers 404 until
  `KNOWLEDGE_SERVICE_TOKEN` or `KNOWLEDGE_SERVICE_CLIENT_ID` is set (see "Service
  credentials").
- **Turning it on.** Set it in `production.env` to a random secret of 32 characters or more,
  and give the same value to the knowledge service. Requests must then carry
  `Authorization: Bearer <token>`; no user sign-in is involved.
- **Never public.** The bundled nginx answers 404 for `/api/internal` whatever the tokens
  hold, and the CI deployment job checks it, and the knowledge portal's edge.

## Connecting the knowledge portal

This service reads from the knowledge service over its internal API (ADR-0099): library search
and retrieval, architecture matching, the knowledge event feed, and the read-only viewers'
passages and evidence. The link is optional (ADR-0104), and set in `production.env`.

- **Configure both or neither:** `KNOWLEDGE_API_BASE_URL` and `REQUIREMENT_SERVICE_TOKEN`, the
  secret this service presents. It is 32+ characters, and the knowledge service holds the same
  value. Startup refuses one without the other.
- **On one Docker host,** layer `deploy/compose.peer.yaml` over the manifest. It joins `api`
  and `worker` to the external network `platform-internal` (`PEER_NETWORK`), where `api` is
  `requirement-api`; the knowledge portal joins it with its own overlay as `knowledge-api`.
  Set `KNOWLEDGE_API_BASE_URL=http://knowledge-api:8000`:

  ```bash
  docker network create platform-internal          # once per host
  docker compose -f deploy/compose.production.yaml -f deploy/compose.peer.yaml up -d
  ```

  On separate hosts, skip the overlay and point `KNOWLEDGE_API_BASE_URL` at a private address
  that reaches the knowledge API directly, never its edge.
- **Links.** `KNOWLEDGE_PORTAL_URL` in `deploy/.env` is the knowledge portal's address, ending
  in `/` (for example `https://knowledge.example.com/knowledge/`). It is built into the web
  image for the links to it, and read when `web` starts to redirect old `/knowledge/`
  bookmarks there, keeping the rest of the path. Unset, the links are hidden and `/knowledge/`
  answers 404. Rebuild `web` when it changes.
- **Or a client of its own** in place of the token: see "Service credentials".
- **Neither set:** deterministic fakes stand in, with no library, one empty catalogue version
  (`offline-catalogue`), and nothing for the viewers to show. Production may run this way too
  (ADR-0104).
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


## Service credentials

With the shared tokens, each service holds the other's secret too. Per-direction credentials
(ADR-0104) give each service only its own: a confidential client at the OIDC issuer, which
grants it short-lived tokens through the client-credentials grant. The receiving service checks
them against the issuer's signing keys and holds no secret at all.

| Direction | Keycloak client | This service's settings |
|---|---|---|
| Requirement work calls the knowledge service | `requirement-service`, audience `knowledge-internal` (`deploy/keycloak/realm-requirement-ai.json`) | `REQUIREMENT_SERVICE_CLIENT_ID=requirement-service` and `REQUIREMENT_SERVICE_CLIENT_SECRET` |
| The knowledge service calls requirement work | `knowledge-service`, audience `requirement-internal` (knowledge-portal's `deploy/keycloak/`) | `KNOWLEDGE_SERVICE_CLIENT_ID=knowledge-service` |

1. Import the realm, or add the client to an existing realm, and copy the secret Keycloak
   generated for `requirement-service` (Clients, `requirement-service`, Credentials). The realm
   file stores no secret.
2. Set the settings above in `production.env`, with `OIDC_ISSUER_URL` set to the realm. The
   knowledge service sets its own client's ID and secret, and `REQUIREMENT_SERVICE_CLIENT_ID`.
3. With client credentials, they are used in place of `REQUIREMENT_SERVICE_TOKEN`. `/internal`
   admits either `KNOWLEDGE_SERVICE_TOKEN` or a granted token while both are set, so the two
   services can move over one at a time. Remove the shared tokens once both use their clients.

Tokens are renewed before they expire. If the issuer cannot be reached, calls to the knowledge
service report it as unavailable, and `/internal` answers 503 to a granted token it cannot check.

After 5 calls in a row to the knowledge service fail as unavailable, including failed token
grants, calls stop for 30 seconds and fail at once. Then one call tests the service, and success
resumes them. An analysis meanwhile is kept and marked "references not checked".
## Image updates

- **Pinning.** Base and service images are pinned by digest. Dependabot opens
  weekly pull requests to move the pins.
- **Scanning.** CI scans both images with Trivy and fails on fixable HIGH or
  CRITICAL vulnerabilities.
- **Patches.** The web image applies Alpine security updates at build time.

Rebuild and redeploy when those pull requests merge, even if no application
code changed (ADR-0077). With released images, that means cutting a patch
release (ADR-0108).

## Not included

- **TLS termination.** Put a load balancer or reverse proxy in front of `web`.
- **The model servers.** Point `LLM_PROVIDER` (or the model profiles) at the
  models you run or subscribe to. Architecture mapping uses the same knowledge
  model and embedding as the rest of the application.
- **OCR and office previews.** The image omits the optional `document-ocr` extra
  (docling) and LibreOffice. Extend the image if you need
  `ATTACHMENT_OCR_ARTIFACTS_PATH` or `DOCUMENT_OFFICE_PREVIEW_EXECUTABLE`.
- **Off-host backup storage.** The `backup` service writes dumps to the
  `backups` volume on this host. Copying them elsewhere, and scheduling the
  service, is the operator's part (`backup-restore.md`). A managed PostgreSQL
  server's own backups can replace both.

- **Identity.** `deploy/keycloak/` is a development identity provider, not a
  production one.
