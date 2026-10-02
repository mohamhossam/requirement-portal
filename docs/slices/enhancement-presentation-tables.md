# Enhancement — Reviewable PowerPoint table rows

## Objective

Deliver a bounded extraction-quality checkpoint of the approved document-knowledge enhancement.
Implemented and locally validated; repository-wide lint/format failures and CI remain open.
PowerPoint tables previously flattened into slide paragraphs, preventing table-aware children.
This checkpoint fixes that path without changing stored extractions or publications (ADR-0055).

## User Outcome

An owner reviews individual slide/table rows with explicit cell positions, excludes private rows,
and previews/builds exact table-aware search children through the existing library workflow.

## In Scope

- PPTX table/row/cell positions, empty cells, text runs/line breaks, and explicit merge annotations.
- Slide/table/notes separation, no duplicated flattened table text or inferred business headers.
- Safe malformed-table failure and bounded cell traversal.
- Extraction, application/API, persistence and desktop/narrow browser regression evidence.

## Out of Scope

Other format extraction refinements, OCR, model-tokenizer qualification, unified retrieval,
model rollout, quality/load/restore qualification and CI remain in the parent enhancement ledger.
No parent scope is dropped. The checked-in embedding model is gemini-embedding-001; no verified
matching tokenizer has been established, so a different model's counter is not substituted.

## Domain

Reuse immutable evidence blocks, TABLE_ROW, saved reviews, exclusions and publication approvals.
No new domain types or changes to previously stored evidence.

## Application Use Cases

Existing ingestion, review, table-aware preview/build and owner activation consume structured rows.
Separate table parents prevent context from pulling a different table or speaker notes.

## Ports

Reuse DocumentExtractorPort and its typed result; no new dependency boundary.

## Adapters

SafeDocumentTextExtractor adds a PPTX-specific extraction version and ordered row rendering.
Existing memory/PostgreSQL JSON persistence and bounded child-process extraction remain in use.

## API

Existing ingestion/status/review/build/search contracts expose table rows and warnings unchanged.
Malformed input uses the existing explicit extraction failure, not a leaked parser exception.

## UI

Existing library renders each row as a reviewable/excludable passage, displays extraction warnings,
and previews TABLE_ROW children. No new component or visual design; browser tests verify this path.

## Business Rules

- Coordinates describe source layout, not inferred header semantics or policy applicability.
- Merged continuation markers never copy another cell's wording into a new row.
- Excluded row text must not survive in a duplicate slide paragraph or context label.
- New uploads use the new extraction version; historical extraction/citation bytes stay unchanged.
- The byte-budget counter remains explicitly unqualified as a model tokenizer.

## Tests

English/Arabic and mixed-direction rows, multiple slides/tables/notes, split runs, empty/merged cells,
malformed spans/widths, safety limits, owner exclusion, exact offsets, publication and search.

## Acceptance Criteria

- [x] Slide tables reach row-level review and table-aware build/search without duplicated text.
- [x] Cell locations and explicit merge uncertainty survive extraction and persistence.
- [x] Excluded rows do not appear in search or surrounding context.
- [x] Quality commands and desktop/narrow browser evidence are recorded.
- [ ] Repository gates and CI are all green.

## Validation Evidence

Executed on Windows, 2026-09-21, using the existing runtime
`C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe` and
`PYTHONPATH=C:/Users/moham/.codex/worktrees/92ae/smb-ai-requirement-agent/src`.
The sandbox denied that runtime; approved escalated commands used the same checkout.
Database tests used only disposable `codex_document_knowledge_test_20260921` on localhost,
never the application database. Prior evidence remains in enhancement-table-corpus-builds.md.

```text
python -m pytest tests/unit/test_presentation_tables.py tests/unit/test_document_domain_and_extraction.py
27 passed, 1 warning in 0.32s

python -m pytest tests/unit/test_presentation_tables.py tests/unit/test_document_library.py tests/integration/test_library_postgres.py
36 passed, 1 warning in 2.57s

python -m pytest --tb=short
1229 passed, 1 warning in 217.95s (0:03:37)

python -m ruff check src tests scripts/evaluate_document_knowledge.py
All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
381 files already formatted
python -m mypy src tests
Success: no issues found in 380 source files
lint-imports
Contracts: 6 kept, 0 broken

npm --prefix frontend run api:check
PASS — existing API types match the OpenAPI snapshot
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
Test Files 39 passed (39); Tests 267 passed (267); Duration 11.08s
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8161 SMOKE_UI_PORT=4261 SMOKE_PYTHON=<existing runtime>
npm --prefix frontend run test:smoke -- library-presentation.spec.ts
2 passed (25.0s) — 1440px desktop and 390px narrow view

git diff --check
PASS — only pre-existing CRLF conversion warnings
```

Both generated preview captures were opened and inspected. The browser test uses the same synthetic
OOXML fixture as the backend, through real multipart upload and isolated extraction, then exercises
row/notes exclusions, saved review, table preview/build/activation, public projection and citation
navigation. There were no UI component/style changes. Full browser-suite rerun was not claimed;
the prior source-dialog failures remain documented in the preceding checkpoint.

All five repository gates were attempted, including the failures:

```text
python -m ruff check . --output-format concise
Found 72 errors. Ruff exit: 1
python -m ruff format --check .
3 files would be reformatted, 792 files already formatted
```

Both failures are unchanged `.claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py`
issues. No exclusions or edits hide them. CI was not triggered/verified for this uncommitted tree.
No live model/scanner/OCR, representative customer deck, human quality benchmark or restore
qualification was performed.

## Changed Files in This Checkpoint

- `src/smb_requirement_agent/infrastructure/documents/text_extractor.py`.
- `tests/presentation_fixtures.py`, `tests/unit/test_presentation_tables.py`,
  `tests/unit/test_document_library.py`, `tests/integration/test_library_postgres.py`.
- `frontend/tests/library-presentation.spec.ts`; no frontend component or contract changes.
- This specification, parent enhancement ledger, ADR-0055 and architecture index,
  `docs/operations/document-knowledge.md`, `ROADMAP.md`, `WORKSPACE.md`.

All earlier uncommitted implementation is preserved. No new port, configuration, dependency or SQL
migration was necessary; the existing extraction boundary and owner-governed build path are reused.

## Deferred / Open

See enhancement-document-knowledge.md. No live tokenizer, OCR or human quality benchmark is claimed.
