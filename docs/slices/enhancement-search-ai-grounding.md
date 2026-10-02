# Enhancement — Search and AI grounding

## Objective
Complete the search and grounding checkpoint of the approved document-knowledge enhancement.

## User Outcome
Search Requirements and published documents together, inspect exact citations, and review
document-backed clarification suggestions without automatically accepting policy applicability.

## In Scope
- Unified, source-balanced search with current-source checks and explicit source labels.
- Published-reference clarification suggestions with provenance and stale-source rejection.
- Reference-aware screening and copied-evidence safeguards.
- Semantic-quality evaluation using explicit human judgments, separate from retrieval metrics.

## Out of Scope
The parent enhancement's OCR, load, operational and production qualification work remains open.
No external publication or automatic applicability approval.

## Domain
Suggestions retain published-reference citations separately from Requirement evidence.

## Application Use Cases
Unified search composes existing indexes. Suggestion generation validates every supplied citation
and rechecks source currency at persistence and selection. Screening exposes reference decisions.

## Ports
Extend the focused suggestion boundary with labelled published references; reuse existing indexes,
access, publication validation and persistence ports.

## Adapters
Configured/OpenAI/offline suggesters and backward-compatible PostgreSQL JSON persistence.

## API
Add unified search while preserving the document-only endpoint and existing citation contracts.
Extend suggestion and screening responses with reference evidence.

## UI
Extend the existing library search and clarification/knowledge review surfaces with explicit
source labels, exact citation links, pending states and stale-source guidance.

## Business Rules
Publication does not establish applicability. Copied reference evidence is never independent
corroboration. Stale sources cannot support a selected suggestion. Owners retain decisions.

## Tests
Domain, adapter, use-case, API, persistence, UI and browser regression tests; all repository gates.

## Acceptance Criteria
- [x] Unified search returns labelled current Requirement/document evidence.
- [x] Reference-backed suggestions preserve exact citations and fail closed on source changes.
- [x] Screening explains reference conflicts/decisions without bilateral document findings.
- [x] Semantic judgment metrics are reproducible and distinguish fixtures from human evaluation.
- [x] Required checks have recorded evidence; CI status is reported honestly.

## Validation Evidence
Executed locally on Windows, 2026-09-22, with deterministic fake providers. PostgreSQL used only
`codex_document_knowledge_test_20260921`; `select current_database()` verified that target first.
No live LLM call or human benchmark result is implied.

```text
TEST_DATABASE_URL=<verified disposable database> .venv/Scripts/python.exe -m pytest --tb=short
1380 passed, 1 warning in 181.59s (0:03:01)

.venv/Scripts/python.exe -m ruff check .
All checks passed!
.venv/Scripts/python.exe -m ruff format --check .
840 files already formatted
.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 404 source files
.venv/Scripts/lint-imports.exe
Contracts: 6 kept, 0 broken.

npm --prefix frontend run api:check
Generated TypeScript matches the OpenAPI snapshot; exit 0
npm --prefix frontend run lint
exit 0
npm --prefix frontend run typecheck
exit 0
npm --prefix frontend test -- --reporter=dot
Test Files 40 passed (40); Tests 274 passed (274)
npm --prefix frontend run build
2001 modules transformed; built successfully; exit 0

SMOKE_API_PORT=8351 SMOKE_UI_PORT=4351 npm --prefix frontend run test:smoke -- search-grounding.spec.ts reference-applicability.spec.ts library-flow.spec.ts
Existing library/applicability cases: 6 passed. New search cases initially failed on an exact
getByLabel selector that included native select option text; corrected to the named combobox.
SMOKE_API_PORT=8353 SMOKE_UI_PORT=4353 npm --prefix frontend run test:smoke -- search-grounding.spec.ts
2 passed (21.2s)
SMOKE_API_PORT=8357 SMOKE_UI_PORT=4357 npm --prefix frontend run test:smoke -- search-grounding.spec.ts
2 passed (22.4s), including scrollWidth <= viewport at 1440 and 390 pixels.

.venv/Scripts/python.exe scripts/evaluate_grounding.py docs/evaluation/grounding-synthetic.json
cases=3, answered=2, supported=1, unsupported=1, applicability_failures=1,
missed_conflicts=1, correct_abstentions=1; support/abstention rates=0.5.
These deliberately mixed synthetic judgments exercise arithmetic, not provider quality.

impeccable detect --json <LibraryPage.tsx> <AnalysisPanel.tsx> <KnowledgeView.tsx>
[]
git diff --check
exit 0
```

