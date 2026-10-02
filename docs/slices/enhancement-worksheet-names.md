# Enhancement — Independently reviewed worksheet names

## Objective

Continue the approved document-knowledge ledger after ADR-0060 with the smallest remaining
metadata-isolation path: XLSX worksheet headings. ADR-0061 records this bounded checkpoint.
Implemented and locally validated; inherited repository gates, CI and the overall enhancement
remain open.

## User Outcome

An owner corrects or excludes a worksheet name and publishes selected rows with neutral exact
locations. Requirement attachments expose the same positions and explicit hidden-sheet opt-in.

## In Scope

- Worksheet heading text independent of row labels, paths, warnings and image/chart parents.
- Shared workbook tab positions including empty, hidden/veryHidden and chart tabs.
- Existing library review/build/activation/search and attachment API/browser exposure.
- Immutable history, hidden-sheet selection, merge/formula/image/chart regression coverage.

## Out of Scope

Broader format/layout quality, visual previews, scoped warning exclusions, async attachments,
actual embedding-tokenizer qualification, dedicated Requirement indexing, unified retrieval and
generalized lineage, reference-backed suggestions, OCR, model rollout/rollback, evaluation/load/
restore/telemetry and CI remain in the approved parent ledger. No scope is dropped.

## Domain

Reuse HEADING/WORKSHEET_RANGE evidence, reviewed passages and immutable publication approvals.
Existing hidden-sheet identifiers are read from the stored extraction, preserving legacy behavior.

## Application Use Cases

Existing ingestion/review/build/activation/search and attachment selection consume the new
extraction. Only included corrected headings enter same-sheet surrounding context.

## Ports

Reuse DocumentExtractorPort, library/blob/index repositories and transactions.

## Adapters

SafeDocumentTextExtractor versions new XLSX output and shares one positional mapping between
rows, charts and images. Existing merge, formula/cache and image-readiness behavior remains.
No new dependencies or schema migration.

## API

Existing library and attachment schemas expose positional labels/paths, independently reviewable
name text and an explanatory warning. Hidden worksheet identifiers in new uploads are positional;
legacy revisions keep name-based identifiers. No new endpoint or error mapping is required.

## UI

Existing library corrections/exclusions, warnings, previews, build/activation, search and exact
citation controls expose the path at desktop/390px. Existing attachment outline and hidden-sheet
checkboxes show positional identifiers with original names in heading content. No new component
or style changes are required; browser coverage verifies real upload and persisted selection.

## Business Rules

- Names are reviewable heading text, not copied navigation metadata.
- Source formulas/chart passages may explicitly reference names and need separate review.
- Exclusions/corrections do not rename positions or change hidden-sheet selection.
- New upload/review/publication is required; prior revisions and publications stay immutable.
- Conservative UTF-8 budget units are not measured embedding-model tokens.

## Tests

English/Arabic names, empty/hidden/veryHidden/chart tabs, image/chart context, unchanged source
formula references, corrected/excluded heading publication, immutable replacement, PostgreSQL
restart/activation, attachment API/selection and desktop/mobile publication/citation navigation.

## Acceptance Criteria

- [x] Corrected/excluded worksheet names leave no copied shared metadata.
- [x] Merge/formula/chart/image and hidden-sheet behavior retained.
- [x] Existing API/UI path tested end to end, including PostgreSQL persistence.
- [x] Five mandatory backend gates and relevant frontend/browser results recorded.
- [ ] Repository-wide gates and CI green.

## Validation Evidence

Executed on Windows, 2026-09-22. Runtime:
`C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe`, with
`PYTHONPATH=C:/Users/moham/.codex/worktrees/92ae/smb-ai-requirement-agent/src`,
`PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`. Worktree writes/external runtime execution used
sandbox escalation. The actual worktree is under `C:/Users/moham/.codex/`; the supplied path
without the separator before `.codex` did not exist. No other worktree/task was created.

