# Slice 7 — Architecture Impact Mapping

## Objective

Attach explicit, reviewable architecture impact to the current Feature and Story
breakdown using replaceable, versioned SMB architecture knowledge.

## User Outcome

A reviewer can map the whole current breakdown, see likely systems and capabilities,
identify missing squad ownership and system dependencies, and spot cross-system
Features before governance decisions are made.

## In Scope

- Deterministic Feature and Story mapping from a packaged YAML catalogue.
- One explicit whole-breakdown map/refresh action.
- Durable architecture impact in current state and immutable revisions.
- Systems, capabilities, optional squad ownership, dependencies, catalogue provenance,
  empty results, and cross-system warnings in the browser.

## Out of Scope

- Flag resolution and decisions (Slice 8).
- Story/full-backlog approval gating (Slice 9).
- Catalogue administration or verified squad maintenance (Slice 14).
- LLM, RAG, database, or enterprise-architecture mapping adapters.

## Domain

- `SystemReference`, `SystemCapability`, `SquadReference`, and
  `ArchitectureDependency` describe neutral architecture knowledge.
- `ArchitectureImpact` records the catalogue version, aware mapping timestamp, systems,
  dependencies, and the derived cross-system state.
- Feature and Story edits/replacements clear their own mapping. Upstream staleness
  preserves prior impact for audit.

## Application Use Cases

- `MapFeatureArchitecture`
- `MapStoryArchitecture`
- `DetectCrossSystemFeature`
- `MapBreakdownArchitecture` orchestrates the selected whole-breakdown action.

Mapping requires a current human-confirmed analysis, current Epic, at least one
Feature, and no stale Feature or Story. All matches are computed before persistence.

## Ports

- `ArchitectureKnowledgePort` accepts item-local text plus human-declared systems and
  returns provider-neutral matches.

## Adapters

- `YamlArchitectureKnowledge` loads and validates the packaged source-derived catalogue
  at startup and owns every phrase-to-system rule.
- Human-declared systems absent from the catalogue are preserved as non-catalogued
  references.
- The initial catalogue deliberately has no squads because the source does not provide
  an authoritative roster.

## API

- `POST /requirements/{requirement_id}/architecture-mapping` maps or refreshes the whole
  current breakdown and returns its Feature/Story hierarchy.
- Feature and Story responses expose nullable `architecture` impact.
- Mapping prerequisites and stale content return centrally mapped HTTP 409 responses;
  a completed empty match returns 200.

## UI

- One Breakdown-level Map/Refresh architecture action.
- Feature and Story panels show systems, matched capabilities, squad or Unassigned,
  dependencies, catalogue version, and mapping time.
- Unmapped and mapped-with-no-results states are distinct.
- Features spanning more than one system show an informational cross-system warning.

## Business Rules

- Cross-system means more than one distinct mapped system.
- Assumptions and unresolved questions are never architecture facts.
- Mapping does not change review status or generation provenance.
- Architecture warnings remain informational in this slice.

## Tests

- Domain invariants, cross-system threshold, and mapping lifecycle.
- Application query construction, batch mapping, prerequisites, and state preservation.
- YAML matches and malformed catalogue cases.
- Snapshot backward compatibility, in-memory revision capture, and opt-in PostgreSQL
  round trips.
- API contract/error behavior, UI states, and responsive browser flow.

## Acceptance Criteria

- [x] Reviewers can explicitly map and refresh the current breakdown.
- [x] Features and Stories retain reviewable system, capability, ownership, and
  dependency impact.
- [x] Cross-system Features are visibly warned.
- [x] Unknown declared systems and missing squads remain explicit.
- [x] Mapping survives persistence and appears in revision snapshots.
- [x] The domain contains no keyword-to-system rules or provider dependencies.

## Validation Evidence

- `.venv\Scripts\python.exe -m pytest` — PASS: 412 passed, 5 skipped in 7.17s.
  The skipped tests are the opt-in PostgreSQL suite; `TEST_DATABASE_URL` was not
  configured locally.
- `.venv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv\Scripts\ruff.exe format --check .` — PASS: 250 files already formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 206 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 156 files and 676 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run api:check` — PASS: committed OpenAPI TypeScript output has no drift.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS: 15 files, 70 tests in 8.31s.
- `npm.cmd run build` — PASS: 1,911 modules transformed; built in 626ms.
- `$env:SMOKE_API_PORT='8017'; $env:SMOKE_UI_PORT='4187'; npm.cmd run test:smoke`
  — PASS: 4 tests across desktop and responsive Chromium in 13.7s. Alternate
  ports isolated the run from an unrelated process already listening on port 8000.
- CI — NOT RUN for the working-tree changes. The branch matches
  `origin/refactor/ui-journeys` at `6b629db`; the preserved pre-existing Slice 6
  changes remain staged and unpushed. The GitHub CLI is unavailable and the
  unauthenticated GitHub API returns 404 for this repository.

## Deferred

- Authoritative squad ownership data and catalogue editing — Slice 14.
- Unified architecture flags, resolution, and decisions — Slice 8.
