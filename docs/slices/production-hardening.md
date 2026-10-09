# Production Hardening — Second Production-Readiness Review

## Status

**Specified 2026-10-08; not scheduled.** Nothing below is implemented yet. This record keeps the
plan for closing every finding of the second production-readiness review (security, deployment and
CI, reliability and observability, frontend) so it can be scheduled later. When work starts, each
PR converts its part into the `WORKSPACE.md` §10 sections and fills in Validation Evidence here.

Review baseline (2026-10-08, commit `41a7516`): `pytest` 1795 passed / 75 skipped, `ruff check`,
`ruff format --check`, `mypy src tests` (678 files) and `lint-imports` (42 contracts) green;
frontend build, lint, typecheck, OpenAPI drift and `npm audit` green, vitest 501/502 (the failure
is a Node 22 vs Node 24 test-environment difference, fixed in PR 12).

## Context

A production-readiness review covered security, deployment and CI, reliability and observability, and the frontend. The codebase is strong:
- **Backend:** 1795 tests pass, mypy strict is clean, and all 42 import contracts hold.
- **Frontend:** 501 of the 502 vitest tests pass. The one failure is a Node 22 versus Node 24 difference in the test environment, fixed in PR 12.

The gaps are in how the app is released, recovered and operated, plus some failure modes under real load. This plan closes every finding. It was checked against the code in a design review before being recorded.

Decisions taken by the repository owner (2026-10-08):
- **Frontend logic fixes:** allowed as an explicit, recorded exception to CLAUDE.md's "presentation only" rule. They go in their own PRs and are never mixed with redesign work.
- **Kernel fixes:** shipped as a **platform-kernel v1.1.0 release**, after which this repo bumps the pin (AGENTS.md §2.1).
- **Synchronous provider routes:** moved to the durable job queue now.
- **Provider rate limit across replicas:** counted in **Postgres**.

Why the job-queue move is smaller than it sounds:
- The UI already starts every AI operation as a durable job, except architecture mapping. `frontend/src/app/requirement/BreakdownView.tsx:88-91` still calls the synchronous `POST /architecture-mapping`.
- That route already has its own durable path: `POST /architecture-mapping/jobs` plus `GET …/jobs/{id}` (`routes/architecture.py:41-90`), on a separate queue from AI jobs.
- The synchronous routes are therefore mostly unused API surface. Their main users are about 25 test files that call them for setup.

## Process (AGENTS.md compliance)

**Roadmap and slice**
- Recorded in the ROADMAP.md status ledger and in "Bounded Enhancements and Maintenance Record", both pointing to this file.
- When implementation starts, this file is restructured to the WORKSPACE.md §10 template.
- The slice's UI field lists the UI items below.
- Validation Evidence is updated in every PR.

**ADRs** (template: `docs/architecture/adr-template.md`)

| ADR | Decision |
|---|---|
| 0104 | Provider work runs only as durable jobs; the synchronous routes are retired |
| 0105 | Provider rate limit shared across replicas, stored in Postgres. Retires debt row AGENTS.md:722 |
| 0106 | AI-job retry with backoff (the attempt cap is already an ADR-0020 amendment) |
| 0107 | Release images, deploy by tag, backups, and expand/contract migrations |
| 0108 | Scope of the frontend logic exception. Updates debt row AGENTS.md:723 |

**Rules for every PR**
- All five backend gates pass, plus `cd frontend && npm run build`, lint, typecheck and tests.
- Every new error is added to `workflows/application/public_errors.py` with a status-code test. New errors in this plan: `attempts_exhausted`, `database_busy`, and the client-errors 429.
- New constructor parameters are required, never defaulted to `None` (§12).
- Variables read by `settings.py` are documented in `.env.example`. Compose-only variables (`WEB_PORT`, `IMAGE_TAG`, `POSTGRES_MAX_CONNECTIONS`, `DATABASE_SSLMODE`, …) are documented in `docs/operations/deployment.md`, not in `.env.example` (§4.5).

**Existing tests and checks the work must keep passing**

