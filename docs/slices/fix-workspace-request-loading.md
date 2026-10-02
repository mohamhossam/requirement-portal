# Maintenance — Scoped workspace requests and shared AI jobs

## Objective

Correct the unnecessary resource reads and repeated job-driven refreshes in the
existing Slice 5B workspace and Slice 8C job UI. This is the user-approved
frontend-only maintenance task of 2026-09-18, not a new roadmap slice.

## User Outcome

Clarification does not request Epic, Features, Stories, or revision history.
Generated and stale backlog content remains readable on Breakdown, and active
jobs continue to expose progress, cancellation, retry, and persisted results.

## In Scope

- View-specific loading and explicit empty/loading/error states.
- One requirement-scoped job provider and operation-specific cache invalidation.
- Actor-scoped transition history, fast completion, and navigation recovery.
- Request-count tests, regression checks, and fake-provider browser journeys.

## Out of Scope

- Eliminating the initial expected 404 for an optional resource that does not exist.
- Backend contract changes, availability metadata, migrations, or provider configuration.
- Resolving the separate upstream provider failure during clarification resolution.

## Domain

No change. Existing generation, staleness, approval, and question rules remain
authoritative. Reading a backlog does not require confirmed analysis; generation
continues to require the existing confirmation and approval checks.

## Application Use Cases

No backend use-case changes. The UI refresh policy follows the persisted effects
of the existing use cases and does not introduce business rules.

## Ports

No new outbound ports or changes to existing ports.

## Adapters

No backend adapter changes. Existing actor-scoped API requests and optional 404
handling remain in use.

## API

No endpoint, schema, generated OpenAPI, or persistence changes for this task.
Feature result links in the existing job response identify the Feature-specific
Story/quality/proposal cache. Legacy results without Feature identity fall back
to the requirement-scoped cache prefix.

## UI

- Epic loads only on Breakdown; Features load after an Epic exists. Unconfirmed
  analysis or stale content does not prevent these reads.
- Analysis rounds and question suggestions load only on Clarify/Confirm;
  revision history loads only on Revisions. Shared requirement, access, analysis,
  and knowledge reads support the source rail and journey indicators.
- Disabled Features show the empty/dependency state rather than a perpetual
  loading message. Epic, Feature, and Story read failures remain visible.
- Re-analysis confirmation describes preserved history without counting unloaded
  caches. The server-backed source-edit impact acknowledgement is retained.
- `RequirementJobsProvider` owns the one-second active-job polling interval,
  cancel/retry actions, and central `startJob` registration. Existing per-action
  mutation states still retain their own errors and pending controls.
- The first authoritative job list establishes a history baseline. Existing
  terminal jobs do not invalidate artifacts. Active-to-terminal transitions and
  newly appearing terminal jobs are handled once. Intake, starts, retries, and
  lazy screening register job identity before terminal detection.
- Observation data stays in the actor/requirement query cache, with a disabled
  cache observer keeping it alive while the workspace is mounted. Normal cache
  garbage collection applies after leaving. If history has expired, fresh visible
  resource reads still recover off-page results without replaying old jobs.
- Visible shared data refreshes on workspace entry. Scoped queries refresh when
  re-enabled on their view; leaving a section marks its caches stale without
  fetching. Story/review panels refresh when remounted. Existing focus freshness
  remains enabled with its original freshness window.
- Cancelled job-list reads cannot process stale transitions. Terminal observation
  state cannot regress to an active status; retries use new identities.
- Successful jobs invalidate affected caches and their dependent review/approval
  data. Failure/cancellation refresh workflow summaries and notifications only.
  Hidden caches become stale without fetching. Batch completions deduplicate keys.
- Approval refreshes exclude unchanged child artifacts. Successful review/approval
  writes retain the returned authoritative result while refreshing dependents.
- All cache prefixes use actor-scoped query keys; the old unscoped Story and
  proposal invalidations are removed.

## Business Rules

Existing permission, confirmation, revision, and human-review rules are preserved.
No new business assumptions or external publication behavior are introduced.

## Tests

