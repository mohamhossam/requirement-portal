# Enhancement — Architecture and Production-Readiness Review Remediation

## Objective
Resolve the findings of the 2026-09-24 clean-code / clean-architecture /
production-readiness review of `main` @ `c277cb1`, in phases that each leave the
repository green and deployable. No new product capability is introduced.

## User Outcome
Operators can deploy, scale and probe the service safely; maintainers work in a
codebase whose newest slices follow the same conventions as the oldest.

## In Scope
Every review finding, grouped into phases. Each phase is independently
mergeable and must keep all five gates plus the frontend gates green.

### Phase 1 — Correctness and safety fixes (no structural change)
| # | Finding | Change |
|---|---|---|
| 1.1 | `/ready` pinned to migration `024` while `025`/`026` exist | Readiness compares against the newest packaged migration, derived from the migration directory. |
| 1.2 | Knowledge document upload reads an unbounded body | Read at most `max_bytes + 1`, exactly like Requirement document uploads; take upload time from `ClockPort`. |
| 1.3 | `knowledge_provider` is a raw string; memory persistence + local knowledge leaves architecture jobs queued forever | `KnowledgeProvider` enum; reject `PERSISTENCE_PROVIDER=memory` with `KNOWLEDGE_PROVIDER=local` at boot until Phase 3 runs those jobs in-process. |
| 1.4 | Runtime `assert` statements (stripped under `python -O`) | Replace with explicit errors or type-safe narrowing. |
| 1.5 | Authentication is opt-in per router | Test that walks every route and fails when one lacks an authenticated actor (except the documented public probes). |
| 1.6 | Duplicate migration prefix `018` | Test that forbids new duplicate prefixes (the historic pair is grandfathered — renaming an applied migration would re-run it). |
| 1.7 | CI ignores `uv.lock`; CI Postgres 16 vs Compose Postgres 17 | CI installs with `uv sync --locked`; all Postgres CI services use the Compose image. |
| 1.8 | Dead "docstring" inside a `with` block in `generate_epic` | Move it to the function docstring. |

### Phase 2 — Connection pooling and process separation
- 2.1 `psycopg_pool.ConnectionPool` owned by the composition root and closed by
  `close_resources`; `PostgresStore` and every architecture adapter borrow from
  it instead of calling `psycopg.connect` per call.
- 2.2 `API_BACKGROUND_WORKERS=false` runs an HTTP-only API replica (PostgreSQL
  required); `/ready` reports only the workers the process runs. The container
  names every background worker in one mapping; the architecture job poller
  joins it under local knowledge, lifting the Phase 1.3 restriction. (Chosen
  over `AI_JOB_WORKER_CONCURRENCY=0`, which covered one of three worker types.)
- 2.3 Worker-only entrypoint `python -m smb_requirement_agent.interfaces.worker`
  replacing `infrastructure/architecture/worker.py`. See ADR-0069.

### Phase 3 — Slice 14 conventions
- 3.1 ~~Run architecture jobs on `AiJobs`.~~ **Revised:** ADR-0068 deliberately
  keeps release-scoped builds out of the Requirement-owned `AiJobs` aggregate,
  and this plan does not overturn an accepted ADR. Phase 2 already gives both
  job types one runtime (`BackgroundWorker`, one worker process). What remains:
  `ArchitectureJobs` uses `ClockPort` instead of `datetime.now`, typed job kind
  and status enums instead of strings, a typed fingerprint instead of a
  `|`-joined string, and replaces the `run_inline` flag with the composition
  root choosing inline execution explicitly.
- 3.2 Typed release status / job kind enums in the knowledge domain.
- 3.3 Knowledge routes obtain use cases through `dependencies.py`; authorization
  moves into use cases; API-owned request/response schemas replace domain
  dataclasses as transport models.
- 3.4 ~~import-linter contract: infrastructure must not import interfaces.~~
  Delivered in Phase 2.

