# Slice 8B — Collaborative Clarification and Analysis Audit

> Status: **complete locally; CI pending push**. Every roadmap field is
> implemented. Nothing was dropped from the approved plan.

## Objective

Make analysis clarification collaborative, concurrency-safe, and auditable
across immutable rounds while retaining synchronous generation.

## User Outcome

Owners and reviewers can ask, classify, assign, draft, and resolve stable
questions. Reviewers can inspect every analysis round, its source evidence and
provenance, and who supplied each answer.

## Domain

- Added analysis/question identities, ordered rounds, severity, blocker state,
  source, lifecycle status, optimistic version, assignment history, draft
  attribution, and final-answer attribution.
- Resolved and superseded questions are immutable. Saving/clearing a draft
  transitions between in-progress/open.
- New analyses carry complete provenance and source Requirement version;
  historical payloads may truthfully omit unavailable metadata.
- `HumanClarification` now links to a question and immutable actor/time snapshot.

## Application Use Cases

- `AnalysisCollaboration` generates and inspects rounds, reconciles stable
  questions, asks/classifies/assigns, saves drafts, resolves with immediate
  re-analysis, and supports the legacy batch endpoint.
- Provider work occurs before the transaction. Commit rechecks Requirement,
  analysis, and question versions and checkpoints the new breakdown revision.
- Confirmation reads active blocker designations; active non-blocking questions
  remain visible and flow into breakdown review.
- Requirement source edits supersede active questions. Team removal/transfer
  clears affected active assignments without deleting drafts or attribution.

## Ports

- Added `AnalysisAuditRepositoryPort` for insert-only round reads/appends and
  versioned question persistence.
- Extended analysis candidates with trusted adapter model/prompt metadata.
- Reused Requirement, analysis, access, actor-directory, document, clock,
  transaction, review, worklist, and revision ports.

## Adapters

- In-memory and PostgreSQL audit repositories implement ordered rounds and
  versioned question mutations.
- Migration `007_analysis_audit.sql` creates/backfills audit tables and installs
  immutable-round and terminal-question triggers.
- Fake, local, and OpenAI analysis adapters stamp model/prompt provenance after
  sanitizing provider content.
- Snapshot mapping round-trips new audit state and accepts pre-8B JSON.

## API

- Analysis responses preserve existing fields and add identity, round,
  provenance, source version, and canonical questions.
- Added round list/detail and question ask/classify/assign/draft/resolve routes.
- Existing analysis POST accepts `force=false`; repeat generation without force
  is `409`. The legacy batch route resolves uniquely matched current IDs and
  records the authenticated actor.
- Central error mapping covers missing rounds/questions, stale versions,
  invalid transitions, authorization, and provider failures.

## UI

- Clarification question cards display severity, blocker status, lifecycle,
  assignee, draft attribution, and answer attribution.
- Explicit Save draft and per-question resolution originally retained local
  text on conflicts/failures and disabled duplicate mutations. Enhancement
  8B.2 later replaced the browser's per-question model action with one stable-ID
  batch action while retaining the compatibility endpoint.
- Team members can use Ask someone and current Requirement owner/reviewer targets.
- Round history expands immutable content, provenance, Requirement version,
  document references, initial questions, drafts, and attributed answers.
- Re-analysis remains visibly synchronous; no polling or background state was added.

## Business Rules

- AI/migrated questions default medium/blocking; human questions default
  medium/non-blocking. Only attributed authorized humans can change policy.
- Owner/reviewers manage questions; assignment targets are current team members;
  assignee/owner answer. Legacy batch answers remain team-compatible.
- Only active blockers prevent owner confirmation. Stable question IDs drive
  review flags; blocker designation drives blocking versus warning severity.
- Explicit forced regeneration preserves exact active questions/drafts. Source
  edits supersede active questions and new analysis creates new identities.

## Tests

- Domain lifecycle, attribution, optimistic versions, terminal immutability,
  ordered rounds, provenance, snapshot compatibility, and adapter metadata.
- Application/API authorization, invalid targets, drafts, conflicts, immediate
  re-analysis, stable forced reconciliation, source supersession, non-blocking
  confirmation, compatibility resolution, provider rollback, and audit reads.
- PostgreSQL opt-in restart durability, immutable trigger, terminal trigger, and
  version conflict coverage.
- UI question actions, attribution/recovery rendering, Ask someone, and full
  round-history display; browser smoke workflow extends the owner/reviewer path.

## Acceptance Criteria

- [x] Every new analysis and question has stable identity and audit metadata.
- [x] Assignment, partial draft, classification, and terminal rules are enforced.
- [x] Resolution creates one new immutable round and provider failures lose no work.
- [x] Forced analysis and source-edit reconciliation preserve truthful history.
- [x] Worklist, confirmation, and breakdown review consume active stable questions.
- [x] API, browser UI, OpenAPI, TypeScript, migration, ADR, and docs are complete.

## Validation Evidence

- `.venv\Scripts\pytest.exe` — PASS: 467 passed, 8 skipped in 5.27s.
  The skipped tests are the opt-in PostgreSQL integration suite because
  `TEST_DATABASE_URL` is not configured; the suite now includes Slice 8B
  restart durability, version conflicts, and immutable audit triggers.
- `.venv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv\Scripts\ruff.exe format --check .` — PASS: 286 files already formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 236 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 181 files and 854 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run api:check` — PASS: generated OpenAPI TypeScript output has no
  drift. The existing Node `DEP0190` warning was emitted by the check script.
- `npm.cmd run lint` — PASS: ESLint clean.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS: 18 files, 80 tests in 6.59s.
- `npm.cmd run build` — PASS: 1,916 modules transformed; built in 330ms.
- `$env:SMOKE_API_PORT='8030'; $env:SMOKE_UI_PORT='4200'; npm.cmd run test:smoke`
  — PASS: 8 tests across desktop and responsive Chromium in 14.4s, including
  owner assignment of a reviewer, reviewer draft/resolution, a new immutable
  round, blocker reclassification, and owner confirmation.
- CI — NOT RUN for these uncommitted working-tree changes; pending push.

## Deferred

- Async jobs, retries, cancellation, polling, and notifications — Slice 8C.
- Formal backlog approval/comments — Slice 9.
- Activity projections and reporting — Slice 10A.
