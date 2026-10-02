# Enhancement 11B.1 — Automatic Dual-Source Clarification Suggestions

> Status: **complete locally; CI pending push**.

## Objective

Automatically generate and progressively display up to three supported answers for every active
clarification question, with source labels that distinguish unconfirmed current analysis from
trusted cross-Requirement knowledge, while preserving deliberate human submission.

## Roadmap Scope Check

| Roadmap field | Delivery |
|---|---|
| Domain | Unconfirmed current-analysis evidence kind and citation-derived suggestion source. |
| Application | Transactional/idempotent automatic scheduling, explicit worker path, dual evidence validation and staleness. |
| Ports | Automatic scheduling port and dual-source focused suggester signature. |
| Adapters | Versioned dual-source fake, OpenAI, and local prompts/adapters; existing persistence reused. |
| API | Additive `source` response field; existing GET and AI-job contracts retained. |
| UI | Automatic/progressive loading, source badges, empty/failure states, refresh, editable selection. |
| Tests | Scheduling, evidence boundaries, citations, source derivation, staleness, authorization, transactions, API/UI/browser and gates. |

Nothing in the Enhancement 11B.1 roadmap entry is dropped.

## Behavior

- Persisting an analysis/re-analysis round schedules one active-equivalent-safe automatic job per
  active retained, replaced, newly generated, or human-authored question.
- Current-analysis evidence contains only known facts, business rules, and constraints from the
  current round and remains visibly unconfirmed. Uncertainty categories cannot support an answer.
- Trusted evidence continues to come from accessible current chunks belonging to other
  Requirements. The two evidence collections remain separate at the LLM boundary.
- Every provider citation must resolve to a supplied current or trusted chunk. Source is derived
  from validated citation ownership and each ranked result contains no more than three suggestions.
- Provider prompt version `clarification-suggestions-v3` identifies supplied evidence with compact,
  positive sequence numbers. The adapter maps those numbers back to immutable chunk IDs before the
  Application validates them, avoiding unreliable verbatim reproduction of SHA-256 identifiers
  without weakening the grounding boundary.
- Question edits/replacement, current-analysis changes, and cited trusted-knowledge changes hide
  stale suggestions. Invalid generation cannot overwrite a prior valid set.
- An empty successful set displays “No supported answer found.” A missing set after job failure is
  unavailable and retryable. Analysis review itself remains available.
- Selecting a suggestion fills editable answer text and retains optional provenance. Only the
  existing human resolve/re-analyse action confirms it.
- User-originated analysis and review jobs are dispatched before automatic knowledge backfill,
  with FIFO ordering retained within each origin. The UI distinguishes queued work from work that
  a model is actively processing.

## Validation Evidence

- `TEST_DATABASE_URL=postgresql://smb:smb_dev@127.0.0.1:5432/smb_requirements pytest -q` — PASS, 634 tests; includes PostgreSQL compatibility, transactional rollback, startup lifecycle, and user-priority dispatch.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 365 files formatted.
- `mypy src tests` — PASS, 296 source files.
- `lint-imports` — PASS, 2 contracts kept and 0 broken.
- `npm test -- --run` — PASS, 23 files and 114 tests.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run build` — PASS (non-blocking bundle-size advisory only).
- `npm run api:check` — PASS.
- `npm run test:smoke` on isolated ports — PASS, 14 Playwright cases across desktop and responsive Chromium; automatic suggestion display is exercised without a manual first click.
- CI — pending push; local success is not CI authority.

### Defect correction — 2026-09-07

- `pytest -q` — PASS, 648 collected; 630 passed and 18 PostgreSQL tests skipped because
  `TEST_DATABASE_URL` was not configured.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 376 files formatted.
- `mypy src tests` — PASS, 303 source files.
- `lint-imports` — PASS, 2 contracts kept and 0 broken.
- Configured local Qwen adapter probe — PASS; two numbered citations mapped back to the exact
  supplied current-analysis and trusted-knowledge chunk IDs.

### Defect correction — 2026-09-10

- Local knowledge screening and clarification suggestions now reserve at most 2,048 output
  tokens. Their bounded schemas retain sufficient response space while a configured 16K context
  can carry the ranked evidence that previously failed before the provider call when the global
  8K generation allowance left only 8K for input.
- Domain, Application, Ports, API, and UI contracts are unchanged; this is confined to the local
  infrastructure adapters. No roadmap field is dropped.
- `pytest tests/unit/test_requirement_knowledge_adapters.py -q` — PASS, 5 tests including a
  prompt requiring more than half of the 16K context.
- `pytest -q` — PASS; PostgreSQL-dependent tests skipped because `TEST_DATABASE_URL` was not set.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 429 files formatted.
- `mypy src tests` — PASS, 339 source files.
- `lint-imports` — PASS, 6 contracts kept and 0 broken.

## Architecture Impact

ADR-0028 supersedes the on-demand/trusted-only portion of ADR-0027. Concrete job storage and LLM
adapters remain selected only in the composition root; Application owns orchestration and source
validation, and Domain owns the deterministic source classification.

## Deferred / Open

- No auto-selection, auto-submission, general-web evidence, or new confidentiality model.
- CI remains pending until the branch is pushed.