### Phase 4 — Orchestration out of routes
- 4.1 `RequirementCommands` (ADR-0070) owns snapshot, membership/owner fence,
  context-token check and presentation order; routes name the command and view.
  Duplicate route fences around self-fencing use cases are removed, and draft
  attachment visibility moved into `ListDocuments`/`GetDocument`. (Delivered as
  one generic runner rather than one handler class per operation — see ADR-0070.)
- 4.2 **Decided 2026-09-24: keep both** the synchronous generation endpoints and
  the job API.

### Phase 5 — Structural refactors
- 5.1 Delivered in two steps (ADR-0071).
  - Step 1: `interfaces/api/composition/` took LLM provider selection, the
    projection refresh and the operational entry points.
  - Step 2: persistence selection (`build_persistence` → `PersistenceAdapters`)
    and one builder per context (identity, analysis, architecture, requirement
    knowledge, documents).
  - The backend-specific locals that blocked step 2 now stay inside
    `PersistenceAdapters`: the PostgreSQL store, the activity projection and the
    memory lock. Worklist wiring comes from a `worklist(review)` factory.
  - `container.py` fell from 2,528 to 1,116 lines. It no longer tests the
    persistence, identity or knowledge provider, and keeps only the
    cross-context backlog use-case graph and the `Container` assembly.
- 5.2 Delivered. `ai_jobs` → `ai_job_execution` + `ai_job_scheduling`;
  `requirement_knowledge` → `answer_suggestions`; `story_workflow` →
  `story_change_proposals` (the shared Story kernel is now named public API);
  `breakdown_review` → `breakdown_review_evidence` + `breakdown_review_policy`.
  No use-case module exceeds 1,000 lines. All 16 function-level imports in
  domain/application were hoisted — none was breaking a real cycle — and a guard
  test forbids new ones. The policy did not move into the domain: its evidence
  fingerprint builds on application quality-evidence DTOs.
- 5.3 **Revised.** The analysis candidates are `TypedDict`s — statically checked
  port contracts, not untyped dictionaries — so they stay. The defects were the
  five `type: ignore`s: stage provenance is now typed as
  `AnalysisStageProvenanceCandidate`, and the merge helpers take typed lists
  instead of runtime field names. The six ignores in `bounded_extractor` are
  replaced by protocols. The one remaining ignore is `pypdfium2`'s missing stubs.
- 5.4 Delivered (ADR-0072). OpenAI runs on the shared structured adapters via
  `OpenAIStructuredOutputClient`; this fixed real drift in OpenAI analysis.
  `OPENAI_TIMEOUT_SECONDS` replaces hard-coded timeouts; `openai>=3.8,<4`.
- 5.5 **Not done.** No test needs deterministic identifiers (tests generate
  their own), so an ID port would be a speculative abstraction (AGENTS.md §16).
  Revisit when a test or replay feature needs it.

### Phase 6 — Frontend
Scoped on 2026-09-24. CLAUDE.md's UI Redesign Rules predate this plan and limit
every change under `frontend/` to presentation. They forbid changes to hooks,
services, state logic or API calls. Items needing frontend logic changes were
therefore deferred to the redesign, with the user's agreement. They are
recorded in AGENTS.md §19.
- 6.1 **Backend delivered; frontend deferred** (ADR-0073).
  - Review rules live once in the domain: `ActionAvailability`, approval and
    regeneration on every generated aggregate, Epic decomposition, Feature
    Stories, and Epic generation from analysis.
  - Use cases refuse with the same predicates.
  - Analysis, Epic, Feature and Story responses carry typed `actions`.
  - `src/review/rules.ts` stays until the redesign reads `actions`.
- 6.2 **Deferred to the redesign.** Replacing `api/knowledge.ts` changes API
  service code.
- 6.3 **Deferred to the redesign.** Splitting `AnalysisPanel.tsx` moves state
  and hooks, and the redesign rebuilds that screen.
