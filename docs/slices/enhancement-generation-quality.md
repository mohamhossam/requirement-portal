# Enhancement — Quality and risks during generation

## Status
Implementation and automated regression checks are locally validated. Live local-model quality remediation remains open: the evaluator can still misjudge unsupported business behavior. CI for these uncommitted changes has not run; deployment remains separate.

## Objective
Consider dependencies, uncertainty, architecture and INVEST during generation, refine once,
and save the final candidates with their evidence before presenting the draft to a reviewer.

## User Outcome
Generated Features and Stories already carry architecture mappings and Story quality findings.
Remaining concerns are visible without a separate evaluation operation. Existing content changes
only through explicit generation/regeneration or application of a reviewed proposal.

## In Scope
- Feature generation; Story generation, set/single regeneration, and AI split/merge previews.
- One initial draft, at most one corrective pass, final assessment, atomic evidence persistence.
- Existing authorization, concurrency, cancellation, approval and provenance protections.
- All configured providers, offline fakes, API, browser, persistence and regression tests.

## Out of Scope
- Bulk improvement of existing work, automatic approval, external publication and production deployment.
- New business facts, invented squad ownership, changes to INVEST thresholds or catalogue matching rules.

## Domain
- Preserve six-criterion INVEST and existing severity/splitting rules.
- Store prepared proposal candidates and assessments with source/context fingerprints; older proposals
  remain readable and never acquire fabricated assessments.

## Application Use Cases
- Assess unsaved candidates with the existing semantic evaluator and deterministic Testable rule.
- Map unsaved candidates and feed concrete findings, SPIDR advice and the previous draft into one
  correction pass. Single regeneration and merge retain one output; split retains at least two.
- Save final candidates, mappings, quality and a provider-free review together. Provider exceptions
  abort the operation, while valid output with remaining quality failures is saved with concerns.
- Reuse current quality snapshots on review refresh; mark missing quality as blocking and unevaluated.
- Preview application uses the checked candidates; changed source sets or context require a new preview.

## Ports
- Typed GenerationGuidance extends existing generator operations with architecture matches,
  potential dependencies, ambiguities, concrete feedback, previous draft content and a required split minimum.
- Typed StoryQualityEvidence distinguishes source facts, human decisions, uncertainty and Feature scope;
  generation and explicit assessment share this input, and cache freshness includes its content.
- Existing quality, architecture, progress, transaction and repository ports remain the boundaries.

## Adapters
- Fake, local, OpenAI and OpenRouter paths accept guidance. Feature/Story prompts advance to v5; semantic assessment advances to story-quality-v3.
- Existing PostgreSQL JSON payloads retain checked proposal evidence; optional fields preserve legacy reads.
- Quality snapshots and reviews use existing repositories; no relational migration is required.
- PostgreSQL replacement moves existing positions aside transactionally to preserve retained IDs while
  inserting or reordering candidates. Checked proposal application advances the retained Story version.

## API
- Existing endpoints and job operations remain available.
- Proposal candidate responses add optional quality and architecture fields.
- No provider call occurs on review GET. Errors continue through centralized HTTP translation.

## UI
- Show preparing, generating, checking, refining and saving stages through the existing job feed.
- Display generated quality immediately. Manual/legacy content requires explicit assessment; mounting
  the Story list no longer schedules quality jobs.
- Label the review section Remaining concerns and show quality in AI proposal previews.

## Business Rules
- Never promote uncertainties to confirmed requirements or drop security/compliance/edge/NFR coverage.
- Real cross-system dependencies may remain after refinement; failed quality remains reviewable.
- Preserve human edits, approval checkpoints, identities and immutable history under existing rules.

## Tests
- Candidate refinement, bound enforcement, evidence propagation and unchanged read behavior.
- Provider failure, invalid payload, rollback, conflict/cancellation and proposal persistence.
- Frontend explicit reassessment, generation progress, and full browser generation/review flow.

## Acceptance Criteria
- [x] Generated content and saved assessments agree without additional browser evaluation actions.
- [x] Corrective generation is bounded to one pass and receives the actual draft/findings.
- [x] Unresolved concerns remain visible; failed operations preserve the previous saved state.
- [x] Proposal application preserves checked evidence and refuses changed generation context.
- [x] Backend, frontend, PostgreSQL and browser checks pass locally.
- [ ] CI confirms these changes after commit/push.

## Validation Evidence

The first record below covers the initial implementation. The regression follow-up later in this
section supersedes its test counts and records the subsequent live-provider probes.

Environment: Windows, repository Python 3.14.5, fake LLM providers. PostgreSQL tests use a newly
created, isolated database on the local pgvector PostgreSQL 17 service; it is dropped after the
run. No application database was truncated. No live provider or ADO calls were made.

