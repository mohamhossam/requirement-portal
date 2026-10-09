# Production Hardening — Second Production-Readiness Review

## Status

**Specified 2026-10-08; in progress since 2026-10-09.** PR 1, PR 8, PR 2, PR 4a and PR 4b are delivered (see their entries and Validation Evidence); everything else is not implemented yet. This record keeps the
plan for closing every finding of the second production-readiness review (security, deployment and
CI, reliability and observability, frontend) so it can be scheduled later. When work starts, each
PR converts its part into the `WORKSPACE.md` §10 sections and fills in Validation Evidence here.

**Revalidated 2026-10-09 against `main` 6f255d9.** Every item was rechecked after ADR-0104
(independent portals), the platform-kernel v1.1.0 pin and the AI job trace-gap fixes
(`docs/slices/fix-ai-job-trace-gaps.md`) merged; the plan below reflects that state.

Review baseline (2026-10-08, commit `41a7516`): `pytest` 1795 passed / 75 skipped, `ruff check`,
`ruff format --check`, `mypy src tests` and `lint-imports` green (43 import contracts on `main`
6f255d9); frontend build, lint, typecheck, OpenAPI drift and `npm audit` green, vitest 501/502
(the failure is a Node 22 vs Node 24 test-environment difference, fixed in PR 12).

## What changed since 2026-10-08

| Change on main | Effect on the plan |
|---|---|
| **ADR-0104 independent portals.** This compose runs requirement work only, with an optional `deploy/compose.peer.yaml`. The knowledge portal is optional in production: `/knowledge-api/` → 404 and `/knowledge/` → 301 to `KNOWLEDGE_PORTAL_URL`. | All `x-knowledge`, `knowledge-*` and `/knowledge-api/` items are **obsolete**. PR 8 gets a third state, "not connected". The fail-closed fix for the knowledge portal moves to that repo (PR 16). |
| **ADR-0104 number taken.** | Plan ADRs become **0105–0109**. |
| **platform-kernel v1.1.0 released and pinned**, adding service credentials, `OidcSigningKeys` and service JWT verifiers. | Phase 0 ships as **v1.2.0**. JWKS work moves to `OidcSigningKeys` and also protects `/internal`. |
| **G1 attempt cap merged** (`ai_job_execution.py:134,159,187-199`). | PR 2 shrinks to backoff plus the exhausted metric. Exhausted jobs are still counted as `status="failed"`, so that metric is **not** delivered. |
| **G2 refuses a doomed analysis before enqueue.** The trace-gap doc defers the same check for Epic, Features and Stories. | Folded into PR 4b. |
| **Frontend exceptions on record:** G3/G4/G6, plus the portal URL and role logic. | ADR-0109 consolidates the policy. |
| **One requirements database only.** Monitoring scrapes only `api` and `worker`. | PR 6 and PR 9 shrink. |
| **New secrets:** `REQUIREMENT_SERVICE_CLIENT_SECRET`, and service tokens now set in `production.env`. | Added to PR 10. |
| **New migrations `202610091000`/`202610091200`** (a dynamic `DROP` inside `EXECUTE`). | The expand/contract cutoff must be at or after `202610091200`, and the scan must also catch `EXECUTE`. |
| **`.importlinter` now has 43 contracts.** | Baseline wording. |

Everything else was rechecked and is still valid; line references below are against `main` 6f255d9.

## Decisions (owner, 2026-10-08, unchanged)
- **Frontend logic fixes:** allowed as a recorded exception to CLAUDE.md's "presentation only" rule, in their own PRs.
- **Kernel fixes:** shipped as a kernel release, now **v1.2.0**, followed by a pin bump here.
- **Synchronous provider routes:** move to the durable job queue now.
- **Provider rate limit across replicas:** counted in Postgres.

## Process
- **ADRs:**

  | ADR | Decision |
  |---|---|
  | 0105 | Durable-only provider work |
  | 0106 | Postgres provider rate limit and spend cap; retires debt row AGENTS.md:722 |
  | 0107 | AI-job retry with backoff, amending ADR-0020 next to G1's cap |
  | 0108 | Release images, deploy by tag, backups, expand/contract migrations |
  | 0109 | Policy for frontend logic exceptions; consolidates G3/G4/G6, the portal-link exception and this plan; updates AGENTS.md:723 |

