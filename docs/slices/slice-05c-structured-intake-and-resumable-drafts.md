# Slice 5C — Structured Intake and Resumable Drafts

## Objective

Let authors safely pause and resume incomplete structured intake, make analysis
eligibility explicit, and require an acknowledged impact preview before a source
edit invalidates generated work.

## User Outcome

An author can begin with incomplete information, see automatic save success or
failure, retry a failed save, resume the latest server-backed draft, and start
analysis only after title, business need, and desired outcome are present.

## Domain

- `RequirementDraft` accepts normalized partial title, description, desired
  outcome, customer, channel, system, rule, and constraint context.
- `Requirement` retains validated title/description and gains structured
  context, optimistic version, update timestamp, and `AnalysisEligibility`.
- Draft and Requirement versions must be positive and advance monotonically.

## Application

- Create, get, list, save, and promote draft use cases.
- Analysis rejects an ineligible Requirement before invoking a provider.
- Requirement update checks the expected version and invalidates derived
  artifacts only for an actual source change.
- Impact preview reports analysis/Epic/Feature/Story counts. The final update
  recomputes impact inside the transaction and requires acknowledgement when
  generated content is affected.

## Ports

`RequirementDraftRepositoryPort` persists partial drafts without exposing an
adapter. Existing worklist snapshots provide the current cross-aggregate input
for impact preview.

## Adapters

- `InMemoryRequirementDraftRepository` keeps offline development and tests
  account-free.
- `PostgresRequirementDraftRepository` uses the shared transactional store and
  migration `003_requirement_drafts.sql`.
- Requirement and draft writes use compare-and-swap version checks.
- Snapshot mapping remains backward compatible with pre-5C Requirement JSON.

## API

- `POST/GET /requirements/drafts`
- `GET/PUT /requirements/drafts/{draftId}`
- `POST /requirements/drafts/{draftId}/promote`
- `POST /requirements/{id}/impact-preview`
- Requirement create/update/response schemas include structured fields,
  versions, timestamps, and analysis eligibility.
- Concurrent edits and unacknowledged downstream impact return HTTP 409;
  ineligible analysis returns HTTP 422.

## UI

- Three numbered intake sections for need/outcome, context, and boundaries.
- Debounced server autosave with accessible saving, saved, and failed live
  states plus explicit retry.
- Dashboard resume band and save-draft-and-exit behavior.
- Deep-linkable Capture, Clarify, Confirm, Breakdown, nested backlog, and
  Revisions routes; the legacy Requirement route redirects to persisted stage.
- Dedicated confirmation route shows separate facts, business rules,
  constraints, resolved answers, and the existing guarded “Confirm analysis”
  action.
- Source editing shows affected aggregate counts before acknowledged commit.

## Tests

- Domain/application: partial drafts, normalization, eligibility, promotion,
  optimistic conflicts, no-op source edits, and impact acknowledgement.
- API: draft lifecycle, missing draft, ineligible analysis, preview, 409
  conflicts, invalidation, and regenerated OpenAPI.
- UI: structured input validation, resume routing, save-only flow, autosave
  failure/retry live state, worklist stage links, and compatibility redirect.
- PostgreSQL tests remain opt-in through `TEST_DATABASE_URL`.

## Acceptance Criteria

- [x] Partial source data persists without weakening Requirement invariants.
- [x] Drafts resume in memory and PostgreSQL modes with version/timestamp data.
- [x] Autosave is debounced, announced accessibly, conflict-aware, and retryable.
- [x] Analysis eligibility lists missing fields and blocks provider calls.
- [x] Structured context reaches the analysis prompt as untrusted source data.
- [x] Source impact is previewed and recomputed before acknowledged commit.
- [x] All planned stage routes are deep-linkable and the legacy route redirects.
- [x] Confirmation remains blocked by unresolved analysis items.

## Validation Evidence

- `.venv\\Scripts\\pytest.exe` — PASS, 362 passed / 4 PostgreSQL tests
  skipped because `TEST_DATABASE_URL` is absent.
- `.venv\\Scripts\\ruff.exe check .` — PASS, all checks passed.
- `.venv\\Scripts\\ruff.exe format --check .` — PASS, 207 files
  formatted.
- `.venv\\Scripts\\mypy.exe src tests` — PASS, no issues in 169 source
  files.
- `.venv\\Scripts\\lint-imports.exe` — PASS, 2 contracts kept / 0 broken.
- `npm.cmd run api:check` — PASS; generated TypeScript matches committed
  OpenAPI.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS, 12 files / 54 tests.
- `npm.cmd run build` — PASS, Vite emitted local Archivo assets.
- `npm.cmd run test:smoke` — PASS, full flow in Chromium at 1440×1000 and
  responsive 740×1000.
- Playwright screenshots for dashboard, structured intake, and clarification
  were visually inspected from `frontend/test-results/`.
- CI — not independently verifiable from this workspace because the GitHub
  repository is private and no authenticated GitHub CLI/session is available.

## Explicitly Deferred

No Slice 5C roadmap field was dropped. Source Documents, upload/extraction,
attachment analysis context, and document catalogue routes remain Slice 5D.
Identity-scoped draft ownership remains Slice 8A.

## Fresh Intake and Quiet Autosave Follow-up

`/requirements/new` now always starts from an empty form. It no longer loads a
browser-remembered or newest server draft implicitly. The dashboard's Resume
action carries the selected draft identity explicitly as
`/requirements/new?draft={draftId}`, so refresh/resume behavior is deliberate
and testable.

Background autosave no longer sets the full form's submission-busy state. The
accessible save-status region still announces unsaved, saving, saved, and
failure states, while fields retain focus and submit controls do not flash or
change labels. The first successful autosave also keeps the same form instance
instead of remounting it when the server assigns a draft ID.

Follow-up validation:

- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS, 14 files / 63 tests.
- `npm.cmd run build` — PASS.
- `git diff --check` — PASS.