| Constraint | What it requires |
|---|---|
| `test_action_pins.py` | Actions pinned by SHA with a `# vX.Y.Z` comment |
| `test_image_pins.py` | Images pinned by digest, exactly one pgvector image |
| `test_platform_deployment.py` | Compose structure assertions; updated where noted below |
| `test_deployment_mounts.py` | Identical volumes on all backend services |
| `test_monitoring_metrics.py` | Every `smb_*` metric must exist in the installed kernel's `metrics.py`; this plan adds a pinned allow-list for `pg_*`, `process_*` and `node_*` names |
| `test_route_authentication.py` | Allow-list of public routes |
| `test_provider_rate_limit.py` | Every provider-calling route is rate limited |
| `test_migration_catalogue.py` | Migration naming and ordering; new migrations use timestamp names |
| `ci.yml:256` | CI greps for the CSP `<meta>` tag, so it must stay |

---

## Phase 0: platform-kernel v1.1.0 (separate repo, attached with add_repo when implementing)

| Change | Kernel file |
|---|---|
| **Migration runner:** session `pg_advisory_lock` around the run; `SET lock_timeout` per file | `persistence/migrations.py:29-65` |
| **Pooled connector:** a `configure(conn)` hook (for timeouts) and a public `stats()` (for pool metrics) | `persistence/connector.py:77-100` |
| **OIDC:** configurable leeway (default 60s); check `typ`/`azp` when present | `identity/oidc.py:53,68-75,140-157` |
| **JWKS:** fetch keys outside the lock; keep serving the last good keys while refreshing or when the identity provider errors | `identity/oidc.py:53,68-75,140-157` |
| **OpenAI:** send a configurable `max_completion_tokens` | `llm/openai_structured_output.py:65-76` |
| **Metrics:** register Process/Platform/GC collectors | `observability/metrics.py:33-77` |
| **New metrics:** `smb_build_info`, `smb_ai_jobs_queued`, `smb_ai_job_oldest_queued_age_seconds`, `smb_db_pool_connections{state}`, `smb_ready`, `smb_ingestion_failures_total`, `smb_client_errors_total`, `smb_provider_spend_blocked_total` | `observability/metrics.py:33-77` |
| **`InternalHttpClient` circuit breaker:** consecutive failures open it, a half-open probe tests recovery, and it fails fast with `ServiceUnavailableError`. Note the effect on knowledge-portal, which shares the kernel, in the kernel changelog | `http/client.py:24-81` |

Then, in this repo:
- Bump `pyproject.toml:12` and `uv.lock`.
- Wire the new settings in `settings.py`, `composition/identity.py`, `composition/llm.py` and `composition/persistence.py:405-415`.

Phase 1 is designed not to wait for this release. PRs 3, 9 and 10 do wait for it.

---

## Phase 1: P0, required before a controlled pilot

### PR 1 · Production config fails closed
- **Hard-code production values.** In `deploy/compose.production.yaml`, set `APP_ENV: production` and `IDENTITY_PROVIDER: oidc` in both the `x-backend` and `x-knowledge` environment blocks.
  - Compose `environment:` overrides `env_file` and isn't affected by stray values in the operator's shell.
- **Separate demo override.** New `deploy/compose.demo.yaml`, used by the CI `deployment` job and the demo instructions:
  - restores `development` and `fake`;
  - publishes `127.0.0.1:${WEB_PORT:-8080}:8080`.
  - Update `deploy/demo.env.example` and `test_platform_deployment.py` to match.
- **Stricter production validation** in `settings_validation.py` (~141-206, 240). In production, also reject:
  - `LLM_PROVIDER=fake`, including any fake entry inside an `LLM_CONFIG_PATH` profile set (`settings.py:256-259`);
  - `DEBUG_TRACE_ENABLED=true`;
  - `LOG_FORMAT` other than `json`.
  - `interfaces/deployment_preflight.py` gets the same checks.
- **Close the public API docs at the edge.** In `deploy/web/default.conf.template`, return 404 for `/api/docs`, `/api/redoc` and `/api/openapi.json`.
  - Settings load only in the lifespan (`main.py:116-120`), after the app has been constructed, so the app itself can't decide this.
  - Add the paths to the CI edge check.
- **Production actually boots in CI.** The `deployment` job starts `api` and `worker` in production mode, using:
  - the dev Keycloak compose (`deploy/keycloak/compose.yaml`) behind a TLS sidecar with a CI-generated certificate as the OIDC issuer;
  - `LLM_PROVIDER` set to a profile that points at the local compatible fake.
  - The job asserts `/ready`, asserts a 401 without a token, runs `deployment_preflight` (expects exit 0), and checks that a fake-identity variant refuses to boot.
