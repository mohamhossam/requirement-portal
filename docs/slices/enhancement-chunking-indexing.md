# Enhancement checkpoint — Chunking and dedicated Requirement indexing

## Objective

Complete the remaining local implementation and bounded qualification of chunking/indexing in the
approved document-knowledge plan. The overall enhancement and production qualification remain open.
Decision: ADR-0062. Existing uncommitted work is preserved; no commit or push is part of this task.

## User Outcome

Requirement knowledge prepares in the background. Screening and answer suggestions wait for current
knowledge without rebuilding the portfolio themselves. The Knowledge page exposes preparation,
saved passage progress, failure/retry and a model-rebuild requirement. Existing library build,
manifest, activation and citation UI remains the owner-controlled path for document model changes.

## Scope and roadmap coverage

All Domain/Application/Ports/Adapters/API/UI/Tests fields of the active roadmap entry were considered.
This checkpoint supplies the chunking/indexing portion of each; no overall enhancement scope is
dropped. OCR, broader visual extraction, unified retrieval/generalized lineage, reference-backed
suggestions and production operations remain in their existing ledger rows.

| Remaining chunk/index item | Delivered evidence | Qualification boundary |
|---|---|---|
| Actual embedding token qualification | Real selected-model `countTokens`, strict response validation, no fallback; same-sample embedding acceptance; dated JSON evidence | 64 synthetic fixtures, not an exhaustive language/tokenizer proof; runtime byte budgets retain their name |
| Structured table quality/fixtures | Reproducible reviewed DOCX/PPTX/XLSX/CSV/TSV children, exact reconstruction and offsets, corrected/excluded headers/merges; existing extraction/browser/PostgreSQL contracts plus versioned token fixture | Representative customer/OCR tables remain broader ingestion/release qualification |
| Coordinated model rollout/rollback | Two-owner authority/activation/mixed-identity/exclusion/citation/history contract in memory and PostgreSQL; actual 001→2→001 provider exercise | Isolated synthetic corpus, not a deployed maintenance rehearsal |
| Dedicated Requirement indexing | Separate worker; 16-text batches; durable progress/cache; expiring lease and source-change fencing; fair pagination; retry/backoff; queue prerequisite; API/UI | Existing clean indexes need an explicit rebuild or source change to adopt long-field children |

## Domain

Existing Requirement source kinds, evidence fingerprints and citation validation remain authoritative.
No reference-derived analysis is promoted into independent trusted Requirement evidence. Existing
document approvals/extractions remain immutable; owner approval is never inferred from a build.

## Application

`IndexRequirementKnowledge` drives one batch per turn. `RequirementKnowledgeCorpus.index_source`
assembles trusted content; field-local children and bounded query text prevent unbounded embedding
inputs. Screening/suggestions require a current index. Manual CLI generation rebuild remains an
explicit operator path; it does not run on GET or screen requests.

## Ports

`RequirementIndexProgressPort` carries lease-fenced derived batch progress. Existing index ports add
optional source pagination; AI queue ports add blocked-operation selection so unrelated jobs proceed.
`TokenCounterPort` supports explicit actual-model qualification independently of runtime budgets.

## Adapters

Memory/PostgreSQL progress adapters and migration 023; dedicated worker lifecycle/readiness; queue
gate; strict Google embedding count adapter; offline embeddings now support Arabic-only/punctuation
content without zero vectors. Concrete construction remains in the API composition root.

## API

- `GET /requirements/{id}/knowledge-index`: member-visible state and local progress.
- `POST /requirements/{id}/knowledge-index/retry`: member-authorized derived retry.
- Direct knowledge operations return mapped, retryable 503 while the corpus is pending.
- `/ready` includes Requirement worker health. Existing library APIs expose owner builds/activation.

## UI

Knowledge preparation notice polls with actor-scoped cache keys, shows completed/total passages,
explains failed/rebuild states and offers explicit retry. Existing review content stays available.
Impeccable and React guidance were applied to the incumbent UI. Desktop/390px captures were reviewed;
the initial capture revealed a missing shared button class, corrected before the final browser rerun.

## Business Rules

- Never publish partial vectors or a result whose Requirement changed during embedding.
- Lease expiry rejects a stale checkpoint; a new worker can resume saved batches after expiry.
- Model identities partition caches and generations. No model silently falls back to another.
- Three failures stop source retries; source edits or an explicit member retry make it eligible.
- A blocked first page must not starve later Requirements.
- Model-incompatible documents make search unavailable during coordinated maintenance. Every owner
  must approve/activate their own build. Rollback does not resurrect superseded citations.
- New runtime Requirement spans use budget units. Actual-model measurements live in separate
  evidence fields named `measured_model_tokens`.

## Tests

New tests cover partial invisibility, bounded batches, restart/cache reuse, source-change and lease
fencing, retry limits, fairness after 100 blocked sources, member authorization, queue waiting,
Unicode spans and malformed token counts. The shared two-owner switch/rollback contract runs in
memory and real PostgreSQL; live provider qualification is opt-in and never collected by pytest.
Frontend covers progress, retry and incompatible model states. Browser coverage includes actual
background readiness plus an explicitly mocked terminal provider failure/recovery state.

