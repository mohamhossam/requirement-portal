# Enhancement — Requirements Dashboard

> Status: **implemented locally**. A bounded enhancement to delivered Slices 01
> and 4A, not the start or partial delivery of a future roadmap slice. It
> retires the "No list endpoint" debt recorded in
> `slice-04a-review-ui.md`.

## Objective

Make the browser entry point a dashboard that lists the existing requirements,
opens any of them into the review flow, and starts a new one — so a reviewer no
longer has to remember or paste a requirement id.

## User Outcome

Landing on `/`, a Business Owner sees every requirement they have created
(most recently updated first), clicks one to open its full review page, or
starts a new requirement from the same screen.

## Why this was needed

Slice 4A shipped the review surface but, by explicit recorded decision, "the UI
works from a requirement id" — the only ways in were creating a new requirement
or pasting an id, with the last id kept in `localStorage`. On a real workspace
with several requirements that is unusable: there was no way to see what exists.
This enhancement adds the one missing read (`GET /requirements`) and the
dashboard that consumes it.

## Scope

### Backend (the one missing read)
- `RequirementRepositoryPort.list_all()` — returns every Requirement, most
  recently touched first. (Named `list_all`, not `list`, to avoid shadowing the
  builtin in return annotations — the same convention the codebase already uses
  for `StoryChangeProposals.list_proposals`.)
- Implemented in `InMemoryRequirementRepository` (newest-first by insertion
  order), `PostgresStore` (`ORDER BY updated_at DESC`), and the revision-tracking
  decorator `TrackingRequirementRepository` (delegates).
- `ListRequirements` application use case.
- `GET /requirements` → `RequirementListResponse` (`{ requirements: [...] }`),
  plus container and dependency wiring.

### Frontend
- `DashboardPage` at `/` (replaces the old `LandingPage`): lists requirements as
  cards linking to `/requirements/:id`, an empty state, and a "New requirement"
  action that opens the guided `/requirements/new` intake route. Reuses
  `RequirementForm`.
- Client `listRequirements()`, `requirementList` query key, regenerated
  `openapi.json` and `schema.d.ts`.
- Editing a requirement's title/description on the review page now invalidates
  the dashboard list so the change is reflected when the reviewer returns.

## Out of scope

- Search, filtering, pagination, and delete/archive. The list is a flat
  newest-first read; those are separate concerns to add when the volume needs
  them.
- Any new requirement field (owner, timestamps in the response, counts of
  downstream artifacts). The dashboard shows title, id, status and description.

## Tests

- Repository: `list_all` empty and newest-first (in-memory contract test).
- Use case: `ListRequirements` empty and newest-first ordering.
- API: `GET /requirements` empty (`{"requirements": []}`) and newest-first after
  two creations.
- Frontend: `DashboardPage` lists requirements as links, shows the empty state,
  and links to the guided intake route; `NewRequirementPage` explains and saves
  the source requirement.
- Smoke: the Playwright flow now starts on the dashboard ("New requirement"),
  runs the whole review journey, then returns to the dashboard and reopens the
  requirement from the list.

## Original Validation Evidence
- `pytest` — 295 passed, 3 skipped (Postgres integration, no live DB).
- `ruff check .` — All checks passed.
- `ruff format --check .` — clean.
- `mypy src tests` — Success, no issues.
- `lint-imports` — Contracts: 2 kept, 0 broken.
- `npm --prefix frontend run lint` / `typecheck` / `api:check` — clean.
- `npm --prefix frontend test` — 10 files, 38 tests passed.
- `npx playwright test` (`LLM_PROVIDER=fake`, `PERSISTENCE_PROVIDER=memory`) —
  1 passed, dashboard-to-review-to-dashboard.

## Customer-experience refresh (2026-09-02)

The dashboard and intake entry were refined after hands-on customer feedback:

- `/` is now workspace-first: a compact header, clear primary action, concise
  four-step journey, requirement count, and existing work are visible in one
  responsive layout. The previous half-screen marketing panel no longer pushes
  the working list into a narrow column.
- Creating a requirement now uses the dedicated `/requirements/new` route, so
  starting a draft no longer replaces or hides the dashboard in place.
- The intake page explains when AI analysis starts, what happens after save,
  and which details make a useful source requirement without implying that the
  input must already be complete.
- The requirement form provides example text, field-specific guidance,
  accessible descriptions, field-level validation, keyboard focus on the first
  intake field, and responsive actions.
- The API, domain model, and downstream review lifecycle are unchanged.

## Refresh Validation Evidence

- `pytest` with live PostgreSQL — 341 passed.
- `ruff check .` — All checks passed.
- `ruff format --check .` — 191 files already formatted.
- `mypy src tests` — Success, no issues in 157 source files.
- `lint-imports` — Contracts: 2 kept, 0 broken.
- `npm --prefix frontend run api:check` — generated types match OpenAPI.
- `npm --prefix frontend run lint` — clean.
- `npm --prefix frontend run typecheck` — clean.
- `npm --prefix frontend test` — 11 files, 47 tests passed.
- `npm --prefix frontend run build` — production build completed.
- `npm --prefix frontend run test:smoke` (`LLM_PROVIDER=fake`,
  `PERSISTENCE_PROVIDER=memory`) — 1 passed, dashboard → guided intake →
  review → dashboard.

## Retires

- `slice-04a-review-ui.md` debt: "No list endpoint … `GET /requirements` does
  not exist and this slice does not add it." It exists now, and the dashboard
  removes the paste-an-id entry path.
