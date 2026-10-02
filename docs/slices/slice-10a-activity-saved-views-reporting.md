# Slice 10A — Activity, Saved Views, and Reporting

> Status: **complete locally; CI pending push**.

## Objective

Expose traceable portfolio activity, private reusable worklist criteria, and
operational trend/blocker reporting without duplicating audit history.

## User Outcome

Every authenticated reviewer can follow business milestones and drill from
weekly metrics or blockers to their Requirement. Each actor can create, apply,
rename/update, and delete private worklist views.

## Roadmap Scope Check

| Roadmap field | Delivery |
|---|---|
| Domain / Application | Application read models and queries project existing immutable audit evidence; saved-view criteria are application-owned preference models. No dashboard state enters a business aggregate. |
| Ports | Focused `ActivityReadPort`, `ReportingReadPort`, and `SavedViewRepositoryPort`. |
| Adapters | Memory/PostgreSQL audit projection and actor-scoped saved-view adapters; migration 009 and time-read indexes. |
| API | Authenticated Activity, operational report, and saved-view CRUD routes; worklist latest activity attribution. |
| UI | Activity and Reports routes/navigation, filters, evidence links, worklist attribution, full saved-view controls, accessible weekly table and blocker links. |
| Tests | Projection/query/report boundaries, CRUD/isolation/conflicts, API/error/OpenAPI contracts, component interaction, PostgreSQL restart, and browser smoke. |

Nothing in the Slice 10A roadmap entry is dropped.

## In Scope

- Deterministic, source-referenced business milestone projection from persisted
  Requirement/breakdown revisions, analysis rounds/questions, access changes,
  terminal AI jobs, approvals, comments, decisions, and review transitions.
- Portfolio filtering, stable ordering, offset pagination, explicit legacy
  attribution, and latest worklist action/actor without changing `updated_at`.
- Private named worklist criteria with case-insensitive uniqueness and
  optimistic update/delete versions.
- Four-, twelve-, and twenty-six-week Monday-UTC reporting; the current partial
  week ends at the injected clock instant.
- Weekly created/analysis/question-resolution/artifact-approval/final-approval
  counts with evidence IDs, clarification cohort metrics, and ten oldest fresh
  current blockers with source/navigation evidence.

## Out of Scope

- Custom date ranges, exports, SLA policy, external BI, sharing/default/team
  views, maintained templates, ADO publication, and non-terminal job noise.

## Domain

No domain aggregate changes. Historic domain actor snapshots remain optional in
the application projection and are never fabricated.

## Application Use Cases

- `ListActivity` filters normalized events and applies timestamp/ID ordering and
  pagination.
- `GetOperationalReport` builds weekly and clarification cohort metrics plus
  current blockers from traceable evidence.
- `SavedViews` performs actor-private list/create/update/delete with name and
  optimistic-version policy.
- `ListRequirementWorklist` attaches the newest projected event while retaining
  the source snapshot's `updated_at`.

## Ports

- `ActivityReadPort`
- `ReportingReadPort`
- `SavedViewRepositoryPort`

## Adapters

- `InMemoryActivityReadAdapter` and `PostgresActivityReadAdapter` compose current
  repository/revision/audit/job ports; neither stores copied events.
- `InMemorySavedViewRepository` and `PostgresSavedViewRepository` provide the
  same actor/version/name contract.
- `009_saved_requirement_views.sql` adds restart-durable JSONB criteria and
  indexes supporting saved-name and time-ordered audit reads.

## API

- `GET /activity`
- `GET /reports/operational?weeks=12`
- `GET /saved-views`
- `POST /saved-views`
- `PUT /saved-views/{view_id}`
- `DELETE /saved-views/{view_id}?expected_version=...`

All routes resolve an authenticated actor. Portfolio activity/reports do not
apply Requirement-team authorization; saved resources return 404 across actor
boundaries, 409 for duplicate/stale writes, and 422 for invalid input through
central translation.

## UI

- Global and responsive navigation reaches Requirements, Activity, and Reports.
- Activity supports category, Requirement, actor, inclusive-start, and
  exclusive-end filters; rows expose actor/unavailable attribution, timestamp,
  source, and Requirement navigation.
