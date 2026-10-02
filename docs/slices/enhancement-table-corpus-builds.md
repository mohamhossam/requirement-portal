# Enhancement — Table children and explicit corpus builds

## Objective

Deliver the next bounded vertical slice of the document-knowledge enhancement: versioned table
children with owner-visible corpus member build and activation. Implemented and locally validated;
overall enhancement, repository-wide failures and CI remain open.

## User Outcome

An owner previews table-aware children, approves a saved review for building, waits for indexing,
then explicitly activates the complete result. The previous publication stays searchable during
the build. Discard and retry are available; activation explains downstream citation reconciliation.

## In Scope

- TABLE_ROW/WORKSHEET_RANGE field packing and oversized-field exact offsets.
- Versioned source/index identity, durable build manifest, recovery and explicit activation.
- Owner-only preview/build/activation/discard API and existing library UI.
- Memory/PostgreSQL behavior, legacy policy coexistence, citation currency and browser tests.

## Out of Scope

OCR/Docling/Tesseract qualification, tokenizer benchmarking, dedicated Requirement indexing,
unified retrieval and generalized lineage, reference-backed suggestions, human evaluation,
load/restore/telemetry remain in the parent ledger. No parent scope is dropped.

## Domain

Publication records explicit-activation intent, replaced publication, completed manifest/count
and build time. Domain activation preserves history and rejects incomplete or obsolete sources.

## Application Use Cases

ReferenceKnowledge previews, creates, builds, verifies, activates and discards corpus generations.
The corpus rolls forward through independently owned publication members (ADR-0054).

## Ports

ReferenceIndexPort exposes exact stored manifests. DocumentLibraryPort checks supported identities.
Reuse existing transactions, clock, embedding and token-budget boundaries.

## Adapters

Memory and PostgreSQL implement manifest inspection and pending-build selection. Existing JSON
payloads receive compatible defaults; no migration or new configuration is needed.

## API

GET /library/documents/{id}/builds/preview; POST /library/documents/{id}/builds;
POST /library/documents/{id}/builds/{build_id}/activation and /discard. Existing LibraryView and
Publication responses expose generation state. Mutation bodies carry source/version/manifest
preconditions. Existing 403/409/422/502 mappings apply.

## UI

Extend the library's saved-review area with table-aware preview, approve/build, ready/failed state,
explicit activation warning and pending-build discard. Unsaved edits prevent preview/build/activation.
Technical identity/manifest details live in history disclosures; product controls describe decisions.
Replacement uploads also wait for unsaved passage edits to be saved, preserving the review form.

## Business Rules

- No private/excluded content becomes searchable during build.
- Complete manifests and current source approvals are required at activation.
- Prior publication/citations stay current during build, then require explicit reconciliation.
- Legacy boundaries and approval history remain unchanged.
- UTF-8 budget units are not qualified model token counts.

## Tests

Field/offset preservation, bilingual budgets, old/new policies, source/owner/version/manifest guards,
discard and provider races, restart/recovery and ready-build invisibility; API and browser actions.

## Acceptance Criteria

- [x] Table children retain exact approved offsets and bounded input.
- [x] Owner preview/build/activate/discard works across API and browser.
- [x] Ready/failed/partial builds preserve active publication and durable recovery.
- [x] PostgreSQL and regression validation is recorded.
- [ ] All repository gates and CI are green.

## Validation Evidence

Executed on Windows, 2026-09-21. This carried-over worktree has no local virtual environment.
Commands used `C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe` with
`PYTHONPATH=C:/Users/moham/.codex/worktrees/92ae/smb-ai-requirement-agent/src`, ensuring imports
came from this checkout. The sandbox denied launching that external runtime; approved escalated
runs used the same runtime and working tree. Frontend dependencies were installed with `npm ci`.

All database tests set `TEST_DATABASE_URL` to the designated disposable
`codex_document_knowledge_test_20260921` database on `127.0.0.1:5432`.
No application database was used or truncated.

