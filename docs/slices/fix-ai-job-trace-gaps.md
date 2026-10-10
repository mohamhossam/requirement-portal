# Fix — AI job trace gaps

## Objective

Close seven gaps found by tracing one AI job from the browser click to its finished result
(`POST /requirements/{id}/ai-jobs` → `AiJobs.start` → worker claim → `ExecuteAiJob` → notification).
This is corrective work on Slice 8C (`slice-08c-async-ai-jobs-notifications.md`, ADR-0020), approved
by the owner on 2026-10-08 as a seven-gap plan. It is not a new roadmap slice.

## User Outcome

- A job whose worker keeps dying ends as a visible, retryable failure instead of being claimed
  forever, and its creator is told.
- A reclaimed job shows its new attempt's progress, not the dead attempt's.
- Asking for an analysis that can only fail (one already exists and *Start a new analysis* was not
  chosen, or the Requirement is incomplete) is refused at once, with the same 409 or 422 as the
  direct route, instead of queueing a job that fails a moment later and sends a failure notice.
- A page holding an out-of-date or missing context token refreshes itself and asks the person to try
  again, instead of sending a request the server can only refuse.
- Trying a start again after a lost response (network failure, 5xx) replays the first request, so
  no second job is queued.
- Both Analyse buttons say what an incomplete Requirement still needs before anyone clicks.

## In Scope

| Gap | Where | Change |
|---|---|---|
| G1 | `workflows/application/use_cases/ai_job_execution.py` | `ExecuteAiJob` takes a required keyword-only `max_attempts`; after the cancellation check, a claim with `attempt_count > max_attempts` finishes as `failed`, `attempts_exhausted`, retryable, without dispatching. `AI_JOB_MAX_ATTEMPTS` (default 3, minimum 1). |
| G2 | `analysis/application/use_cases/analysis_collaboration.py`, `workflows/application/use_cases/ai_jobs.py` | The active/conflict/eligibility checks of `_generate` become the public `require_can_generate(requirement_id, *, force)`. `AiJobs` takes a required `analysis: AnalysisCollaboration` and calls it for `analyse_requirement`, after the idempotency replay and before `find_active_equivalent`. |
| G3 | `frontend/src/app/workspaceInvalidation.ts`, `features/jobs/RequirementJobsProvider.tsx` | `contextTokenKeys(id, input)`; `startJob` refreshes those reads and throws "This page was out of date and has been refreshed. Try again." when the token is blank, without sending the request. |
| G4 | same, plus `app/NewRequirementPage.tsx` | On an `ApiError` 409, `startJob` refreshes the token's reads and rethrows. The new-requirement *Retry analysis* always re-reads the Requirement first. |
| G5 | `frontend/src/app/requirement/AnalysisView.tsx` | Both Analyse buttons get `blockedReason` "Still needed: …" from `analysis_eligibility.missing_fields`. |
| G6 | `frontend/src/features/jobs/startKeys.ts` (new) | `createStartKeys()`: one Idempotency-Key per start input (`JSON.stringify(input)`), kept after a status-0 or 5xx error, forgotten after a success or a 4xx. Used by `startJob` (an explicit key still wins) and by `NewRequirementPage` through a `useRef`. |
| G7 | `jobs/infrastructure/postgres_ai_jobs.py` | `claim_next` resets `phase` (`preparing_analysis` for analyser operations, bound as `::text[]`, else `running`), `completed_units=0`, and `total_units`, `current_section_label` and `failure` to NULL. `cancellation_requested` rows are unchanged. No migration. |

## Out of Scope

- Refusing other generation operations (Epic, Features, Stories) before enqueue. See Deferred.
- Back-off between reclaims, or a cap on how often one Requirement's lease may be reclaimed.
- Any change to the job HTTP contract or the OpenAPI document. Every status these changes return
  was already catalogued (`requirement_analysis_conflict` 409, `requirement_analysis_ineligible`
  422).
- The user's local edit to `deploy/demo.env.example`, which stays on their machine.

## Exception to CLAUDE.md's presentation-only rule

