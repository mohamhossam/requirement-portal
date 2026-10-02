# Enhancement — Source lineage and change-impact completion

## Objective

Complete the user's six remaining lineage, dependency, corroboration, impact review, persistent
index and browser-validation outcomes. This extends the approved reviewed-document enhancement,
not a later ADO publication slice. ADR-0066 records the structural decision.

## User Outcome

From a document or Requirement, inspect exact recorded source passages and follow direct citations
or indirect dependencies into answers, analyses, Epics, Features and Stories. After replacement or
withdrawal, the Requirement owner can record a reasoned impact decision while preserving prior
content, reviews and approvals.

## In Scope

All six requested outcomes; every Domain/Application/Ports/Adapters/API/UI/Tests field in the
active roadmap entry is addressed below. No requested field was omitted.

## Out of Scope

The parent enhancement's separate live model judgment, real scanner/OCR deployment, customer load
and production restore qualification. Existing unrecorded legacy origins cannot be inferred from
matching text. No external backlog publication or automatic approval.

## Domain

Immutable SourceLineage and attributed ImpactDecision values. Clarification answers, analyses,
reviewable generations and Requirement knowledge evidence retain recorded source lineage.

## Application Use Cases

Preserve origins on accepted proposals, suggestion submission, reanalysis and backlog derivation.
DependencyProjection updates only the changed Requirement at commit. SourceImpactReview provides
owner/member authorization, publication comparison, content-bound retain/revise and CAS. Generation
guards validate actual inputs; final review checks the whole active backlog. Retrieval excludes
copied document evidence from independent corroboration.

## Ports

SourceDependencyPort defines indexed replacement, retrieval, pagination and immutable decisions.
Existing reference validation and answer-suggestion boundaries retain typed evidence. No framework,
database or provider objects enter the domain/application layers.

## Adapters

In-memory transactional snapshots and PostgreSQL migration 024 implement the same contract.
Existing snapshot/knowledge codecs preserve lineage. Explicit projection maintenance backfills
recorded historical citations; startup readiness requires the new migration and completed backfill.

## API

- GET `/library/documents/{id}/source-impact`: document owner, Requirement access-filtered.
- GET `/library/requirements/{id}/source-impact`: Requirement member.
- POST `/library/source-impact/{dependency_id}/decisions`: Requirement owner, expected review
  version and displayed publication-state token, rationale, retain_historical or revise_content.
- Existing `/dependencies` compatibility view now reads the maintained index.
- Search, active-only selection, bounded offset/limit and next-page indicator; no private counts.
- Existing 403/404/409/422 error translations; regenerated OpenAPI/browser types.

## UI

Source impact appears in the Library governance and Requirement clarification views. It loads on
request, supports search, active/history filtering, refresh and pagination, distinguishes direct
citations from indirect inputs, exposes exact source identity/range and prior decisions, and offers
owner-only reasoned reconciliation. Successful review invalidates analysis and approval reads.
Shared controls and component-owned styles work on direct navigation and narrow screens.

## Business Rules

- Only recorded citations/input paths establish dependencies; equal wording alone never does.
- Pending/rejected proposal evidence remains inspectable; rejected/historical rows are not active.
- Copies from the same document do not provide independent corroboration.
- Retain is specific to content and displayed document/publication state. Revise does not silently
  clear a blocker or discard provenance. New generated content needs its own historical-source review.
- History and approvals remain immutable. Content replacement deactivates previous index rows.
- Document handover never grants access to unrelated private Requirement names or counts.

## Tests

Domain/application and API tests cover selected-answer origins, all backlog levels, codec round
trips, source deduplication, content-bound decisions, revision recovery, ownership, CAS and private
counts. PostgreSQL tests cover transactional rollback, two simultaneous owner decisions, restart,
nonempty index rebuild and access changes. Component tests cover owner/read-only controls and cache
refresh. Playwright covers publish → reuse answer → both dependency views → replace → reconcile →
withdraw → preserved history/renewed review, in memory and PostgreSQL, desktop and narrow viewports.

## Acceptance Criteria