## Acceptance Criteria

- [x] Requirement indexing is independent of screening and suggestions.
- [x] Batches are bounded, resumable, fenced, and observable through API/browser.
- [x] Structured fixtures reconstruct selected reviewed rows and preserve exclusions.
- [x] Actual embedding-model token measurements and acceptance are recorded reproducibly.
- [x] Cross-owner switching/rollback is exercised with real providers and PostgreSQL contracts.
- [ ] Deployed production rollout, representative documents, operational load/restore and green CI.

## Validation Evidence

Executed in `C:/ai/projects/smb-ai-requirement-agent` on branch `refactor-ux`, 2026-09-22.
Runtime: `C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe`.
Every Python test command set `PYTHONPATH` to this checkout's `src`, `PYTHONUTF8=1`, and
`PYTHONIOENCODING=utf-8`. Database runs set `TEST_DATABASE_URL` to the disposable
`codex_document_knowledge_test_20260921` on `localhost:5432`, `hostaddr=127.0.0.1`.
`select current_database()` returned exactly that name before both full-suite runs.

Live evidence (synthetic text only):

```text
python -m tests.chunk_token_fixtures
Wrote 64 synthetic samples to docs/evaluation/chunk-token-fixtures.json
python -m smb_requirement_agent.interfaces.cli.llm qualify-tokens --config config/llm.yaml --samples docs/evaluation/chunk-token-fixtures.json --input-limit 2048
exit 0; 64 samples; 18–528 measured model tokens; all within limit; all embedded successfully
python -m tests.live_model_rollout --config config/llm.yaml --target-model gemini-embedding-2
exit 0; two owners/two documents; rollout and rollback passed
```

Evidence artifacts: `docs/evaluation/gemini-embedding-001-token-qualification-20260922.json`,
`docs/evaluation/embedding-rollout-qualification-20260922.json`, and versioned fixture JSON.
Regeneration tests verify fixture JSON equals actual reviewed chunk output. Neither live exercise
changed the application database, running model selection, historical publications or credentials.

Final executed gates and checks (supporting logs: `logs/chunk-index-*`):

```text
.venv/Scripts/python.exe -m pytest
1360 passed, 1 warning in 154.00s (0:02:34); PostgreSQL included; no skips
.venv/Scripts/python.exe -m ruff check .
FAIL: 72 inherited errors, all in .claude/skills/ui-ux-pro-max/scripts
.venv/Scripts/python.exe -m ruff format --check .
FAIL: core.py, design_system.py, search.py in that same skill directory;
3 files would be reformatted, 826 files already formatted
.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 399 source files
.venv/Scripts/lint-imports.exe
Contracts: 6 kept, 0 broken
.venv/Scripts/python.exe -m ruff check src tests scripts/evaluate_document_knowledge.py
All checks passed!
.venv/Scripts/python.exe -m ruff format --check src tests scripts/evaluate_document_knowledge.py
400 files already formatted

npm --prefix frontend test
Test Files 40 passed (40); Tests 270 passed (270); 32.34s
python scripts/dump_openapi.py
npm --prefix frontend run api:generate
npm --prefix frontend run api:check
PASS on retry; generated types match the sorted API snapshot
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend run build
PASS

SMOKE_PYTHON=C:/ai/projects/smb-ai-requirement-agent/.venv/Scripts/python.exe
SMOKE_API_PORT=8195 SMOKE_UI_PORT=4295 npm --prefix frontend run test:smoke -- requirement-indexing.spec.ts library-build.spec.ts reference-applicability.spec.ts
6 passed (46.1s), desktop and responsive/390px; unused ports verified
SMOKE_API_PORT=8197 SMOKE_UI_PORT=4297 npm --prefix frontend run test:smoke -- requirement-indexing.spec.ts
2 passed (9.6s), final rerun after shared-button class correction; unused ports verified

python -m pytest tests/integration -k "cross_owner or requirement_index_batches"
2 passed, 33 deselected, 1 warning in 3.49s (targeted, before full suite)
python -m pytest tests/unit/test_requirement_indexing.py tests/unit/test_embedding_token_qualification.py
21 passed, 1 warning in 6.74s (before full suite)
python -m pytest tests/unit/test_api_lifespan.py
4 passed, 1 warning in 0.06s (final worker-readiness assertion)
```

The full-suite warning is the inherited Starlette/AnyIO deprecation. Frontend tests emitted two
jsdom navigation notices; browser logs included Node color notices. Neither caused failed tests.
CI was not run or verified. Product checks are green; the two repository-wide Ruff gates are not.
The earlier mobile source-panel positioning failures were not repaired or requalified here.

### Failures and corrections during implementation

- Initial affected tests expected synchronous corpus indexing: 17 failures. Fixtures now explicitly
  drive the worker; the targeted workflow/lifecycle/API rerun passed 37 tests.
- The first complete backend run passed 1,336 tests, no skips, before all new tests were added.
- First new PostgreSQL restart test failed because Arabic-only fake embeddings were zero vectors.
  The fake now hashes Unicode words and guarantees a usable fallback; both new PostgreSQL tests pass.