Read-only connections, including immediately before the full suite, asserted and printed:
`Verified current_database(): codex_document_knowledge_test_20260921`.
`TEST_DATABASE_URL` uses only that disposable database with `host=localhost hostaddr=127.0.0.1
port=5432`. No application database is used.

```text
python -m pytest tests/unit/test_worksheet_names.py tests/unit/test_spreadsheet_merges.py tests/unit/test_document_library.py tests/unit/test_documents_api.py tests/unit/test_document_domain_and_extraction.py --tb=short
88 passed, 1 warning in 19.84s
(before adding two legacy/new hidden-selection regressions; covered by the full suite)

python -m ruff check . --output-format concise
FAIL, exit 1 — Found 72 errors (inherited skill scripts)
python -m ruff format --check .
FAIL, exit 1 — 3 files would be reformatted, 814 files already formatted
python -m ruff check src tests scripts/evaluate_document_knowledge.py
PASS — All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
PASS — 390 files already formatted
python -m mypy src tests
PASS — Success: no issues found in 389 source files
lint-imports
PASS — Contracts: 6 kept, 0 broken

git diff --check
PASS — existing CRLF conversion warnings only
```

Initial typing failed on the new openpyxl chart fixture: the installed stub combines Worksheet
and Chartsheet methods, giving `add_chart` the wrong signature. An `isinstance` assertion did not
resolve that stub inheritance. The fixture now uses the existing repository's explicit Worksheet
cast pattern; final typing/product checks above pass. Ruff corrected two new test import-order
findings. No production behavior was changed to satisfy those test typing/lint issues.

Repository-wide Ruff failures remain confined to
`.claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py`; those files are unchanged
and no exclusion hides them. Static-gate output is retained in ignored
`logs/worksheet-names-gate-*.log` and `logs/worksheet-names-architecture.log`; initial gate-4
records the typing failure, superseded by the successful final command above.

```text
npm --prefix frontend run api:check
PASS — generated types match the OpenAPI snapshot
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
Test Files 39 passed (39); Tests 267 passed (267); Duration 10.91s
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8189 SMOKE_UI_PORT=4289
SMOKE_PYTHON=C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe
npm --prefix frontend run test:smoke -- library-worksheet-names.spec.ts library-spreadsheet-merges.spec.ts
8 passed (1.2m)
```

Both smoke ports were checked unused before launch. Four new desktop/390px cases exercise real
upload/bounded extraction, correction/exclusion of names, saved review, preview/build/activation,
public projection/search JSON and exact row citations with overflow checks. Four existing cases
retain spreadsheet merge exclusions and attachment hidden-sheet opt-in across reload, including
attachment overflow assertions at 360, 390, 740, 900 and 1440px. Desktop exclusion and mobile
corrected-heading preview screenshots were opened and visually inspected. No React component,
style or API schema changed. No earlier source-panel positioning fix is claimed.

### Full backend suite

```text
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 TEST_DATABASE_URL=<verified disposable database>
python -m pytest --tb=short
1335 passed, 1 warning in 228.63s (0:03:48)
```

No database tests were skipped. The suite includes the new PostgreSQL worksheet-name exclusion
and ready-build restart/activation contract, and both new/legacy hidden-sheet selection tests.
The only warning is the existing Starlette/AnyIO deprecation. Full output is retained in ignored
`logs/worksheet-names-pytest.log`. All new extraction, application, API, PostgreSQL and browser
behavior tests passed on their first run; the earlier typing/import corrections are recorded above.

CI is unverified. Nothing was committed or pushed; previous uncommitted work is preserved.

## Changed Files in This Checkpoint

- `src/smb_requirement_agent/infrastructure/documents/text_extractor.py`.
- `tests/spreadsheet_fixtures.py`, `tests/unit/test_worksheet_names.py`,
  `tests/unit/test_spreadsheet_merges.py`, `tests/unit/test_document_library.py`,
  `tests/unit/test_documents_api.py`, `tests/unit/test_document_domain_and_extraction.py`,
  `tests/integration/test_library_postgres.py`.
