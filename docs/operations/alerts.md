# Alert runbooks

Every alert in `deploy/monitoring/prometheus/alerts.yml` links to its section here through its
`runbook_url`. `docs/operations/slos.md` says which alerts guard an objective.

**Severities**
- **critical**: someone acts now.
- **warning**: someone looks within the working day.
- **info**: shown in Alertmanager and Grafana, never sent.

**Where to look first**
- `docker compose -f deploy/compose.production.yaml ps`, then the service's logs.
- Grafana's **Requirement AI — overview** dashboard.
- Prometheus's Alerts page. Prometheus is not published, so reach it through the host:
  `docker compose ... exec prometheus wget -qO- http://127.0.0.1:9090/api/v1/alerts`.

## Processes

### ProcessDown

Prometheus has not reached a container's metrics for 2 minutes. The `job` label names the
container: `api`, `worker`, `postgres`, `node` or `alertmanager`.

1. Run `docker compose ps`. Is the container running, restarting, or unhealthy?
2. Read its logs. An `api` or `worker` that exits at start prints the configuration error. For
   example, a missing OIDC setting exits with code 2.
3. If it runs but cannot be scraped, check `METRICS_PORT` (9464) and that the container is on the
   default network.
4. Restart it: `docker compose ... up -d <service>`.

While a target is down, its own warning and info alerts are suppressed.

### ReadinessFailing

An API (`/ready`) or worker process has reported "not ready" for 5 minutes.

1. Call `/api/ready` through the edge. Its `checks` name what failed:
   - `persistence`: the database cannot be reached, or the schema is behind this release's newest
     migration, or the maintenance marker is missing. Check PostgreSQL, then run `migrate`
     (`deployment.md`, "Upgrade").
   - a background worker by name: it stopped. The worker process exits for a restart on its own.
     Read its logs for the cause.
   - `accepting_requests`: the API is starting or stopping.
2. If PostgreSQL is busy rather than down, see **DbPoolSaturation** and
   **PostgresConnectionsHigh**.

## API

### HttpServerErrors

More than 5% of API requests answered 5xx for 10 minutes.

1. In the dashboard, find the routes with the 5xx share (`smb_http_requests_total` by `route`).
2. Read the API logs for those routes. Each line has the request's `correlation_id`. 503
   `database_busy` means a statement or lock wait ran past its limit: see **DbPoolSaturation**.
   503 `identity_provider_unavailable` means the OIDC issuer is unreachable.
3. If one release introduced it, roll back (`deployment.md`, "Rollback").

### HttpLatencyP95

The 95th-percentile API response time has been over 2 seconds for 15 minutes. Health probes are
excluded.

1. Find the slow routes in the dashboard.
2. Slow everywhere usually means the database: check **DbPoolSaturation** and the host's CPU.
3. Model work runs as jobs, never inside a request, so a slow route is not a slow provider.

### RateLimitBiting

*Info.* More than 10 requests in 15 minutes were refused with 429: the provider rate limit
(`PROVIDER_RATE_LIMIT_PER_MINUTE`), the edge limit (`EDGE_RATE_PER_SECOND`), or the daily budget.

- If it is legitimate use, raise the limit that refused it. The response's `code` says which one.
- If one client address floods the edge, find it in the edge logs.

## AI work

### ProviderErrors

More than 10% of a provider's requests have failed for 10 minutes.

1. `outcome="4xx"` is usually quota, an expired key (401/403) or a rejected model. Check the
   provider's console and the key in `production.env` or the model profile.
2. `5xx` or `error` is the provider's outage or the network. Check the provider's status page.
   Jobs retry transient failures with backoff (`AI_JOB_RETRY_*`).

### SlowAiGeneration

The 95th-percentile generation call to a provider has taken over 2 minutes for 15 minutes.

- The provider is slow or overloaded, or the model is too large for its hardware (local models).
- Jobs keep working but finish late. If calls start timing out, consider a faster model or
  profile.

### AiJobsFailing

More than 20% of an operation's job attempts have failed for 15 minutes.

1. Open a failed job in the UI, or read the worker log line for it (`job_id`, `operation`,
   `status`). Its failure `code` names the cause.
2. Codes starting with `model_` point at the provider: see **ProviderErrors**.
   `database_busy` points at the database.
3. A failure that repeats on every attempt is usually configuration: a model, a profile, or a
   missing index.

### AiJobsExhausted

A job failed after using all `AI_JOB_MAX_ATTEMPTS` attempts on a transient failure. Its creator
was notified.