- Clarify/Confirm request counts; missing Epic skips Features without a spinner.
- Stale backlog visibility under unconfirmed analysis; real Epic/Feature errors.
- Re-analysis wording and view return inside the normal freshness window.
- Browser focus does not refetch a resource inside the normal freshness window.
- Historical job baseline, shared polling across multiple Story lists, interval
  stopping, fast completion, failure/cancellation, and off-page completion.
- Actor/requirement isolation, Feature-specific invalidation, hidden-cache
  staleness, intake completion versus historical jobs, and terminal non-regression.
- Existing UI tests explicitly mount the required shared provider and use valid
  typed job fixtures instead of empty response objects.
- Desktop and responsive fake-provider journeys assert no backlog/history reads
  from Capture/Clarify/Knowledge/Confirm and preserve source-edit impact/staleness.

## Acceptance Criteria

- [x] Clarify does not read backlog artifacts or revision history.
- [x] Historical jobs cause no artifact refresh burst.
- [x] Multiple job consumers share one polling owner.
- [x] Changed data refreshes; hidden and unrelated resources are not fetched.
- [x] Fast completion, retries, navigation, and identity isolation are covered.
- [x] Existing stale items and explicit loading/empty/error states are preserved.
- [x] Re-analysis and source-edit confirmation remain truthful.
- [ ] CI validates the uncommitted changes after push.

## Changed Files

- Workspace: `frontend/src/app/RequirementPage.tsx`, `workspaceInvalidation.ts`,
  `NewRequirementPage.tsx`, and `RequirementPage.test.tsx`/`NewRequirementPage.test.tsx`.
- Jobs: `frontend/src/features/jobs/RequirementJobsProvider.tsx`,
  `RequirementJobsProvider.test.tsx`, `jobObservation.ts`, `useRequirementJobs.ts`,
  and `AiJobStatusPanel.test.tsx`.
- Consumers: `frontend/src/features/stories/StoryList.tsx`/`StoryList.test.tsx`,
  `frontend/src/features/review/ApprovalWorkflowPanel.tsx`/`ApprovalWorkflowPanel.test.tsx`,
  `BreakdownReviewPanel.tsx`/`BreakdownReviewPanel.test.tsx`,
  `frontend/src/features/knowledge/useLazyKnowledgeScreening.ts`, and
  `frontend/src/features/features/FeatureTree.test.tsx`.
- Verification: `frontend/src/test/renderWithClient.tsx`, `jobFixture.ts`, and
  `frontend/tests/review-flow.spec.ts`.
- Documentation: this maintenance spec and `WORKSPACE.md`.

Existing unrelated working-tree edits are retained. No backend file is changed
by this maintenance task.

## Validation Evidence

Commands executed locally on 2026-09-18:

```text
.venv/Scripts/python.exe -m pytest
1016 passed, 23 skipped, 1 warning in 61.61s (0:01:01)

.venv/Scripts/ruff.exe check .
All checks passed!

.venv/Scripts/ruff.exe format --check .
456 files already formatted

.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 356 source files

.venv/Scripts/lint-imports.exe
Analyzed 321 files, 2243 dependencies.
Contracts: 6 kept, 0 broken.

npm.cmd run lint
eslint . — exit 0

npm.cmd run typecheck
tsc -b --pretty false — exit 0

npm.cmd test -- --reporter=dot
Test Files 26 passed (26)
Tests 161 passed (161)

npm.cmd run api:check
openapi-typescript — exit 0; generated schemas have no drift

SMOKE_API_PORT=8030 npm.cmd run build
vite production build — exit 0

SMOKE_API_PORT=8030 SMOKE_UI_PORT=4200 IDENTITY_PROVIDER=fake
npm.cmd run test:smoke -- --grep 'Product Owner completes|Knowledge entry lazily'
4 passed (desktop and responsive Chromium)
```

The 23 backend skips are opt-in PostgreSQL coverage with no `TEST_DATABASE_URL`.
Existing warnings include the Starlette/AnyIO deprecation, API-check Node shell
deprecation, and Vite's bundle-size notice. A development warning about the
observation cache query was corrected by explicitly using `skipToken`.

CI — not run: these changes are uncommitted and have not been pushed.

## Deferred

- API availability metadata was deliberately excluded by the user's frontend-only choice.
- Separate upstream provider failures remain outside this maintenance task.