- **Gate `start.sh` migrations.** `start.sh:281-289` asks for confirmation (or needs `--migrate`) before migrating any `DATABASE_URL` that isn't localhost.

### PR 2 · AI-job retry with backoff (ADR-0106; attempt cap already delivered by G1)

Depends on PR 8, so a knowledge outage isn't retried by re-running a paid analysis.

- **Attempt cap: already delivered elsewhere.** `docs/slices/fix-ai-job-trace-gaps.md` (G1, commit
  `79d28a9`) added `AI_JOB_MAX_ATTEMPTS` and fails a claim past the cap as `attempts_exhausted`,
  as an ADR-0020 amendment. Before starting this PR, check what remains against that work; the
  bullets below are the original design, kept for reference.
  - Claim jobs as today.
  - At the start of `execute()` in `workflows/application/use_cases/ai_job_execution.py`, when `attempt_count > AI_JOB_MAX_ATTEMPTS`, finish with `AiJobAttemptsExhaustedError` (`attempts_exhausted`, retryable) through the existing `_finish_failure`/`_notify` path (469-485). The owner is notified, and the existing `fail()` transition already allows running → failed.
  - Explicit retry already creates a new job (`ai_jobs.py:334-343`), so nothing needs resetting.
  - Count exhausted jobs in the existing `smb_ai_jobs_total{status="attempts_exhausted"}`. No kernel dependency.
- **Retry with backoff:**
  - New migration `2026101xxxxx_ai_job_retry_backoff.sql` adds `ai_jobs.next_attempt_at timestamptz NULL` and an index.
  - New domain transition `requeue(next_attempt_at)` in `jobs/domain/entities.py`. It keeps `attempt_count`, unlike `defer()` (193-210).
  - Retry only on these failure **codes** from `describe_public_error` (`public_errors.py:393-404`): `model_rate_limit`, `model_unavailable`, `platform_service_unavailable`.
  - Timeouts and invalid model output stay terminal, which avoids paying twice.
  - Backoff follows `knowledge_handoff.py:129-143`.
  - Both claim implementations (`in_memory_ai_jobs.py:233-283`, `postgres_ai_jobs.py:351-419`) skip a job until its `next_attempt_at`. While it waits, they also block other jobs on the same requirement, so ordering is preserved.
- **Settings:** `AI_JOB_MAX_ATTEMPTS` (3), `AI_JOB_RETRY_FIRST_SECONDS`, `AI_JOB_RETRY_MAX_SECONDS`.
- **Tests:**
  - domain transitions;
  - a crash-looping job ends as `attempts_exhausted` and the queue keeps moving;
  - a backed-off job isn't claimable early, and same-requirement jobs wait for it;
  - Postgres integration in `tests/integration/test_postgres_persistence.py`.

### PR 4a · Architecture mapping becomes a job; probes and timeouts (ADR-0104, part 1)
- **Frontend (exception):**
  - `BreakdownView.tsx:88-91` starts `POST /architecture-mapping/jobs` and polls `GET /architecture-mapping/jobs/{id}` through a new hook. That queue is separate from the AI-jobs provider.
  - New client functions; `npm run api:generate`.
- **Probes:**
  - `/health` becomes `async def`.
  - `/ready` becomes `async def`, running the DB check via `anyio.to_thread.run_sync` with its own small limiter and a 2s timeout, so probes never wait behind request threads.
  - `/ready` still reports false when the DB pool is saturated. That is intended.
- **Shutdown:**
  - `serve.py:38` sets `timeout_graceful_shutdown`.
  - Compose sets `stop_grace_period: 30s` on `api` and adds a `web` healthcheck.
- **Startup coupling:** `web.depends_on` for `knowledge-web` changes to `service_started`, so `knowledge-unavailable.html` can show while the knowledge web app starts. Update `test_platform_deployment.py:120` to match.

### PR 4b · Retire the synchronous provider routes (ADR-0104, part 2)
- **Routes deleted** (all listed in `tests/architecture/test_provider_rate_limit.py:63-105`), each of which has a durable equivalent:
  - analysis, clarifications, question resolutions;
  - epic, features;
  - stories, story regeneration, change proposals;
  - feature quality;
  - breakdown review and its resolution;
  - architecture mapping.
