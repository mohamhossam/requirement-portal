# Enhancement — Bounded surrounding context for exact references

## Objective

Improve interpretation of retrieved library evidence without weakening exact citations or silently
changing the approved chunking/embedding identity. This is one bounded checkpoint of the approved
document-knowledge enhancement, not completion or production qualification.

## User Outcome

An owner can preview the exact chunks that will be shared and inspect their surrounding approved
same-section context. Search results keep the matching sentence visibly distinct while offering
the same context in a disclosure. Applicability generation receives that context, but every
proposal still cites the exact published child passage.

## In Scope

- Deterministic, source-bounded parent-context expansion over approved chunks.
- A provider-neutral exact-citation-plus-context DTO for reference applicability.
- Compatible API fields and library preview/search UI.
- Backend, API-contract, React and browser regression coverage.

## Out of Scope

Table/wide-row rechunking, model-tokenizer qualification, corpus-generation rebuild/activation,
unified Requirement/document retrieval, OCR deployment qualification, semantic evaluation, load
measurement and restore rehearsal remain in the parent enhancement ledger.

## Domain

No new domain invariant. `PublishedReference` remains the exact immutable child excerpt and
offset range. Surrounding context is an Application retrieval projection, not approved
applicability or a second citation.

## Application Use Cases

`StructureAwareChunks` attaches a bounded context window from the same structural parent.
`ReferenceKnowledge.search` reconstructs it from the current approved revision before returning a
candidate. `ReferenceGrounding` budgets and supplies `ReferenceEvidence` to the proposer while
persisting only exact citations.

## Ports

`ReferenceProposerPort` accepts `ReferenceEvidence`: an exact `PublishedReference`, bounded
context text and its locations. `ReferenceChunk` adds context projection fields. Existing
token-counter, index and embedding boundaries remain unchanged.

## Adapters

Structured and fake proposers consume context but map output citations back to the exact child.
The applicability prompt advances to `reference-applicability-v2`. Memory/PostgreSQL chunk payloads
remain compatible; no migration or re-embedding is required.

## API

Chunk preview and `POST /knowledge/search` add `context_text`, `context_locations` and
`context_token_count`. Exact child fields and citation URLs are unchanged.

## UI

Saved-chunk preview and published search label the child as the exact passage. Context is a compact
disclosure explaining that it is interpretive, owner-approved and same-section only. Text keeps
automatic direction and the existing responsive library layout.

## Business Rules

- Context contains only selected passages from the cited publication and structural parent.
- The 1,536-unit context ceiling uses the configured counter; it is not a token-quality claim.
- Context cannot replace, widen or alter the exact citation excerpt.
- Exclusions, withdrawal and publication replacement retain their existing fail-closed behavior.
- Child embedding inputs and identity are unchanged in this checkpoint.

## Tests

- Unit: section/exclusion boundaries, budget, exact citation, prompt payload/version.
- API contract: new fields are present without changing existing response paths.
- UI: exact/context distinction and mixed-direction-safe rendering.
- Browser: publish/search flow reveals approved neighbours and never excluded text.

## Acceptance Criteria

- [x] Retrieved chunks expose bounded same-section context built only from approved passages.
- [x] Applicability generation can use context while persisting exact child citations.
- [x] Preview/search UI makes the distinction understandable.
- [x] Existing embedding identity and publication compatibility are preserved.
- [ ] Repository-wide gates and CI are green.

## Validation Evidence

Executed locally on Windows, 2026-09-21. PostgreSQL tests used only the dedicated disposable
`codex_document_knowledge_test_20260921` database.

```text
TEST_DATABASE_URL=<dedicated disposable database>
.venv/Scripts/python.exe -m pytest -rA --tb=short
1206 passed, 1 warning in 198.42s

.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 378 source files

.venv/Scripts/lint-imports.exe
Contracts: 6 kept, 0 broken

.venv/Scripts/python.exe -m ruff check src tests scripts/evaluate_document_knowledge.py
All checks passed!
.venv/Scripts/python.exe -m ruff format --check src tests scripts/evaluate_document_knowledge.py
379 files already formatted

npm --prefix frontend test -- --reporter=dot
Test Files 39 passed (39); Tests 265 passed (265)
npm --prefix frontend run api:check
PASS
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=8143 SMOKE_UI_PORT=4243
npm --prefix frontend run test:smoke -- library-flow.spec.ts
4 passed in 33.3s

SMOKE_API_PORT=8145 SMOKE_UI_PORT=4245
npm --prefix frontend run test:smoke -- analysis-sources.spec.ts
FAIL — 2 existing cases: source dialog x=38px; test expects x=0/full 390px width

C:/Users/moham/.agents/skills/impeccable/scripts/impeccable.cmd detect --json
  frontend/src/app/LibraryPage.tsx frontend/src/app/library.css
[]
```

The first browser run exposed only an ambiguous text locator after context correctly repeated the
exact excerpt; the assertion was scoped to the unique result article and the complete desktop/narrow
flow then passed. The two pre-existing `analysis-sources.spec.ts` source-dialog geometry failures
were reproduced with the same x=38px versus x=0 assertion. Their accessible label/source/focus path
passed before that assertion. They were not changed or hidden and remain outside this bounded
library slice.

Repository-wide gates were rerun and remain red only in the same unrelated skill scripts:

```text
.venv/Scripts/python.exe -m ruff check . --output-format concise
FAIL — 72 errors, all in .claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py
.venv/Scripts/python.exe -m ruff format --check .
FAIL — 3 files would be reformatted, 787 files already formatted
```

The browser flows generated desktop and narrow screenshots. Direct image inspection was attempted
through both the local image viewer and computer-use fallback, but this session's Windows sandbox
helper failed during both reads. No manual visual-inspection claim is made. CI was not triggered.

## Deferred

No parent-enhancement scope is dropped. The remaining work stays recorded in
`enhancement-document-knowledge.md` and `docs/operations/document-knowledge.md`.