- 6.4 Delivered. `frontend/contentSecurityPolicy.ts` is a build-only Vite
  plugin that emits a `<meta>` policy:
  - `default-src 'self'`;
  - the inline theme script admitted by SHA-256 hash, computed after CRLF→LF
    normalisation as browsers do;
  - `data:` and `blob:` images for evidence previews;
  - `object-src 'none'`, `frame-src 'none'` and `base-uri 'self'`;
  - API and OIDC origins from `VITE_API_BASE` and `CSP_IDENTITY_ORIGINS`.

  `frame-ancestors` and reporting need response headers and move to Phase 7.1.
- Contract artifacts regenerated (`frontend/openapi.json`,
  `frontend/src/api/schema.d.ts`), and the typed test fixtures in
  `frontend/src/test/fixtures.ts` gained the new `actions` fields. These are
  generated or test-data changes, not runtime logic.

### Phase 7 — Production packaging and operability
- 7.1 Delivered (ADR-0074, `docs/operations/deployment.md`).
  - Images:
    - One backend image, `deploy/api/Dockerfile`, runs the API, worker,
      migrate and maintenance processes, chosen by command.
    - `deploy/web/Dockerfile` is unprivileged nginx serving the build. It
      proxies `/api/`, adds `frame-ancestors` and the other security headers,
      and sets `X-Request-ID` at the edge.
  - Reference manifest, `deploy/compose.production.yaml`:
    - PostgreSQL and ClamAV;
    - a one-shot `migrate` that everything waits for;
    - a profile-gated `maintenance` for first install and maintenance windows;
    - an HTTP-only API with a `/ready` healthcheck;
    - a separate, scalable worker;
    - `web` as the only published port.

    Containers run read-only and non-root.
  - Entrypoint and CI: `python -m smb_requirement_agent.interfaces.api.serve`
    configures logging before serving. A new CI `deployment` job builds both
    images and starts the manifest.
- 7.2 Delivered.
  - `LOG_LEVEL`/`LOG_FORMAT` (`text`/`json`) choose stdout logging, with a
    context-variable correlation ID: the request's `X-Request-ID`, or
    `job:<id>`.
  - One log line per request (route template, status, duration) and one per
    job attempt.
  - Prometheus metrics on a container-owned registry: HTTP by route template,
    provider requests via a metered `httpx`/`httpx2` transport on every
    provider client, and AI job attempts. They are served on `METRICS_PORT`,
    never through the proxy.
  - `prometheus-client` added to `uv.lock`. `LocalEmbeddings` now takes an
    injected HTTP client instead of calling `httpx.post`.
- 7.3 **Revised to a per-actor limit.**
  - `ProviderCallRateLimit` caps provider-calling operations per actor per
    minute (`PROVIDER_RATE_LIMIT_PER_MINUTE`, default 30, 0 disables).
  - It covers the 23 provider-calling routes, including job starts and
    retries. Refusals are 429 with `Retry-After`.
  - An architecture test pins the route set.
  - The count is per process. A global spend ceiling is deferred (AGENTS.md
    §19).
- 7.4 Delivered. Migrations after `026` are named
  `YYYYMMDDHHMM_description.sql`, enforced by
  `tests/unit/test_migration_catalogue.py` and documented in `WORKSPACE.md`.

## Out of Scope
- New product capabilities or roadmap slices.
- Renaming already-applied migrations.

## Domain
Phase 3.2 only (typed knowledge release status / job kind).

## Application Use Cases
No new business use cases. Phases 3–5 restructure existing ones.

## Ports
Phase 2 (connection pool is an adapter concern, no new port); Phase 5.5 (ID port).

## Adapters
Phases 2, 3 and 5.4.

## API
Phase 1.2 (bounded read, no contract change); Phase 3.3 (knowledge schemas —
shape-compatible); Phase 4.2 (decision required); Phase 6.1 (additive fields).

## UI
Phase 6. No user-visible behaviour change in Phases 1–5.

## Business Rules
Unchanged.

## Tests
Each phase adds the tests that prove its change; see Validation Evidence.

