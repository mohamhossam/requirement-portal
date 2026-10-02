# Enhancement — Reviewable spreadsheet merged ranges

## Objective

Continue the approved format-quality ledger after ADR-0057. Make XLSX merge boundaries visible
without spreading anchor text across independently excludable rows. ADR-0058 records this bounded
checkpoint. Implemented and locally validated; the overall document-knowledge enhancement remains
in progress, with inherited repository failures and CI still open.

## User Outcome

An owner uploads XLSX, compares merge annotations with the original, excludes private anchor/header
and hidden-sheet rows, then builds/activates searchable evidence with exact row citations.
Requirement attachments expose the same annotations through their existing structured evidence path.

## In Scope

- Row-local anchor/range/continuation annotations and explicit empty merged anchors.
- Merge extents beyond populated rows; no copied anchor wording or inferred header meanings.
- Explicit invalid/overlapping/oversized merge failures and cumulative traversal limits.
- Existing library and attachment API/UI exposure, publication governance and immutable history.
- Extraction, application, API, PostgreSQL restart and desktop/mobile browser regressions.
- Responsive attachment outline, warning and metadata layout using the existing breakpoint tiers.

## Out of Scope

Other format/layout quality, visual previews, scoped blocking-warning exclusions, async attachment
migration, actual model tokenizer qualification, dedicated Requirement indexing, unified retrieval/
generalized lineage, reference-backed suggestions, OCR, rollout/rollback, evaluation/load/restore/
telemetry remain in the parent ledger. No approved scope is dropped.

## Domain

Reuse WORKSHEET_RANGE blocks, extraction warnings, revisions, reviewed exclusions and approvals.

## Application Use Cases

Existing ingestion/review/build/activation/search and attachment upload consume the new extraction
version. Selected rows alone feed exact citations and approved surrounding context.

## Ports

Reuse DocumentExtractorPort, metadata/blob/index repositories and transactions.

## Adapters

SafeDocumentTextExtractor reads validated merge metadata with the existing XML/openpyxl path.
Adapter-internal range/row structures carry no domain behavior. Existing formula and hidden-sheet
rules are preserved. No new runtime dependencies, environment settings or migrations.

## API

Existing library ingestion/status/review/preview/build/search returns annotated rows and merge
warnings. Malformed XLSX has visible failed ingestion and no publication. Requirement attachment
upload returns the same extraction version and row annotations without a contract change.

## UI

Reuse library row review/exclusion, warnings, table-aware preview, build/activation and exact
citation navigation at desktop and 390px. Reuse attachment structured outline with a narrow CSS
fix: one column below the existing md tier, stacked warnings, wrapping evidence identifiers and
single-column metadata below sm. Browser tests verify excluded anchor/hidden-sheet text never
reaches public projection, retrieval context or citation view, and attachment review fits widths
360, 390, 740, 900 and 1440px. No new component or API schema is required.

## Business Rules

Only an anchor's own row contains its wording. Continuations identify coordinates only. Never
execute formulas, follow external workbook links or silently choose between overlapping ranges.
Current hidden-sheet authorization/selection remains unchanged. Stored publications are immutable;
a new upload/review is required to adopt merge extraction, not a rebuild of old text.

## Tests

Horizontal/vertical/rectangular merges, empty anchors and trailing continuation rows, Arabic/English
multiline content, inert formulas, malformed/overlapping/duplicate ranges, conflicting continuation
values, dimension/aggregate budgets, excluded rows/sheets, exact offsets, durable restart, attachment
API compatibility and real browser publication/navigation.

## Acceptance Criteria

- [x] Merge boundaries/continuations are visible without copied anchor wording.
- [x] Invalid metadata and resource limits fail explicitly.
- [x] Existing library/attachment APIs and review UI expose the change end to end.
- [x] PostgreSQL, five mandatory backend gates and relevant frontend/browser evidence recorded.
- [ ] Repository gates and CI green.

## Validation Evidence

Executed on Windows, 2026-09-22. Runtime:
`C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe`, with
`PYTHONPATH=C:/Users/moham/.codex/worktrees/92ae/smb-ai-requirement-agent/src`.
External runtime/worktree writes required sandbox escalation. All prior changes were preserved.

Before the full run, a read-only connection asserted `current_database()` equals disposable
`codex_document_knowledge_test_20260921`. TEST_DATABASE_URL used host localhost, hostaddr 127.0.0.1,
port 5432 and only that database; the application database was not used. No database tests skipped.