- New-test typing found three fixture defects (view/entity variable, asserting a void return, and
  using an adapter-only checkpoint). Fixed using typed public use cases; their required impact
  acknowledgement was subsequently added. One frontend fixture needed numeric progress fields.
- Generating child-extraction fixtures from Python stdin failed under Windows multiprocessing.
  A guarded importable module fixed it; the failed probe was stopped without affecting app processes.
- Sorted OpenAPI regeneration hit a transient Node `UNKNOWN` file-open failure and exposed a stale
  generated type file; the generation/check rerun is recorded with final results.
- Automatic approval review rejected a proposed bulk migration marking all existing sources dirty.
  That command did not run. The delivered migration creates derived storage only; adoption uses
  source changes or an explicit configured-generation rebuild. No source rows were bulk rewritten.

## Follow-up fix — index-pending knowledge jobs are deferred, not failed (2026-09-24)

**Defect.** `IndexReadyJobQueue.claim_next` checked `ready()` and then claimed as two separate
steps. A Requirement created in between, whose automatic `screen_requirement_knowledge` job was
queued in that gap, let the worker claim the screen before the index caught up.
`require_index_current` then raised `KnowledgeIndexPendingError`, the job was marked failed, and
the UI showed "Screening requirement knowledge failed" until a manual Retry. This was observed
against `deploy/compose.production.yaml` (separate worker, PostgreSQL, fake providers). The first
automatic screen failed in 31 ms and the Retry succeeded seconds later. The same gap applied to any
source change anywhere, because the index check covers the whole portfolio. It also applied to
`suggest_clarification_answers`.

**Decision.** `ExecuteAiJob` owns the fix, not the gate. A re-check after claiming would only
narrow the window: a source can still change between that re-check and `require_index_current`.
The gate now reads as a hint that saves a pointless claim. Execution is the point that decides.

- Domain: `AiJobOperation.requires_current_index` names the two index-gated operations. The gate
  and the executor both read it. `AiJobStatus.holds_attempt` is true only for running and
  cancellation-requested jobs. `AiJob.defer(now)` returns a running job to `queued`. It gives back
  the attempt the claim added and clears the progress fields. It also clears `started_at` if no
  earlier attempt remains. Any other status is rejected.
- Application: if an index-gated operation raises `KnowledgeIndexPendingError`, the executor calls
  `_defer`. That records the deferred job with a fenced save under the claimed worker and attempt
  token. It sends no failure notification. If cancellation was requested, it finishes the
  cancellation instead. If the lease was lost, it raises `_LeaseLost` and writes nothing. For any
  other operation the error still produces an explicit failure.
- Ports and adapters: the `save_fenced` contract now reads "a job that no longer holds an attempt
  releases the lease". Before, only terminal states released it; now a deferred `queued` job does
  too. The in-memory and PostgreSQL adapters clear the job's worker, token and lease. PostgreSQL
  also clears the Requirement lease row in the same transaction. The old attempt token can no
  longer heartbeat or write. The next claim issues a new token.
- No hot loop: the indexer's `ready()` is `not pending_sources(1)`, the same check that raised. So
  the gate holds the deferred job until the index is current.
- Composition root: `Container.execute_ai_job` exposes the existing executor so tests can drive
  the interleaving deterministically. No API, OpenAPI or UI change.

**Tests.**
- `test_source_created_after_gate_check_requeues_screen_without_failing_or_consuming`: `ready()`
  returns true, then a Requirement is created before the claim. The claimed screen is deferred
  with attempt 0 and no failure or failure notification, and its old token is fenced. The gate
  withholds it until the index drains; it is then reclaimed with attempt 1 and succeeds. Against
  the previous executor this test fails with `FAILED`, which reproduces the production defect.
- Domain and in-memory store tests cover deferral, the fenced save and reclaiming.
- A PostgreSQL integration test checks that the Requirement lease is released at once and that a
  stale token cannot defer.

**Validation, 2026-09-24.** Run in the `eager-williams-70fc74` worktree with the repository
`.venv`, `PYTHONPATH=src` and `PYTHONUTF8=1`. `TEST_DATABASE_URL` pointed at a disposable
`pgvector/pgvector:0.8.6-pg16-trixie` container on `127.0.0.1:55499`, removed afterwards.

```text
python -m pytest                 1433 passed, 1 warning (PostgreSQL included; no skips)
python -m ruff check .           All checks passed!
python -m ruff format --check .  892 files already formatted
python -m mypy src tests         Success: no issues found in 448 source files
lint-imports                     Contracts: 6 kept, 0 broken
```

The fix has not been re-run against the reference deployment, and CI has not run.

## Deferred / Open

The complete document-knowledge enhancement remains open. Local synthetic qualification does not
prove representative extraction quality, semantic retrieval quality, production rollout readiness,
one-million-chunk/25-user performance, scanner/OCR deployment, restore recovery or green CI.
Repository-wide inherited Ruff failures and earlier mobile source-panel positioning remain tracked.
Existing clean Requirement indexes require adoption through a normal source change or explicit
rebuild; no production migration or model switch was performed. Nothing committed or pushed.
