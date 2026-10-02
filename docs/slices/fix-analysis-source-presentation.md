# Maintenance — Quiet analysis sources

## Objective

Reduce citation noise in the existing requirement clarification workspace. This is
user-authorized presentation maintenance of Slice 8B and Enhancement 5D.2, following
ADRs 0019, 0029 and 0044; it introduces no new roadmap slice.

## User Outcome

Findings stay readable. One compact Sources control shows document-reference and
human-answer counts. A side panel reveals the supporting documents and attributed
answers without changing the reading position.

## In Scope

- Shared, analysis-scoped source panel for facts, rules, constraints, intent proposals
  and stateful clarification questions.
- Exact duplicate removal in presentation, preserving distinct answers and versions.
- Document/version grouping, original section/block labels and source links.
- Separate human support, including question, answer, actor, time and suggestion origin.
- Neutral styles, collapsed reference metadata, keyboard focus and mobile presentation.
- Component, network and fake-provider browser verification.

## Out of Scope

Provider resolution performance/failures, source extraction, backend citation validation,
API changes, database migrations and changes to business decisions or stored evidence.
The source viewer retains its existing current-document preview and block-anchor route;
historical version selection in that viewer is separate maintenance.

## Domain

No change. Document evidence and human answers remain distinct. Unsupported content
gets no Sources control. Display deduplication never changes persisted evidence.

## Application Use Cases

No backend change. Existing analysis and answer attribution supply the presentation.

## Ports

No new ports or changes.

## Adapters

No backend changes. The panel uses analysis document metadata already loaded, making
no additional API requests. Opening an explicitly chosen source retains the existing
document route in a new tab.

## API

No endpoint, schema, OpenAPI or provider configuration changes.

## UI

`AnalysisSourcesProvider` owns one native modal dialog per displayed analysis. Sources
buttons replace repeated red reference titles. The panel groups references by document,
version and checksum, retaining full source labels. Document IDs, version IDs and
checksums are collapsed under Reference details. Human answers appear separately with
their originating question and attribution. Exact record duplicates collapse; different
questions, answer text, dates, actors, suggestion origins and source versions remain.

The dialog supports Escape, close and backdrop dismissal; Tab/Shift+Tab remain in the
panel and closing returns focus to the original finding. It becomes a full-width sheet
on small screens, with scrollable content. Requirement, actor and analysis changes
dispose of the panel through the existing workspace scope and analysis key.

## Business Rules

Existing confirmation, permissions, staleness, source inclusion and provenance rules
remain authoritative. No inferred evidence or fabricated legacy attribution is added.

## Tests

- Compact initial display, empty support and on-demand source details.
- Exact deduplication, document grouping, different versions and distinct human answers.
- Legacy metadata, analysis-scope reset, Escape and focus restoration.
- Browser keyboard loops, dismissal, mobile width/overflow and new-tab source links.
- Network assertion: panel opening makes no document/analysis/backlog/history requests.
- Existing review/source-upload journey updated to verify the new source control.

## Acceptance Criteria

- [x] A finding displays one quiet Sources control rather than repeated full links.
- [x] Document and human support remain separately identifiable and auditable.
- [x] Existing source labels and links are preserved; technical metadata is collapsed.
- [x] Exact duplicates disappear without hiding different answers or source versions.
- [x] Keyboard and mobile interaction work without extra source fetches.
- [x] Unrelated working-tree changes are preserved.

## Validation Evidence

Executed locally on 2026-09-18; commands run against the complete existing working tree.

- `npm run test` — PASS: 27 files passed, 164 tests passed.
- `npm run lint` — PASS: ESLint exit 0.
- `npm run typecheck` — PASS: TypeScript exit 0.
- `npm run build` — PASS: 1932 modules transformed, production build completed.
  Existing bundle-size warning remains (JavaScript bundle above 500 kB).
- `npm run api:check` — PASS: generated API types match the OpenAPI snapshot, exit 0.
  Existing Node shell deprecation warning remains.
- Source-panel Playwright checks — PASS: 2 tests passed, including 390px mobile and
  desktop/responsive projects; isolated fake/memory servers on ports 8058 and 4258.
- `$env:SMOKE_API_PORT='8058'; $env:SMOKE_UI_PORT='4258'; npm run test:smoke -- tests/analysis-sources.spec.ts tests/review-flow.spec.ts`
  — PASS: `20 passed (1.2m)`, including source-panel checks and all 18 existing review
  journeys with the source-upload assertion updated to the new Sources control.
  The first review run had 16 passes and two failures from the obsolete inline
  `Source:` link assertion; the final updated suite has no failing tests.
- `.venv\Scripts\python.exe -m pytest -o addopts="" -q` — PASS:
  `1151 passed, 23 skipped, 1 warning in 64.01s (0:01:04)`.
  PostgreSQL tests skip without configured TEST_DATABASE_URL; the warning is the
  existing Starlette/AnyIO deprecated BlockingPortal alias.
- `.venv-uv\Scripts\ruff.exe check .` — PASS: `All checks passed!`
- `.venv-uv\Scripts\ruff.exe format --check .` — PASS: `457 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS:
  `Success: no issues found in 356 source files`.
- `.venv\Scripts\lint-imports.exe` — PASS:
  `Analyzed 321 files, 2243 dependencies. Contracts: 6 kept, 0 broken.`
- CI — not run for these uncommitted changes; no CI completion claimed.

## Deferred

No roadmap field is dropped: this maintains the existing UI and audit slices.
Historical source-version selection remains an existing source-viewer limitation.