- `frontend/tests/library-worksheet-names.spec.ts`, `frontend/tests/library-spreadsheet-merges.spec.ts`.
- This spec, ADR-0061/index, parent ledger, ROADMAP, WORKSPACE, AGENTS debt register and runbook.

## Deferred / Open

The parent enhancement remains incomplete. gemini-embedding-001 tokenizer remains unqualified.
Existing XLSX publications need owner inspection/new upload to remove copied worksheet metadata.
Inherited Ruff/format failures, earlier mobile source-panel positioning and CI remain open unless
actual evidence below establishes otherwise. No live provider/OCR/scanner, representative format
corpus, human evaluation, load, restore or model rollout qualification is claimed. No commit/push.


## Local integration into refactor-ux — 2026-09-22

Integrated the accumulated 132 changed files from worktree `92ae` into the existing
`C:/ai/projects/smb-ai-requirement-agent` checkout on `refactor-ux`, preserving its earlier
checkpoint work. Both checkouts started at `899741a`; there were no destination-only changed
files. Before copying, saved existing files, Git diffs/status and SHA-256 manifests under ignored
`logs/refactor-ux-integration-20260922-121157/`. Source worktree, branch HEAD and index remain
unchanged. No commit, push or database migration was performed.

47 existing files updated (including line-ending differences), 41 files added, 44 already
identical. All 132 matched source bytes immediately after integration. Subsequent integration
validation changed only the corpus-build browser test and this validation record. Test-generated
captures are preserved in the backup directory; the integrated source captures were restored.

Commands ran from the destination checkout with `PYTHONPATH` pointing to its `src`, the same
Python runtime, `PYTHONUTF8=1`, and `PYTHONIOENCODING=utf-8`. Immediately before pytest,
`current_database()` was asserted as `codex_document_knowledge_test_20260921` using
localhost:5432 with hostaddr=127.0.0.1. No application database was used.

```text
python -m pytest --tb=short
1335 passed, 1 warning in 235.38s (0:03:55); no skips
python -m ruff check . --output-format concise
FAIL — 72 inherited skill-script errors
python -m ruff format --check .
FAIL — 3 inherited formatting failures; 814 files already formatted
python -m ruff check src tests scripts/evaluate_document_knowledge.py
PASS — All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
PASS — 390 files already formatted
python -m mypy src tests
PASS — no issues in 389 source files
lint-imports
PASS — 6 contracts kept, 0 broken
npm --prefix frontend run api:check
PASS
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
267 tests passed in 39 files; 40.24s
npm --prefix frontend run build
PASS — 1999 modules transformed
```

The expanded browser group exposed an older test assumption: `library-build.spec.ts` excluded
record 2 instead of private record 3 and expected an inferred `Rule:` label, despite ADR-0057
making the header independently reviewable. This deliberately approved the fixture's private
record, contaminating subsequent fake-search assertions. Corrected that test's exclusion index
and field expectation to `R2C2:`; production behavior and worksheet tests were unchanged.

```text
SMOKE_PYTHON=C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe
SMOKE_API_PORT=8191 SMOKE_UI_PORT=4291
npm --prefix frontend run test:smoke -- library-build.spec.ts library-worksheet-names.spec.ts reference-applicability.spec.ts
Initial: 6 failed, 2 passed (1.8m)
SMOKE_API_PORT=8193 SMOKE_UI_PORT=4293
Same browser command after the two-line test correction:
8 passed (1.3m)

cd frontend
npm --prefix frontend exec -- eslint tests/library-build.spec.ts
PASS — exit 0
```

Both port pairs were checked unused. Initial error contexts/traces remain in the ignored backup's
`browser-initial/`. Backend logs are `logs/refactor-ux-integration-*.log`. The existing repository
Ruff failures and unverified CI remain open; passing integration does not qualify the full
knowledge enhancement, tokenizer, OCR, retrieval quality or operations.