```text
python -m pytest tests/unit/test_spreadsheet_merges.py tests/unit/test_document_domain_and_extraction.py tests/unit/test_document_library.py tests/unit/test_library_api.py tests/unit/test_documents_api.py --tb=short
Initial: 1 failed, 79 passed, 1 warning in 15.97s
Final: 80 passed, 1 warning in 15.58s

TEST_DATABASE_URL=<verified disposable database> python -m pytest --tb=short
1292 passed, 1 warning in 98.67s (0:01:38)

python -m pytest tests/unit/test_spreadsheet_merges.py --tb=short
20 passed, 1 warning in 0.14s (after lint-only corrections)

python -m ruff check . --output-format concise
FAIL, exit 1 — Found 72 errors (inherited skill scripts)
python -m ruff format --check .
FAIL, exit 1 — 3 files would be reformatted, 805 files already formatted
python -m ruff check src tests scripts/evaluate_document_knowledge.py
PASS, exit 0 — All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
PASS, exit 0 — 387 files already formatted
python -m mypy src tests
PASS, exit 0 — Success: no issues found in 386 source files
lint-imports
PASS, exit 0 — Contracts: 6 kept, 0 broken

npm --prefix frontend run api:check
PASS — generated types match the OpenAPI snapshot
npm --prefix frontend run lint
PASS (also rerun after the final browser-test correction)
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
Test Files 39 passed (39); Tests 267 passed (267); Duration 8.50s
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8177 SMOKE_UI_PORT=4277 SMOKE_PYTHON=<external runtime>
npm --prefix frontend run test:smoke -- library-spreadsheet-merges.spec.ts library-delimited.spec.ts library-word-tables.spec.ts
8 passed, 2 failed (1.2m)
All library flows passed at 1440px/390px. Both attachment cases reached the merge preview
but the new test incorrectly expected the server-controlled checkbox to change immediately.
Changed the test to click and await the saved checked state, then verify it after reload.

git diff --check
PASS — existing CRLF conversion warnings only
```

The initial extraction failure proved the read-only parser omits empty tail rows; traversal now
covers the bounded merge extent. Initial new lint findings (three long lines and a missing zip
strict argument) were fixed. A first static-gate output wrapper hit Windows cp1252 decoding on
Ruff's diagnostic output; all static gates were rerun with explicit UTF-8 capture as recorded above.
Repository-wide failures remain in `.claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py`;
no exclusion was added to hide them. No CI run or commit/push was performed.

The library browser cases use real multipart upload/bounded extraction, saved exclusions,
preview/build/activation, public API projection, search and exact citation navigation. Desktop and
390px spreadsheet merge-preview screenshots were opened and inspected. Attachment cases cover
real upload, merge warnings/outline and persisted hidden-sheet opt-in. The final focused rerun passed:

```text
SMOKE_API_PORT=8179 SMOKE_UI_PORT=4279 SMOKE_PYTHON=<external runtime>
npm --prefix frontend run test:smoke -- library-spreadsheet-merges.spec.ts --grep "attachments expose"
2 passed (12.9s)
```

All ten distinct targeted browser cases therefore passed across the original run and corrected
attachment rerun; no claim is made that the initial ten-case command was green. Visual inspection
of the first mobile attachment screenshot then exposed horizontal overflow (611px content at a
390px viewport). The existing two-column outline, warning grid and evidence intrinsic widths were
corrected with existing breakpoint tiers. The final spreadsheet rerun after this CSS fix is green:

```text
npm --prefix frontend run lint
PASS, exit 0
npm --prefix frontend run typecheck
PASS, exit 0
npm --prefix frontend test -- --run
Test Files 39 passed (39); Tests 267 passed (267); Duration 8.54s
npm --prefix frontend run build
PASS, exit 0 - 1999 modules transformed

SMOKE_API_PORT=8183 SMOKE_UI_PORT=4283 SMOKE_PYTHON=<external runtime>
npm --prefix frontend run test:smoke -- library-spreadsheet-merges.spec.ts
4 passed (28.5s)

impeccable.cmd detect --json frontend/src/styles/06-source-documents.css
Exit 0 - three warnings for existing colored left borders, none introduced by this change
```

Final desktop/mobile attachment screenshots were opened and inspected; browser assertions verify
no horizontal overflow at 360, 390, 740, 900 and 1440px. Impeccable context/adapt/craft-floor guidance
was used for this bounded responsive correction. Existing colors and typography were preserved;
legacy design-context drift and the three detector warnings were not expanded into a redesign.
Earlier mobile source-panel positioning failures were not rerun or claimed resolved. No production
workbook corpus, live tokenizer/OCR/scanner, human retrieval evaluation, load, restore, or model
rollout qualification was performed.

## Changed Files in This Checkpoint

- `src/smb_requirement_agent/infrastructure/documents/text_extractor.py`.
- `tests/spreadsheet_fixtures.py`, `tests/unit/test_spreadsheet_merges.py`,
  `tests/unit/test_document_library.py`, `tests/unit/test_library_api.py`,
  `tests/unit/test_documents_api.py`, `tests/integration/test_library_postgres.py`.
- `frontend/tests/library-spreadsheet-merges.spec.ts`, `frontend/src/styles/06-source-documents.css`.
- This specification, parent ledger, ADR-0058/index, ROADMAP.md, WORKSPACE.md and operations runbook.

## Deferred / Open

The parent enhancement remains incomplete. gemini-embedding-001 tokenizer remains unqualified;
conservative UTF-8 budget units are not measured model tokens. Old XLSX revisions retain their prior
representation. Representative workbook/OCR/retrieval quality, model rollout and operations remain
open. Inherited Ruff/format errors, earlier mobile source-panel positioning and CI are not resolved
by this checkpoint. All prior uncommitted work is preserved; nothing committed or pushed.