## Acceptance Criteria
- [x] Phase 1 — all items delivered, local gates green (CI pending push).
- [x] Phase 2 — delivered, local gates green (CI pending push).
- [x] Phase 3 — delivered, local gates green (CI pending push).
- [x] Phase 4 — delivered, local gates green (CI pending push).
- [x] Phase 5 — delivered with the recorded revisions, local gates green (CI pending push).
- [x] Phase 6 — delivered in the agreed scope (6.1 backend, 6.4); 6.1 frontend, 6.2 and 6.3 deferred to the redesign. Local gates green (CI pending push).
- [x] Phase 7 — delivered (7.3 revised to a per-actor, per-process limit). Local gates and a local run of the deployment job green (CI pending push).

## Validation Evidence
Recorded per phase below.

### Phase 1 — 2026-09-24, branch `fix/review-remediation`
Delivered: 1.1–1.8 as listed. Also found by the 1.8 scan: the same dead string
in `generate_features`; and the launcher `startup_check` crashed with a
traceback on `ConfigurationError` (now a clean exit 1).

Tests added:
- `tests/unit/test_migration_catalogue.py` — readiness target is the newest
  migration; no new duplicate prefixes.
- `tests/integration/test_postgres_persistence.py::test_readiness_requires_the_newest_migration_and_maintenance_marker`
  — fails against the previous hard-coded `024` check.
- `test_architecture_upload_reads_at_most_one_byte_past_the_limit` — the use
  case receives 9 bytes of a 1 MB body (previously all of it).
- `test_local_knowledge_refuses_memory_persistence_the_worker_cannot_see`,
  `test_unsupported_knowledge_provider_names_supported_values`.
- `tests/architecture/test_route_authentication.py` — 161 operations; verified
  to fail when an unauthenticated router is added.
- `tests/architecture/test_runtime_invariants.py` — no `assert` under `src/`.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1437 passed (includes PostgreSQL integration)
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 896 files
- `mypy src tests` — PASS, 451 source files
- `lint-imports` — PASS, 6 contracts kept
- `npm run api:check`, `npm run typecheck`, `npm run lint` — PASS
  (OpenAPI snapshot and `schema.d.ts` regenerated: two operation descriptions)
- `uv sync --locked --extra dev --dry-run` — PASS (lockfile satisfies CI install)
- `npm run test` / Playwright smoke — not run locally; the only frontend change is
  generated doc comments. CI covers both.

## Deferred
Phases 2–7 until scheduled; Phase 4.2 awaits the product owner's decision.

### Phase 2 — 2026-09-24, branch `fix/review-remediation`
Delivered 2.1–2.3 (ADR-0069), plus from Phase 3: 3.4 (import-linter contract
`infrastructure_not_interfaces`, after removing `infrastructure/architecture/worker.py`
and the `backfill_worklist_projection` shim; the runbook now names
`interfaces.maintenance`). Dependency: `psycopg[binary,pool]` (`psycopg-pool 3.3.3`
in `uv.lock`).

Found while converting adapters: the architecture audit mapper passed untyped
row values into `KnowledgeAuditEvent` (hidden by `Any`-typed rows); it now
decodes with `_integer`/`_datetime`. `AiJobWorkerPort` gained the `healthy`
property `/ready` already relied on.

Tests added:
- `tests/integration/test_postgres_connection_pool.py` — session reuse, rollback
  and error paths return clean connections, `external_call` frees the only
  pooled connection for another thread, exhausted pool fails with
  `PersistenceError`, readiness via the pool. Mutation check: with `release()`
  patched to leak, 4 of 5 fail.
- `tests/unit/test_worker_process.py` — architecture poller drains, survives a
  failed poll, stops; worker process refuses memory persistence, exits 1 on an
  unhealthy worker, stops cleanly on SIGTERM (reverse start order).
- `tests/unit/test_api_lifespan.py` — rewritten for `background_workers`; new:
  HTTP-only replica neither starts nor reports workers; a worker that fails to
  stop keeps resources open while the others still stop.