Initial fixture/version and message expectation failures, Windows text encoding, and Ruff findings
were corrected and rerun. Final UI inspection found 484px content in a 390px viewport; the finish
reviewer required responsive reflow. Min-width constraints, wrapping source/status labels and
citation text corrected it. Both final captures now fit, and the reviewer returned `ship` for
that single scored fix. Full desktop/mobile search and selected-answer captures were opened.
No new visual identity or raster asset was introduced; pre-existing DESIGN.md drift is retained.

CI has not been triggered or verified for this uncommitted working tree. Local green results are
not a release/CI claim. The final full-suite rerun returned:

```text
TEST_DATABASE_URL=<verified disposable database> .venv/Scripts/python.exe -m pytest --tb=short
1380 passed, 1 warning in 269.31s (0:04:29)
```

One further regression test verifies document withdrawal during answer re-analysis cannot commit
either the answer or a new analysis. The existing generation-context guard rejects that race with
`ArtifactVersionConflictError`; the test's initial exception expectation was corrected to match
that safe failure. The focused grounding suite then passed (14 tests, exit 0).

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_reference_grounding.py -q --tb=short
.............. [100%]
exit 0 (one existing Starlette/AnyIO deprecation warning)

.venv/Scripts/python.exe -m ruff check .
All checks passed!
.venv/Scripts/python.exe -m ruff format --check .
840 files already formatted
.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 404 source files
```

The independent documenter completed both surface-brief checkpoints. The final desktop/mobile
captures and incumbent styles were verified; `DESIGN.md` and its design sidecar were unchanged.

## Deferred
No requested implementation scope dropped. Actual human-labelled semantic judgments, production
retrieval/latency qualification, broader generalized lineage and green CI remain tracked in the
parent enhancement. The existing conservative exclusion now also covers suggestion-derived human
answers, preventing copied evidence from appearing as independent corroboration. Such answers
remain attributed human decisions in immutable analysis history; policy applicability stays in
the existing owner proposal workflow. The new search scans bounded candidate sets (100 Requirement
candidates before membership filtering, at most 20 returned with at most 3 per source), so this is
not portfolio-scale retrieval qualification.


## Changed Files

- Domain: `domain/knowledge/entities.py` adds separate published-reference suggestion evidence.
- Application: `ports/{reference_grounding,requirement_knowledge}.py`,
  `use_cases/{unified_knowledge_search,reference_knowledge,requirement_knowledge,analysis_collaboration}.py`,
  and `grounding_evaluation.py` implement search, provenance/currency, screening and evaluation.
- Infrastructure: knowledge prompts, real/offline suggestion adapters, memory/generation/PostgreSQL
  index adapters and PostgreSQL suggestion JSON persistence. No new migration is needed.
- API: container/dependencies, library/knowledge routes and knowledge schemas; OpenAPI and TypeScript
  snapshots updated compatibly.
- UI: `LibraryPage.tsx`, `AnalysisPanel.tsx`, `labels.ts`, `KnowledgeView.tsx`, and API client.
- Verification: grounding/evaluation/adapter/knowledge tests, PostgreSQL library contract, library UI
  test, fixture updates, `search-grounding.spec.ts`, semantic evaluation CLI/rubric/synthetic fixture.
- Documentation: ADR-0064, roadmap, workspace, parent enhancement ledger and this specification.