- **Also deleted:** the two synchronous-only quality routes `story.py:301,318`, which nothing calls.
- **Kept:** `POST /knowledge/search/unified`, which only embeds the query and is used by `tests/release_load.py`.
- **Cleanup:**
  - Remove the now-unused frontend client functions.
  - Regenerate `frontend/openapi.json` (`test_openapi_snapshot.py`).
  - Check `contracts/requirement-internal.openapi.json` and `scripts/` for references.
- **Tests:** `tests/job_driver.py` starts jobs through the public API and drains them through the container's existing executor and queue, with no test-only production code. Migrate the roughly 25 affected test files and the rate-limit sets.
- **Timeouts:** nginx `/api/` `proxy_read_timeout` goes from 600s to 60s. `/knowledge-api/` stays at 600s, because the knowledge service still has long synchronous routes.

### PR 5 · Frontend session safety and crash handling (exception, ADR-0108)
- **Token renewal stops cancelling requests:**
  - `src/api/client.ts:165-169` gains `replaceAuthenticationHeaders()`, which swaps headers without aborting.
  - `src/auth/AuthProvider.tsx:139-143`: when `renewed.profile.sub` matches the current subject, it only replaces the headers. A different subject still aborts.
  - After a successful renewal, call `queryClient.invalidateQueries()` so queries that failed with 401 recover.
- **Consistent abort errors:** aborts after the response arrives (`client.ts:177,215,310,350`) become `ApiError(0)`, and `app/mutationErrors.ts` shows no toast for them.
- **Error boundaries:** new `components/states/ErrorBoundary.tsx` built on `ErrorState`.
  - A root boundary goes in `main.tsx`, and a route boundary around `<Suspense>` at `app/App.tsx:46`.
  - A chunk-load error shows "A new version is available — reload".
- **Tests:** same-subject renewal keeps an in-flight request alive; a different subject aborts it; the boundary renders on a crash and on a chunk-load error.

### PR 6 · Releases, backups, upgrade and rollback (ADR-0107)
- **Release workflow** `.github/workflows/release.yml`, triggered by `v*` tags, with SHA-pinned actions and per-job permissions (`packages: write`, `id-token: write`):
  - checks that the tag matches both `pyproject.toml` and `frontend/package.json`;
  - builds once, with the kernel token as a BuildKit secret;
  - runs Trivy, generates an SBOM with syft, and signs with cosign keyless;
  - pushes `ghcr.io/mohamhossam/requirement-{api,web}` tagged `vX.Y.Z` and `sha-…`;
  - creates a GitHub release from the CHANGELOG.
- **Compose:** `image: ${REQUIREMENT_API_IMAGE:-requirement-platform/api}:${IMAGE_TAG:-local}`, and the same for web. Update the prefix assertion in `test_platform_deployment.py`.
- **Version reporting:** `FastAPI(version=importlib.metadata.version(...))`, and `/health` returns the version. `smb_build_info` follows the kernel bump.
- **Backups:**
  - New `backup` compose service under a `backup` profile, using the pinned pgvector image. It runs `pg_dump -Fc` for both databases into a `backups` volume and keeps the last N dumps.
  - New `docs/operations/backup-restore.md` covering:
    - the schedule (host cron or a systemd timer) and the off-host copy;
    - restore steps, checked with `tests/release_recovery.py verify`;
    - RPO/RTO targets, which the owner confirms.
- **Upgrade runbook:** rewrite `deployment.md` "Upgrades" (202-217) as backup → `pull` by tag → `migrate` → `up`.
  - Rollback means redeploying the previous tag.
  - When a release notes a contract step, roll back by restoring the backup instead.
- **Migration policy:**
  - Document the expand/contract policy in WORKSPACE.md.
  - An architecture test rejects `DROP`, `RENAME` and `ALTER … TYPE` unless the file carries a `-- contract-step:` marker. Migrations dated before the policy are grandfathered by a timestamp cutoff.

---

## Phase 2: P1

