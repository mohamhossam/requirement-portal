# Slice 8C — Async AI Jobs and Notifications

> Status: **complete locally; CI pending push**. Every roadmap field is
> implemented. Nothing was dropped from the approved slice.

## Objective

Move model-backed work behind a durable lifecycle so it continues after
navigation and exposes safe status, cancellation, retry, failure, and
notification behavior.

## User Outcome

Reviewers can start AI work, leave the page, return to persisted progress, cancel
or retry when allowed, and opt into completion/failure browser notifications.

## Domain

- Added stable AI job identity, operation and lifecycle states, actor snapshot,
  idempotency fingerprint, attempts, failures, result resources, and explicit
  transition invariants.
- Added actor notification identity/kind/read state and notification preference.
- Added Feature quality snapshots with Story-set fingerprints and generation
  time so asynchronous results remain readable and truthfully stale.

## Application Use Cases

- Added start/get/list/cancel/retry orchestration with actor-scoped idempotency,
  active-equivalent reuse, Requirement-owner/creator control, and typed errors.
- Added one dispatcher over existing focused use cases. Generated artifacts,
  terminal job state, notifications, and revision checkpoints share the
  application transaction.
- Jobs check cooperative cancellation before dispatch and before commit.
- Feature quality evaluation caches current results and rechecks the source
  fingerprint before save.

## Ports

- Added separate AI job repository, leased queue, worker lifecycle,
  notification repository, and Story quality snapshot ports.
- Existing model-specific ports and synchronous use cases remain unchanged and
  reusable during migration.

## Adapters

- Added a thread-safe in-memory queue/notification adapter for offline use.
- Added PostgreSQL queue and notification adapters with leased
  `FOR UPDATE SKIP LOCKED` claims, heartbeats, expired-lease recovery, and
  per-Requirement serialization.
- Added bounded in-process polling workers owned by the FastAPI lifespan.
- Migration `008_async_ai_jobs.sql` adds jobs, indexes, notifications,
  preferences, and durable Feature quality snapshots.

## API

- Added typed start/list/status/cancel/retry routes under
  `/requirements/{id}/ai-jobs`; starts and retries require `Idempotency-Key`.
- Added actor-scoped notification list/read/preference routes.
- Added persisted Feature quality assessment reads while retaining the previous
  synchronous quality endpoint.
- Worklist responses now carry active operation and compute live `reanalysing`.
- New errors are translated only by the central error map.

## UI

- Requirement analysis, clarification resolution, Epic/Feature/Story
  generation, Story regeneration/proposals/quality, and breakdown-review AI
  actions now start durable jobs.
- A shared status panel polls while work is active, explains that navigation is
  safe, and exposes cancel/retry and failure detail. Each operation keeps only
  its latest non-cancelled status actionable, so a newer active or successful
  run clears older failures from the panel while durable job history remains.
- Terminal transitions invalidate affected persisted views; Story quality is
  evaluated once when a missing/stale snapshot is discovered.
- The header notification center shows durable unread results, deep-links to
  resources, marks items read, and requests browser permission only after an
  explicit opt-in.

## Business Rules

- An Idempotency-Key cannot describe different input for the same actor.
- Equivalent active commands reuse one job. Only one job mutates a Requirement
  at a time across workers and replicas.
- Only the job creator or Requirement owner may cancel or retry. Only cancelled
  or retryable failed jobs may retry.
- Queued cancellation is immediate; running cancellation is cooperative and
  generated changes do not commit after cancellation is observed.
- Notification preference never implies browser permission and is scoped to the
  authenticated actor.

## Tests

- Domain transitions, idempotent start, conflicting key, creator/owner control,
  retry, cancellation, per-Requirement serialization, and expired-lease
  recovery.
- API error mapping and actor-scoped notification preference.
- Opt-in PostgreSQL migration/idempotence and job survival across adapter
  restart.
- API client idempotency header, browser polling/status cancellation,
  notification opt-in, migrated intake/Story journeys, and current-status
  failure cleanup across retry and main-action paths.

## Acceptance Criteria

- [x] Model-backed browser actions return durable work immediately.
- [x] Status, retry, cancellation, failures, and result resources are persisted.
- [x] Idempotency and per-Requirement serialization prevent duplicate races.
- [x] PostgreSQL leases recover work after worker loss.
- [x] `reanalysing` is derived from active persisted jobs.
- [x] In-app notifications work without permission; browser alerts are opt-in.
- [x] API, UI, migration, OpenAPI, ADR, tests, and configuration are complete.

## Validation Evidence

- `.venv\Scripts\python.exe -m pytest` — PASS: 481 passed, 9 skipped in 5.49s.
  The skipped tests are the opt-in PostgreSQL suite because
  `TEST_DATABASE_URL` is not configured; it includes Slice 8C migration,
  restart durability, and leased claim coverage.
- `.venv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv\Scripts\ruff.exe format --check .` — PASS: 303 files already formatted.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS: no issues in 251 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 195 files and 939 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run api:check` — PASS: generated OpenAPI TypeScript output has no
  drift. The existing Node `DEP0190` warning was emitted by the check script.
- `npm.cmd run lint` — PASS: ESLint clean.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd test` — PASS: 20 files, 83 tests in 6.87s.
- `npm.cmd run build` — PASS: 1,919 modules transformed; built in 302ms.
- `$env:SMOKE_API_PORT='8030'; $env:SMOKE_UI_PORT='4200'; npm.cmd run test:smoke`
  — PASS: 8 desktop/responsive Chromium flows in 45.8s, including the full
  async analysis/decomposition journey with worker completion observed by UI
  polling.
- CI — NOT RUN for uncommitted working-tree changes; pending push.

### Maintenance validation — 2026-09-05

- `.venv\Scripts\python.exe -m pytest` — PASS: 567 passed, 12 skipped, 1
  warning in 22.92s.
- `.venv-uv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv-uv\Scripts\ruff.exe format --check .` — PASS: 345 files already
  formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 281 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 218 files and 1,116 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd test -- --run` — PASS: 22 files, 102 tests.
- `npm.cmd run build` — PASS: 1,922 modules transformed; Vite emitted its
  existing large-chunk advisory.
- `npm.cmd run api:check` — PASS; Node emitted its existing `DEP0190` warning.
- CI — NOT RUN for local working-tree changes; pending push.

## Deferred

- Formal backlog approval/comments remain Slice 9.
- Activity projections/reporting remain Slice 10A.
- External brokers or separate worker services are unnecessary at current scale
  and may later replace the queue/worker adapters without changing domain rules.
