# Slice 5B — Desktop Worklist and Journey Refactor

## Objective

Replace the marketing-style browser shell with the exported Modernist desktop
worklist, intake, and clarification journeys, backed by truthful cross-aggregate
status data. Preserve all delivered Epic, Feature, Story, proposal, staleness,
and revision behavior. A dedicated mobile journey is explicitly out of scope;
ordinary responsive reflow and accessibility remain required.

## User Outcome

A reviewer can find the next Requirement needing work, filter and search the
portfolio, create and immediately analyse a Requirement, resolve uncertainty,
record human confirmation, and continue into the existing backlog review flow
without unsupported controls or invented dashboard data.

## Domain

No new domain concept. Dashboard state is a cross-aggregate read model and does
not expand `Requirement`. The existing explicit analysis confirmation remains
the source of truth for the Breakdown gate.

## Application

- `ListRequirementWorklist` classifies snapshots, selects the next action,
  ranks up to three attention items, and applies search/filter/sort/pagination.
- Status precedence is durable re-analysis (reserved for Slice 8C), stale,
  needs answers, approved (reserved until Slice 9 can approve the full
  backlog), ready for review, then draft.
- `GenerateEpic` rejects an unconfirmed analysis with
  `AnalysisConfirmationRequiredError`.

## Ports

`RequirementWorklistSnapshotPort` supplies Requirement, analysis, Epic,
Feature, Story, and latest-activity data without exposing persistence details.

## Adapters

- `InMemoryRequirementWorklistSnapshotAdapter` composes current in-memory and
  revision repositories.
- `PostgresStore.list_snapshots()` loads the equivalent view in bounded bulk
  queries.
- Both are selected only by `interfaces/api/container.py` (ADR-0012).

## API

`GET /requirements` retains existing Requirement fields and adds:

- `q`, repeated `workflow_status`, `sort`, `offset`, `limit` (20 default, 100
  maximum);
- enriched worklist items with workflow status, stage, next action,
  answered/unresolved/stale counts, Epic/Feature/Story counts, and `updated_at`;
- total/pagination metadata, search-relative status facets, and up to three
  globally ranked attention items.

`POST /requirements/{id}/epic` now returns HTTP 409 until analysis is explicitly
human-confirmed. Detail and mutation endpoints otherwise remain compatible.

## UI

- Modernist tokens: locally bundled Archivo, red/ink/light-ground palette,
  square controls, visible structural rules, and labelled Lucide actions.
- Dashboard: collapsible real attention band, status counter filters,
  server-backed ID/title/description search, sort, Load more, progress/open
  counts, update time, and textual next actions.
- Intake: anchor rail, two persisted source fields, validation summary with
  focus, writing guidance, worked example, next-step explanation, save-only and
  save-and-analyse actions. Failed analysis leaves the created Requirement
  accessible and offers retry.
- Analysis: Capture → Analyse → Clarify → Confirm → Breakdown header, sticky
  source/facts rail, open-item progress and free-text answers, synchronous
  re-analysis state, and a locked Breakdown until confirmation.
- Existing Epic, Feature, Story, proposal, stale-content, and revision flows are
  visually restyled without removing behavior.
- Export-runtime `_ds_bundle.js` and `support.js` are not shipped.

## Tests

- Application classification/precedence, actions, counts, ranking, search,
  filters, sorting, pagination, and facets.
- API enriched response, query validation, OpenAPI snapshot, and confirmation
  error mapping.
- UI worklist controls/attention, intake intents/failure preservation,
  clarification progress/gate, and existing review-action regressions.
- PostgreSQL integration remains opt-in through `TEST_DATABASE_URL`.
- Playwright desktop smoke exercises the complete fake-provider flow.

## Acceptance Criteria

- [x] Worklist data is derived from persisted aggregates/revisions, never UI
      fixtures or inferred ownership.
- [x] Search, repeated status filters, sort, pagination, facets, attention
      ordering, counts, and next action are server-backed.
- [x] Epic generation cannot bypass explicit human analysis confirmation.
- [x] Intake supports save-only and save-and-analyse; analysis failure preserves
      and links to the created Requirement.
- [x] Clarification is the primary workspace and Breakdown is locked until
      confirmation.
- [x] Existing backlog/revision actions remain available.
- [x] Archivo and Lucide are local dependencies; Claude export runtimes are not
      included.
- [x] Responsive reflow and accessible states are retained without a dedicated
      mobile journey.

## Validation Evidence

- `pytest -q` — PASS (4 PostgreSQL tests skipped because `TEST_DATABASE_URL`
  is absent).
- `ruff check .` — PASS, all checks passed.
- `ruff format --check .` — PASS, 198 files formatted.
- `mypy src tests` — PASS, no issues in 162 source files.
- `lint-imports` — PASS, 2 contracts kept / 0 broken.
- `npm.cmd run api:check` — PASS; generated types match committed OpenAPI.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS, 11 files / 52 tests.
- `npm.cmd run build` — PASS, Vite production build emitted local Archivo
  assets.
- `npm.cmd run test:smoke` — PASS, 1 Playwright Chromium journey at 1440px.
- Playwright captured `wireframe-dashboard.png`, `wireframe-intake.png`, and
  `wireframe-clarification.png` under the ignored `frontend/test-results/`
  evidence directory; all three were visually inspected.
- CI — pending branch push; no remote branch or pull request was created.

## Explicitly Deferred

No roadmap field for 5B was dropped. The following wireframe capabilities are
not part of 5B and are carried by named slices: structured/autosaved drafts
(5C), attachments/templates (5D), identity/ownership (8A), collaborative
question assignment/audit (8B), async jobs/notifications (8C), formal approval
(9), and activity/saved views/reporting (10A). The absence of a dedicated mobile
journey was approved in the 5B plan; normal responsive behavior remains.

## Design Reference Alignment Follow-up

The supplied Stitch archive was rechecked against the running application. The
shared shell now follows its Precision Engineering design system: a fixed 64px
header, 254px project-context rail, cool-blue layered surfaces, restrained red
actions, subtle one-pixel structural dividers, compact low-radius controls, and
locally bundled Archivo Narrow typography. Worklist, intake, clarification,
confirmation, backlog, documents, and revision routes inherit the same shell.

Mock Library/Archive/profile controls, mock telecom content, Tailwind CDN,
Google Fonts, and Material Symbols remain excluded. Responsive layouts collapse
the context rail and preserve all existing workflows.

Follow-up validation:

- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS, 14 files / 59 tests.
- `npm.cmd run build` — PASS; Vite emitted only local Archivo Narrow assets.
- Live 1280px worklist and clarification plus 740px intake captures were
  visually compared with the supplied reference screens.
