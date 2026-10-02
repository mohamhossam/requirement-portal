# Slice 11 — Neutral Export

> Status: **complete locally; CI pending push**.

## Objective

Export one exact, formally approved immutable backlog revision as a portable JSON
package or readable Excel workbook without invoking AI or Azure DevOps.

## User Outcome

The current Requirement Owner or an assigned reviewer can select an approved
historical revision in the browser and download its complete delivery hierarchy.

## Roadmap Scope Check

| Roadmap field | Delivery |
|---|---|
| Application | `ExportBreakdown` selects and validates one immutable revision. |
| Port | `BacklogExportPort` renders an application-owned `1.0` neutral contract. |
| Adapters | Deterministic JSON and formula-safe, lossless XLSX adapters. |
| API | Authenticated revision-specific download with format, media type, filename, and cache controls. |
| UI | Revision history exposes eligibility, final approval, format selection, and download. |
| Tests | Eligibility, authorization, schema/hierarchy/criteria, adapters, API, UI, PostgreSQL restart, and browser download. |

Nothing in the Slice 11 roadmap entry is dropped.

## In Scope

- Exact historical revision selection and current team authorization.
- Formal final-approval and complete-tree eligibility.
- Approval manifest, Epic/Feature/Story content, provenance, architecture tags,
  and structured Given/When/Then criteria.
- JSON plus `Manifest`, `Epic`, `Features`, `Stories`, `Acceptance Criteria`,
  `Systems`, and `Dependencies` XLSX sheets.
- Explicit refusal when XLSX cannot represent a value without truncation.

## Out of Scope

- CSV, analysis/source documents, full governance history, stored exports,
  download audit events, background jobs, ADO mapping/publication, and external IDs.

## Domain

No domain changes. Existing immutable revisions, access membership, and
content-bound approvals remain authoritative.

## Application Use Cases

- `ExportBreakdown(requirement_id, revision_number, format, actor)` verifies the
  Requirement, current membership, exact revision, formal approval, and complete
  tree before building the neutral package.
- A historical approved revision remains eligible after later content changes.

## Ports

- `BacklogExportPort` exposes format, extension, media type, and rendering.

## Adapters

- JSON uses stable field/order conventions, UTF-8, UTC RFC 3339 values, and a
  final newline.
- XLSX preserves relational IDs/sequences, writes no formulas, and never truncates.
- `openpyxl` is a runtime dependency; no setting, migration, or repository is added.

## API

- `GET /requirements/{id}/revisions/{number}/export?format=json|xlsx`
- Responses are attachments with a safe deterministic filename and
  `Cache-Control: private, no-store`.
- Missing Requirement/revision returns 404, non-member returns 403,
  non-exportable revision returns 409, and invalid/unsupported XLSX input returns 422.
- Revision summaries expose eligibility and final approver/time; access responses
  expose the server-derived export capability.

## UI

- The existing Revision History view labels formal approvals and ineligible
  revisions, offers JSON/XLSX selection, and downloads with current auth headers.
- Non-members see the restriction instead of an enabled action; API enforcement
  remains authoritative.
- Download failures remain visible and temporary object URLs are revoked.

## Business Rules

- An artifact status or legacy approved label is not a formal export approval.
- Export reads only the selected immutable snapshot and never regenerates content.
- Current membership controls who may download; the selected revision controls
  what is eligible and exported.
- The `1.0` schema excludes internal review discussion and provider-specific fields.

## Tests

- Application/API lifecycle, authorization, historical-selection, errors, headers,
  stable JSON, hierarchy, acceptance criteria, provenance, and architecture.
- XLSX sheets, relationships, exact text, formula safety, and size/control limits.
- Component/client download behavior and desktop/responsive browser downloads.
- PostgreSQL restart export when `TEST_DATABASE_URL` is configured.

## Acceptance Criteria

- [x] A team member can download any formally approved immutable revision.
- [x] JSON and XLSX preserve Epic → Feature → Story and Given/When/Then structure.
- [x] Manifest data identifies the revision and exact actor-attributed final approval.
- [x] Provenance and architecture tags survive both adapters.
- [x] Ineligible revisions and unauthorized actors fail explicitly.
- [x] Export causes no persistence write, AI call, or ADO operation.
- [x] Browser download works at desktop and responsive viewports.

## Architecture Impact

ADR-0023 records the application-owned neutral contract, outbound renderer port,
two infrastructure adapters, historical approval rule, and current-access policy.
Dependency direction and the single composition root remain unchanged.

## Validation Evidence

- `TEST_DATABASE_URL=postgresql://... pytest` — PASS: 532 tests, including
  PostgreSQL historical-revision export after store reconstruction.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS: 335 files formatted.
- `mypy src tests` — PASS: 277 source files.
- `lint-imports` — PASS: 2 contracts kept, 0 broken.
- `npm run api:check` — PASS.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run test` — PASS: 22 files, 91 tests.
- `npm run build` — PASS; production Vite bundle created.
- `SMOKE_API_PORT=8011 SMOKE_UI_PORT=4184 npm run test:smoke` — PASS: 12 tests,
  including JSON structure and XLSX signature downloads at both viewports.
- CI — pending push; local success is not CI authority.

## Deferred

- CSV, export persistence/audit, background exports, complete audit archives,
  ADO publication/external mappings, and architecture catalogue management remain
  in later or explicitly unscheduled scope.