| Command | Recorded result |
|---|---|
| `.venv/Scripts/python.exe -m pytest --tb=short` with `TEST_DATABASE_URL` set to the disposable database | `778 passed, 1 warning in 69.93s (0:01:09)`; includes all 22 PostgreSQL integration tests. |
| `.venv/Scripts/python.exe -m ruff check .` | `All checks passed!` |
| `.venv/Scripts/python.exe -m ruff format --check .` | `436 files already formatted` |
| `.venv/Scripts/python.exe -m mypy src tests` | `Success: no issues found in 343 source files` |
| `.venv/Scripts/lint-imports.exe` | `Contracts: 6 kept, 0 broken.` |
| `npm --prefix frontend run api:check` | Generated TypeScript contract matches the committed OpenAPI snapshot; exit 0. |
| `npm --prefix frontend run lint` | `eslint .` — exit 0. |
| `npm --prefix frontend run typecheck` | `tsc -b --pretty false` — exit 0. |
| `npm --prefix frontend run test -- --maxWorkers=2` | `Test Files 24 passed (24)` / `Tests 136 passed (136)` |
| `npm --prefix frontend run build` | `1923 modules transformed` / `built in 669ms` |
| `npm --prefix frontend run test:smoke` with isolated API/UI ports | `18 passed (1.6m)` across desktop and responsive Chromium. |
| `git diff --check` | No whitespace errors. |
| CI | Not run for the uncommitted working tree. No commit or push was performed. |

Focused regression run: `tests/unit/test_generation_checks.py` — `10 passed`.
The browser journey explicitly asserts that no `evaluate_feature_quality` or
`generate_breakdown_review` job is submitted between draft generation and opening Remaining concerns.

Intermediate failures resolved: refresh tests assumed no saved review existed; OpenAPI needed
regeneration; one UI file needed UTF-8 normalization; PostgreSQL split application exposed a
unique-position collision; a browser locator targeted a changing first row rather than the
specific Feature. Existing dependency deprecation and bundle-size warnings remain non-failing.

Raw local output is retained in ignored `logs/generation-*.txt`; browser artifacts are in
`frontend/test-results/`. The final suite output is recorded below.

```text
.venv/Scripts/python.exe -m pytest --tb=short
778 passed, 1 warning in 69.93s (0:01:09)
```

## Regression Follow-up — 11 September 2026

The reported local-model run used `story-v4`; it did execute an initial assessment and correction.
The correction largely repeated the first draft. Both drafts invented an approval step, attack
signatures and a notification target absent from the confirmed business input. The semantic
review also contradicted itself about security value and nonexistent sibling dependencies.

Retained changes:
- Separate the application correction task from catalogue guidance, diagnostics and quoted AI drafts.
- Make source facts, human decisions and uncertainty available to all semantic assessment paths.
- Bind quality/review freshness to the same business evidence; keep older snapshots readable and stale.
- Require populated Story and acceptance-criteria arrays in provider schemas. Keep content cleaning.
- Reject a correction returning one oversized Story after a required split; retain single/merge cardinality.
- Clarify the INVEST rubric without changing criteria or thresholds; generate the evidence message before
  its boolean verdict. Preserve missing policy decisions rather than prescribing made-up business answers.

| Command | Actual output |
|---|---|
| `.venv/Scripts/python.exe -m pytest --tb=short` with a newly created disposable PostgreSQL database | `784 passed, 1 warning in 88.87s (0:01:28)`; database `smb_generation_test_e76a0d3dbf97` removed afterward. |
| `.venv/Scripts/python.exe -m pytest tests/unit/test_generation_checks.py tests/unit/test_story_adapters.py tests/unit/test_story_quality.py --tb=short` | `39 passed, 1 warning` on the final retained correction changes. |
| `.venv/Scripts/python.exe -m ruff check .` | `All checks passed!` |
| `.venv/Scripts/python.exe -m ruff format --check .` | `436 files already formatted` |
| `.venv/Scripts/python.exe -m mypy src tests` | `Success: no issues found in 343 source files` |
| `.venv/Scripts/lint-imports.exe` | `Contracts: 6 kept, 0 broken.` |
| `npm --prefix frontend run api:check`, `lint`, `typecheck` | Each exited 0. |
| `npm --prefix frontend run test -- --maxWorkers=2` | `Test Files 24 passed (24)` / `Tests 136 passed (136)` |
| `npm --prefix frontend run build` | `built in 813ms`; existing large-bundle warning remains. |
| `npm --prefix frontend run test:smoke` on isolated ports 18911/18912 | `18 passed (1.6m)` |
| Local app restart using `start.ps1 -Provider local -DebugTrace` | API and UI returned 200. Original reported Story content fingerprint unchanged. Older quality/review snapshots correctly report `fresh: false`. |
| CI | Not run for the uncommitted/unpushed working tree. |

The first browser run passed 17/18 and recorded a fetch failure during a development persona switch.
The isolated responsive scenario passed, followed by the complete 18-scenario rerun. No product/test
logic was changed to conceal that failure. Logs are in ignored `logs/generation-fix-*.txt`.

### Live-model limitation — still open

