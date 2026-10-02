# Enhancement — Exclusion-safe Word table evidence

## Objective

Continue the approved document-knowledge extraction-quality work after ADR-0055. Fix DOCX
table extraction that duplicates the first row as inferred headers and copies merged anchors
into later rows. Implemented and locally validated under ADR-0056; the parent enhancement,
repository-wide gate failures and CI remain open.

## User Outcome

An owner reviews Word table rows with explicit grid positions, excludes a header/merged anchor
or nested table, and publishes only the selected wording using the existing library workflow.

## In Scope

- Row/grid coordinates, spans, skipped positions, merge annotations and paragraph breaks.
- Independently reviewable nested tables with bounded traversal and separate context parents.
- Neutral table/image labels, no copied row content or invented header semantics.
- Existing ingestion, review, preview/build/activation/search API/UI and persistence contracts.
- Adapter, exclusion/citation, malformed-input, PostgreSQL and browser validation.

## Out of Scope

Other formats, OCR, actual tokenizer qualification, unified Requirement retrieval, model rollout,
and human/load/restore qualification remain in the parent ledger. No parent scope is dropped.

## Domain

Reuse TABLE_ROW evidence, immutable extraction revisions, reviewed exclusions and approvals.

## Application Use Cases

Existing document ingestion/review and corpus preview/build/activation consume the improved rows.
Selected rows alone supply citation text and same-table context.

## Ports

Reuse DocumentExtractorPort, persistence, index and transaction boundaries.

## Adapters

Version new DOCX extractions independently. Preserve stored evidence and other format versions.
Validate external table metadata and bound cells/grid positions/nesting before returning blocks.

## API

Reuse ingestion/status/review/preview/build/search endpoints. Warnings and exact row locations
flow through existing schemas. Invalid metadata uses the existing explicit extraction error.

## UI

Reuse row review/exclusion controls, extraction warnings, chunk preview and activation. New browser
coverage must show excluded headers/anchors/nested rows absent from public search and citations.
No new page or component is needed for this checkpoint.

## Business Rules

- Coordinates and bracketed markers describe extraction structure, not business meaning.
- No cell's wording is copied into another row or into a table/image label.
- Nested tables have independent blocks and parents; excluding them removes their wording.
- Paragraph/run text and original table order are preserved in the extracted representation.
- Previously stored extraction and publication history is not rewritten.

## Tests

Mixed English/Arabic, two/three-column rows without inferred headers, empty/merged/omitted cells,
nested tables, malformed spans/flags, bounded traversal, durable exclusions and exact citations.

## Acceptance Criteria

- [x] Owners can review and publish Word rows without copied excluded content.
- [x] Grid and nested structure is explicit and safely bounded.
- [x] API/browser and PostgreSQL evidence is recorded.
- [x] All five backend gates and relevant frontend checks are recorded.
- [ ] Repository gates and CI are green.

## Validation Evidence

Executed on Windows, 2026-09-21, using
`C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe` with
`PYTHONPATH=C:/Users/moham/.codex/worktrees/92ae/smb-ai-requirement-agent/src`.
The external runtime required approved sandbox escalation, as in the preceding checkpoint.
PostgreSQL tests used only disposable `codex_document_knowledge_test_20260921` on localhost;
the application database was not used. Prior evidence is in enhancement-presentation-tables.md.

```text
python -m pytest tests/unit/test_word_tables.py tests/unit/test_document_domain_and_extraction.py tests/unit/test_presentation_tables.py
42 passed, 1 warning in 0.37s

python -m pytest tests/unit/test_word_tables.py tests/unit/test_document_library.py tests/unit/test_library_api.py tests/integration/test_library_postgres.py --tb=short
44 passed, 1 warning in 11.16s

python -m pytest --tb=short
1247 passed, 1 warning in 222.63s (0:03:42)

python -m pytest tests/unit/test_word_tables.py tests/unit/test_document_domain_and_extraction.py --tb=short
31 passed, 1 warning in 0.39s (after the two lint-only corrections)

python -m ruff check src tests scripts/evaluate_document_knowledge.py
All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
383 files already formatted (final run after line-ending normalization)
python -m mypy src tests
Success: no issues found in 382 source files
lint-imports
Contracts: 6 kept, 0 broken

npm --prefix frontend run api:check
PASS — existing API types match the OpenAPI snapshot
npm --prefix frontend run lint
PASS (also rerun after attachment test selector changes)
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
Test Files 39 passed (39); Tests 267 passed (267); Duration 11.54s
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8163 SMOKE_UI_PORT=4263 SMOKE_PYTHON=<existing runtime>
npm --prefix frontend run test:smoke -- library-word-tables.spec.ts library-presentation.spec.ts review-flow.spec.ts --grep 'Word row|slide table|Author uploads'
4 passed, 2 failed (1.1m)
Word and PowerPoint library flows passed at 1440px and 390px. Both attachment cases
expected the replaced "Channel: BCRM" representation; actual text was
"R2C1: Channel | R2C2: BCRM".

SMOKE_API_PORT=8165 SMOKE_UI_PORT=4265 SMOKE_PYTHON=<existing runtime>
npm --prefix frontend run test:smoke -- review-flow.spec.ts --grep 'Author uploads'
2 passed (25.6s), after updating the exact extraction expectation and stale source-panel
selectors to the existing "Where this came from" / "Open this passage" labels.

git diff --check
PASS — only Git CRLF conversion warnings
```

Both Word preview screenshots were opened and inspected. The browser exercises real multipart
upload and bounded extraction, owner exclusions, saved review, table preview/build/activation,
public projection and citation navigation. The attachment regression also verifies analysis source
navigation and immutable replacement. No React component, styling or API schema was changed.
The prior source-panel mobile positioning failures were not rerun or claimed resolved.

All five backend gates were executed. Final repository-wide failures remain:

```text
python -m ruff check . --output-format concise
Found 72 errors. Repository Ruff exit: 1
python -m ruff format --check .
3 files would be reformatted, 797 files already formatted. Repository format exit: 1
```

These are the inherited `.claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py`
failures. Initial new-code lint findings (one long string and a bytes literal) and mixed line endings
were corrected; final product checks above pass. No exclusion hides the inherited failures.
CI was not triggered or verified. No live OCR/tokenizer/scanner, representative production Word
document, human benchmark, load measurement or restore qualification was performed.

## Changed Files in This Checkpoint

- `src/smb_requirement_agent/infrastructure/documents/text_extractor.py`.
- `tests/word_table_fixtures.py`, `tests/unit/test_word_tables.py`,
  `tests/unit/test_document_domain_and_extraction.py`, `tests/unit/test_document_library.py`,
  `tests/unit/test_library_api.py`, `tests/integration/test_library_postgres.py`.
- `frontend/tests/library-word-tables.spec.ts`, `frontend/tests/review-flow.spec.ts`.
- This specification, parent enhancement ledger, ADR-0056 and architecture index,
  `docs/operations/document-knowledge.md`, `ROADMAP.md`, `WORKSPACE.md`, `AGENTS.md` debt register.

The existing extractor port, JSON persistence and publication workflow are reused. No new adapter
selection, runtime dependency, environment setting or migration is added. Earlier uncommitted work
is preserved.

## Deferred / Open

The parent delivery ledger remains authoritative. No live provider/OCR/tokenizer quality or
representative production-document benchmark is claimed by synthetic fixtures.
Legacy DOCX revisions can retain previously copied wording. Owners must inspect affected
publications and upload/review a new version to apply this fix; rebuilding old text is insufficient.
That cleanup is recorded in the debt register and runbook rather than rewriting approved history.
