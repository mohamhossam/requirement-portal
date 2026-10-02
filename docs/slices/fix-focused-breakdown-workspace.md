# Maintenance — Focused Breakdown Workspace

## Objective

Implement the approved focused Epic → Feature → Story workspace within the existing
workspace (5B), Story review (5A), async jobs (8C) and approval (9) slices.

## User Outcome

Users see the selected item's content, status and relevant action immediately, with
sources, administration, successful quality checks and metadata available on demand.

## In Scope

- Compact Breakdown header, backlog navigator, route selection and responsive drawers.
- Focused artifact cards, acceptance criteria, quality reports and explicit merge mode.
- Existing source impact preview, People management, revision and final review access.
- Actor/requirement/artifact-scoped in-workspace draft retention and conflict handling.
- Lazy Story, quality and proposal reads and existing shared job polling.
- Request, navigation, accessibility and regression tests.

## Out of Scope

- Backend endpoints, response fields, migrations, provider changes and domain rules.
- Replacement generated content, Sites migration, publication or a component library.

## Domain

Existing artifact identity, provenance, staleness, reconciliation and approval rules remain.

## Application Use Cases

Existing generation, edit, review, approval, split/merge proposal, retry and cancellation
use cases remain authoritative; the frontend changes their presentation only.

## Ports

Existing ports are retained without changes.

## Adapters

Existing API client and actor-scoped React Query caches are reused. The single jobs
provider stores start/retry input targets locally to label affected items.

## API

Existing Epic/Feature/Story and governance URLs and server contracts remain compatible.

## UI

Breakdown has an explicit header/card variant, a 280px tree and spacious detail. Below
900px the tree opens in a native modal drawer. Item URLs select one review surface.
Unselected editors remain mounted; their data reads are disabled unless expanded.
Source and People move into drawers, while History and Review breakdown stay linked.
Quality failures are visible and successful checks collapse. Selection mode exposes
merge controls. Content is displayed verbatim. ADR-0045 records the composition change.

## Business Rules

- Stale and unapproved existing artifacts remain readable.
- Generation and mutation permissions use existing rules and server preconditions.
- Source editing retains server-counted impact acknowledgement and explicit save.
- Missing content, disabled reads, loading and request failures have distinct states.
- Disappearing observed Story selection returns to the parent with a completion notice.
- Drafts survive item selection but reset on identity/requirement change or page reload.

## Changed Files

- `frontend/src/app/RequirementPage.tsx` and `RequirementPage.test.tsx`.
- `frontend/src/components/AppHeader.tsx` and `WorkspaceDrawer.tsx`.
- `frontend/src/components/ConfirmDialog.tsx` (Breakdown-only keyboard containment).
- `frontend/src/features/breakdown/BreakdownWorkspace.tsx`.
- `frontend/src/features/epic/EpicCard.tsx` and `features/FeatureCard.tsx`.
- `frontend/src/features/stories/StoryList.tsx`, `StoryCard.tsx` and `StoryQualityPanel.tsx`.
- `frontend/src/features/jobs/RequirementJobsProvider.tsx`, `AiJobStatusPanel.tsx`
  and `AiJobStatusPanel.test.tsx`.
- `frontend/src/styles.css`, `frontend/tests/focused-breakdown.spec.ts`
  and `frontend/tests/review-flow.spec.ts`.
- This maintenance spec, ADR-0045 and the ADR index.

## Tests

- Existing frontend review, editor conflict, proposal, approval and jobs tests.
- Focused browser tests for direct links, reload, Back, invalid IDs and retained drafts.
- Story request isolation and one polling owner, mobile drawer focus/Escape, selection mode.
- Source impact warning in modal drawer, actor reset, loading, request failure and stale reads.
- Full fake-provider source-to-final-review regression journey at desktop and tablet sizes.
- Mobile reflow, zoom-equivalent viewport and 200% CSS zoom checks.

## Acceptance Criteria

- [x] Focused item routes and lazy request ownership implemented.
- [x] Existing editing, reconciliation, governance and source impact controls retained.
- [x] Explicit Breakdown styling leaves other journey stages on their existing variants.
- [x] All local checks recorded below; 166 frontend tests and 32 browser journeys pass.
- [ ] CI verification after push (not run by this local task).

## Validation Evidence

Local commands executed on 2026-09-18:

- `npm run test` — PASS: 27 files, 166 tests.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run build` — PASS: 1,933 modules; existing chunk-size warning (569.99 kB bundle).
  Initial build detected a non-UTF-8 edit; encoding was corrected before the passing build.
  A new test initially used a Playwright-only matcher option; it was replaced with a
  supported Testing Library matcher before the passing typecheck/build.
- `npm run api:check` — PASS: generated types match the current OpenAPI snapshot.
- `.venv/Scripts/python.exe -m pytest -o addopts="" -q` — PASS: 1,151 passed,
  23 PostgreSQL integration tests skipped (`TEST_DATABASE_URL is not configured`);
  one existing Starlette deprecation warning.
- `.venv-uv/Scripts/ruff.exe check .` — PASS: `All checks passed!`.
- `.venv-uv/Scripts/ruff.exe format --check .` — PASS: `458 files already formatted`.
- `.venv/Scripts/python.exe -m mypy src tests` — PASS: no issues in 356 source files.
- `.venv/Scripts/lint-imports.exe` — PASS: 321 files, 2,243 dependencies,
  `Contracts: 6 kept, 0 broken`.
- `$env:SMOKE_API_PORT='8059'; $env:SMOKE_UI_PORT='4259'; npm run test:smoke`
  — PASS: `32 passed (1.5m)`, desktop and responsive Chromium, with explicit 390px
  mobile, 1280×720 desktop and 200% CSS zoom checks inside focused tests.
- CI — not run/verified; local results do not establish green CI.

Backend result output:

```text
1151 passed, 23 skipped, 1 warning in 61.89s (0:01:01)
All checks passed!
458 files already formatted
Success: no issues found in 356 source files
Analyzed 321 files, 2243 dependencies.
Contracts: 6 kept, 0 broken.
```

Final browser output:

```text
Running 32 tests using 1 worker
32 passed (1.5m)
```

Browser iteration corrected item-transition test locators to wait for visible editors,
fixed 200% zoom header reflow and selected the intended linked requirement pair in the
shared contradiction test instead of the first relationship in shared fake-provider
data. The pair assertion handles either subject/related orientation because screening
can finish in either order. The targeted source-warning keyboard and shared-contradiction
rerun passed all four desktop/tablet tests. Request assertions retain one jobs owner and
omit Story requests on Epic entry. Focused confirmations contain Tab and restore focus;
Escape dismisses an impact warning while keeping its parent Source drawer open.
One full run had 31 passing tests and one fixture POST connection reset (`ECONNRESET`)
before any workspace UI was loaded. The isolated fake-data setup now allows one
Playwright transport retry for that failure. Application requests are unchanged.
Computed-style assertions verify 16px acceptance criteria and failed-check messages;
the live Breakdown shell and Epic paragraphs use the system sans-serif font at 16px.

## Deferred

CI execution requires the normal push/PR pipeline. PostgreSQL integration needs its
configured test database. Unrelated working-tree changes are preserved.