- `tests/unit/test_settings_and_container.py` — pool settings parsed/bounded,
  HTTP-only requires PostgreSQL, container names its workers, local knowledge
  adds `architecture_job_worker`.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1453 passed (includes PostgreSQL integration); the two test
  files later adjusted for mypy re-run: PASS
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 901 files
- `mypy src tests` — PASS, 455 source files
- `lint-imports` — PASS, 7 contracts kept
- Live run against PostgreSQL: `API_BACKGROUND_WORKERS=false` API → `/ready`
  `{"accepting_requests":true,"persistence":true}`, `POST /requirements` 201,
  worklist 200; `python -m smb_requirement_agent.interfaces.worker` started
  `requirement_index_worker, workers, document_worker` and claimed queued jobs.

### Phase 3 — 2026-09-24, branch `fix/review-remediation`
Delivered 3.1 (revised), 3.2 and 3.3:
- `ArchitectureJobKind` / `ArchitectureJobStatus` (`StrEnum`, same stored and
  JSON values); `IndexJobInput` / `MappingJobInput` produce and parse the
  idempotency key in one place (format unchanged, so already-queued jobs still
  run); `ArchitectureJobs` takes `ClockPort` and an explicit
  `ArchitectureJobExecution` chosen by the composition root instead of
  `run_inline: bool`.
- `KnowledgeReleaseStatus` in the domain; releases built from plain values are
  coerced, invalid values raise `InvalidKnowledgeError`.
- Knowledge and job routes receive use cases through `dependencies.py` and no
  longer check roles; `ManageArchitectureKnowledge` gained `list_releases`,
  `view_active` and `view` (authorize before load), `upsert_system`,
  `remove_system` and `export_yaml` authorize first; document download moved to
  `ReadKnowledgeDocument`. API-owned schemas in
  `interfaces/api/schemas/architecture_knowledge.py` replace domain dataclasses
  as transport models.