- [x] Exact document version and passage survive recorded reuse and backlog derivation.
- [x] Requirement/analysis/Epic/Feature/Story dependencies distinguish direct and indirect origins.
- [x] Recorded document copies cannot amplify independent corroboration.
- [x] Publication changes support explicit owner review, preserving history and approvals.
- [x] Maintained transactional index supports access-filtered search and pagination.
- [x] Validation command evidence and authoritative hosted CI link recorded below.

## Validation Evidence

2026-09-23, Windows; isolated PostgreSQL 17/pgvector database, synthetic fake providers.
Executed final local commands (PowerShell; Python invoked through `.venv/Scripts/python.exe`):

```text
TEST_DATABASE_URL=<isolated PostgreSQL test database> python -m pytest -q
..............................                                           [100%]
exit 0; collection verified separately: 1398 tests (PostgreSQL tests enabled)

python -m ruff check .
All checks passed!
python -m ruff format --check .
855 files already formatted
python -m mypy src tests
Success: no issues found in 417 source files
lint-imports
Analyzed 359 files, 2611 dependencies.
Contracts: 6 kept, 0 broken.

npm run lint
eslint . (exit 0)
npm run typecheck
tsc -b --pretty false (exit 0)
npm run api:check
openapi-typescript 7.13.0 (exit 0)
npm run test
Test Files 41 passed (41)
Tests 277 passed (277)
npm run build
2004 modules transformed; built in 370ms (exit 0)

SMOKE_LINEAGE_POSTGRES=1 DATABASE_URL=<isolated test database> npm run test:smoke -- source-lineage.spec.ts
2 passed (41.7s)
```

Browser captures verified at 1440, 740 and 390 pixels. Impeccable detector returned `[]`;
independent UI finish reviewer returned `ship`, limited to screenshots/code (not computed contrast
or backend certification). Documenter recorded the surface extension and preserved design-system
files; existing design documentation drift was not repaired. The broader memory browser regression
run exposed obsolete pre-existing question/action selectors; the 24-test run had 20 passes and four stale-selector failures. The corrected scenarios were
rerun in both projects:

```text
npm run test:smoke -- review-flow.spec.ts --grep 'owner assigns|Product Owner completes'
4 passed (55.5s)
npm run lint; npm run typecheck
exit 0 (both)
```

These retain reviewer drafting/owner confirmation and the full Epic/Feature/Story/approval/staleness
journeys. Hosted CI runs the entire browser suite. PR #14 targets the existing `refactor-ux` base:
https://github.com/mohamhossam/smb-ai-requirement-agent/pull/14.
No production scanner or live provider qualification is claimed.

## Changed Files

Core: domain/document/lineage.py; domain analysis/knowledge/shared generation values;
application/ports/source_dependencies.py; use_cases/source_lineage.py, dependency_projection.py,
source_impact.py, analysis_collaboration.py, analysis_mapping.py, generation_context.py,
generate_epic.py, generate_features.py, story_workflow.py, requirement_knowledge.py,
unified_knowledge_search.py, breakdown_review.py and library_governance.py.
Persistence: source_dependencies.py, migrations/024_source_dependencies.sql, snapshot_mapper.py,
postgres_requirement_knowledge.py, in_memory_transaction.py, postgres_store.py.
Interfaces: container.py, dependencies.py, library routes and generated API contracts.
Browser: SourceImpactPanel.tsx/source-impact.css and tests, AnalysisView/AnalysisPanel,
LibraryGovernance, client.ts, Playwright configuration/source-lineage.spec.ts.
Validation/operations: source-lineage unit and PostgreSQL tests, tests/lineage_smoke.py, CI,
ADR-0066, roadmap/workspace/parent ledger/runbook and debt register.

## Deferred / Open

