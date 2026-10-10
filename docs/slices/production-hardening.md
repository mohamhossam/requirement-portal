# Production Hardening — Second Production-Readiness Review

## Status

**Specified 2026-10-08; in progress since 2026-10-09.** Phase 0 (platform-kernel v1.2.0, and this repository's move to it) is delivered. PR 1, PR 8, PR 2, PR 4a, PR 4b, PR 5 and PR 6 are delivered, which completes the pilot gate (Phase 1), and so is all of Phase 2: PR 7, PR 3, PR 9, PR 10, PR 11 and PR 12 (see their entries and Validation Evidence). Phase 3 has started: PR 13, PR 14 and PR 15 are delivered. This record keeps the
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

*Delivered 2026-10-09:* kernel [mohamhossam/platform-kernel#7](https://github.com/mohamhossam/platform-kernel/pull/7), tagged `v1.2.0`, then the pin bump on `claude/production-hardening-kernel-1.2.0`.

**Kernel changes from this table**
- **One transaction per migration run.** A run stays one transaction. The `lock_timeout` (10s) is set before each file. Per-file transactions were tried and dropped, because this repository's migration test requires a failed run to apply nothing.
- **Exact pool count.** The pool counts lent connections itself.

**Wired here**
- **`OIDC_LEEWAY_SECONDS`** (60), for user tokens and `/internal`'s granted tokens.
- **Authorized parties.** A person's token must name `OIDC_CLIENT_ID` as `azp`, the owner's choice on 2026-10-09; `OIDC_AUTHORIZED_PARTIES` adds clients. The `typ` check is the kernel default.
- **`OPENAI_MAX_OUTPUT_TOKENS`** (8192, the owner's choice), through `openai_transport` and the seven OpenAI adapters.
- **One circuit breaker** shared by both knowledge clients.
- **ADR-0018 amendment.**

**Left to the PRs that use them**
- The pool `configure` hook, `stats()` and `smb_db_pool_*`: PR 3.
- The build, readiness, queue and spend-blocked metrics: PR 9.
- `smb_ingestion_failures_total`: PR 10.
- `smb_client_errors_total`: PR 12.

**Plan as specified**
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

**PR 5 · Session safety and crash handling** (exception, ADR-0109) — *delivered on `claude/production-hardening-pr5`, 2026-10-09*
- **Renewal stops aborting requests.**
  - `client.ts` gains `replaceAuthenticationHeaders()`, which swaps the token without aborting
    the credential session.
  - In `AuthProvider`, a renewal whose `profile.sub` matches the signed-in subject only replaces
    the headers, clears "session expired" and calls `queryClient.invalidateQueries()`.
  - It no longer runs `loadActor`. That used to hide the workspace behind "Resolving identity…"
    on every silent renewal.
  - A renewal that brings a different subject still aborts, reloads the identity and clears the
    cache.
- **Abandoned requests are typed.**
  - A request abandoned because the identity changed is `ApiError(0, …, "request_aborted")`. This
    covers the fetch, and reading the JSON or blob body after it arrived (`sessionBody`).
  - It used to be a raw `AbortError` after the answer arrived, or a toast-bearing status 0
    before it.
  - `mutationErrorToast` stays silent on it, while a real network failure still toasts.
  - `startKeys.ts` keeps a start's key on it, because the start may have reached the server.
- **Error boundaries.**
  - `components/states/ErrorBoundary.tsx` is built on `ErrorState`. It is the root boundary in
    `main.tsx`, and wraps the routes' `<Suspense>` in `App.tsx`.
  - The route boundary resets when the path changes. A crash offers "Try again" and "Reload the
    page".
  - A chunk-load error (a redeploy removed the page's code) offers only the reload.
- **ADR-0109** records the policy for frontend logic exceptions, with the exceptions so far. The
  AGENTS.md debt row for the deferred frontend items points to it.

**PR 6 · Releases, backups, upgrade and rollback** (ADR-0108) — *delivered on `claude/production-hardening-pr6`, 2026-10-09*
- **Release workflow.** `.github/workflows/release.yml` runs on `v*.*.*` tags.
  - It checks the tag against `pyproject.toml`, `frontend/package.json` and a `CHANGELOG.md`
    section (new file, `v0.1.0` written).
  - It runs all of `ci.yml` as a reusable workflow (a `workflow_call` trigger is added).
  - It builds each image once, refuses fixable HIGH/CRITICAL findings with Trivy, and pushes
    `ghcr.io/<owner>/requirement-api` and `requirement-web-production`.
  - It signs both images keyless with cosign, and attests syft SPDX SBOMs.
  - It creates the GitHub release from the changelog section, with both digests and SBOMs.
- **The web image is built per deployment** (owner's decision, 2026-10-09). Its CSP and links
  are baked in, so the release builds it from the `production` GitHub environment's variables.
  `CSP_IDENTITY_ORIGINS` is required; `KNOWLEDGE_PORTAL_URL` and `KNOWLEDGE_PORTAL_ROLE` are
  optional.
- **Deploy by tag.** The manifest names its images
  `${REQUIREMENT_API_IMAGE:-requirement-platform/api}:${IMAGE_TAG:-local}`, and the same for
  web. `test_image_pins.py` treats both variables as this repository's own images, so CI's
  Trivy loop is unchanged.
- **Version reporting.** `FastAPI(version=…)` takes it from the installed package's metadata,
  and `/health` returns `version`.
- **Backups.**
  - The `backup` service (profile `backup`, on the database image) writes a custom-format
    `pg_dump` into the `backups` volume. Each dump is renamed into place only once complete,
    and old dumps are pruned past `BACKUP_RETENTION_DAYS` (14).
  - CI's `deployment` job runs it and restores the dump into a new database.
  - `docs/operations/backup-restore.md` covers scheduling, the off-host copy, restore and
    switch-over, how the procedure is checked, and the proposed RPO 24h / RTO 1h, marked for the
    owner to confirm.
- **Upgrade and rollback runbook.** `deployment.md` "Releases and upgrades" covers:
  - upgrade: back up → pull by tag → `up -d --no-build` (`migrate` first) → check
    `/health`'s version and `/ready`;
  - rollback: redeploy the previous tag, or restore the pre-upgrade backup across a contract
    step. `/ready` checks only that the release's own newest migration is applied, so a
    rolled-back release passes on a database migrated further.
- **Migration policy.** WORKSPACE.md now has "Migrations: expand, then contract", and
  `tests/architecture/test_migration_expand_contract.py` enforces it.
  - The test refuses `DROP` (except `DROP DEFAULT`/`NOT NULL`), `RENAME`, column retypes and
    `TRUNCATE`, including in `EXECUTE` string literals. A file with a
    `-- contract-step: <reason>` line is allowed.
  - It grandfathers migrations through `202610091200`. Its scan does flag both of the knowledge
    tables' dynamic drops, so it would have caught them.

## Phase 2: P1 (PRs 3, 9 and 10 need kernel v1.2.0)

**PR 3 · Postgres timeouts and connection budget** — *delivered on `claude/production-hardening-pr3`, 2026-10-09* (ADR-0074 amendment)
- **Session limits on every pooled connection.** `session_limits(settings)` in `composition/persistence.py` is the kernel pool's `configure` hook. It sets `statement_timeout`, `lock_timeout` and `idle_in_transaction_session_timeout` from `DATABASE_STATEMENT_TIMEOUT_SECONDS` (30), `DATABASE_LOCK_TIMEOUT_SECONDS` (5) and `DATABASE_IDLE_TRANSACTION_TIMEOUT_SECONDS` (60).
  - The plan's four named adapters, and connections taken after `external_call`, all come from the one pool, so the hook covers them.
  - The values are configurable rather than fixed, so a deployment with a legitimately slow statement can raise one without a release.
- **`database_busy`.**
  - `DatabaseBusyError(PersistenceError)` is raised for SQLSTATE 57014 and 55P03 by one helper, `infrastructure/persistence/database_errors.py`. The unit of work and every adapter that caught `psycopg.Error` use it.
  - The catalogue answers 503 `database_busy`.
  - Beyond the plan, AI jobs requeue it with backoff (an ADR-0020 amendment line).
  - An idle transaction that lost its session stays 500 `persistence`: it is a defect in the code holding it.
- **Connection budget.**
  - The manifest's `postgres` runs `max_connections=${POSTGRES_MAX_CONNECTIONS:-200}`.
  - `deployment.md` has "Database connections and limits", with the sizing formula.
  - Each process's pool is exported on scrape (`watch_db_pool(connector.stats)`) as `smb_db_pool_connections`, `smb_db_pool_max_connections` and `smb_db_pool_requests_waiting`.

*Plan as specified:*
- **Timeouts:**
  - Use the kernel `configure` hook to set `statement_timeout` (30s), `lock_timeout` (5s) and `idle_in_transaction_session_timeout` (60s) on every pooled connection, including those used after `external_call`, and in `architecture_mapping_stats.py`, `postgres_architecture_jobs.py`, `corpus_counts.py` and `knowledge_portfolio.py`.
  - `lock_timeout` also bounds `pg_advisory_xact_lock` (`postgres_store.py:125-128`).
  - One-shot commands keep using direct connections, with no limits.
  - Errors 57014 and 55P03 map to a 503 `database_busy`.
- **Connection budget:**
  - Postgres runs with `-c max_connections=${POSTGRES_MAX_CONNECTIONS:-200}`.
  - `deployment.md` gets a sizing formula.
  - The pool reports `smb_db_pool_connections` from `stats()`.

**PR 7 · Shared rate limit, spend cap and edge limits** (ADR-0106) — *delivered on `claude/production-hardening-pr7`, 2026-10-09*
- **Shared limit.** `ProviderCallRateLimit` keeps its sliding window and refunds, over a new
  `ProviderCallLogPort`.
  - `PostgresProviderCallLog` keeps one row per counted call in `provider_calls`, checked under a
    per-actor transaction advisory lock. It is exact across replicas, and old rows are pruned as
    calls arrive.
  - `InMemoryProviderCallLog` keeps the old behaviour offline.
  - This replaces the plan's fixed-window upsert, which admits a double burst across a minute
    boundary.
- **Spend cap.** The owner chose "pause AI work until reset", 2026-10-09.
  - `PROVIDER_DAILY_TOKEN_BUDGET` (0 is unlimited) and `ProviderSpendBudget` work over
    `ProviderSpendPort`: `provider_token_spend`, one row per UTC day.
  - `SpendCountingTransport` (and the `httpx2` one for the OpenAI SDK) sits inside every model
    client's `MeteredTransport` and records each response's reported tokens. It never fails a
    call.
  - `AiJobs` refuses new starts and retries with 429 `provider_budget_exhausted` and
    `Retry-After` until 00:00 UTC.
  - `SpendGatedQueue` stops workers claiming until the reset.
  - Editing, indexing and knowledge-service work are not paused.
  - The container now builds persistence before the model adapters, which need the counter.
- **Edge limits.**
  - nginx takes the client address from `X-Forwarded-For` only from `TRUSTED_PROXY_CIDR`
    (default `127.0.0.1/32`, trusting no one).
  - `limit_req` on `location /api/` allows `EDGE_RATE_PER_SECOND` (50) per address with bursts
    of `EDGE_BURST` (100). A nested `impact-preview` location adds 2/s, bursts of 5.
  - Refusals are a JSON 429 (`edge_rate_limited`, `Retry-After`) from `@edge_rate_limited`. The
    API's own 429s pass through.
  - The defaults are `ENV` lines in `deploy/web/Dockerfile`, passed through the manifest.
  - CI's `deployment` job floods `/api/health` last and requires both admitted requests and JSON
    refusals.
- **Docs.** ADR-0106. The AGENTS.md per-process debt row is removed. `deployment.md` "Rate
  limiting" is rewritten, and `.env.example` updated.

**PR 9 · Alerting, SLOs and runbooks** — *delivered on `claude/production-hardening-pr9`, 2026-10-10*
- **The application reports what the alerts read** (kernel 1.2.0 instruments):
  - `smb_build_info`, set when the exporter starts;
  - `smb_ready`, from the API's `/ready` and the worker's health loop;
  - `smb_ai_jobs_queued` and `smb_ai_job_oldest_queued_age_seconds`. Each exporting process samples them every 15s through a new `AiJobBacklogPort` (Postgres and in-memory). A job in retry backoff ages from when it is due.
  - `smb_provider_spend_blocked_total`. `ProviderSpendBudget` takes a required `held_back` callable and reports `start` and `claim`.
- **Monitoring overlay.**
  - Alertmanager v0.34.1. Its entrypoint renders the configuration for `ALERTMANAGER_RECEIVER` (`none`, `webhook` or `slack`). The URL goes to a mode-600 tmpfs file used through `url_file`/`api_url_file`, and is never written into the configuration.
  - postgres-exporter v0.20.1, reading as the application's user. Its password is passed as `DATA_SOURCE_PASS`, like the API's `DATABASE_URL`: Compose refuses an environment-sourced secret for a read-only container ("`file` is the sole supported option"), which CI's first run showed.
  - node-exporter v1.12.1.
  - All three are digest-pinned and scraped, and Prometheus sends alerts to Alertmanager.
- **Alerts.** There are 18 alerts, each with `runbook_url` to `docs/operations/alerts.md`.
  - `ProcessDown` now covers every target.
  - `AiJobsFailing` became a ratio with `for: 15m`.
  - Added: ReadinessFailing, HttpLatencyP95, AiJobsExhausted, QueueBacklog and OldestQueuedJobAge (both with `max()`), ProviderSpendBlocked, DbPoolSaturation, ProcessMemoryHigh, PostgresConnectionsHigh, DatabaseSizeGrowth and DiskLow.
  - Alertmanager inhibits a down target's other warnings.
- **Docs.**
  - `docs/operations/alerts.md` has a runbook per alert.
  - `docs/operations/slos.md` has four objectives with their PromQL, proposed for the owner to confirm.
  - `deployment.md` "Monitoring add-on" is rewritten.
- **CI.**
  - The monitoring step starts all five containers, and checks they are scraped and `pg_up`.
  - It runs `promtool check config` and `promtool test rules` (`alerts.test.yml`, including a forced readiness failure), and `amtool check-config` for every receiver.
  - It checks that Prometheus has an active Alertmanager.
  - `test_monitoring_metrics.py` parses PromQL: series must be instruments or allow-listed exporter metrics, and every alert needs a runbook section.

*Plan as specified:*
- **Monitoring stack** (`compose.monitoring.yaml`, currently Prometheus and Grafana only): add Alertmanager (config rendered by an entrypoint, secrets through `*_file`), one postgres-exporter and node-exporter, all digest-pinned. Scrape them in `prometheus.yml:13-30`.
- **Alerts:**
  - Fix `AiJobsFailing` (`alerts.yml:39-44`) to use a ratio with `for: 15m`.
  - Add ReadinessFailing, QueueBacklog/OldestQueuedJobAge (with `max()`), AiJobsExhausted (needs PR 2's metric), HttpLatencyP95, DbPoolSaturation, PostgresConnectionsHigh, DatabaseSizeGrowth, DiskLow and ProcessMemoryHigh.
  - Every alert gets a `runbook_url`. `DailyTokenBudgetExceeded` already exists.
- **Docs:** `docs/operations/slos.md` and `docs/operations/alerts.md`.
- **CI:** `promtool check rules` and `amtool check-config` next to `ci.yml:353`, plus a metric-name allow-list in `test_monitoring_metrics.py`.

**PR 10 · Container and edge hardening** — *delivered on `claude/production-hardening-pr10`, 2026-10-10*

**Compose**
- `x-logging` (json-file, 10m × 5) on every service, and `mem_limit`, `cpus` and `pids_limit` on every service, including `backup`.
- The memory limits of api, worker, postgres and clamav are Compose variables. `ProcessMemoryHigh` now warns at 80% of the API and worker defaults.
- Healthchecks:
  - `clamav` runs `clamdcheck.sh`, with a 10-minute start period;
  - `worker` reads its exporter's `smb_ready 1.0`, from PR 9.
- CI's platform step waits for this stack's `clamav` as well as the knowledge portal's.

**Secrets**
- `_secret(name)` in `settings.py` reads `NAME` or `NAME_FILE`, never both, and an unreadable or empty file stops the boot. It covers:
  - `OPENAI_API_KEY` and `OPENROUTER_API_KEY`;
  - both shared service tokens and `REQUIREMENT_SERVICE_CLIENT_SECRET`;
  - a new `DATABASE_PASSWORD`, filled into a `DATABASE_URL` without a password (a URL that has one is refused);
  - model profiles' `api_key_env` names. Only the names a profile asks for are resolved, so an unrelated `*_FILE`, such as `SSL_CERT_FILE`, is never read.
- `docs/operations/secrets.md` gives rotation steps for each.

**Managed Postgres**
- `DATABASE_URL: ${DATABASE_URL:-postgresql://smb:…@postgres:5432/smb_requirements?sslmode=${DATABASE_SSLMODE:-prefer}}`.
- `deployment.md` has a "managed PostgreSQL" paragraph. The plan's line reference to old wording no longer matched anything.

**Forwarded headers**
- nginx believes `X-Forwarded-Proto` only from `TRUSTED_PROXY_CIDR` (a `geo` and `map` on `$realip_remote_addr`), forwards that as `$forwarded_scheme`, and sends `Strict-Transport-Security: max-age=31536000` only over HTTPS. The value is a `map`, set in the shared header snippet.
- `networks.default` has a fixed subnet (`REQUIREMENT_SUBNET`, `172.30.80.0/24`), and uvicorn's `--forwarded-allow-ips` names it instead of `*`.

**IngestionLoop**
- Every failure increments `smb_ingestion_failures_total`. This covers the knowledge-event, historic-requirement, historic-index, approved-backlog and attachment loops.
- A report goes to the log at most once a minute: the exception types, the count, and the frames, never the message.
- Stopping joins for `AI_JOB_SHUTDOWN_GRACE_SECONDS`.

**Errors and heartbeat**
- `error_handlers.py` logs the exception type chain and correlation ID for mapped 5xx errors. For unexpected failures it adds frames, without the message. The opt-in debug trace keeps the detail. `infrastructure/log_safety.py` holds the shared helpers.
- The heartbeat retries a failed renewal while the next try still falls inside the lease. When the lease is about to lapse, or another worker took it, renewing stops and `lease_lost` is set.
- A worker running an attempt stays healthy, so the process is not restarted under a provider call. The attempt finishes, and fenced saves refuse its result if another worker claimed the job.

*Plan as specified:*
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

**PR 11 · CI and supply chain** — *delivered on `claude/production-hardening-pr11`, 2026-10-10*

**CI**
- `ci.yml` has top-level `permissions: contents: read`. It also binds the release workflow, which calls it.
- A `secrets` job runs gitleaks 8.30.1 (a digest-pinned image, like release's Trivy) over the whole history.
  - `.gitleaks.toml` keeps the default rules and allows only lines containing `ci-only`.
  - Before the allowlist, the history had 4 findings: the Grafana `curl -u admin:ci-only` checks.
- Ruff's `S` rules are on. Tests ignore `S101`, `S105` and `S106`: asserts, and made-up credentials.
  - The other 52 findings carry a `noqa` with its reason. The 33 S608 ones in `src/` only interpolate a constant table name, a table checked against `BLOB_TABLES`, a constant column list, or clauses of constant fragments with `%s` parameters.
- `test_image_pins.py` now reads every workflow, including images named in an environment variable for `docker run`, and the Keycloak manifest.

**More scanning**
- `codeql.yml` covers `python`, `javascript-typescript` and `actions` with `build-mode: none`, so the private kernel is not needed. It runs on pull requests, on `main` and weekly. The repository is public, so code scanning needs no Advanced Security licence.
- `rescan.yml` runs Trivy (release's image and flags) every Monday, and on demand, over the latest release's two images. It does nothing until a release exists. `deployment.md` says what a red run means.

**Keycloak**
- Both images are digest-pinned and `restart: unless-stopped`.
- Keycloak comes from Docker Hub's `keycloak/keycloak`, the project's own namespace there, because quay.io was unreachable from the build environment to resolve a digest.
- Dependabot covers `/deploy/keycloak`, and ignores `postgres` majors as it does `pgvector`.

**Docs**
- New `docs/operations/identity-provider.md`:
  - the public `requirement-spa` and confidential `requirement-service` clients;
  - Keycloak's default lifetimes, since the export sets none;
  - why renewal uses refresh tokens, so needs no third-party cookies, and that offline tokens are not used.
- A test keeps refresh tokens on for `requirement-spa`.

*Plan as specified:*
- **`ci.yml`:**
  - top-level `permissions: contents: read`;
  - a gitleaks job, with an allowlist for the CI-only tokens at `ci.yml:193-197`;
  - ruff `S` rules (`pyproject.toml:58`), ignoring `S101` in tests and with justified `noqa` comments for the constant-fragment SQL.
- **More scanning:** `codeql.yml`, and a weekly Trivy rescan of release images (after PR 6).
- **Keycloak images:** digest-pin both lines in `deploy/keycloak/compose.yaml` (:3, :17) and add `restart:`. Add the file to `test_image_pins.py:28-33` and `dependabot.yml:54-62`.
- **`docs/operations/identity-provider.md`:**
  - token lifespans and refresh tokens, so silent renewal doesn't need third-party cookies;
  - the public `requirement-spa` and confidential `requirement-service` clients.

**PR 12 · Frontend resilience** (exception) — *delivered on `claude/production-hardening-pr12`, 2026-10-10*

*Exception to CLAUDE.md's presentation-only rule (ADR-0109, owner-approved).* The frontend files
whose logic changes:
- `api/client.ts`, `api/errors.ts`, `api/knowledge.ts` and the new `api/clientErrors.ts`;
- `app/mutationErrors.ts`, `components/states/ErrorBoundary.tsx` and `main.tsx`;
- each `queryFn`, which now passes `{ signal }`.

**Timeouts and cancellation**
- `sessionFetch` gives up after 30 s, or 120 s for `FormData` uploads, `download` and `requestBlob`.
- It tells three endings apart:
  - an identity change, or a caller's abort: `request_aborted`, which is silent;
  - a timeout: the new `request_timeout`, which keeps the status-0 retry policy;
  - a network failure.
- The 34 read methods of `api`, and the 3 of `knowledgeApi`, take `{ signal }`. All 47 `queryFn`s pass it. The two `skipToken` ones need none.

**Correlation IDs**
- `errorReference(error)`, and a small `ErrorReference` (mono, `select-all`) under the message of `ErrorNotice`, `ErrorState` and failure toasts.
- 33 call sites that hold the error pass it. Those holding only a string have no ID to show; the global mutation toast carries it for every failed action.

**Client error reports**
- `POST /client-errors` is public (`PUBLIC_OPERATIONS`). It takes `{kind}` with `extra="forbid"`: `render`, `chunk_load`, `uncaught_error` or `unhandled_rejection`. It counts `smb_client_errors_total{kind}`, logs the kind, and answers 204.
- The edge gives it its own zone: 1 r/s, burst 10, and a 1 KB body.
- `reportClientError` sends each kind once per page load, with `keepalive`, outside the session. The callers:
  - the boundaries (`chunk_load` or `render`);
  - `error`/`unhandledrejection` listeners, which skip `request_aborted`.

**Runtime values**
- The image's build (`WEB_RUNTIME_CONFIG=true`) leaves placeholders:
  - `__CSP_IDENTITY_ORIGINS__`, always after a space, in `connect-src`, `frame-src` and `form-action`;
  - `<meta name="knowledge-portal-url|role">`.
- `deploy/web/render-index.sh` (`/docker-entrypoint.d/30-render-index.sh`) checks the values character by character, so they can't break the HTML or `sed`. It refuses to start under OIDC without an origin, and writes `/run/web/index.html`, which `location = /index.html` serves.
- `knowledge.ts` reads the metas, then `import.meta.env`.
- Compose drops the web build args and gains `IDENTITY_PROVIDER`, `CSP_IDENTITY_ORIGINS`, `KNOWLEDGE_PORTAL_ROLE` and the `/run/web` tmpfs. The demo sets `IDENTITY_PROVIDER: fake`.
- `release.yml` builds the web image without deployment values.
- Any other build bakes the values as before.
- CI's deployment job checks that:
  - the served page has no placeholder left;
  - `web` refuses to start under the production manifest without an issuer origin.
- `sessionFetch` joins its signals with `AbortSignal.any`, or by hand on Safari before 17.4. Vite's default build target still includes Safari 16.

**Node**
- `engines.node >=24` and `.nvmrc`.
- `client.test.ts` uses a string body, which closes the deferred trace-gap item.

*Plan as specified:*
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

**PR 13 · Bounded reads and payload retention** (part exception) — *delivered on `claude/production-hardening-pr13`, 2026-10-10*

*Owner decisions (2026-10-10):* prune succeeded and cancelled jobs' inputs, so a cancelled job
past the window can't be retried (ADR-0079 amendment); the server returns owner titles; no new
metric, the retention command reports blob usage instead.

**Drafts, paged** (`GET /requirements/drafts`)
- `q` (title, case-insensitive, wildcards literal), `sort` (`updated_desc` by default,
  `updated_asc`, `title_asc`, `title_desc`), `offset` and `limit` (1–100, default 20); `unowned`
  stays. The answer is `{drafts, total, offset, limit, has_more}`.
- `CataloguePagesPort` reads a page in SQL, joining `draft_ownership` for the owner filter, with
  `draft_id` breaking ties. Eligibility is read for the whole page with
  `DocumentRepositoryPort.list_for_drafts` (`= ANY`).

**Documents, paged** (`GET /documents`)
- `q` (filename or owner title), `filter` (`all`, `attention`, `included`, `excluded`), `owner`,
  `sort` (`added_desc` by default, `added_asc`, `name_asc`, `name_desc`; documents needing
  attention first), `offset` and `limit` (1–100, default 50).
- The answer adds `counts` per state and the `owners` to filter by, and each document its
  `owner {kind, id, title}`. `GET /documents/{id}` carries the owner too.
- Visibility is unchanged and decided in SQL: requirement documents for everyone, draft
  documents for the draft's owner only, in rows, counts and owners alike.
- No per-row lookups: the integration test fails if a page reads a draft's ownership or
  documents one by one. A batched `get_draft_ownerships` was not needed.

**Frontend** (exception, ADR-0109): `DocumentsPage` sends its search, filter, owner and sort to
the API and loads more with `useInfiniteQuery`; `useDocumentOwners` is deleted
(`features/documents/owners.ts` builds the links); `DocumentDetailPage` reads the owner from
the response; `DashboardPage` asks for one draft. The layout is unchanged.

**Retention**
- `AI_JOB_PAYLOAD_RETENTION_DAYS` (default 90). The `retention` command clears `command` of
  succeeded and cancelled jobs finished before the window, in batches of 500
  (`FOR UPDATE SKIP LOCKED`), and sets `payload_pruned_at` (additive migration
  `202610101000`, with a partial index). Knowledge screens are skipped. Rows stay.
- Retrying a pruned job answers 409 `ai_job_inputs_pruned`. A pruned clarification job reports
  no `item_count`.
- The command prints the document blobs' count, bytes and orphans: blobs that no source
  document version (removed ones included) or attachment upload refers to. It deletes none.
- `deployment.md` "Retention" and the `DatabaseSizeGrowth` runbook describe both.

*Plan as specified:*
- **Paging:**
  - `GET /documents` (`documents.py:361`) and `GET /requirements/drafts` (`requirements.py:334`) get `offset`/`limit` plus `q` and sort, following `requirements.py:290-291` and `schemas/requirements.py:178-179`.
  - Batch the ownership lookups (`identity_access.py:371-384`, `owned_requirements.py:98-99`).
  - `DocumentsPage` and `DashboardPage` move to `useInfiniteQuery` (exception).
- **Retention:** prune payloads of succeeded and cancelled AI jobs only. Report orphaned document blobs, and add a size metric (dropped by the owner: `pg_database_size_bytes` already covers it). The daily retention schedule is already documented.

**PR 14 · Tracing** — *delivered on `claude/production-hardening-pr14` with platform-kernel 1.3.0, 2026-10-10*

*Owner decisions (2026-10-10):* the mechanism goes in the kernel (1.3.0, `tracing` extra); every
outbound call is a span but only the knowledge portal is sent `traceparent`; a bundled backend.
Recorded in ADR-0110.

**Kernel 1.3.0** (mohamhossam/platform-kernel#8):
- `configure_tracing` returns a `Tracing`: OTLP/HTTP, ratio sampling, no global provider.
- `TracedTransport`/`TracedTransport2` trace calls and propagate only when asked.
- `request_span`, `span` and `instrument_connection` cover requests, named units of work and SQL.
- JSON logs gain `trace_id`/`span_id`. A parentless client span starts no trace.

**Portal**
- **Settings:** `OTEL_EXPORTER_OTLP_ENDPOINT` (unset: off) and `OTEL_TRACES_SAMPLER_ARG`, both
  validated. `build_tracing` makes the container's `Tracing`, flushed when it closes.
- **Requests:** the request middleware opens the server span. It is named by route template,
  with the correlation ID; probes are not traced. FastAPI's own telemetry is disabled
  (`auto_configure: False`).
- **Jobs:** `PollingAiJobWorker` wraps each attempt in `ai_job <operation>`. Pooled connections
  are instrumented in the pool's `configure` hook (`pooled_session`).
- **Outbound calls:**
  - the knowledge client propagates;
  - the model clients (OpenAI via `TracedTransport2`), the JWKS clients and the token client do
    not (`identity_client`).
- **Edge:** nginx clears `traceparent`/`tracestate`.
- **Overlay:** the collector (0.159.0) and Tempo (3.1.0), digest-pinned, with a Grafana Tempo
  data source. `api` and `worker` default to the collector.
- **CI:** the deployment job finds a request's trace in Tempo through Grafana. The trace was
  started by the API despite a forged `traceparent`, holds its SQL, and has no query string.

*Plan as specified:*
- Optional OpenTelemetry, off when no OTLP endpoint is set.
- Instrument FastAPI, httpx (which also covers the token client at `references.py:133`) and psycopg.
- Send `traceparent` to the portal only when one is connected.

**PR 15 · Frontend polish** (part exception) — *delivered on `claude/production-hardening-pr15`, 2026-10-10*

**Presentation only**
- **404 page.** `NotFoundPage` (an `EmptyState` under a "Page not found" title, with a link
  to the dashboard) replaces the dashboard on the catch-all route. `/auth/*` keeps the
  dashboard: after an OIDC sign-in, `AuthProvider` rewrites the address outside the router,
  which can still be on the callback path.
- **Focus on route change.** `<main tabIndex={-1}>` (`AppShell.tsx`) takes focus when the
  pathname changes, unless focus is still inside the page, as when a breakdown-tree choice
  changes the address. A query-string change is not a new page.
- **Prior-art links.** `PriorArtPanel` links a work item only through an `https:` URL;
  `javascript:`, `data:`, `http:` and unparseable values show the ID without a link.

**Under the exception** (ADR-0109)
- `app/lastRequirement.ts` guards every `localStorage` access for the last requirement:
  `RequirementPage`, `NewRequirementPage` and `DashboardPage`.
- `client.ts` revokes a download's object URL after 40 s (`DOWNLOAD_URL_LIFETIME_MS`).

*Plan as specified:*
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

### PR 5 (2026-10-09, branch `claude/production-hardening-pr5`)

Frontend-only, apart from documentation. Run locally on Node 22. The one vitest failure is the
known Node 22 export test; CI uses Node 24. The smoke ran on a preinstalled Chromium, whose
missing built-in PDF viewer frame fails the two CSP PDF checks, as on PR 4b.

```text
npm run test                523 passed, 1 failed (client.test.ts export, Node 22 only)
  new: aborted JSON/blob answers, non-aborting renewal, network failure without the aborted code,
       silent aborted toast, start keys kept on abort, same-subject renewal keeps the workspace,
       other-subject renewal reloads the identity, route/root/chunk-load error boundaries
npm run typecheck / lint    clean
npm run api:check           OpenAPI types match frontend/openapi.json (no API change)
npm run build               ✓ built in 1.24s
npm run test:smoke          45 passed, 2 failed (content-security-policy PDF viewer frame, local Chromium only)
pytest tests/architecture   passed
```

### PR 6 (2026-10-09, branch `claude/production-hardening-pr6`)

Run locally on Python 3.13 against a local PostgreSQL 16 with pgvector. There is no Docker
daemon here, so:
- `docker compose config` rendered the manifest, with and without the release image variables
  and the `backup` profile;
- the backup service's script ran as written against a migrated local database. It wrote a
  complete dump and pruned a 20-day-old one, and the dump restored into a new database with
  `pg_restore --exit-on-error` at migration `202610091400`.

CI's `deployment` job runs the same backup and restore inside Compose. The release workflow
itself runs only on a tag. actionlint passes on it and on `ci.yml`, and its version check and
release-notes extraction were exercised locally on `v0.1.0`, which was accepted, and `v0.1.1`,
which was refused.

```text
pytest --cov (PostgreSQL)   1957 passed; total coverage 94.61% (floor 92.5%)
ruff check .                All checks passed!
ruff format --check .       1247 files already formatted
mypy src tests              Success: no issues found in 681 source files
lint-imports                Contracts: 43 kept, 0 broken.
actionlint                  release.yml, ci.yml clean
```

### PR 7 (2026-10-09, branch `claude/production-hardening-pr7`)

Run locally on Python 3.13 against a local PostgreSQL 16 with pgvector. The edge configuration
was rendered as the image renders it and checked with a local nginx (`nginx -t`), then exercised
against a stub upstream:
- a burst past the per-address budget got `edge_rate_limited` JSON 429s, with `Retry-After` and
  the security headers;
- an upstream 429 passed through unchanged;
- impact preview was cut at its own budget while other API paths were not;
- CI's 400-request flood, with the production defaults, admitted 143 requests and refused 257,
  in the API's error shape.

Integration tests show two limiters over one database admit no more than one would. A
knowledge-migration test is now robust to later migrations adding tables.

```text
pytest --cov (PostgreSQL)   1972 passed; total coverage 94.59% (floor 92.5%)
ruff check .                All checks passed!
ruff format --check .       1255 files already formatted
mypy src tests              Success: no issues found in 688 source files
lint-imports                Contracts: 43 kept, 0 broken.
actionlint                  ci.yml, release.yml clean
```

### Phase 0 (2026-10-09, platform-kernel#7, then branch `claude/production-hardening-kernel-1.2.0`)

**Kernel**
- Gates on Python 3.12 against PostgreSQL 16: 420 passed, 85% coverage. `ruff check`, `ruff format --check`, `mypy --strict` and `lint-imports` were clean, and CI's `gates` passed.
- New tests cover:
  - two migration runners started together;
  - a migration refused by `lock_timeout` leaving nothing applied;
  - the pool's `configure` hook and lent count;
  - stale signing keys kept through a failed reload;
  - callers sharing one cold-cache fetch;
  - the breaker's open, half-open and closed states.
- A test for the key-rotation race failed 3 times out of 3 on the first design and passed 5 times out of 5 on the fix.
- This repository's suite, run against the kernel checkout before the tag: 1972 passed, and mypy was clean.

**This repository**
- New tests check that:
  - `build_identity` refuses a token issued to `requirement-service`, a token with no `azp`, and ID or refresh tokens;
  - a client added in `OIDC_AUTHORIZED_PARTIES` is accepted, and a token expired 30s ago passes only with the default leeway;
  - the OpenAI transport sends `max_completion_tokens`;
  - five failures through the everyday knowledge client pause the historic-content client without a request. This test fails when the breaker is not shared.

```text
pytest --cov (PostgreSQL)   1985 passed; total coverage 94.60% (floor 92.5%)
ruff check .                All checks passed!
ruff format --check .       1257 files already formatted
mypy src tests              Success: no issues found in 690 source files
lint-imports                Contracts: 43 kept, 0 broken.
npm run api:check           no drift
```

### PR 3 (2026-10-09, branch `claude/production-hardening-pr3`)

Run locally on Python 3.13 against a local PostgreSQL 16 with pgvector, with platform-kernel 1.2.0.
`docker compose config` renders `max_connections=200` by default, and the override when set.

New PostgreSQL tests check that:
- a pooled session shows its three limits;
- `pg_sleep` past the statement limit raises `DatabaseBusyError`;
- a Requirement advisory lock held elsewhere fails within the lock limit as `DatabaseBusyError`;
- a transaction left idle past its limit loses its session, and the pool replaces it;
- through the API, `GET /requirements/{id}` answers 503 `database_busy` while another session
  holds `ACCESS EXCLUSIVE` on `requirements`, and 200 once it is released;
- the exporter shows `smb_db_pool_connections` and `smb_db_pool_max_connections`.

The whole suite passes with the limits on every pooled session.

```text
pytest --cov (PostgreSQL)   1998 passed; total coverage 94.60% (floor 92.5%)
ruff check .                All checks passed!
ruff format --check .       1260 files already formatted
mypy src tests              Success: no issues found in 693 source files
lint-imports                Contracts: 43 kept, 0 broken.
```

### PR 9 (2026-10-10, branch `claude/production-hardening-pr9`, stacked on PR 3)

Run locally on Python 3.13 against PostgreSQL 16, with promtool 3.15.0 and amtool 0.34.1 (the
pinned images' versions):
- `promtool check rules` found 18 rules.
- `promtool test rules alerts.test.yml` passed: readiness, process down, the failure ratio, the
  queue alerts firing once across processes, pool saturation, spend blocked and PostgreSQL
  connections, each with its negative case.
- `promtool check config` passed.
- `amtool check-config` passed for `none`, `webhook` and `slack`, and a receiver without a URL
  is refused.
- `docker compose config` rendered the overlay with the production manifest.

New tests show:
- the in-memory and PostgreSQL backlog count queued jobs and age only those due;
- a sample sets the queue gauges;
- the exporter names the release;
- `/ready` sets `smb_ready`;
- a refused start and a skipped claim are counted.

```text
pytest --cov (PostgreSQL)   2006 passed; total coverage 94.62% (floor 92.5%)
ruff check .                All checks passed!
ruff format --check .       all files formatted
mypy src tests              Success: no issues found
lint-imports                Contracts: 43 kept, 0 broken.
actionlint                  ci.yml, release.yml clean
```

### PR 10 (2026-10-10, branch `claude/production-hardening-pr10`, stacked on PR 9)

Run locally on Python 3.13 against PostgreSQL 16:
- `docker compose config` renders the manifest with its limits, logging, subnet and
  healthchecks, and a managed `DATABASE_URL` overrides the default.
- The edge template, rendered and served by a local nginx (`nginx -t` passes), was checked against
  a stub upstream:
  - from a trusted proxy, `X-Forwarded-Proto: https` reaches the API and HSTS is sent;
  - from an untrusted address, the API sees `http` and no HSTS is sent;
  - a plain request gets no HSTS.
- promtool still finds 18 rules, and their tests pass.

New tests cover:
- reading secrets from files, refusing both forms at once, and refusing a missing or empty file;
- filling the database password into the URL;
- profile keys from files;
- ingestion failures counted every time and reported once a minute, without messages;
- stopping that waits for the step under way;
- error logs without messages;
- the heartbeat riding out failures while the lease lasts, stopping when it lapses or is taken
  back, and the worker staying healthy under the attempt;
- manifest and edge structure.

### PR 11 (2026-10-10, branch `claude/production-hardening-pr11`)

Run locally on Python 3.13 against PostgreSQL 16:
- gitleaks 8.30.1 over the full history (`gitleaks git`) and the working tree (`gitleaks dir`):
  - 4 findings without `.gitleaks.toml`, all `curl-auth-user` on the `ci-only` Grafana checks;
  - none with it.
- `ruff check .` with `S` enabled is clean, and so are `ruff format --check`, mypy, lint-imports and the full pytest suite with coverage.
- actionlint is clean on `ci.yml`, `codeql.yml`, `rescan.yml` and `release.yml`.
- `docker compose -f deploy/keycloak/compose.yaml config` renders.
- The image-pin test fails when the Keycloak digests are removed.

Not run locally: the workflows themselves. CI runs `secrets` and CodeQL on this PR. `rescan.yml` runs on its schedule, or from the Actions tab.

### PR 12 (2026-10-10, branch `claude/production-hardening-pr12`)

Run locally on Python 3.13 against PostgreSQL 16, and Node 22, the only version on this machine:
- Backend: full pytest with coverage, ruff (with `S`), format, mypy and lint-imports are clean.
- Frontend: `npm test` passes (now including the export test on Node 22); so do lint, typecheck, `npm run build` and `npm run api:check`.
- The image's build, served through `default.conf.template` on a local nginx with a stub API (`nginx -t` passes):
  - `vite build` with `WEB_RUNTIME_CONFIG=true` emits the placeholders, and none reach the JS bundles;
  - `render-index.sh` fills them;
  - `/`, a deep route and `/index.html` all serve the rendered page with `no-cache`, its CSP naming the configured issuer, and assets stay immutable;
  - `/api/client-errors` lets 10 of a burst of 20 through, then answers 429, and answers 413 to a 2 KB body, while the rest of `/api/` keeps its own budget.

New tests cover:
- timeouts (30 s and 120 s), caller cancellation and network failure;
- the reference in `ErrorState`, `ErrorNotice` and toasts;
- reports: once per kind, no token, swallowed failures, the listeners, and the boundary kinds;
- the route: public, counted, and refusing unknown kinds and extra fields;
- the edge zone;
- `render-index.sh`: rendering, the demo, and 13 refusals including quote, pipe, `&`, wildcard and newline injection;
- the knowledge metas and the CSP placeholder mode.

Not run locally: the image itself (no Docker daemon). CI's deployment job builds it and runs the stack with the rendered page.

### PR 13 (2026-10-10, branch `claude/production-hardening-pr13`)

Run locally on Python 3.13 against PostgreSQL 16, and Node 22:
- Backend: full pytest with coverage (94.77%), ruff (with `S`), format, mypy and lint-imports are clean.
- Frontend: `npm test` (60 files, 545 tests), lint, typecheck, `npm run build` and `npm run api:check` pass.
- gitleaks finds no leaks.

New tests cover:
- both pages against the in-memory store and PostgreSQL alike (`tests/catalogue_scenarios.py`): paging metadata, the 422 limits, search (wildcards literal), sort, the state filter and counts, owners, and privacy of another person's draft documents;
- no per-row lookups: the PostgreSQL test fails if a page reads a draft's ownership or documents one by one;
- pruning in PostgreSQL: only old succeeded and cancelled jobs change, screens, failed, recent and running jobs keep their inputs, a batch of one still reaches every job, a rerun prunes nothing, a pruned job still reads with no `item_count`, and its retry answers 409 `ai_job_inputs_pruned`;
- the blob report: uploads are referenced, a stray blob is counted with its size, and nothing is deleted;
- the setting's default and refusals, the use case, and the command's output;
- the Documents page's server parameters, "Load more", and owners from the response; the detail page's owner; the dashboard's one-draft read.

Not run locally: Playwright. Two specs that read `GET /requirements/drafts` now read its envelope.

### PR 14 (2026-10-10, branch `claude/production-hardening-pr14`)

Run locally on Python 3.13 against PostgreSQL 16:
- **Kernel 1.3.0:** pytest (with PostgreSQL), ruff, format, `mypy --strict`, lint-imports and
  actionlint are clean.
- **Portal:**
  - full pytest with coverage, ruff (with `S`), format, mypy, lint-imports, actionlint and
    gitleaks are clean;
  - `npm run api:check` is current;
  - `docker compose -f deploy/compose.production.yaml -f deploy/compose.monitoring.yaml config`
    renders the collector and Tempo, and points `api` and `worker` at the collector.
- **End to end, with the release binaries:**
  - `otelcol validate` accepts the collector config;
  - Tempo 3.1.0 starts single-binary with it and the retention flags;
  - the portal exported a request's spans through the collector into Tempo, found by TraceQL
    and named `GET /requirements/{requirement_id}`.

New tests cover:
- the settings and their refusals;
- the off path (`NO_TRACING`, FastAPI's telemetry never configured);
- request spans: named by route, continuing a caller's trace, with the correlation ID, no path
  ID or query text, and no probe spans;
- a job attempt as one root span holding its work;
- `traceparent` to the knowledge portal only, never to a model or the identity provider;
- SQL spans under a request in PostgreSQL, without values;
- the nginx header clearing.

Not run locally: the overlay's containers (no Docker daemon). CI's deployment job runs them.

### PR 15 (2026-10-10, branch `claude/production-hardening-pr15`)

Run locally on Node 22:
- `npm test` (62 files, 552 tests), lint, typecheck, `npm run build` and `npm run api:check`
  pass. There is no backend change.

New tests cover:
- the 404 page: its title, heading, way back and document title, and the sign-in callback
  path still landing on the dashboard;
- focus moving to the new page from a link inside the page and from the navigation, and
  staying put for an in-page address or query change;
- `main` as a non-Tab-stop target;
- the https-only work-item links, including `javascript:`, `data:`, `http:` and an
  unparseable value;
- the download revoke waiting `DOWNLOAD_URL_LIFETIME_MS`.

Not run locally: Playwright (CI's smoke job).