CLAUDE.md limits frontend changes to presentation during the UI redesign. **G3, G4 and G6 change
frontend logic** (`RequirementJobsProvider.startJob`, `workspaceInvalidation.ts`, the new
`startKeys.ts`, and `NewRequirementPage`'s retry). The owner approved this on 2026-10-08 as a
labelled exception for this fix only, because each gap makes the browser send a request that can
only fail or that duplicates work, and no presentation change can prevent that. G5 is presentation
only. No other hook, service, query or API call was changed, and the exception sets no precedent
for the redesign.

## Domain

No change. `AiJob.claim` already reset progress in memory; G7 makes PostgreSQL match it.
`AiJobFailure` already carries `retryable`.

## Application Use Cases

- `ExecuteAiJob` — new required keyword-only `max_attempts`; the cap check (G1).
- `AnalysisCollaboration.require_can_generate` — new public method; `_generate` calls it (G2).
- `AiJobs` — new required constructor argument `analysis`; `_start` calls
  `require_can_generate` for `analyse_requirement` with `force` from `command.arguments` (G2).

## Ports

No change.

## Adapters

- `PostgresAiJobStore.claim_next` — the reset above (G7).
- Settings: `AI_JOB_MAX_ATTEMPTS` in `options.py`, `settings.py` and `settings_validation.py`;
  documented in `.env.example` and `WORKSPACE.md` (G1).
- Composition (`interfaces/api/composition/jobs.py`): `max_attempts=settings.ai_job_max_attempts`
  and `analysis.analysis_collaboration`.

## API

No contract change. `POST /requirements/{id}/ai-jobs` for `analyse_requirement` can now answer 409
(analysis exists, no `force`) or 422 (ineligible) directly, as the synchronous analysis route
already did. A replayed Idempotency-Key still returns its original job before any check runs.

## UI

- Requirement workspace, Clarify: *Analyse this requirement* and *Start a new analysis* are
  `aria-disabled` and described by "Still needed: …" while the Requirement is ineligible (G5).
- Any job start with a blank context token, or refused with 409, refreshes the page's reads; the
  blank case shows "This page was out of date and has been refreshed. Try again." (G3, G4).
- New requirement: *Retry analysis* re-reads the Requirement and replays a lost start (G4, G6).

## Business Rules

- An attempt that a pending cancellation covers is cancelled, never failed for exhaustion.
- A deferred attempt (index pending, prior-art budget spent) is not consumed, so waiting never
  counts towards the cap.
- `attempts_exhausted` is retryable: a retry is a new job with a fresh count, chosen by a person.

## Tests

- `tests/unit/workflows/test_ai_job_execution.py::test_a_job_whose_worker_keeps_dying_fails_once_its_attempts_are_spent`
  — failed, `attempts_exhausted`, retryable, provider never called, creator notified.
- `tests/unit/jobs/test_ai_jobs.py::test_re_analysis_is_refused_before_enqueue_unless_forced` —
  409 with no job queued, a replayed key returns the original job, `force` returns 202.
- `tests/unit/jobs/test_ai_jobs.py::test_analysis_of_an_ineligible_requirement_is_refused_before_enqueue`
  — 422, no job queued.
- `tests/unit/test_settings_and_container.py` — `AI_JOB_MAX_ATTEMPTS` default, read, and rejection
  of 0 and non-numeric values.
- `tests/integration/test_postgres_ai_job_queue.py::test_a_claim_and_a_reclaim_start_the_attempt_with_no_progress`
  — both phases; fails against the previous SQL (checked).
- `tests/architecture/test_provider_rate_limit.py` — the job list, read and cancellation routes are
  listed as not provider-calling: `AiJobs` now holds `AnalysisCollaboration`, which the
  reachability check sees, but only to refuse a start.
- Frontend: `RequirementJobsProvider.test.tsx` (blank token, 409, key reuse and reset, explicit
  key), `RequirementPage.test.tsx` (G5 on both buttons, blank token, 409),
  `NewRequirementPage.test.tsx` (retry re-reads and replays the key),
  `workspaceInvalidation.test.ts` (`contextTokenKeys`). Every test that pins `startAiJob`'s
  arguments now expects `expect.any(String)` for the key.

## Acceptance Criteria

- [x] A job past `AI_JOB_MAX_ATTEMPTS` fails as `attempts_exhausted`, retryable, and is notified.
- [x] PostgreSQL claim and reclaim reset progress and failure.
- [x] An analysis start that can only fail is refused before enqueue with 409 or 422.
- [x] The browser never sends a blank context token, and refreshes after a 409.
- [x] A start retried after status 0 or 5xx reuses its Idempotency-Key.
- [x] Both Analyse buttons explain ineligibility.
- [x] Five backend gates and the frontend test, lint, typecheck, build and api:check are green.

## Validation Evidence

Run on 2026-10-08 against the branch head, with `TEST_DATABASE_URL` pointing at a local
PostgreSQL 16 with pgvector, as CI runs it.

Backend (Python 3.13 virtualenv from `uv sync --locked --extra dev`):

- `pytest` — PASS: `1878 passed in 263.85s (0:04:23)`, PostgreSQL integration tests included.
- `ruff check .` — PASS: `All checks passed!`
- `ruff format --check .` — PASS: `1236 files already formatted`
- `mypy src tests` — PASS: `Success: no issues found in 678 source files`
- `lint-imports` — PASS: `Contracts: 42 kept, 0 broken.`

Frontend (`cd frontend`):

- `npm test` on Node 24 (CI's version) — PASS: `Tests  512 passed (512)`.
- `npm test` on Node 22 — `Tests  1 failed | 511 passed (512)`. The one failure is
  `src/api/client.test.ts` "downloads an authenticated export using the server filename"
  (`object.stream is not a function`), which fails identically on the unchanged base commit.
- `npm run lint` — PASS (exit 0, no findings).
- `npm run typecheck` — PASS (exit 0).
- `npm run build` — PASS: `✓ built in 1.55s`.
- `npm run api:check` — PASS (exit 0): the committed OpenAPI types are current.

Fix-specific: the new PostgreSQL claim test fails against the previous `claim_next` SQL (both
parametrised cases) and passes with G7.

## Deferred

- **Refusal before enqueue for the other generation operations.** G2 covers
  `analyse_requirement` only, as planned. `generate_epic`, `generate_features` and the Story
  operations can still queue a job that fails on a conflict the start could have seen (for
  example an existing Epic without `force`). The same `require_can_generate` shape would serve
  them; carry it if those failures show up in use. *(2026-10-09: carried for Epic, Features
  and first Stories by production hardening PR 4b, ADR-0105.)*
- **Back-off between reclaims.** A dying job is now bounded, but its attempts run back to back.
- **Frontend pre-existing failure on Node 22.** `src/api/client.test.ts` ("downloads an
  authenticated export…") fails on Node 22 with or without this change; it passes on Node 24,
  which CI uses. *(2026-10-10: closed by production hardening PR 12. The test's response
  body is now a string, so it passes on Node 22 too, and `frontend/package.json` declares
  `engines.node >=24`, with a `.nvmrc`.)*
