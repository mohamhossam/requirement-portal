# Enhancement — Exclusion-safe TXT/Markdown sections

## Objective

Continue the approved format-quality ledger after ADR-0058 with independent TXT/Markdown heading
review. ADR-0059 records this bounded checkpoint. Implemented and locally validated; the overall
enhancement remains in progress, with inherited repository failures and CI still open.

## User Outcome

An owner excludes or corrects a heading, publishes its selected descendant passages, and searches
or opens exact line citations without the original heading wording surviving in shared metadata.

## In Scope

- Neutral positional section paths and heading text confined to its own evidence block.
- Correct grouping of repeated headings, skipped levels and sibling/ancestor transitions.
- Existing library ingestion/review/preview/build/activation/search and attachment API exposure.
- Adapter, application, API/browser, immutable replacement and PostgreSQL restart coverage.

## Out of Scope

Other format quality, full Markdown parsing/rendering, visual previews, scoped warning exclusions,
async attachment migration, tokenizer qualification, dedicated Requirement indexing, unified
retrieval/generalized lineage, reference-backed suggestions, OCR, model rollout/rollback and
operational evaluation/load/restore/telemetry remain in the parent ledger. No scope is dropped.

## Domain

Reuse HEADING/PARAGRAPH blocks, extraction warnings, reviewed passages, revisions and approvals.

## Application Use Cases

Existing ingestion, saved review, corpus build/activation and exact search consume the new
extraction. Only selected corrected wording contributes to same-section retrieval context.

## Ports

Reuse DocumentExtractorPort, library/blob/index repositories and transaction boundaries.

## Adapters

SafeDocumentTextExtractor versions TXT/Markdown independently and uses source line positions in
section paths. A level-keyed path preserves real declared ancestry without copied heading text.
Existing UTF-8, NUL, blank-content and character-limit validation remains explicit.

## API

Existing library status/review/preview/search and public document projection expose neutral
paths and review warnings. Existing TXT attachment upload exposes the same extraction contract.
No new endpoint or schema is needed; browser tests also inspect public/search JSON.

## UI

Existing Library line review/exclusion, correction, warnings, saved preview, build/activation and
citation navigation provide the usable path at 1440px and 390px. Existing attachment evidence
consumers retain their contract. No React component or style changes are needed.

## Business Rules

- Original heading wording appears only in its own reviewable block.
- Excluded wording cannot survive in descendants' metadata or search context headers.
- Reviewed heading corrections, when included, can supply approved same-section context.
- Source line positions include blank lines; repeated titles do not merge sections.
- Hash-heading recognition remains a line-based navigation hint, not full Markdown semantics.
- Old extractions/publications remain immutable; new upload/review is required to adopt the change.

## Tests

BOM/CRLF/blank lines, Arabic/English, long and repeated headings, skipped levels, inert markup,
malformed/empty/oversized text, exclusion/correction isolation, exact citations, unchanged historical
versions, TXT attachment API, PostgreSQL ready-build restart and real desktop/mobile library flow.

## Acceptance Criteria

- [x] Heading wording remains independently reviewable without descendant metadata copies.
- [x] Repeated/skipped heading levels retain distinct positional context groups.
- [x] Existing API/UI exposes the checkpoint end to end.
- [x] PostgreSQL, five backend gates and relevant frontend/browser results recorded.
- [ ] Repository-wide gates and CI green.

## Validation Evidence

Executed on Windows, 2026-09-22, using
`C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe` and
`PYTHONPATH=C:/Users/moham/.codex/worktrees/92ae/smb-ai-requirement-agent/src`.
Worktree writes and external runtime execution required sandbox escalation.

```text
python -m pytest tests/unit/test_text_sections.py tests/unit/test_document_library.py tests/unit/test_documents_api.py --tb=short
58 passed, 1 warning in 16.85s

python -m ruff check . --output-format concise
FAIL, exit 1 — Found 72 errors (inherited skill scripts)
python -m ruff format --check .
FAIL, exit 1 — 3 files would be reformatted, 808 files already formatted
python -m ruff check src tests scripts/evaluate_document_knowledge.py
PASS, exit 0 — All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
PASS, exit 0 — 388 files already formatted
python -m mypy src tests
PASS, exit 0 — Success: no issues found in 387 source files
lint-imports
PASS, exit 0 — Contracts: 6 kept, 0 broken

npm --prefix frontend run api:check
PASS — generated types match the OpenAPI snapshot
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
Test Files 39 passed (39); Tests 267 passed (267); Duration 11.49s
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8185 SMOKE_UI_PORT=4285
SMOKE_PYTHON=C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe
npm --prefix frontend run test:smoke -- library-text-sections.spec.ts library-flow.spec.ts
8 passed (1.1m)

git diff --check
PASS — existing CRLF conversion warnings only
```