### PR 8 · Analysis survives a knowledge-service outage (lands before PR 2)
- `analysis/application/use_cases/reference_grounding.py:43-115` catches `ServiceUnavailableError` and returns the primary analysis, following the pattern at `knowledge_handoff.py:109-125`.
- Record the outcome as a `stage_provenance` entry `reference_applicability` with status `unavailable`.
  - This uses the existing `AnalysisStageProvenance` (`analysis/domain/entities.py:280-298`), so no new aggregate field is needed.
  - Expose it in `schemas/analysis.py`.
- **UI:** the analysis view shows "References could not be checked — re-run analysis to ground them".
- Unified search keeps returning 503. The kernel circuit breaker makes it fail fast.

### PR 3 · Postgres timeouts and connection budget (after the kernel bump)
- **Timeouts on every pooled connection:**
  - Use the kernel `configure` hook to set `statement_timeout`, `lock_timeout` and `idle_in_transaction_session_timeout` on every pooled connection, including those used after `external_call`, and in the four adapters that call `connector.connection()` directly.
  - `lock_timeout` also bounds `pg_advisory_xact_lock` (`postgres_store.py:125`).
  - The one-shot maintenance, retention and migrate commands use their own direct connections, which keep no limits.
  - Settings: `DATABASE_STATEMENT_TIMEOUT_MS` (30000), `DATABASE_LOCK_TIMEOUT_MS` (5000), `DATABASE_IDLE_TX_TIMEOUT_MS` (60000).
  - Postgres errors 57014 and 55P03 map to a public 503 `database_busy`.
- **Connection budget:**
  - Compose postgres: `command: ["postgres","-c","max_connections=${POSTGRES_MAX_CONNECTIONS:-200}"]`.
  - `deployment.md` gets a sizing formula.
  - Publish `smb_db_pool_connections` from the pool's `stats()`.

### PR 7 · Shared provider rate limit, edge limits and spend cap (ADR-0105)
- **Shared limit:**
  - New port `jobs/application/ports/provider_call_rate.py`.
  - `ProviderCallRateLimit` (`provider_call_rate.py:32-95`) keeps `acquire`/`refund` and sits on top of the port.
  - In-memory adapter: today's deque logic.
  - Postgres adapter: new table `provider_call_windows(actor_id, window_start, calls)`, upserted with the pattern from `knowledge/infrastructure/prior_art.py:212-228`. It estimates the sliding window from the current and previous minute, and prunes old windows in the same statement.
  - Wire it in `container.py:794-796`.
- **Spend cap:**
  - New `PROVIDER_DAILY_TOKEN_BUDGET`, stored in a Postgres daily counter that the provider metering path updates.
  - Once the budget is spent, provider calls are refused with a public error, and the refusal is counted in `smb_provider_spend_blocked_total`.
- **Edge limits:**
  - nginx `real_ip` from `TRUSTED_PROXY_CIDR` (with a Dockerfile `ENV` default, so the template always renders), then a per-IP `limit_req_zone`.
  - Applied to `/api/` and `/knowledge-api/`, returning a JSON 429.
  - A stricter location for expensive non-provider routes such as `POST /requirements/{id}/impact-preview` (`requirements.py:432`).
- **Docs:** remove debt row AGENTS.md:722; update `deployment.md` "Rate limiting" (326).

### PR 9 · Alerting, SLOs and runbooks (after the kernel bump)
- **Monitoring stack** in `deploy/compose.monitoring.yaml`, all images digest-pinned:
  - Alertmanager, with its config rendered by an entrypoint script and receiver secrets read through `*_file` fields;
  - postgres-exporter for both databases;
  - node-exporter for disk space.
  - Add all of them to `prometheus.yml`.
- **Alerts** in `alerts.yml`:
  - Fix `AiJobsFailing` to use a ratio with `for: 15m`.
  - Add ReadinessFailing, QueueBacklog/OldestQueuedJobAge (with `max()` across workers), AiJobsExhausted, HttpLatencyP95, DbPoolSaturation, PostgresConnectionsHigh, DatabaseSizeGrowth, DiskLow and ProcessMemoryHigh.
  - Every alert has a `runbook_url`.
- **Metrics:** the worker loop publishes queue depth and oldest-job age; Grafana panels for the new metrics.
- **Docs:** `docs/operations/slos.md` (availability, API p95 latency, job start latency) and `docs/operations/alerts.md` (a runbook per alert).
- **CI:** `promtool check rules` and `amtool check-config`; add the metric-name allow-list to `test_monitoring_metrics.py`.

