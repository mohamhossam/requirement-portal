# Enhancement — Exclusion-safe and correction-safe Word prose

## Objective

Continue the approved document-knowledge ledger after ADR-0059 by removing copied Word prose
from labels and heading paths. ADR-0060 records this bounded checkpoint. Implemented and locally
validated; overall scope, inherited repository gates and CI stay open.

## User Outcome

An owner corrects Word prose, excludes or corrects its heading, then publishes searchable selected
wording with neutral exact paragraph citations. Requirement attachments expose the same positions.

## In Scope

- Positional heading/paragraph/list labels and descendant paths.
- Body-paragraph numbering including blank/skipped contents entries; distinct repeated sections.
- Neutral image/external-reference paths with unchanged image-readiness decisions.
- Existing library and attachment API/UI exposure, publication governance and immutable history.
- Extraction, application, API, PostgreSQL restart and desktop/mobile browser regressions.

## Out of Scope

Broader Word/layout/format quality, full visual previews, scoped blocking-warning exclusions,
async attachment migration, actual model-tokenizer qualification, dedicated Requirement indexing,
unified retrieval/generalized lineage, reference-backed suggestions, OCR, rollout/rollback and
operational evaluation/load/restore/telemetry remain approved in the parent ledger. No scope dropped.

## Domain

Reuse HEADING, PARAGRAPH, LIST_ITEM and other evidence blocks, warnings, immutable revisions,
reviewed passages and content-bound publication approvals.

## Application Use Cases

Existing ingestion/review/build/activation/search and attachment upload consume the new extraction.
Only selected corrected prose supplies excerpts and approved surrounding context.

## Ports

Reuse DocumentExtractorPort, metadata/blob/index repositories and transactions.

## Adapters

SafeDocumentTextExtractor versions new DOCX output. Keep table extraction from ADR-0056 and text
content/list numbering unchanged. Preserve unsupported-image readiness using an explicit private
adapter parameter, without retaining raw heading wording in output metadata. No new dependencies.

## API

Existing library ingestion/status/review/preview/build/search and public projections expose neutral
prose locations and warnings. Existing Requirement attachment upload returns the same contract.
No endpoint/schema additions or new domain/application errors are needed.

## UI

Existing library review/correction/exclusion, warnings, preview, build/activation and exact citation
navigation expose the full path at desktop and 390px. Existing attachment outline/source navigation
is regression tested. No new React component or style changes are required.

## Business Rules

- Prose wording occurs in its own reviewable text, not copied location labels or section metadata.
- Included corrected headings can supply approved context; excluded headings cannot.
- Repeated titles occupy distinct positional sections while declared levels retain ancestry.
- Paragraph numbers count direct body paragraphs, including blanks/skipped contents entries.
- Table row/merge semantics, image readiness, approval and history rules stay intact.
- Adoption requires new upload/review/publication; old extraction rebuilding is insufficient.

## Tests

English/Arabic prose, list classification/numbering, custom heading styles, long/repeated/skipped-
level headings, blank/contents positions, image/reference paths, preserved image readiness,
corrected/excluded heading and prose publication, exact citations, durable ready-build restart,
attachment API, existing table contracts and real desktop/mobile publication/source navigation.

## Acceptance Criteria

- [x] Word heading exclusion and prose correction leave no original wording in shared metadata.
- [x] Existing table evidence and image-readiness decisions are preserved.
- [x] Existing API/UI exposes neutral review locations and exact citations.
- [x] PostgreSQL, all backend gates and relevant frontend/browser results recorded.
- [ ] Repository-wide gates and CI green.

## Validation Evidence

Executed on Windows, 2026-09-22. Runtime:
`C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe` with
`PYTHONPATH=C:/Users/moham/.codex/worktrees/92ae/smb-ai-requirement-agent/src`,
`PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`. Worktree writes/external runtime use escalation.
Before the full suite, a read-only connection asserted and printed:
`Verified current_database(): codex_document_knowledge_test_20260921`. Tests used only that
designated disposable database on localhost:5432 with hostaddr=127.0.0.1. No application database
was used; no PostgreSQL tests were skipped.