- **Rules for every PR:**
  - The five backend gates pass, plus the frontend build, lint, typecheck and tests.
  - New public errors go in `public_errors.py` with a status test.
  - Constructor parameters are required (§12).
  - Variables read by `settings.py` go in `.env.example`. Compose-only variables (`WEB_PORT`, `IMAGE_TAG`, `POSTGRES_MAX_CONNECTIONS`, `DATABASE_SSLMODE`, `KNOWLEDGE_PORTAL_URL`, `PEER_NETWORK`, …) go in `deployment.md`.
- **Constraint tests on main:**

  | Test or check | Constraint |
  |---|---|
  | `test_action_pins.py` | Actions pinned by SHA |
  | `test_image_pins.py` | `OWN_IMAGES` at :16; scans the 3 compose files plus ci.yml |
  | `test_platform_deployment.py` | Rewritten for ADR-0104: no knowledge services, volumes `{postgres_data, clamav_data}` at :51, `web.depends_on` only `api` at :80-81 |
  | `test_deployment_mounts.py` | 5 backend services |
  | `test_monitoring_metrics.py` | `smb_*` names must exist in the kernel |
  | `test_route_authentication.py` | Public routes allow-list |
  | `test_provider_rate_limit.py` | Every provider-calling route is limited |
  | `test_migration_catalogue.py` | Migration naming and ordering |
  | `ci.yml:275` | CI greps for the CSP `<meta>` tag |

## Phase 0: platform-kernel v1.2.0
| Change | Note |
|---|---|
| Migration runner: session advisory lock, plus per-file `lock_timeout` | Not in 1.1.0 |
| Pooled connector: `configure(conn)` hook and public `stats()` | App pool built at `composition/persistence.py:407-415` |
| OIDC leeway (default 60s); `typ`/`azp` checks for user tokens | Service tokens already check `azp` |
| `OidcSigningKeys`: fetch outside the lock, and serve the last good keys while refreshing or when the IdP errors | Now shared by sign-in and `/internal` (`composition/identity.py:58-90`) |
| `max_completion_tokens` for the plain `LLM_PROVIDER=openai` client | Profiles already support output limits (`profiles.py:29`) |
| Process/Platform/GC collectors and new metrics: `smb_build_info`, `smb_ai_jobs_queued`, `smb_ai_job_oldest_queued_age_seconds`, `smb_db_pool_connections`, `smb_ready`, `smb_ingestion_failures_total`, `smb_client_errors_total`, `smb_provider_spend_blocked_total` | |
| `InternalHttpClient` circuit breaker, which also covers failed client-credential grants | Note in the changelog that knowledge-portal is affected too |

Then bump `pyproject.toml:12` and `uv.lock`, and wire the new settings. Phase 1 doesn't wait for this; PRs 3, 9 and 10 do.

## Phase 1: P0, the pilot gate

**PR 1 · Production config fails closed** — *delivered on `claude/production-hardening-pr1`, 2026-10-09*
- **Manifest pins production.** `deploy/compose.production.yaml` sets `APP_ENV: production` and `IDENTITY_PROVIDER: oidc` in the `x-backend` environment, which overrides `production.env`; ADR-0074 amendment "The manifest fails closed".
- **Demo overlay.** New `deploy/compose.demo.yaml` restores `development`/`fake` for `migrate`, `maintenance`, `retention`, `api` and `worker`, and publishes `web` with `ports: !override` on `127.0.0.1` only. CI's `COMPOSE` and every demo command in `README.md` and `START_GUIDE.md` §2 add it; `demo.env.example` keeps its two lines because the knowledge-portal demo reuses the file.
- **Production refusals.** `settings_validation.py` refuses `LLM_PROVIDER=fake`, `DEBUG_TRACE_ENABLED=true` and any `LOG_FORMAT` other than `json` under `APP_ENV=production`; `deployment_preflight.py` refuses the fake model and the debug trace under any `APP_ENV`. Model profiles always name a real endpoint, so there is no fake profile to refuse.
- **API documentation closed at the edge.** `deploy/web/default.conf.template` answers 404 for `/api/docs` (with `oauth2-redirect`), `/api/redoc` and `/api/openapi.json`; the CI edge loop checks all four.
- **Production boots in CI, without Keycloak.** OIDC discovery is lazy, so the CI `deployment` job starts the manifest alone (no demo overlay) with a placeholder HTTPS issuer and `LLM_PROVIDER=openai` with a placeholder key. It checks the preflight exits 0, `/ready` answers, `/identity/me` answers 401 with and without `X-Fake-Actor-Id`, fake identity stops the boot and the fake model makes the preflight exit 2. A real sign-in against an issuer stays with the knowledge-portal and Keycloak guides.
- **Launchers.** `start.sh --migrate`, `start.ps1 -Migrate` and `start.bat -Migrate`: an external PostgreSQL named by `DATABASE_URL` is never migrated without it; local PostgreSQL still is.

