# Enhancement 8B.2 — Batch Clarification Resolution

> Status: **complete locally; CI pending push**. Every roadmap field is
> implemented. Nothing was dropped from the approved plan.

## Objective

Resolve several stable clarification questions through one durable analysis
cycle without weakening authorization, confirmation, concurrency, or audit
rules.

## User Outcome

An Owner or assigned reviewer can complete any subset of answers and submit
them once. Unanswered questions remain active, while every submitted answer is
attributed and incorporated into one new analysis round.

## Domain

- Existing question identity, lifecycle, version, assignment, blocker, and
  attribution invariants are unchanged.
- Each resolved question retains its own final answer and resolution event even
  when several are committed together.

## Application Use Cases

- `AnalysisCollaboration.resolve_batch` accepts stable IDs, final answers, and
  expected versions; single-question and legacy resolution delegate to the same
  orchestration.
- Empty or duplicate batches fail before provider work. Every question is
  loaded, authorized, and resolved in memory before the analyzer is invoked.
- One analyzer invocation receives all existing and newly submitted human
  clarifications. Requirement, analysis, and every selected question version
  are rechecked before an atomic commit of resolutions and one new round.
- Provider or concurrency failure commits no batch resolution or analysis
  round. Durable job input remains available for retry.

## Ports

- Existing Requirement, analysis, audit, analyzer, document, access,
  actor-directory, clock, transaction, AI-job, notification, activity, and
  revision ports are reused unchanged.

## Adapters

- In-memory and PostgreSQL job adapters already round-trip arbitrary typed JSON
  commands, including the new answer collection.
- Existing question/round persistence and activity projections record every
  resolved question and the single generated round without schema changes.
- Provider adapters keep their existing structured-output recovery behavior;
  the application starts only one analysis cycle per submitted batch.
- No relational database migration is required.

## API

- `POST /requirements/{requirement_id}/analysis/question-resolutions` accepts
  one or more `{question_id, answer, expected_version}` entries and returns the
  refreshed analysis workspace.
- Durable jobs add `resolve_clarification_questions` with the same answer list.
  Job responses expose `item_count` so polling UI can display the durable batch
  size.
- Single-question resolution and kind/subject legacy batch routes remain
  backward compatible.
- Blank/duplicate input maps to 422, unauthorized batches to 403, missing
  resources to 404, and stale/concurrent state to 409.

## UI

- Stable question cards retain editable answer text, assignment,
  classification, and provider-free Save draft actions.
- Per-card re-analysis is removed. One sticky batch bar reports the number of
  nonblank typed or saved answers and submits them in one job.
- Extracted evidence is grouped under Known facts, Business rules, and
  Constraints. Items needing confirmation are grouped under Assumptions, Open
  questions, Ambiguities, and Potential dependencies, with per-category counts.
- The batch action is disabled with no ready answers or while Requirement AI
  work is active. Local answers are not cleared on submission or job failure.
- Active and failed job panels display `Resolving N questions`; terminal
  polling refreshes analysis, rounds, activity-derived views, and notifications.

## Business Rules

- Any answered subset may be submitted; unanswered questions remain active.
- Owners may answer any active question. Reviewers may include only questions
  assigned to them. One unauthorized entry rejects the whole batch.
- Active blockers continue preventing confirmation. Owners may explicitly
  classify an advisory item as non-blocking without invoking the provider.
- Adapter retries or focused recovery may make additional physical provider
  requests only when structured output requires recovery.

## Tests

- Application/API tests cover one analyzer call, one new round, subset behavior,
  attribution, duplicates, blank input, authorization, missing/stale questions,
  concurrent mutation, and provider rollback.
- Job/OpenAPI and opt-in PostgreSQL tests cover operation validation, durable
  command JSON, batch size, retry/idempotency compatibility, and generated types.
- Activity assertions prove one resolution event per question while analysis
  and job events remain per batch.
- UI tests cover ready counts, typed and saved answers, one callback, removed
  per-card actions, category grouping for stable and legacy analyses,
  busy/error behavior, and durable batch status.
- Browser smoke resolves four fake-provider blockers with one click and observes
  one additional immutable round before Owner confirmation.

## Acceptance Criteria

- [x] Several completed answers start exactly one durable resolution job.
- [x] The application invokes the analyzer once and creates one new round per batch.
- [x] Unanswered questions remain active and blocker confirmation rules remain intact.
- [x] Validation, authorization, provider failure, and concurrency cannot partially commit.
- [x] Single-question and legacy API compatibility is retained.
- [x] Extracted evidence and confirmation items are visibly grouped by category.
- [x] API, UI, audit/activity, persistence, OpenAPI, browser flow, and docs are complete.

## Validation Evidence

- `.venv\Scripts\pytest.exe` — PASS: 553 passed, 12 skipped in 10.86s.
  The skipped tests are the opt-in PostgreSQL integration suite because
  `TEST_DATABASE_URL` is not configured; its durable AI-job test now includes
  the batch answer JSON command.
- `.venv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv\Scripts\ruff.exe format --check .` — PASS: 343 files already formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 281 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 218 files and 1,115 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run api:check` — PASS: generated OpenAPI TypeScript has no drift.
  Node emitted its existing `DEP0190` warning.
- `npm.cmd run lint` — PASS: ESLint clean.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test -- --run` — PASS: 22 files, 96 tests in 6.32s.
- `npm.cmd run build` — PASS: 1,922 modules transformed; production bundle built.
  Vite emitted its existing large-chunk advisory.
- `$env:SMOKE_API_PORT='8033'; $env:SMOKE_UI_PORT='4203'; npm.cmd run test:smoke`
  — PASS: 12 tests across desktop and responsive Chromium in 47.2s. The full
  journey submitted four answers once and observed exactly round 2 before
  confirmation.
- Live browser inspection — PASS: extracted findings and all 13 stable
  confirmation items rendered under their expected category headings with
  accurate per-category counts; the single batch action remained available.
- CI — NOT RUN for these uncommitted working-tree changes; pending push.

## Deferred

- No approved behavior is deferred.
- Strictly one physical provider request is not required; existing recovery
  calls remain available for malformed or incomplete structured output.