### PR 10 · Container and edge hardening
- **Compose:**
  - `x-logging` (json-file with `max-size`/`max-file`) on every service;
  - `mem_limit`, `cpus` and `pids_limit` on every service;
  - healthchecks for `clamav` and `worker`.
- **Secrets:**
  - A `*_FILE` convention, read only in `settings.py`, for the database password, service tokens and provider keys, backed by Docker secrets.
  - New `docs/operations/secrets.md` with rotation steps for each.
- **Managed Postgres:** `DATABASE_URL: ${DATABASE_URL:-postgresql://…?sslmode=${DATABASE_SSLMODE:-prefer}}`, so a managed database needs no manifest edit. Update the test's substring assertion.
- **Forwarded headers:**
  - nginx forwards the original scheme with a `map` on `$http_x_forwarded_proto` that defaults to `$scheme`.
  - HSTS is set through a `map` in `default.conf.template`; `security-headers.conf` isn't templated.
  - Compose sets a fixed network subnet, and uvicorn's `--forwarded-allow-ips` names it instead of `*`.
- **Logging and shutdown:**
  - `IngestionLoop` (`ingestion_loop.py:28-47`) logs a traceback with document text stripped, increments `smb_ingestion_failures_total`, and joins for the configured shutdown grace instead of 1s.
  - `error_handlers.py:58-67` logs the exception type and correlation ID only; the full message stays in the opt-in debug trace.
- **Heartbeat** (`polling_worker.py:125-143`):
  - Tolerate transient renewal errors until the lease is actually at risk.
  - When the lease is lost, set cooperative cancellation. Documented: a provider HTTP call already in progress finishes first.

### PR 11 · CI and supply chain
- **`ci.yml`:**
  - top-level `permissions: contents: read`;
  - a gitleaks job;
  - ruff `S` rules, with tests ignoring `S101` and justified per-line `noqa` for the existing f-string SQL that only inserts constant fragments.
- **More scanning:** a new `codeql.yml` for Python and JavaScript, and a weekly scheduled Trivy rescan of the latest release images.
- **Keycloak images:** pin both in `deploy/keycloak/compose.yaml:3,17` by digest, add a restart policy, and add them to `test_image_pins.py` and to `dependabot.yml` (`/deploy/keycloak`).
- **Identity-provider guidance:** new `docs/operations/identity-provider.md` on production settings: token lifespans, and issuing refresh tokens so silent renewal doesn't depend on third-party cookies in an iframe.

### PR 12 · Frontend resilience and support (exception)
- **Timeouts and cancellation:**
  - `sessionFetch` gets default timeouts through `AbortSignal.timeout`: 30s for JSON, 120s for uploads and downloads.
  - `api` methods accept an optional `{ signal }`, and query functions pass React Query's signal through, starting with the polling providers and workspace hooks.
- **Correlation IDs:** show `ApiError.correlationId` as "Reference: …" in `ErrorNotice`, `ErrorState` and error toasts.
- **Client error reporting:**
  - `window.onerror`, `unhandledrejection` and the error boundary post to a new `POST /api/client-errors`.
  - It is public but rate-limited, so failures before login and chunk-load failures still get reported. Add it to `test_route_authentication.py`.
  - The body is size-bounded and logged as JSON, and counted in `smb_client_errors_total`.
- **CSP identity origins at runtime:**
  - The build emits a placeholder in the CSP `<meta>` tag.
  - A `/docker-entrypoint.d/` script writes the final `index.html` to a separate tmpfs (`/run/web`), served via `location = /index.html`.
  - The script refuses to start when `IDENTITY_PROVIDER=oidc` (now passed to `web`) and `CSP_IDENTITY_ORIGINS` is empty.
- **Node version:** `package.json` gets `engines.node >=24` and an `.nvmrc`; `src/api/client.test.ts:219` uses a string body instead of a jsdom Blob.

---

## Phase 3: P2 and scale

### PR 13 · Bounded reads and data lifecycle
- **Paging for documents and drafts:**
  - `GET /documents` and `GET /requirements/drafts` get `offset`/`limit` (max 100) plus server-side `q` and sort, following the worklist convention (`routes/requirements.py:288-289`, `schemas/requirements.py:174-180`).
  - Visibility is filtered in SQL.
  - A batch ownership lookup (`get_draft_ownerships(ids)`) removes the N+1 queries in `identity_access.py:383-389` and `owned_requirements.py:94-109`.