**PR 8 · Analysis survives a knowledge outage** — *delivered on `claude/production-hardening-pr8`, 2026-10-09*
- **Grounding recorded on the analysis**, as a new `RequirementAnalysis.reference_grounding` (`ReferenceGroundingStatus`: `grounded`, `no_evidence`, `not_connected`, `unavailable`) rather than a `stage_provenance` entry: a stage record needs a model, prompt version and input fingerprint that a skipped check does not have. It is persisted only when set, so older payloads and the characterisation goldens are unchanged, and the stories generation-context token leaves it out while unset so tokens minted before the change stay valid. Glossary: "Reference grounding".
- **The reference port says whether a portal stands behind it** (`ReferenceKnowledgePort.is_connected()`: the offline stand-in `False`, the HTTP adapter and the test library `True`), so `not_connected` is not confused with `no_evidence`.
- **`ReferenceGrounding.augment`** catches `ServiceUnavailableError` from `has_published` or any `search_evidence` call (including a failed client-credentials grant) and returns the primary analysis marked `unavailable`, with no reference proposals; the paid-for primary result is kept.
- **API and UI.** `GET /requirements/{id}/analysis` returns `reference_grounding`; the analysis panel shows "References were not checked" only for `unavailable`.
- **Unified search** answers with Requirement hits only when a connected library is unreachable, and sets `X-Reference-Library: unavailable`; the response body keeps its shape (`tests/release_load.py` reads it).
- ADR-0104 amendment "An unreachable portal degrades, it does not fail".