- The dashboard applies saved criteria as a complete replacement and therefore
  starts a fresh first-page query; controls support create, update/rename, and
  delete.
- Worklist and attention rows show the latest activity actor, using explicit
  unavailable/system labels.
- Reports offers 4/12/26 weeks, a semantic table, clarification summary, blocker
  links, and exact-window metric drilldowns into Activity without a charting
  dependency.

## Business Rules

- Projection identity is deterministic from action plus persisted source;
  repeated audit evidence across revisions is emitted once.
- Running, queued, cancellation-requested, retry, and heartbeat job records are
  not feed milestones. Success, failure, and cancellation are.
- Question resolution rate cohorts questions opened inside the report window
  and checks resolution by the current window end.
- Current blockers include active blocking questions and open blocking flags
  only when their review evidence is fresh.
- Saved criteria never contain offset, limit, expanded rows, or other UI state.

## Tests

- Application filtering/order/pagination, UTC report boundaries, partial week,
  evidence IDs, clarification rates/median, blocker order/limit, and saved-view
  lifecycle/isolation/conflicts.
- API attribution/filter/report/CRUD/error and generated-contract coverage.
- PostgreSQL migration idempotency and saved-view restart durability when
  `TEST_DATABASE_URL` is configured.
- React Activity/Reports rendering, exact drilldowns, saved-view application,
  last-activity labels, responsive navigation, and browser smoke coverage.

## Acceptance Criteria

- [x] Activity rows and report measures are derived from and trace to persisted evidence.
- [x] Historic missing attribution is presented as unavailable and never inferred.
- [x] Private saved views round-trip only complete worklist criteria and enforce ownership/name/version rules.
- [x] Reports implement the approved windows, UTC week policy, clarification cohort, and fresh oldest blockers.
- [x] Worklist timestamps retain their previous meaning while separately showing newest milestone attribution.
- [x] Activity and Reports are functional browser routes with drilldown navigation.
- [x] No event-copy table, charting package, environment variable, ADO behavior, or future-slice export is added.

## Architecture Impact

ADR-0022 records the three focused application boundaries, evidence projection,
and private saved-view persistence. Dependency direction and central composition
and error translation remain unchanged.

## Validation Evidence

- `$env:TEST_DATABASE_URL='postgresql://smb:smb_dev@127.0.0.1:5432/smb_requirements'; pytest` — PASS: 519 passed in 10.78s; PostgreSQL migration, bulk projection, and saved-view restart tests executed.
- `ruff check .` — PASS: all checks passed.
- `ruff format --check .` — PASS: 326 files already formatted.
- `mypy src tests` — PASS: no issues in 270 source files.
- `lint-imports` — PASS: 2 contracts kept, 0 broken across 210 files and 1084 dependencies.
- `npm run api:check` — PASS: generated TypeScript matches the committed OpenAPI document.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run test` — PASS: 22 files, 88 tests.
- `npm run build` — PASS: TypeScript and Vite production build completed.
- `npm run test:smoke` — PASS: 12 Playwright tests across desktop and responsive Chromium, including saved-view, attributed activity, metric, and blocker drilldowns.
- CI — pending push; local success is not CI authority.

## Deferred

- Shared/default/team-managed views, custom report ranges, export/external BI,
  SLA policy, maintained templates, neutral export, and ADO remain in their
  explicitly later roadmap scope.

## Desktop sidebar regression

Activity and Reports now retain the shared 254px desktop sidebar offset rather
than centering underneath the fixed navigation. Browser smoke coverage asserts
that portfolio content begins at or beyond the sidebar's right edge; the
existing responsive breakpoint still removes the sidebar below 900px.

Regression validation evidence:

- Live browser geometry at 1686px — PASS: sidebar right `254px`, portfolio
  content left `254px`, overlap `0px` on Activity and Reports.
- `npm run api:check` — PASS.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run test` — PASS: 22 files, 91 tests.
- `npm run build` — PASS.
- `npm run test:smoke` — PASS: 12 desktop/responsive Chromium tests.
- `pytest` — PASS: 532 passed, 12 skipped.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS: 340 files.
- `mypy src tests` — PASS: 281 source files.
- `lint-imports` — PASS: 2 contracts kept.