- **Frontend (exception):** `DocumentsPage.tsx` and `DashboardPage.tsx` move to `useInfiniteQuery`.
- **Retention:**
  - Prune payloads of **succeeded and cancelled** AI jobs older than `AI_JOB_PAYLOAD_RETENTION_DAYS`. Failed jobs keep their `command`, because retry reuses it.
  - Keep the job rows, which activity rebuilds read.
  - Orphaned document blobs: report them and add a size metric only. Deleting them stays a separately authorised change.
  - Document a daily schedule for the `retention` profile.

### PR 14 · Tracing
- Optional OpenTelemetry, disabled when no OTLP endpoint is set, so the app still runs offline.
- Instrument FastAPI, httpx and psycopg in the composition root.
- Propagate `traceparent` to the knowledge service, and record the correlation ID as a span attribute.

### PR 15 · Frontend polish (presentation only)
- A 404 page built on `EmptyState`, replacing `App.tsx:73`.
- On route change, focus the page's `<h1>`, and give `<main>` `tabIndex={-1}` (`AppShell.tsx:124`).
- A guarded storage helper, used at `RequirementPage.tsx:153` and `NewRequirementPage.tsx:146`.
- Only allow `https:` links in `PriorArtPanel.tsx:30`.
- Delay `revokeObjectURL` (`client.ts:319`).

### PR 16 · Repository governance and accepted risks
- **Files:**
  - LICENSE, with the owner choosing the licence;
  - CHANGELOG.md in Keep a Changelog format, used by the release workflow;
  - SECURITY.md, `.github/CODEOWNERS` and a PR template.
- **Recorded in the slice spec as accepted risks or decisions:**
  - tokens in `sessionStorage`, mitigated by the strict CSP;
  - the silent-renewal iframe (see the identity-provider doc);
  - workspace-wide read access (ADR-0075), to be confirmed by the product owner;
  - no i18n framework (English only).
- **Follow-up issue** for knowledge-portal: its images share the fail-open config, CSP and deployment findings.

---

## Order of work

```text
Phase 0 kernel release   (runs in parallel with Phase 1)
PR 1 → PR 8 → PR 2 → PR 4a → PR 4b → PR 5 → PR 6           pilot gate
kernel bump → PR 3, PR 7, PR 9, PR 10, PR 11, PR 12
PR 13 → PR 14 → PR 15 → PR 16
```

## Verification

**Every PR:**
- Backend: `pytest`, `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports`.
- Postgres adapters and migrations: tests run with `TEST_DATABASE_URL` against the pinned pgvector image.
- Frontend: `npm run api:check && npm run lint && npm run typecheck && npm run test:coverage && npm run build`.

**Specific checks:**

| PR | Check |
|---|---|
| PR 1 | The production-mode CI boot passes. The fake-identity variant refuses to start. `/api/docs` returns 404 at the edge. |
| PR 2 | A job that crashes its worker repeatedly ends as `failed/attempts_exhausted` and the queue keeps moving. A provider 503 retries with backoff and keeps requirement order. |
| PR 8 | With the knowledge service stopped, analysis succeeds and is marked as not grounded. |
| PR 4a/4b | No synchronous provider route is left. The Playwright smoke and platform specs pass, with mapping running as a job. `/ready` stays under 2s while requests are saturated. |
| PR 5 | vitest covers renewal and the error boundary. Manually: with a tab open across a deploy, the user gets a reload prompt instead of a blank page. |
| PR 6 | Run `release.yml` on a test tag. Then `compose pull && up` by tag; backup → restore → `tests.release_recovery verify`. |
| PR 3 | Holding a lock makes a second transaction fail after `lock_timeout` with 503 `database_busy`. |
| PR 7 | With two API replicas in the CI deployment job, the N+1th call within one minute returns 429. Spending the token budget blocks the next provider call. |
| PR 9 | `promtool` and `amtool` pass in CI. A forced readiness failure fires its alert. |

**Final:**
- The full CI suite is green: deployment, recovery, smoke, Trivy and the audits.
- Each review finding is closed in the slice spec with a link to its PR.