Found and fixed: `POST /requirements/{id}/architecture-mapping/jobs` checked only
the global `knowledge_reader` role. Any reader could queue mapping jobs for
Requirements they were not a member of, or for Requirements that do not exist
(the worker's own membership check prevented any unauthorized write). Enqueue
now requires Requirement membership: non-member 403, unknown Requirement 404.

OpenAPI: components renamed to the API-owned schemas; the only shape changes are
`status`/`kind` tightened from `string` to enums with unchanged values (verified
by comparing every renamed component's properties). `schema.d.ts` regenerated;
the frontend's hand-written knowledge types are unaffected (Phase 6.2).

Tests added:
- `tests/unit/test_architecture_knowledge_api_contract.py` — release, job and
  audit responses equal the previous domain serialisation; system requests
  round-trip; mapping jobs require membership (403/404/202); readers see
  published but not draft releases, YAML or the release list.
- `tests/architecture/test_authorization_placement.py` — no role checks in routes.
- `tests/unit/test_architecture_jobs.py` — job input keys round-trip, keep the
  stored format, and reject malformed keys as `PersistenceError`.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1467 passed (includes PostgreSQL integration)
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 904 files
- `mypy src tests` — PASS, 458 source files
- `lint-imports` — PASS, 7 contracts kept
- `npm run api:check`, `npm run typecheck`, `npm run lint` — PASS
- `npm run test` — PASS, 41 files / 278 tests

### Phase 4 — 2026-09-24, branch `fix/review-remediation`
Delivered 4.1 (ADR-0070) and recorded decision 4.2 (keep both paths).
- `RequirementCommands.run` / `run_and_present` / `read` replace every route's
  own snapshot, fence and `generation_context.require(...) or ...` idiom in the
  analysis, requirement, Epic, Feature and Story routes.
- Route fences removed where the use case already fences itself:
  `GenerateBreakdownReview`, `RecordDecision`, `ResolveFlag`,
  `MapBreakdownArchitecture`, `SetDocumentInclusion`,
  `SetHiddenWorksheetInclusion`, `RemoveDocument`; duplicate upload checks
  removed (`UploadDocument` authorizes itself).
- Draft-attachment visibility moved from document routes into
  `ListDocuments.visible_to`, `ListDocuments.for_owned_draft` and `GetDocument`
  (`execute`, `blob`, `asset` now take the actor).
- No API contract change: OpenAPI snapshot and generated types unchanged.

Tests added:
- `tests/unit/test_requirement_commands.py` — step order (fence → context →
  command), stale context rejected before the command runs, owner fence, view
  built inside the snapshot, reads inside a snapshot; non-members still receive
  403 on endpoints whose route fence was removed or converted.
- `tests/architecture/test_authorization_placement.py` — routes may not use
  snapshot, lock, fence, transaction or membership/draft-authorization
  primitives, nor call `generation_context.require`; verified to fail against the
  previous `epic.py`.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1480 passed (includes PostgreSQL integration)
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 907 files
- `mypy src tests` — PASS, 460 source files
- `lint-imports` — PASS, 7 contracts kept
- `npm run api:check` — PASS (no contract drift)

### Phase 5 — 2026-09-24, branch `fix/review-remediation`
Delivered 5.1, 5.2 and 5.4; 5.3 revised; 5.5 not done. The Phase 5 scope notes
above explain what changed and why.

Found while consolidating OpenAI: the OpenAI-only analyzer had drifted from the
shared structured analyzer (no focused desired-outcome review, no question-review
reconciliation, no uncertainty-rationale repair, no completeness retry).
`LLM_PROVIDER=openai` now gets the shared behaviour (ADR-0072). Also: the OpenAI
3.x SDK builds on `httpx2`, not `httpx`.

Tests added or changed:
- `tests/unit/test_openai_structured_output.py` — configured model/timeout/schema
  sent; images as data-URL parts; SDK failures map to public codes
  (`model_timeout`, `model_rate_limit`, `model_authentication`,
  `model_configuration`, `model_unavailable`, `model_invalid_output`) without
  provider text; `OPENAI_TIMEOUT_SECONDS` parsed and validated.
- `tests/unit/test_openai_analyzer.py` — migrated to the shared adapter; real
  schema objects instead of `MagicMock` responses; new
  `test_openai_now_runs_the_shared_outcome_review_when_the_source_has_none`;
  the numeric-target test now asserts the completeness retry and the rejection
  reason in the cause chain.
- OpenAI Epic/Feature/Story/quality tests and container tests repointed.
- `tests/architecture/test_runtime_invariants.py` — no function-level project
  imports in domain/application.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1492 passed (includes PostgreSQL integration)
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 917 files
- `mypy src tests` — PASS, 468 source files
- `lint-imports` — PASS, 7 contracts kept
- `npm run api:check` — PASS (no contract drift)
- `uv lock` — only the `openai` specifier changed

5.1 completion (persistence and per-context builders), same day:
- This is a pure wiring move with no behaviour change, so no tests were added.
  The container, API, PostgreSQL persistence and architecture-guard suites
  exercise every builder through `build_container`.
- `pytest` — PASS, 1492 passed (includes PostgreSQL integration)
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 923 files
- `mypy src tests` — PASS, 474 source files
- `lint-imports` — PASS, 7 contracts kept
- `npm run api:check` — PASS (no contract drift)

### Phase 6 — 2026-09-24, branch `fix/review-remediation`
Delivered 6.1 (backend) and 6.4. Deferred 6.1 (frontend), 6.2 and 6.3 to the UI
redesign, under CLAUDE.md's presentation-only rule — see the Phase 6 scope notes.

Found while verifying the CSP in a real browser: hashing the inline theme
script's raw text produced the wrong hash on a CRLF checkout. Browsers hash the
parsed script, and parsing turns CRLF into LF. The browser blocked the script, so
the stored theme was ignored. Every other smoke test still passed, so only the
new CSP spec exposed it. The hash now normalises line endings, and a unit test
covers it.

Tests added:
- `tests/unit/test_review_actions.py`: the `ActionAvailability` invariants;
  approval blocked when stale (naming the changed source) or already approved;
  regeneration confirmation for edited, sent-back and approved content;
  decomposition, Story and Epic-generation readiness.
- `tests/unit/test_review_actions_api.py`: `actions` reported on analysis, Epic,
  Feature and Story responses as review state changes. A blocked action's reason
  equals the message of the command it refuses.
- `frontend/src/test/contentSecurityPolicy.test.ts`: the policy directives; hash
  stability across CRLF and LF; absolute and relative API bases; identity
  origins, including rejection of malformed ones.
- `frontend/tests/content-security-policy.spec.ts`: the built app loads every
  global and requirement-workspace screen, at both smoke viewports, with no
  policy violation, and the hashed theme script runs.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1514 passed (includes PostgreSQL integration)
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 926 files
- `mypy src tests` — PASS, 477 source files
- `lint-imports` — PASS, 7 contracts kept
- `npm run lint` — PASS
- `npm run typecheck` — PASS
- `npm test` — PASS, 42 files, 287 tests
- `npm run build` — PASS
- `npm run api:check` — PASS (regenerated contract matches)
- `npm run test:smoke` — PASS, 89 passed, 5 skipped (`responsive-layout`
  skips itself in the responsive project by design)

### Phase 7 — 2026-09-24, branch `fix/review-remediation`
Delivered 7.1, 7.2 and 7.4. 7.3 was delivered as a per-actor, per-process limit;
a global spend ceiling is deferred (AGENTS.md §19). See the Phase 7 scope notes.

Found while running the reference manifest:
- `/ready` stays 503 on a fresh database until projection maintenance records
  its marker. The manifest therefore has a profile-gated `maintenance` service
  for first install.
- The nginx `conf.d` tmpfs must be owned by uid 101 under a read-only root
  filesystem.
- Pre-existing and out of scope: an automatic knowledge-screen job can be
  claimed between `IndexReadyJobQueue`'s readiness check and its claim. It
  fails as index-pending until retried. This is handed off as a separate task.

Tests added:
- `tests/unit/test_provider_call_rate.py`: the limit, a sliding window,
  per-actor budgets, 0 disables it, and API 429 with `Retry-After`.
- `tests/architecture/test_provider_rate_limit.py`: the limited routes equal
  the pinned set, and every `GenerationRequest` route is limited.
- `tests/unit/test_observability.py`:
  - JSON records, correlation scope and idempotent configuration;
  - request metrics and log by route template, and the correlation reaching
    synchronous endpoints;
  - the metered transport, including failures;
  - job metrics;
  - the exporter serving and stopping.
- `tests/unit/test_api_serve.py`: logging is configured before serving,
  uvicorn's access log and log config are off, and invalid configuration exits
  2.
- `tests/unit/test_migration_catalogue.py`: the timestamped naming rule and its
  sort order.
- Settings tests for `PROVIDER_RATE_LIMIT_PER_MINUTE`, `LOG_LEVEL`,
  `LOG_FORMAT`, `METRICS_PORT` and `METRICS_HOST`, and error-map coverage for
  the 429.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1550 passed (includes PostgreSQL integration)
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 939 files
- `mypy src tests` — PASS, 487 source files
- `lint-imports` — PASS, 7 contracts kept
- `npm run lint`, `npm run typecheck`, `npm run api:check` — PASS
- `npm test` — PASS, 287 tests
- `npm run test:smoke` — PASS, 89 passed, 5 skipped (`responsive-layout` by
  design)
- The CI `deployment` job steps, run locally with Docker 29.7:
  - images built (api 402 MB, web 75.5 MB);
  - `run --rm maintenance` then `up -d --wait web worker`;
  - `/api/ready` returned 200 through nginx;
  - `frame-ancestors 'none'` header present and CSP meta tag served.
- Manual check against the same stack:
  - JSON logs, with nginx's request ID as the correlation ID in the log line
    and the 429 body;
  - the 31st search in a minute refused with `Retry-After: 59`;
  - both processes' metrics served, and `/api/metrics` 404 through the proxy;
  - a browser analysis run executed as a job in the separate worker with no CSP
    violations.
