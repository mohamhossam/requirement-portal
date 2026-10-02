# Enhancement — Independently reviewed CSV/TSV records

## Objective

Continue the approved extraction-quality ledger after ADR-0056 with the smallest usable fix:
stop consuming/copying the first CSV/TSV record as inferred headers. ADR-0057 records the decision.
Implemented and locally validated; the overall document-knowledge enhancement remains in progress.
Inherited repository gates and unverified CI prevent a green overall completion claim.

## User Outcome

An owner uploads CSV/TSV, reviews every nonblank record including the first, excludes private
header/appendix wording, and publishes/searches only selected records with exact citations.

## In Scope

- Positional row/field text, independent first-record review and neutral context labels.
- Quoting, multiline fields, Unicode/BOM, empty cells, inert formula-like text and bounded parsing.
- Existing upload/review/preview/build/activation/search API and browser exposure.
- Adapter, application, failure API, PostgreSQL persistence and desktop/mobile browser coverage.

## Out of Scope

Other format quality, actual embedding tokenizer qualification, dedicated Requirement indexing,
unified retrieval/generalized lineage, reference-backed suggestions, OCR qualification, model
rollout/rollback and operational evaluation/load/restore/telemetry remain in the parent ledger.
No approved scope is dropped.

## Domain

Reuse TABLE_ROW evidence, reviewed exclusions, immutable revisions and content-bound approvals.

## Application Use Cases

Existing ingestion/review and table-aware preview/build/activation/search consume independent
records; exact citations and approved-only context retain existing trust boundaries.

## Ports

Reuse DocumentExtractorPort, library/index/persistence and transaction ports.

## Adapters

SafeDocumentTextExtractor versions CSV/TSV output independently. Validate rectangular records
and resource limits; keep formulas inert and quoted field content intact. No new dependencies.

## API

Existing async ingestion exposes explicit malformed-input failure; review/status/preview/build/
search schemas expose first-record blocks, positions and warnings without a contract change.

## UI

Existing Library upload, row review/exclusion, warning, preview, build, activation and citation
controls expose the full path at desktop and 390px. No React component or styling change needed.

## Business Rules

No first-record wording is copied into another row or metadata. Row numbers count logical records,
including skipped blank records; quoted line breaks do not increment record numbers. No headers
are inferred. Existing publications remain immutable and need new upload/review to adopt the fix.

## Tests

CSV and TSV bilingual/quoted records, literal delimiters/line breaks, empty cells, missing headers,
malformed/oversized input, first/blank-record limits, exact excerpts/budgets, private exclusions,
PostgreSQL ready-build restart/activation, API failures and real browser publication/navigation.

## Acceptance Criteria

- [x] First records are independently reviewable; exclusions never survive in shared metadata/context.
- [x] Parser failure and resource limits are explicit and covered.
- [x] API, PostgreSQL and desktop/narrow browser evidence recorded.
- [x] Five backend gates and relevant frontend checks recorded.
- [ ] Repository-wide gates and CI green.

## Validation Evidence

Executed on Windows, 2026-09-22, with
`C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe` and
`PYTHONPATH=C:/Users/moham/.codex/worktrees/92ae/smb-ai-requirement-agent/src`.
External runtime/worktree writes required sandbox escalation. Earlier uncommitted work was retained.

```text
python -m pytest tests/unit/test_delimited_rows.py tests/unit/test_document_library.py tests/unit/test_library_api.py --tb=short
46 passed, 1 warning in 8.32s

python -m ruff check . --output-format concise
FAIL — Found 72 errors (the inherited .claude/skills/ui-ux-pro-max/scripts files)
python -m ruff format --check .
FAIL — 3 files would be reformatted, 801 files already formatted

python -m ruff check src tests scripts/evaluate_document_knowledge.py
All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
385 files already formatted
python -m mypy src tests
Success: no issues found in 384 source files
lint-imports
Contracts: 6 kept, 0 broken

npm --prefix frontend run api:check
PASS — generated types match the OpenAPI snapshot
npm --prefix frontend run lint
PASS (also rerun after browser-test indentation cleanup)
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
Test Files 39 passed (39); Tests 267 passed (267); Duration 9.59s
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8173 SMOKE_UI_PORT=4273 SMOKE_PYTHON=<external runtime>
npm --prefix frontend run test:smoke -- library-delimited.spec.ts library-word-tables.spec.ts library-presentation.spec.ts
8 passed (59.4s)

git diff --check
PASS — only existing CRLF conversion warnings
```

The eight browser cases cover CSV, TSV, Word and PowerPoint at 1440px and 390px. New cases use
real multipart upload/bounded extraction, first-record and appendix exclusions, saved review,
preview/build/activation, shared API projection, search and exact citation navigation. Desktop CSV
and mobile TSV preview screenshots were opened and inspected. No UI component/style/schema changed.

Database startup initially failed because Docker Desktop was stopped; it was started in the
background. A read-only connection then verified `codex_document_knowledge_test_20260921` before
pytest. The first full run was stopped because each localhost connection waited 5.03 seconds for
IPv6 fallback. Explicit `hostaddr=127.0.0.1` reduced the measured connection to 0.03 seconds; the
rerun retains `host=localhost`, port 5432 and the same designated disposable database. No test was
pointed at the application database. The completed full-suite result is:

```text
TEST_DATABASE_URL=<verified disposable database, IPv4 loopback> python -m pytest --tb=short
1269 passed, 1 warning in 96.26s (0:01:36)
```

This includes both new CSV/TSV PostgreSQL ready-build restart/activation cases; no database tests
were skipped. The stopped IPv6-fallback attempt is not counted as validation.

The repository-wide failures are the unchanged `.claude/skills/ui-ux-pro-max/scripts/`
`core.py`, `design_system.py` and `search.py`; no exclusions were introduced. CI was not triggered
or verified. Earlier source-panel mobile positioning failures were not rerun or claimed resolved.
No live tokenizer/OCR/scanner, representative production-format corpus, human evaluation, load,
restore or model-rollout qualification was performed.

## Changed Files in This Checkpoint

- `src/smb_requirement_agent/infrastructure/documents/text_extractor.py`.
- `tests/delimited_fixtures.py`, `tests/unit/test_delimited_rows.py`,
  `tests/unit/test_document_library.py`, `tests/unit/test_library_api.py`,
  `tests/integration/test_library_postgres.py`.
- `frontend/tests/library-delimited.spec.ts`.
- This specification, parent ledger, ADR-0057/index, operations runbook, ROADMAP.md,
  WORKSPACE.md and AGENTS.md legacy-publication debt register.

## Deferred / Open

All parent-ledger outstanding work remains approved and open. gemini-embedding-001 tokenizer is
unqualified; conservative UTF-8 budget units are not measured model tokens. Existing legacy
CSV/TSV publications may retain copied first-record text and require owner inspection/new upload.
Inherited repository Ruff/format failures, earlier mobile source-panel positioning and CI remain
open unless the validation evidence explicitly establishes otherwise. Nothing committed or pushed.