```text
python -m pytest tests/unit/test_word_prose.py tests/unit/test_word_tables.py tests/unit/test_document_library.py tests/unit/test_documents_api.py tests/unit/test_document_domain_and_extraction.py --tb=short
88 passed, 1 warning in 18.77s

python -m ruff check . --output-format concise
FAIL, exit 1 — Found 72 errors (inherited skill scripts)
python -m ruff format --check .
FAIL, exit 1 — 3 files would be reformatted, 811 files already formatted
python -m ruff check src tests scripts/evaluate_document_knowledge.py
PASS, exit 0 — All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
PASS, exit 0 — 389 files already formatted
python -m mypy src tests
PASS, exit 0 — Success: no issues found in 388 source files
lint-imports
PASS, exit 0 — Contracts: 6 kept, 0 broken

git diff --check
PASS — existing CRLF conversion warnings only
```

The repository-wide Ruff failures remain in
`.claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py`. No exclusion hides them.
The standalone mandatory architecture gate passes all six contracts. No schema/dependency changes.


```text
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 TEST_DATABASE_URL=<verified disposable database>
python -m pytest --tb=short
1327 passed, 1 warning in 230.31s (0:03:50)

npm --prefix frontend run api:check
PASS — generated types match the OpenAPI snapshot
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
Test Files 39 passed (39); Tests 267 passed (267); Duration 47.83s
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8187 SMOKE_UI_PORT=4287
SMOKE_PYTHON=C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe
npm --prefix frontend run test:smoke -- library-word-prose.spec.ts library-word-tables.spec.ts review-flow.spec.ts --grep 'Word prose|Word row|Author uploads'
8 passed (1.3m)
```

All new and selected regression tests passed on their first run. Existing DOCX-version and
heading-label expectations were advanced deliberately before testing; historical evidence in the
older slice specifications remains unchanged. The remaining backend warning is the existing
Starlette/AnyIO deprecation. Static/full-suite output is also retained in ignored
`logs/word-prose-*.log` files.

Four new Word prose browser cases run at 1440px and 390px, correcting paragraph/list wording and
either excluding or correcting its heading. They exercise real upload/bounded extraction, saved
review, preview/build/activation, public metadata/search JSON, exact citations and overflow checks.
Two existing Word table cases preserve row/merge/nested exclusions; two attachment cases preserve
source navigation and immutable replacement at their configured desktop/narrow widths. Desktop
exclusion and mobile corrected-heading screenshots were opened and visually inspected. No React
component, style or API schema changed.

No unrelated source-panel positioning claim follows from the passing attachment journey. Earlier
mobile positioning failures remain open. CI was not triggered or verified. No commit or push;
prior uncommitted work remains intact.


## Changed Files in This Checkpoint

- `src/smb_requirement_agent/infrastructure/documents/text_extractor.py`.
- `tests/word_table_fixtures.py`, `tests/unit/test_word_prose.py`,
  `tests/unit/test_word_tables.py`, `tests/unit/test_document_library.py`,
  `tests/unit/test_documents_api.py`, `tests/integration/test_library_postgres.py`.
- `frontend/tests/library-word-prose.spec.ts`.
- This spec, ADR-0060/index, parent ledger, ROADMAP, WORKSPACE, AGENTS debt register and runbook.

## Deferred / Open

The parent enhancement remains incomplete. gemini-embedding-001 tokenizer is unqualified;
conservative UTF-8 budget units are not measured model tokens. Legacy Word metadata cleanup
requires owner review/new upload. Inherited Ruff/format failures, earlier mobile source-panel
positioning and CI remain open unless evidence below explicitly proves otherwise.
No live provider/OCR/scanner, representative production-format corpus, human benchmark, load,
restore or model-rollout qualification is claimed. Preserve prior changes; no commit or push.
