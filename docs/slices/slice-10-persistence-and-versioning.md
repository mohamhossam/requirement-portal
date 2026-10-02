# Slice 10 — Persistence and Versioning

> Status: **delivered locally**. PostgreSQL durability, migrations, immutable
> revisions, comparison API/UI, and context-budgeted requirement memory are
> implemented. CI remains the authority after these changes are pushed.

## Objective

Keep human requirements, human clarification answers, and generated review
state durable and traceable across API restarts.

## User Outcome

A reviewer can return to the same requirement after restart, see its full
requirement and breakdown revision history, and compare two breakdown versions.

## In Scope

- PostgreSQL current-state persistence for Requirement, analysis, Epic, and Features.
- Ordered startup migrations and a Docker Compose development database.
- Immutable Requirement and Breakdown revisions.
- One transaction for all repository writes in an API action.
- Explicit checkpoint, history, and deterministic breakdown comparison use cases.
- Revision history and change summary in the browser.
- Structured per-requirement memory: source requirement and human clarification answers.
- Iterative answer/re-analysis rounds with explicit Requirement Owner confirmation.
- Configurable 4096-token local context and reserved output budget.

## Out of Scope

- User identity and separate approval records; approval currently belongs to the
  Epic/Feature aggregate status, so `ApprovalRepositoryPort` is not justified.
- Global chat history. It would mix requirements, consume the context window,
  and blur AI output with human-confirmed decisions.
- Database-backed search/listing and reporting projections.
- ADO publication and external IDs.

## Domain

- `RevisionNumber` is positive and local to one requirement/history type.
- `RequirementRevision` carries a complete immutable Requirement snapshot.
- `BreakdownRevision` carries the analysis (including human clarifications),
  Epic, and ordered Features, enforcing their parent identities.

## Application Use Cases

- `CreateRequirementRevision`
- `GetRevisionHistory`
- `CompareBreakdownVersions`

## Ports

- Existing current-state repository ports remain domain oriented.
- `BreakdownRepositoryPort` owns append-only checkpoints and history retrieval.
- `TransactionManagerPort` provides the interface-level atomic action boundary.

## Adapters

- `PostgresStore` and focused analysis/Epic/Feature repository facades.
- JSONB snapshot mapper reconstructs validated domain aggregates.
- In-memory revision adapter and tracking decorators preserve offline operation.
- `compose.yaml` provisions PostgreSQL 17 with a durable named volume.

## API

- `POST /requirements/{id}/revisions` — explicit idempotent checkpoint.
- `GET /requirements/{id}/revisions` — requirement and breakdown history.
- `GET /requirements/{id}/revisions/compare` — deterministic change summary.

## UI

The fifth review section shows human-requirement revisions separately from
analysis/backlog revisions. A reviewer can select two breakdown versions and
see analysis/clarification, Epic, and Feature changes.

## Business Rules

- Revision rows are insert-only; database triggers reject update and delete.
- Approved historical content is never overwritten.
- One action produces a final atomic checkpoint, not partial invalidation state.
- Human clarification answers are durable and stay distinct from source facts.
- An analysis is human-confirmed only after its unresolved set is empty; any
  replacement analysis starts unconfirmed.
- Context overflow is an explicit error; human input is never silently truncated.

## Tests

- Domain/application behavior through the revision API.
- Error-map and OpenAPI contract coverage.
- Opt-in live PostgreSQL migration idempotency, adapter restart durability, and
  database-enforced revision immutability.
- Frontend type, component, lint, and production build checks.

## Acceptance Criteria

- [x] Human requirement survives an API process restart.
- [x] Current analysis/Epic/Features have PostgreSQL adapters.
- [x] Human clarification answers are saved in breakdown revisions.
- [x] Historical revisions cannot be updated or deleted.
- [x] History and comparison are usable from the browser.
- [x] Local LLM calls respect a configurable context/output budget.
- [x] Memory mode remains available without PostgreSQL.

## Validation Evidence

- `TEST_DATABASE_URL=... pytest` — PASS, 284 tests including live PostgreSQL tests.
- API process restart smoke — PASS; requirement reloaded with revision count 1.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 166 files.
- `mypy src tests` — PASS, 138 source files.
- `lint-imports` — PASS, 2 contracts kept.
- `npm run api:check` — PASS.
- `npm run lint` — PASS.
- `npm run test` — PASS, 22 tests.
- `npm run typecheck` — PASS.
- `npm run build` — PASS.
- `SMOKE_PYTHON=... npm run test:smoke` — PASS, 1 Chromium flow.

## Deferred

- CI PostgreSQL service configuration; integration tests are opt-in through
  `TEST_DATABASE_URL` and ran against the local Compose service in this slice.
- Query-optimized relational projections if reporting needs prove JSONB insufficient.

## Startup readiness enhancement

The combined local launchers now perform a bounded authenticated PostgreSQL
query before starting Uvicorn. An unavailable or incorrectly configured
database fails immediately with recovery guidance, while memory persistence
remains fully offline. Schema migration is a separate explicit command and API
container construction never applies DDL (ADR-0024). For developer convenience,
normal combined-launcher startup starts the local Compose service when absent,
waits for readiness, and invokes that command before creating the API process;
external database targets and `-CheckOnly` never trigger local infrastructure.

Enhancement validation evidence:

- `pytest` — PASS, 532 passed and 12 skipped.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 340 files.
- `mypy src tests` — PASS, 281 source files.
- `lint-imports` — PASS, 2 contracts kept.
- `start.ps1 -Provider fake -CheckOnly` with PostgreSQL unavailable — expected
  immediate failure with actionable guidance and no credential disclosure.
- PowerShell and CMD `-CheckOnly` with memory persistence — PASS; no Docker,
  migration, API, or UI process was started.
- `docker compose config --quiet` — PASS.
- Local Compose PostgreSQL startup and explicit migration — PASS; schema current.
- `start.ps1 -Provider local -CheckOnly` against ready PostgreSQL — PASS.