Four new browser cases cover TXT/Markdown at 1440px and 390px; four existing library cases cover
publication/withdrawal and exact passage navigation during replacement at their configured desktop
and narrow widths. The new cases use real multipart upload and bounded extraction, exclude heading
and appendix passages, save review, preview/build/activate, inspect public document/search JSON,
open exact citations, and assert no horizontal overflow. Desktop TXT and mobile Markdown preview
screenshots were opened and visually inspected. No React component, style or API schema changed.

The first static-gate output wrapper encountered Windows cp1252 encoding while printing Ruff's
format diagnostic. All static gates were rerun with explicit UTF-8 stdout/capture as recorded above.
Repository-wide errors remain in
`.claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py`; no exclusion hides them.

### Disposable database recovery and full suite

Initial connections to the designated database timed out because Docker was stopped. Docker
startup then failed on an inaccessible stale `sailor-ingest.sock` reparse point. A narrow socket
rename, removal and reparse inspection each failed without changing it. The crashed processes
started for these tests were stopped. The verified transient directory containing six zero-byte
socket entries was preserved at
`C:/Users/moham/AppData/Local/Docker/run.codex-20260922-backup`; Docker recreated its run directory
and the existing PostgreSQL container became healthy. No container, persistent volume or database
was deleted or reset.

Before pytest, a read-only connection asserted and printed:
`Verified current_database(): codex_document_knowledge_test_20260921`.
The suite receives that database only, with `host=localhost hostaddr=127.0.0.1 port=5432`.
No test used the application database.

```text
TEST_DATABASE_URL=<verified disposable database> python -m pytest --tb=short
1 failed, 1312 passed, 2 warnings in 221.85s (0:03:41)
```

The sole failure was the earlier PowerPoint regression test's expectation that TXT still uses
`structured-evidence-v2`. Updated that format-independence assertion to the intentional new
TXT version. Both new PostgreSQL cases passed. A Windows cp1252 reader warning in the architecture
test subprocess was addressed for the rerun by setting `PYTHONUTF8=1` alongside
`PYTHONIOENCODING=utf-8`; the independently executed architecture gate already passed.
Final rerun, after rechecking `current_database()`:

```text
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 TEST_DATABASE_URL=<verified disposable database>
python -m pytest --tb=short
1313 passed, 1 warning in 271.96s (0:04:31)

python -m ruff check tests/unit/test_presentation_tables.py
All checks passed!
python -m ruff format --check tests/unit/test_presentation_tables.py
1 file already formatted
```

No database tests were skipped. The remaining warning is the existing Starlette/AnyIO deprecation.
The initial failed suite is retained above rather than counted as a successful run. Final suite and
static-gate output were also captured in ignored `logs/text-sections-*.log` files.

CI was neither triggered nor verified. Prior uncommitted work remains; nothing committed or pushed.
No live tokenizer/OCR/scanner, human evaluation, load/restore or model-rollout qualification occurred.
Earlier source-panel mobile positioning failures were not rerun or claimed resolved.

## Changed Files in This Checkpoint

- `src/smb_requirement_agent/infrastructure/documents/text_extractor.py`.
- `tests/unit/test_text_sections.py`, `tests/unit/test_document_library.py`,
  `tests/unit/test_documents_api.py`, `tests/unit/test_presentation_tables.py`,
  `tests/integration/test_library_postgres.py`.
- `frontend/tests/library-text-sections.spec.ts`.
- This spec, ADR-0059/index, parent ledger, ROADMAP, WORKSPACE, AGENTS debt register and operations runbook.

## Deferred / Open

All remaining parent-ledger work stays open. gemini-embedding-001 tokenizer is unqualified;
conservative UTF-8 budget units are not measured model tokens. Old text publications need owner
inspection/new upload to remove previously copied headings. Other formats' heading metadata
requires separate review. Inherited Ruff/format failures, earlier mobile source-panel positioning
and unverified CI remain open. No live provider/OCR/scanner or production quality claim is made.
