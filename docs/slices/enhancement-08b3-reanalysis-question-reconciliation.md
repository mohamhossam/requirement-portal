# Enhancement 8B.3 — Re-analysis Question Reconciliation

> Status: **complete locally; CI pending push**.
> Every approved roadmap field is implemented; nothing was dropped.

## Objective

Reconcile all remaining AI-generated clarification questions after each
re-analysis so the current workspace contains only relevant gaps while every
prior question, draft, answer, and lifecycle decision remains auditable.

## User Outcome

One submitted answer may resolve several related gaps. Reviewers see which
questions stayed, disappeared, changed, or were newly identified, and can trace
revised wording back to its superseded source.

## Domain

- `QuestionChangeAction` defines retained, retired, replaced, and created.
- `AnalysisQuestionChange` records the old/current question ID, decision
  rationale, and optional replacement ID in one immutable round.
- `ClarificationQuestion.replacement` creates an AI question with a new stable
  ID, replacement link, inherited assignee/severity/blocker classification, and
  no copied draft. The superseded predecessor retains its draft and attribution.
- Terminal resolved and superseded questions remain immutable. Legacy question
  and round payloads default to no link and no change records.

## Application

- Initial analysis creates new question records. Re-analysis supplies the full
  active snapshot and excludes questions submitted as resolved from review.
- Every remaining active AI ID must have exactly one review. Human questions
  pass as protected context, remain unchanged, and cannot be duplicated.
- Reviews map the complete replacement analysis back to the four existing
  uncertainty categories. Submitted resolutions, supersessions, replacements,
  new questions, analysis, and round commit atomically.
- Requirement version, current analysis identity, and every active question
  ID/version are rechecked after the analyzer returns. Failure commits nothing.
- Confirmation continues to inspect only active blockers.

## Ports

The existing `RequirementAnalyzerPort` gains provider-independent active
question context, question review candidates, and new uncertainty candidates.
Existing repositories, transaction, identity/access, clock, documents, jobs,
notifications, reporting, and activity ports are reused.

## Adapters

- Fake, local, and OpenAI-compatible analyzers implement `analysis-v4`.
- The provider schema requires complete reviews and separates them from new
  uncertainties. Shared mapping rejects blank, incomplete, duplicate, unknown,
  protected-human, unchanged-replacement, internally inconsistent, and
  duplicate-current content as `RequirementAnalysisGenerationError`.
- When a local model returns useful broad analysis but unusable question
  reviews, the local adapter performs one focused reconciliation recovery
  request. The provider uses simple one-based question numbers in that focused
  exchange; the adapter strictly validates completeness and maps them back to
  application-owned stable IDs. The focused result replaces only the
  question-review portion and is subjected to the same validation before
  anything can be persisted.
- Snapshot mapping adds optional `question_changes` and
  `replaces_question_id`. In-memory and PostgreSQL persistence need no
  relational migration.
- Activity projects `question_superseded` events from retired/replaced round
  records. Human clarification metrics still count only resolved answers.

## API

No endpoint is added. Existing current-analysis, round-history, synchronous
batch, and durable batch-job flows return the reconciled workspace.
`RequirementAnalysisResponse.question_changes` describes the latest round;
`ClarificationQuestionResponse.replaces_question_id` exposes lineage. OpenAPI
and generated TypeScript contracts include both additions.

## UI

- Grouped confirmation sections render active questions only.
- A compact status line counts retained, retired, revised, and new questions.
- Replacement cards display `Revised after re-analysis`.
- Immutable round history includes decision rationale, retired wording,
  replacement wording/ID, and any archived predecessor draft.
- Existing batch-answer, permission, failure-preservation, and busy states are
  unchanged.

## Tests

- Domain tests cover replacement links, metadata inheritance, draft archival,
  terminal behavior, round change records, JSON round trips, and legacy defaults.
- Application/API tests exercise all actions in one analyzer call/round,
  protected human questions, indirect retirement, attribution, activity,
  incomplete-provider rollback, and full active-snapshot concurrency.
- Adapter tests cover valid category-changing replacement/new output and reject
  missing, duplicate, unknown, human, blank, unchanged, or inconsistent reviews.
- API/OpenAPI, opt-in PostgreSQL, frontend component, and browser coverage verify
  response shape, active removal, summaries, badges, archived history, and links.

## Acceptance Criteria

- [x] Submitted questions resolve before reconciliation and are not reviewed.
- [x] Every other active AI question is retained, retired, or replaced exactly once.
- [x] Human-authored active questions remain unchanged and unduplicated.
- [x] Replacement identity, inheritance, lineage, and draft archival are correct.
- [x] One batch invokes one logical analysis and creates one immutable round.
- [x] Provider and concurrent-state failures make no partial changes.
- [x] Current confirmation uses only reconciled active blockers.
- [x] API, persistence, activity, UI, generated contracts, and documentation are complete.

## Validation Evidence

- `.venv\Scripts\python.exe -m pytest` — PASS: 567 passed, 12 skipped, 1
  warning in 22.84s. The skipped tests are the opt-in PostgreSQL integration suite because
  `TEST_DATABASE_URL` is not configured; that suite now includes linked
  replacement and question-change JSON round trips.
- `.venv-uv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv-uv\Scripts\ruff.exe format --check .` — PASS: 345 files already formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 281 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 218 files and 1,116 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run lint` — PASS: ESLint clean.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test -- --run` — PASS: 22 files, 97 tests in 6.49s.
- `npm.cmd run build` — PASS: 1,922 modules transformed and the production
  bundle built. Vite emitted its existing large-chunk advisory.
- `npm.cmd run api:check` — PASS: generated OpenAPI TypeScript has no drift.
  Node emitted its existing `DEP0190` warning.
- `$env:SMOKE_API_PORT='8044'; $env:SMOKE_UI_PORT='4214'; npm.cmd run test:smoke`
  — PASS: 12 desktop/responsive Chromium journeys in 44.8s, including a
  one-answer batch followed by a three-retained reconciliation summary.
- Rendered smoke screenshot inspection — PASS: the responsive clarification
  page keeps extracted and confirmation categories legible, hides the
  re-analysis label on round 1, and preserves the batch controls.
- Read-only live local-provider regression against requirement
  `3b788ea7-621e-4189-ac91-aec7ea11089b` — PASS: `qwen3-vl:8b` entered focused
  recovery and returned 12 validated reviews for 12 active AI questions under
  `analysis-v4`; no application state was written.
- CI — NOT RUN for these uncommitted working-tree changes; pending push.

## Deferred / Open

- No approved behavior is deferred.
- Existing provider recovery retries remain allowed; a batch still creates one
  logical analyzer invocation and one durable job.