**PR 2 · AI-job retry with backoff** — *delivered on `claude/production-hardening-pr2`, 2026-10-09* (recorded as an ADR-0020 amendment beside G1's cap, instead of a separate ADR-0107)
- **Requeue, not fail.** An attempt that fails with `model_rate_limit`, `model_unavailable` or `platform_service_unavailable` while attempts remain returns the job to `queued` through `AiJob.requeue` (the attempt stays spent, unlike `defer`) with `next_attempt_at`; the attempt at `AI_JOB_MAX_ATTEMPTS` fails with the outage's own code. Timeouts and invalid output stay terminal.
- **Backoff** `RetryBackoff`: `AI_JOB_RETRY_FIRST_SECONDS` (30) doubling to `AI_JOB_RETRY_MAX_SECONDS` (300), validated at boot and documented in `.env.example` and WORKSPACE.md.
- **Claims** (`postgres_ai_jobs.py`, `in_memory_ai_jobs.py`) skip a job before its `next_attempt_at` and hold its Requirement's other jobs behind it; migration `202610091400_ai_job_retry_backoff.sql` adds the column and a partial index.
- **Visible.** The job API returns `next_attempt_at`; the job panel says "will try again" and when. `smb_ai_jobs_total` labels requeued attempts `retrying` and capped jobs `attempts_exhausted` (closing the gap G1 left), and `AiJobsFailing` counts `attempts_exhausted`.

**PR 4a · Mapping becomes a job; probes and shutdown** (ADR-0105, part 1) — *delivered on `claude/production-hardening-pr4a`, 2026-10-09*
- **The browser maps through the job routes.** `BreakdownView` starts `POST /architecture-mapping/jobs` and waits for the job (`features/architecture/runMappingJob.ts`, under the recorded frontend exception); the busy state, error toast and refresh work as before. Offline the job finishes inside the request, so nothing is polled. The synchronous route stays until PR 4b.
- **Mapping needs membership, not a role** (owner's decision, ADR-0104 amendment 2026-10-09): the job routes no longer require `architecture_reader`, matching the synchronous route they replace; reading jobs follows ADR-0075; cancelling or retrying another person's job still needs `architecture_maintainer`. `architecture_reader` and the `architecture-readers` group are retired from code, realm, personas and docs.
- **Probes off the request pool.** `/health` and `/ready` are coroutines; `/ready` runs its database check on its own two-thread limiter and answers 503 within 2.5s if the check hangs.
- **Shutdown.** `serve.py` gives in-flight requests 25s (`timeout_graceful_shutdown`), within the manifest's new `api.stop_grace_period: 30s`; `web` has a healthcheck.
- The "no architecture catalogue connected" state needs no new UI: offline mapping still succeeds with the declared systems and the catalogue's uncertainty, as before.

**PR 4b · Retire the synchronous provider routes** (ADR-0105, part 2) — *delivered on `claude/production-hardening-pr4b`, 2026-10-09*
- **Deleted** every route that ran a model inside the request, 16 in all:
  - analysis:
    - `POST …/analysis`;
    - `…/analysis/clarifications`;
    - `…/analysis/question-resolutions`;
    - `…/analysis/questions/{id}/resolution`;
  - mapping: `POST …/architecture-mapping`;
  - generation:
    - `POST …/epic`;
    - `POST …/features`;
    - `POST …/features/{id}/stories`;
  - Story regeneration and proposals:
    - `…/stories/regeneration`;
    - `…/stories/{id}/regeneration`;
    - `…/stories/change-proposals`;
  - quality reads that ran the evaluator:
    - `GET …/stories/quality`;
    - `…/stories/{id}/quality`;
    - `…/split-recommendations`;
  - review:
    - `POST …/breakdown-review`;
    - `…/breakdown-review/open-questions/{id}/resolution`.

  Each has a job equivalent or was unused; Feature quality is read from its stored snapshot.
  Their providers, schemas and `Container` fields went with them, along with three pieces that
  only those routes used:
  - `ValidateStory`: its users now take `AssessStoryCandidate`;
  - `SuggestStorySplit.execute`;
  - `RequirementCommands`' expected-context check, since a job checks the context token when it
    starts.
- **Kept**, where the plan named them for deletion:
  - asking a clarification question (`analysis.py:569` in the plan) and deciding an intent
    proposal. These are human actions that only queue model work, and they stay rate-limited as
    automatic triggers;
  - unified search.
- **Refused before enqueue.** `GenerateEpic`, `GenerateFeatures` and `GenerateStories` expose
  `require_can_generate`, which `AiJobs` calls beside G2's analysis check. A start that can only
  fail gets 409 at once:
  - an Epic from an unconfirmed analysis, or over human work without `force`;
  - Features before the Epic is approved, or over human work without `force`;
  - first Stories that already exist, or for a Feature that is not ready.

  Story regeneration over human work, and mapping refusals, still surface as failed jobs.
- **Tests.** `tests/job_driver.py` starts a job through the public route and plays the worker
  with the container's queue and executor. The workflow helpers and the test files that used the
  routes now go through it, including the PostgreSQL persistence suite. The provider rate-limit
  sets shrink to the job, mapping-job, index-retry and search routes.
- **Client.** `frontend/openapi.json` and `schema.d.ts` are regenerated, and the 15 unused client
  functions are removed.
- **Edge.** nginx `/api/` `proxy_read_timeout` and `proxy_send_timeout` drop from 600s to 60s,
  pinned by a deployment test.
- ADR-0105 records the decision, with an ADR-0020 amendment.

**PR 5 · Session safety and crash handling** (exception, ADR-0109)
- **Renewal stops aborting requests:**
  - `client.ts:163-169`: new `replaceAuthenticationHeaders()`, which doesn't abort.
  - `AuthProvider.tsx:139-145`: on renewal with the same `profile.sub`, only replace the headers; then `queryClient.invalidateQueries()`.
- **Aborts after the response arrives** (`client.ts:177,215,310,350`) become `ApiError(0)`, with no toast. Add a `startKeys.ts` test, because G6 keeps a start's key on a status-0 error.
- **Error boundaries:** `components/states/ErrorBoundary.tsx` built on `ErrorState`, as a root boundary in `main.tsx` and around `<Suspense>` at `App.tsx:46`, with a reload prompt for chunk-load errors.

**PR 6 · Releases, backups, upgrade and rollback** (ADR-0108)
- **Release workflow:** `release.yml` on `v*` tags:
  - checks the tag matches `pyproject.toml:7` and `package.json:4`;
  - builds once, then runs Trivy, generates an SBOM with syft, and signs with cosign;
  - pushes `ghcr.io/mohamhossam/requirement-{api,web}`;
  - creates the GitHub release from the CHANGELOG.
- **Compose images:** `${REQUIREMENT_API_IMAGE:-requirement-platform/api}:${IMAGE_TAG:-local}` (:21, :153), and the same for web. Update `test_platform_deployment.py:42-45`, `test_image_pins.py:16,36` and the Trivy loop at `ci.yml:254`.
- **Version reporting:** `FastAPI(version=importlib.metadata.version(...))` (`main.py:158-161`), and `/health` returns the version.
- **Backups:**
  - One `backup` service (profile `backup`) runs `pg_dump -Fc` for `smb_requirements` into a `backups` volume. Update the volume set at `test_platform_deployment.py:51`.
  - New `docs/operations/backup-restore.md`: schedule, off-host copy, restore checked by `tests.release_recovery verify`, and RPO/RTO for the owner to confirm.
- **Upgrade runbook:** rewrite `deployment.md` "Upgrades" (:168-181) as backup → pull by tag → migrate → up. Roll back by redeploying the previous tag, or by restoring the backup when a release has a contract step.
- **Migration policy:** document expand/contract in WORKSPACE.md, with an architecture test that:
  - rejects `DROP`/`RENAME`/`ALTER … TYPE`, including inside `EXECUTE`/`DO`, unless the file has a `-- contract-step:` marker;
  - grandfathers migrations up to `202610091200`.

## Phase 2: P1 (PRs 3, 9 and 10 need kernel v1.2.0)

**PR 3 · Postgres timeouts and connection budget**
- **Timeouts:**
  - Use the kernel `configure` hook to set `statement_timeout` (30s), `lock_timeout` (5s) and `idle_in_transaction_session_timeout` (60s) on every pooled connection, including those used after `external_call`, and in `architecture_mapping_stats.py`, `postgres_architecture_jobs.py`, `corpus_counts.py` and `knowledge_portfolio.py`.
  - `lock_timeout` also bounds `pg_advisory_xact_lock` (`postgres_store.py:125-128`).
  - One-shot commands keep using direct connections, with no limits.
  - Errors 57014 and 55P03 map to a 503 `database_busy`.
- **Connection budget:**
  - Postgres runs with `-c max_connections=${POSTGRES_MAX_CONNECTIONS:-200}`.
  - `deployment.md` gets a sizing formula.
  - The pool reports `smb_db_pool_connections` from `stats()`.

**PR 7 · Shared rate limit, spend cap and edge limits** (ADR-0106)
- **Shared limit:** a port under `ProviderCallRateLimit` (`provider_call_rate.py:32-95`):
  - The in-memory adapter keeps today's logic.
  - The Postgres adapter uses a `provider_call_windows(actor_id, window_start, calls)` upsert, following `knowledge/infrastructure/prior_art.py:212-228`.
  - Wired at `container.py:794-796`.
- **Spend cap:** `PROVIDER_DAILY_TOKEN_BUDGET`, kept in a Postgres daily counter.
- **Edge limits:**
  - nginx `real_ip` from `TRUSTED_PROXY_CIDR`, defaulted with an `ENV` line as in `deploy/web/Dockerfile:43-44`.
  - Per-IP `limit_req` on `location /api/` (:74-87) only, returning a JSON 429.
  - A stricter limit on `impact-preview` (`requirements.py:431`).
- **Docs:** remove the debt row at AGENTS.md:722; update `deployment.md` "Rate limiting" (:313-330).

**PR 9 · Alerting, SLOs and runbooks**
- **Monitoring stack** (`compose.monitoring.yaml`, currently Prometheus and Grafana only): add Alertmanager (config rendered by an entrypoint, secrets through `*_file`), one postgres-exporter and node-exporter, all digest-pinned. Scrape them in `prometheus.yml:13-30`.
- **Alerts:**
  - Fix `AiJobsFailing` (`alerts.yml:39-44`) to use a ratio with `for: 15m`.
  - Add ReadinessFailing, QueueBacklog/OldestQueuedJobAge (with `max()`), AiJobsExhausted (needs PR 2's metric), HttpLatencyP95, DbPoolSaturation, PostgresConnectionsHigh, DatabaseSizeGrowth, DiskLow and ProcessMemoryHigh.
  - Every alert gets a `runbook_url`. `DailyTokenBudgetExceeded` already exists.
- **Docs:** `docs/operations/slos.md` and `docs/operations/alerts.md`.
- **CI:** `promtool check rules` and `amtool check-config` next to `ci.yml:353`, plus a metric-name allow-list in `test_monitoring_metrics.py`.

**PR 10 · Container and edge hardening**
- **Compose:**
  - `x-logging` with rotation, and `mem_limit`/`cpus`/`pids_limit` on postgres, clamav, migrate, maintenance, retention, api, worker and web;
  - healthchecks for `clamav` and `worker`;
  - the CI clamav step waits for it (`ci.yml:265`).
- **Secrets:** a `*_FILE` convention, read only in `settings.py`, for:
  - the database password;
  - `REQUIREMENT_SERVICE_TOKEN` and `KNOWLEDGE_SERVICE_TOKEN`;
  - `REQUIREMENT_SERVICE_CLIENT_SECRET`;
  - provider keys.
  - New `docs/operations/secrets.md` with rotation steps for each.
- **Managed Postgres:** `DATABASE_URL: ${DATABASE_URL:-postgresql://…?sslmode=${DATABASE_SSLMODE:-prefer}}` (:33). Fix the wording at `deployment.md:437-438`.
- **Forwarded headers:**
  - nginx forwards the original scheme with a `map` (instead of `$scheme` at :81) and adds HSTS through a `map`.
  - Give `networks.default` a fixed subnet, and set uvicorn `--forwarded-allow-ips` (:123) to it instead of `*`. This matters more now, because `compose.peer.yaml` lets other services reach `api` directly.
- **IngestionLoop** (`ingestion_loop.py:28-47`):
  - log a sanitised traceback, rate-limited, because the loop retries about every second while a connected portal is down;
  - increment `smb_ingestion_failures_total`;
  - join for the shutdown grace period instead of 1s.
- **Errors and heartbeat:**
  - `error_handlers.py:58-67` logs the exception type and correlation ID only.
  - The heartbeat (`polling_worker.py:125-143`) tolerates transient errors until the lease is at risk, then cancels cooperatively. A provider call already in progress finishes first.

**PR 11 · CI and supply chain**
- **`ci.yml`:**
  - top-level `permissions: contents: read`;
  - a gitleaks job, with an allowlist for the CI-only tokens at `ci.yml:193-197`;
  - ruff `S` rules (`pyproject.toml:58`), ignoring `S101` in tests and with justified `noqa` comments for the constant-fragment SQL.
- **More scanning:** `codeql.yml`, and a weekly Trivy rescan of release images (after PR 6).
- **Keycloak images:** digest-pin both lines in `deploy/keycloak/compose.yaml` (:3, :17) and add `restart:`. Add the file to `test_image_pins.py:28-33` and `dependabot.yml:54-62`.
- **`docs/operations/identity-provider.md`:**
  - token lifespans and refresh tokens, so silent renewal doesn't need third-party cookies;
  - the public `requirement-spa` and confidential `requirement-service` clients.

**PR 12 · Frontend resilience** (exception)
- **Timeouts and cancellation:**
  - `sessionFetch` default timeouts: 30s for JSON, 120s for uploads and downloads.
  - `api` methods accept an optional `{ signal }`, and query functions pass it through.
- **Correlation IDs:** show `ApiError.correlationId` (`errors.ts:6`) in `ErrorNotice`, `ErrorState` and toasts.
- **Client error reporting:** a new public, rate-limited `POST /api/client-errors`. Add it to `test_route_authentication.py`.
- **Runtime build-time values:**
  - Render `CSP_IDENTITY_ORIGINS`, and the `VITE_KNOWLEDGE_PORTAL_URL`/`ROLE` values that are now baked into the build, at container start.
  - Use a `/docker-entrypoint.d/` script that follows the `check-knowledge-portal-url.sh` precedent (`Dockerfile:39`) and writes `index.html` to a `/run/web` tmpfs.
  - Refuse to start when OIDC is used and the origins are empty. Keep the `<meta>` tag.
- **Node version:** `engines.node >=24` plus `.nvmrc`. `client.test.ts:218` uses a string body, closing the item the trace-gap doc deferred.

## Phase 3: P2 and scale

**PR 13 · Bounded reads and payload retention**
- **Paging:**
  - `GET /documents` (`documents.py:361`) and `GET /requirements/drafts` (`requirements.py:334`) get `offset`/`limit` plus `q` and sort, following `requirements.py:290-291` and `schemas/requirements.py:178-179`.
  - Batch the ownership lookups (`identity_access.py:371-384`, `owned_requirements.py:98-99`).
  - `DocumentsPage` and `DashboardPage` move to `useInfiniteQuery` (exception).
- **Retention:** prune payloads of succeeded and cancelled AI jobs only. Report orphaned document blobs, and add a size metric. The daily retention schedule is already documented.

**PR 14 · Tracing**
- Optional OpenTelemetry, off when no OTLP endpoint is set.
- Instrument FastAPI, httpx (which also covers the token client at `references.py:133`) and psycopg.
- Send `traceparent` to the portal only when one is connected.

**PR 15 · Frontend polish**
- **Presentation only:**
  - a 404 page from `EmptyState` (`App.tsx:73`);
  - focus on route change, with `<main tabIndex={-1}>` (`AppShell.tsx:124`);
  - `https:`-only links in `PriorArtPanel.tsx:30`.
- **Under the exception:**
  - a guarded storage helper at `RequirementPage.tsx:153` and `NewRequirementPage.tsx:149`;
  - delay `revokeObjectURL` (`client.ts:319`).

**PR 16 · Governance and accepted risks**
- **Files:** LICENSE (owner chooses), CHANGELOG.md, SECURITY.md, `.github/CODEOWNERS` and a PR template.
- **Accepted risks to record:**
  - tokens in `sessionStorage`;
  - the silent-renewal iframe;
  - workspace-wide read access (ADR-0075), for the product owner to confirm;
  - English only.
- **Follow-up issue for knowledge-portal:** it now owns its own compose, edge and realm entities (ADR-0104), so PR 1's fail-closed pinning and demo split, the CSP runtime change and the backups all need doing there too. CI runs its v0.2.0 in development/fake mode.

## Order of work
```text
Phase 0 kernel v1.2.0  (in parallel with Phase 1)
PR 1 → PR 8 → PR 2 → PR 4a → PR 4b → PR 5 → PR 6        pilot gate
kernel bump → PR 3, PR 7, PR 9, PR 10, PR 11, PR 12
PR 13 → PR 14 → PR 15 → PR 16
```

## Verification
**Every PR:**
- Backend gates, with `TEST_DATABASE_URL` against the pinned pgvector image.
- Frontend: `api:check`, `lint`, `typecheck`, `test:coverage` and `build`.

**Specific checks:**

| PR | Check |
|---|---|
| PR 1 | The production-mode CI job boots, the fake-identity variant refuses to start, and `/api/docs` returns 404 at the edge. |
| PR 8 | Analysis works in all three grounding states. With the portal down, unified search returns requirement hits plus the flag. |
| PR 2 | A provider 503 is retried with backoff, in requirement order. An exhausted job shows up in the new metric label. |
| PR 4a/4b | No synchronous provider route is left, and smoke plus platform Playwright pass. `/ready` stays under 2s while requests are saturated. |
| PR 5 | Same-subject renewal keeps in-flight requests alive, and the reload prompt replaces the blank page after a deploy. |
| PR 6 | A test-tag release can be pulled and run by tag. Backup → restore → verify succeeds. |
| PR 3 | Holding a lock produces a 503 `database_busy` after `lock_timeout`. |
| PR 7 | Two replicas share one limit, and a spent budget blocks the next call. |
| PR 9 | `promtool` and `amtool` pass, and a forced readiness failure fires its alert. |

**Final:** CI is all green, and every finding is closed in the spec with a link to its PR.

## Validation Evidence

### PR 1 (2026-10-09, branch `claude/production-hardening-pr1`)

Run locally on Python 3.13 with platform-kernel v1.1.0; no Docker daemon was available, so the
PostgreSQL suites skipped locally (CI runs them) and the manifest, nginx template and production
boot are proven by CI's `deployment` job.

```text
pytest                      1832 passed, 78 skipped in 136.62s
ruff check .                All checks passed!
ruff format --check .       1238 files already formatted
mypy src tests              Success: no issues found in 677 source files
lint-imports                Contracts: 43 kept, 0 broken.
cd frontend && npm run build   ✓ built in 919ms
docker compose -f deploy/compose.production.yaml -f deploy/compose.demo.yaml config
                            backend services APP_ENV=development, IDENTITY_PROVIDER=fake;
                            web published on 127.0.0.1:8080 only
docker compose -f deploy/compose.production.yaml config
                            backend services APP_ENV=production, IDENTITY_PROVIDER=oidc
python -m smb_requirement_agent.interfaces.deployment_preflight
                            exit 0 with OIDC and LLM_PROVIDER=openai; exit 2 with LLM_PROVIDER=fake
Settings.from_env() under APP_ENV=production
                            refuses LOG_FORMAT=text and IDENTITY_PROVIDER=fake, naming the setting
bash -n start.sh            syntax OK
```

### PR 8 (2026-10-09, branch `claude/production-hardening-pr8`)

Run locally on Python 3.13 with platform-kernel v1.1.0; no Docker daemon, so the PostgreSQL suites
skipped locally and CI runs them. The one local vitest failure is the known Node 22 export test
(CI runs Node 24; PR 12 fixes it).

```text
pytest                      1841 passed, 78 skipped in 163.95s
ruff check .                All checks passed!
ruff format --check .       1239 files already formatted
mypy src tests              Success: no issues found in 678 source files
lint-imports                Contracts: 43 kept, 0 broken.
npm run test                522 passed, 1 failed (client.test.ts export, Node 22 only)
npm run typecheck / lint    clean
npm run api:check           OpenAPI types match frontend/openapi.json
npm run build               ✓ built in 1.29s
tests/characterisation      70 passed (goldens unchanged)
```

### PR 2 (2026-10-09, branch `claude/production-hardening-pr2`)

Run locally on Python 3.13 with platform-kernel v1.1.0; no Docker daemon, so the PostgreSQL suites
(including the new `test_a_job_waiting_out_an_outage_is_stored_and_not_claimed_before_its_time`)
skipped locally and CI runs them. The one local vitest failure is the known Node 22 export test.

```text
pytest                      1860 passed, 79 skipped in 168.85s
ruff check .                All checks passed!
ruff format --check .       1240 files already formatted
mypy src tests              Success: no issues found in 679 source files
lint-imports                Contracts: 43 kept, 0 broken.
npm run test                523 passed, 1 failed (client.test.ts export, Node 22 only)
npm run typecheck / lint    clean
npm run api:check           OpenAPI types match frontend/openapi.json
npm run build               ✓ built in 1.24s
```

### PR 4a (2026-10-09, branch `claude/production-hardening-pr4a`)

Run locally on Python 3.13 with platform-kernel v1.1.0; no Docker daemon, so the PostgreSQL suites
skipped locally and CI runs them, and CI's deployment job proves the new healthcheck and stop grace.
The one local vitest failure is the known Node 22 export test.

```text
pytest                      1864 passed, 79 skipped in 164.71s
ruff check .                All checks passed!
ruff format --check .       1240 files already formatted
mypy src tests              Success: no issues found in 679 source files
lint-imports                Contracts: 43 kept, 0 broken.
npm run test                529 passed, 1 failed (client.test.ts export, Node 22 only)
npm run typecheck / lint    clean
npm run api:check           OpenAPI types match frontend/openapi.json (no API change)
npm run build               ✓ built in 1.16s
docker compose -f deploy/compose.production.yaml config   valid
```

### PR 4b (2026-10-09, branch `claude/production-hardening-pr4b`)

Run locally on Python 3.13 with platform-kernel v1.1.0, against a local PostgreSQL 16 with
pgvector (`TEST_DATABASE_URL`), so the PostgreSQL suites ran here too. The Playwright smoke ran
against the API with the fake model, in-memory store and in-process workers, on a preinstalled
Chromium. Its two failures are that browser's missing built-in PDF viewer frame, which this
change does not touch; CI installs Playwright's own browser. The one vitest failure is the known
Node 22 export test.

```text
pytest --cov (PostgreSQL)   1938 passed in 339.05s; total coverage 94.61% (floor 92.5%)
ruff check .                All checks passed!
ruff format --check .       1242 files already formatted
mypy src tests              Success: no issues found in 680 source files
lint-imports                Contracts: 43 kept, 0 broken.
npm run test                511 passed, 1 failed (client.test.ts export, Node 22 only)
npm run typecheck / lint    clean
npm run api:check           OpenAPI types match the regenerated frontend/openapi.json
npm run build               ✓ built
npm run test:smoke          45 passed, 2 failed (content-security-policy PDF viewer frame, local Chromium only)
```