```text
python -m pytest --tb=short
1216 passed, 1 warning in 218.54s (0:03:38)

python -m pytest tests/unit/test_document_library.py tests/unit/test_reference_grounding.py -o addopts='' -q
31 passed, 1 warning in 11.61s
(final regression after keeping field labels in surrounding context)

python -m ruff check src tests scripts/evaluate_document_knowledge.py
All checks passed!
python -m ruff format --check src tests scripts/evaluate_document_knowledge.py
379 files already formatted
python -m mypy src tests
Success: no issues found in 378 source files
lint-imports
Contracts: 6 kept, 0 broken

npm --prefix frontend run api:check
PASS — generated TypeScript matches OpenAPI snapshot
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test -- --reporter=dot
39 files passed; 267 tests passed in 11.01s (final run including build-state/edit-preservation tests)
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8153 SMOKE_UI_PORT=4253 SMOKE_PYTHON=<existing runtime>
npm --prefix frontend run test:smoke -- library-build.spec.ts library-flow.spec.ts reference-applicability.spec.ts
8 passed (1.2m), including the new build flow at 1440px and 390px

SMOKE_API_PORT=8157 SMOKE_UI_PORT=4257 SMOKE_PYTHON=<existing runtime>
npm --prefix frontend run test:smoke -- library-build.spec.ts
2 passed (35.7s), final rerun with dirty replacement guard and refreshed screenshots

SMOKE_API_PORT=8155 SMOKE_UI_PORT=4255 SMOKE_PYTHON=<existing runtime>
npm --prefix frontend run test:smoke -- analysis-sources.spec.ts
2 failed — unchanged mobile source-dialog x=38px; expected x=0 and width=390px

impeccable detect --json frontend/src/app/LibraryPage.tsx frontend/src/app/library.css
[]
git diff --check
PASS (only Git's CRLF conversion warnings)
```

The first table test over-specified the layout of a cell containing literal delimiters; it was
corrected to assert exact contiguous source coverage and budgets without inventing field semantics.
All four full-page/control desktop/mobile screenshots were opened and inspected. Independent
review identified replacement upload losing dirty review text; the final UI blocks that action
and explains saving first. The final full frontend suite and desktop/390px browser rerun pass.
The refreshed full-page/control captures plus both dirty-replacement captures were opened and
verified. Impeccable review/documentation disposition is recorded in the surface brief.

Repository-wide gates were run and are still red, preserving the inherited failures:

```text
python -m ruff check . --output-format concise
Found 72 errors — all in .claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py
python -m ruff format --check .
3 files would be reformatted, 789 files already formatted — the same unrelated scripts
```

No exclusions were added and those scripts were not edited. CI has not been triggered or verified
for this uncommitted change. No live model, OCR, human evaluation, load or restore qualification is
claimed. Prior checkpoint evidence remains in enhancement-reference-parent-context.md.

## Changed Files in This Checkpoint

- Domain: `domain/document/library.py`.
- Application: `application/use_cases/reference_knowledge.py`, `document_library.py`;
  `application/ports/reference_index.py`, `document_library.py`.
- Infrastructure: `infrastructure/persistence/reference_index.py`, `document_library.py`.
- API: `interfaces/api/routes/library.py`; `frontend/openapi.json`, `src/api/schema.d.ts`,
  `src/api/client.ts`.
- UI: `frontend/src/app/LibraryPage.tsx`, `LibraryPage.test.tsx`;
  `frontend/tests/library-build.spec.ts`; corpus screenshots and library surface brief.
- Tests: `tests/unit/test_document_library.py`, `test_library_api.py`,
  `tests/integration/test_library_postgres.py`.
- Documentation: ADR-0054 and its index, this slice, parent enhancement ledger, operations runbook,
  ROADMAP.md and WORKSPACE.md. Earlier uncommitted implementation remains in place.

Backend paths above are relative to `src/smb_requirement_agent/`.

## Deferred

See the unchanged parent enhancement ledger. Cross-owner all-at-once activation and zero-downtime
multi-model serving are not claimed by the incremental owner-scoped generation contract.