No implementation scope omitted from this request. The latest hosted result is authoritative and
available on [PR #14 checks](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/14/checks).
Unrecorded legacy origins remain explicitly unknown; maintenance must not manufacture evidence or
rewrite approval history. Parent release qualification remains separately tracked.

### Hosted toolchain correction

Initial frontend jobs failed during `npm ci` with `Exit handler never called!`, before application
checks. Aligning with local Node 24.20.0/npm 11.19.0 and enabling verbose logs revealed the actual
cause: an inherited private-registry override could not resolve on hosted runners. All 377 locked
package URLs use npmjs.org. CI now explicitly selects that registry for its processes; developer
registry configuration and dependency versions remain unchanged. No gate was skipped. Latest hosted
run remains authoritative.


### Full-suite corrections

The first complete browser run reported 68 passed, 13 failed and five intentionally skipped
responsive duplicates. It exposed a native dialog maximum-width cap, catalogue overflow with
long MIME types, a test leaving before asynchronous attachment completion, and publications from
previous tests competing in deduplicated search. Drawer/catalogue sizing is corrected; tests now
wait for the completed attachment and withdraw only publications created by their own fixture.
The original assertions and search deduplication remain intact. A subsequent navigation failure
occurred while the preview assets were rebuilt; the final run uses a stable build throughout.

The first hosted run after registry repair passed 1,398 PostgreSQL-enabled tests, frontend checks
and the PostgreSQL browser journey. Linux mypy exposed seven Windows-only attribute references.
Explicit platform guards preserve the Windows behavior while making Linux type checking valid.

```text
python -m pytest tests/unit/test_presentation_tables.py tests/unit/test_ingestion_format_safeguards.py tests/unit/test_document_domain_and_extraction.py -q
..................................                                       [100%]
exit 0 (34 tests)
python -m mypy --platform linux src tests
Success: no issues found in 417 source files
python -m ruff check .
All checks passed!
python -m ruff format --check .
858 files already formatted
python -m mypy src tests
Success: no issues found in 417 source files
lint-imports
Analyzed 359 files, 2612 dependencies. Contracts: 6 kept, 0 broken.
npm run test -- --run src/components/Modal.test.tsx
7 passed (7)
npm run test:smoke -- analysis-sources.spec.ts
2 passed (7.9s)
npm run lint
exit 0
npm run typecheck
exit 0 (rerun with workspace write access after Windows EPERM)
npm run build
2004 modules transformed; built in 364ms
```

The finish reviewer confirmed the drawer correction at desktop/mobile screenshots and code scope.
The following checkpoint records the complete corrected browser run and focused final correction.


### Final validation checkpoint

Hosted run [35803367061](https://github.com/mohamhossam/smb-ai-requirement-agent/actions/runs/35803367061)
on `a65f9fb` completed the backend quality, frontend and PostgreSQL browser jobs successfully:

```text
pytest
1398 passed, 1 warning in 127.57s (0:02:07)
ruff check .
All checks passed!
ruff format --check .
858 files already formatted
mypy src tests
Success: no issues found in 417 source files
lint-imports
Contracts: 6 kept, 0 broken.
PostgreSQL browser journey
2 passed (56.9s)
```

The complete local memory browser run then reported `80 passed, 1 failed, 5 skipped (9.3m)`.
The five skips are duplicate viewport suites: each already covers eleven widths in the desktop
project. Its one failure was the responsive unified-search assertion expiring while the response
was still pending, as recorded in the browser trace. The test now awaits that response and asserts
its HTTP success before checking the same published-document and Requirement evidence labels.

```text
npm run test:smoke -- search-grounding.spec.ts
2 passed (13.6s)
npm run lint
exit 0
npm run typecheck
exit 0
```

All requested browser paths have passing local evidence. The full hosted suite reruns against the
final commit; its current result and output are maintained on PR #14 checks. A local pass does not
substitute for that hosted gate. The PR completion report records the final run URL and outcome.

Independent finish review returned `ship` for source impact, the drawer fix and the catalogue
responsive correction. Full-page mobile and desktop catalogue evidence is committed; these visual
reviews do not certify contrast, model quality or production scanner operation. DESIGN.md and its
sidecar remain unchanged. The final regression changes also include Modal.tsx, catalogue CSS,
platform guards in process_resources.py/office_preview.py, and isolated browser publication fixtures.