Isolated in-memory probes used the same `smb-qwen3-vl:8b-16k` model and confirmed source as the reported
case. Source-aware prompts and structurally valid output do not guarantee semantic correctness:
this model still sometimes adds unsupported security behavior or calls it estimable. A controlled
replay with a stronger experimental forced-spike instruction over-expanded the draft to ten Stories,
with remaining failure counts `[3, 4, 4, 3, 4, 3, 3, 2, 0, 3]`. That experimental forced-spike instruction
was removed; it is not part of the retained implementation. These probes are not reported as a quality
success. The source itself still says audit criteria are unspecified; a question requesting detection
and suspicious-input behavior has been raised with the user. Existing saved drafts were not regenerated.

Live responses, prompts and the controlled replay remain in ignored `logs/generation-fix-*-result.json`
and trace files. One initial probe accidentally used the environment's OpenRouter setting and returned
429/502; subsequent probes explicitly selected the local provider used by the reported run. No ADO
calls or backlog publication occurred. Production release prerequisites and CI remain outstanding.

## Deferred
Production release prerequisites remain: CI for the delivered change, maintenance window,
backup/restore rehearsal and deployment. No implementation scope was dropped.


## Changed Files

- `ROADMAP.md`
- `WORKSPACE.md`
- `docs/architecture/adr-0015-semantic-story-quality-boundary.md`
- `docs/architecture/adr-0016-deterministic-architecture-knowledge-mapping.md`
- `docs/architecture/adr-0017-durable-breakdown-review-snapshot.md`
- `docs/architecture/adr-0041-generation-time-quality.md`
- `docs/slices/enhancement-generation-quality.md`
- `frontend/openapi.json`
- `frontend/src/api/schema.d.ts`
- `frontend/src/features/jobs/AiJobStatusPanel.test.tsx`
- `frontend/src/features/jobs/AiJobStatusPanel.tsx`
- `frontend/src/features/review/BreakdownReviewPanel.test.tsx`
- `frontend/src/features/review/BreakdownReviewPanel.tsx`
- `frontend/src/features/stories/StoryList.test.tsx`
- `frontend/src/features/stories/StoryList.tsx`
- `frontend/src/features/stories/StoryProposalPanel.tsx`
- `frontend/tests/review-flow.spec.ts`
- `src/smb_requirement_agent/application/ports/feature_generator.py`
- `src/smb_requirement_agent/application/ports/generation_guidance.py`
- `src/smb_requirement_agent/application/ports/story_generator.py`
- `src/smb_requirement_agent/application/ports/story_quality_evaluator.py`
- `src/smb_requirement_agent/application/use_cases/breakdown_review.py`
- `src/smb_requirement_agent/application/use_cases/generate_features.py`
- `src/smb_requirement_agent/application/use_cases/generation_checks.py`
- `src/smb_requirement_agent/application/use_cases/story_quality.py`
- `src/smb_requirement_agent/application/use_cases/story_workflow.py`
- `src/smb_requirement_agent/domain/story/entities.py`
- `src/smb_requirement_agent/infrastructure/llm/fake_feature_generator.py`
- `src/smb_requirement_agent/infrastructure/llm/fake_story_generator.py`
- `src/smb_requirement_agent/infrastructure/llm/fake_story_quality_evaluator.py`
- `src/smb_requirement_agent/infrastructure/llm/local_feature_generator.py`
- `src/smb_requirement_agent/infrastructure/llm/local_story_generator.py`
- `src/smb_requirement_agent/infrastructure/llm/local_story_quality_evaluator.py`
- `src/smb_requirement_agent/infrastructure/llm/openai_feature_generator.py`
- `src/smb_requirement_agent/infrastructure/llm/openai_story_generator.py`
- `src/smb_requirement_agent/infrastructure/llm/openai_story_quality_evaluator.py`
- `src/smb_requirement_agent/infrastructure/llm/prompts/feature_prompt.py`
- `src/smb_requirement_agent/infrastructure/llm/prompts/generation_guidance.py`
- `src/smb_requirement_agent/infrastructure/llm/prompts/story_prompt.py`
- `src/smb_requirement_agent/infrastructure/llm/prompts/story_quality_prompt.py`
- `src/smb_requirement_agent/infrastructure/llm/schemas/story_quality_schema.py`
- `src/smb_requirement_agent/infrastructure/llm/schemas/story_schema.py`
- `src/smb_requirement_agent/infrastructure/persistence/postgres_repositories.py`
- `src/smb_requirement_agent/infrastructure/persistence/snapshot_mapper.py`
- `src/smb_requirement_agent/interfaces/api/container.py`
- `src/smb_requirement_agent/interfaces/api/routes/story.py`
- `src/smb_requirement_agent/interfaces/api/schemas/story.py`
- `tests/integration/test_postgres_persistence.py`
- `tests/unit/test_approval_workflow_api.py`
- `tests/unit/test_breakdown_review.py`
- `tests/unit/test_feature_use_cases.py`
- `tests/unit/test_generation_checks.py`
- `tests/unit/test_story_adapters.py`
- `tests/unit/workflow_helpers.py`