- The outage outlasted the backoff. Find it with **ProviderErrors** or **DbPoolSaturation**.
- Once it has passed, people can start the work again.

### QueueBacklog

Over 50 AI jobs have been waiting for 15 minutes.

1. Is a worker running and claiming? Check **ProcessDown**, and the worker's logs for claims.
2. Is the queue paused? **ProviderSpendBlocked** holds every claim until 00:00 UTC.
3. Otherwise the workers cannot keep up. Raise `AI_JOB_WORKER_CONCURRENCY` or add a worker
   replica, and size the database for it (`deployment.md`, "Database connections and limits").

### OldestQueuedJobAge

A job that could run has waited over 30 minutes to be claimed. A job waiting out its retry
backoff is not counted.

The causes are the same as **QueueBacklog**, plus one more: prior-art screening waits for the
knowledge index, and for its hourly budget (`PRIOR_ART_JUDGE_CALLS_PER_HOUR`). Check
`smb_ai_jobs_queued` by `operation` to see which jobs wait.

### DailyTokenBudgetExceeded

Providers reported more tokens in the last 24 hours than the rule's threshold. The threshold in
`alerts.yml` is set by hand; keep it at or below `PROVIDER_DAILY_TOKEN_BUDGET`.

- Find the provider and model in `smb_provider_tokens_total`.
- Check whether the volume is expected, such as a large import or reindexing, or a loop of
  automatic work.

### ProviderSpendBlocked

Today's `PROVIDER_DAILY_TOKEN_BUDGET` is spent.

- New AI work is refused with 429 `provider_budget_exhausted`. Workers claim nothing until
  00:00 UTC, then the queued jobs run.
- Editing Requirements keeps working.

To resume now, raise the budget and restart the API and worker. Otherwise, wait for the reset.
Find what spent it with **DailyTokenBudgetExceeded**.

## Database

### DbPoolSaturation

A process has had requests waiting for a database connection, or 90% of its pool in use, for
5 minutes.

1. Slow queries hold connections. Statements past `DATABASE_STATEMENT_TIMEOUT_SECONDS` are
   cancelled with 503 `database_busy`. Look for those in the API logs, and for long transactions
   in PostgreSQL:
   `SELECT pid, now() - xact_start, state, query FROM pg_stat_activity ORDER BY 2 DESC NULLS LAST;`
2. If load is legitimately higher, raise `DATABASE_POOL_MAX_SIZE`. Recheck the ceiling first
   (**PostgresConnectionsHigh**).

### PostgresConnectionsHigh

PostgreSQL has used over 80% of `max_connections` for 10 minutes.

- Count what is connected: `SELECT application_name, count(*) FROM pg_stat_activity GROUP BY 1;`
- Raise `POSTGRES_MAX_CONNECTIONS`, or lower the pools, using the formula in `deployment.md`
  ("Database connections and limits"). Changing `max_connections` restarts PostgreSQL.

### DatabaseSizeGrowth

The database grew by more than 20% in a day.

- Expected after a large import. Otherwise, find the largest tables:
  `SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;`
- Make sure the `retention` command is scheduled (`deployment.md`, "Retention"). Its output
  gives the document blobs' total size and how many nothing refers to. If `document_blobs`
  is the largest table and the orphans are a large share of it, find out why before removing
  any by hand.
- If `ai_jobs` is the largest table, check that the command's run cleared the inputs of old
  jobs, and consider a shorter `AI_JOB_PAYLOAD_RETENTION_DAYS`.
- Check that the host has room for the growth and for the backups (**DiskLow**).

## Host

### DiskLow

A filesystem on the host has had less than 15% free for 15 minutes. PostgreSQL stops writing
when its disk is full.

1. Find what is large: `docker system df`, then the `backups` volume. Backups older than
   `BACKUP_RETENTION_DAYS` are removed on each run, but copies made elsewhere on the host are not.
2. Remove unused images (`docker image prune`), or grow the disk.

### ProcessMemoryHigh

An API or worker process has used over 80% of its container's memory limit for 15 minutes. The
thresholds follow the manifest's defaults, `API_MEM_LIMIT` (2g) and `WORKER_MEM_LIMIT` (3g);
change them in `alerts.yml` with the limits. At the limit, the kernel stops the container and
Compose restarts it.

- Document extraction runs in bounded subprocesses (`DOCUMENT_EXTRACTION_MEMORY_BYTES`), so steady
  growth in the main process is the signal.
- Restart the container, and report the version (`/api/health`) with its memory curve.
