# Enhancement 8B.1 — Business Need–Driven Intent Analysis

> Status: **complete locally; CI pending push**. Every roadmap field is
> implemented. Nothing was dropped from the approved plan.

## Objective

Let analysis start from a title and business need while keeping AI-inferred
outcomes, rules, and constraints explicitly governed by the Requirement Owner.

## User Outcome

An author may leave desired outcome blank and start analysis. The Owner sees one
editable outcome candidate and any suggested boundaries, can accept, edit, or
reject each proposal, and can confirm only after the business intent and blocker
questions are resolved.

## Domain

- Analysis eligibility now requires title and business need; desired outcome is
  optional source evidence.
- `IntentProposal` has stable identity, kind, original statement, rationale,
  optional success measures, status, optimistic version, and append-only
  attributed decisions.
- Decisions may be revised before confirmation and are immutable afterwards.
- Effective intent keeps source-backed content separate and projects only
  accepted/edited AI candidates into confirmed context.
- Confirmation requires no pending proposal, no active blocker, and one
  effective desired outcome.

## Application Use Cases

- `AnalysisCollaboration.decide_intent_proposal` applies owner authorization,
  proposal/version checks, transactional persistence, and revision checkpoints.
- Same-Requirement-version re-analysis carries terminal Owner decisions into
  the new round; source edits invalidate active intent with the rest of the
  derived analysis while preserving audit history.
- Epic, Feature, and Story generation add the effective outcome and accepted
  candidate rules/constraints to source-backed findings. Pending and rejected
  proposals are not supplied.

## Ports

- The provider-neutral `RequirementAnalysisCandidate` carries typed intent
  candidates.
- `RequirementAnalyzerPort.analyze` receives prior owner decisions without
  exposing provider SDK types.
- Existing analysis, audit, revision, activity, transaction, clock, identity,
  Requirement, and generation ports are reused.

## Adapters

- Fake, local, and OpenAI-compatible analyzers implement `analysis-v3` and
  normalize proposals before domain construction.
- Blank text, duplicates, malformed output, and numeric targets absent from the
  source are explicit provider-generation failures.
- Local analysis uses an 8,192-token context and 4,096-token output budget by
  default, reports output truncation explicitly, and reuses its HTTP connection
  for focused follow-up calls.
- The local adapter structurally requires usable findings and performs one
  focused outcome review when the broad response omits both an outcome proposal
  and its blocker question.
- Snapshot mapping round-trips proposals and every decision inside analysis
  JSON. Legacy payloads default to no proposals and retain existing outcomes.
- No relational database migration is required.

## API

- Requirement draft/create/update contracts continue accepting an optional
  `desired_outcome`.
- Analysis responses add effective outcome origin, accepted candidate rules and
  constraints, and complete proposal/decision history under `business_intent`.
- `PATCH /requirements/{requirement_id}/analysis/proposals/{proposal_id}` accepts
  a decision, optional edited statement/measures, and `expected_version`.
- Central error translation maps authorization to 403, missing resources to
  404, stale/confirmed transitions to 409, and invalid edits to 422.

## UI

- Intake labels desired outcome optional and uses “Save and analyse business
  need” as the primary action.
- Analysis displays the need-to-outcome trace, source/AI/Owner provenance,
  proposal rationale and decisions, and Owner-only Accept/Edit/Reject actions.
- Decided proposals render as settled evidence. Before final confirmation, the
  Owner must explicitly choose `Change decision` to revise one; redundant
  decisions are disabled, cancellation restores persisted content, and a
  failed save preserves the revision draft.
- Confirmation is visibly disabled with explanatory text while proposals or
  the effective outcome remain unresolved.
- Round history, revision comparison, and Activity expose intent generation and
  Owner decisions.

## Business Rules

- A desired outcome describes observable customer or business value, not a
  technical solution.
- The model may not invent numeric targets, regulations, eligibility policies,
  or system constraints. Missing evidence becomes a blocker question.
- Accepted AI content remains analysis context and never rewrites Requirement
  source fields.
- One outcome proposal is allowed per analysis round; alternatives require an
  Owner edit or a new round.

## Tests

- Domain transition, ownership, optimistic concurrency, confirmation,
  decision-history, and immutability coverage.
- Use-case/API carry-forward, source invalidation, status-code, activity,
  revision, and legacy compatibility coverage.
- Adapter normalization, duplicate/blank/malformed/provider-failure and
  invented-numeric-target coverage.
- PostgreSQL opt-in JSON round-trip coverage and OpenAPI snapshot/type generation.
- UI optional-outcome, proposal editing, provenance, and blocked-confirmation
  coverage, including settled decisions and explicit revision; the browser
  smoke journey covers analysis through Epic generation.

## Acceptance Criteria

- [x] Title and business need are sufficient to start analysis.
- [x] Source-backed findings and AI proposals remain distinct.
- [x] Every proposal requires an attributed Owner decision before confirmation.
- [x] Same-source re-analysis preserves decisions; source edits invalidate them.
- [x] Only effective confirmed intent crosses into downstream prompts.
- [x] API, browser UI, persistence, activity/revision, OpenAPI, ADR, and docs are complete.

## Validation Evidence

- `.venv\Scripts\pytest.exe` — PASS: 547 passed, 12 skipped in 10.59s.
  The skipped tests are the opt-in PostgreSQL integration suite because
  `TEST_DATABASE_URL` is not configured; that suite includes the new intent
  proposal and append-only decision JSON round trip.
- `.venv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv\Scripts\ruff.exe format --check .` — PASS: 342 files already formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 281 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 218 files and 1,115 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run api:check` — PASS: generated OpenAPI TypeScript has no drift.
  Node emitted its existing `DEP0190` warning.
- `npm.cmd run lint` — PASS: ESLint clean.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test -- --run` — PASS: 22 files, 92 tests in 7.86s.
- `npm.cmd run build` — PASS: 1,922 modules transformed; production bundle built.
  Vite emitted its existing large-chunk advisory.
- `$env:SMOKE_API_PORT='8032'; $env:SMOKE_UI_PORT='4202'; npm.cmd run test:smoke`
  — PASS: 12 tests across desktop and responsive Chromium in 1.1 minutes,
  including business need only → analysis → blocker resolution → Owner intent
  acceptance → confirmation → Epic generation.
- CI — NOT RUN for these uncommitted working-tree changes; pending push.

### Maintenance validation — 2026-09-05

- `.venv\Scripts\python.exe -m pytest` — PASS: 567 passed, 12 skipped, 1
  warning in 21.91s.
- `.venv-uv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv-uv\Scripts\ruff.exe format --check .` — PASS: 345 files already
  formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 281 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 218 files and 1,116 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd test -- --run` — PASS: 22 files, 109 tests.
- `npm.cmd run build` — PASS: 1,922 modules transformed; Vite emitted its
  existing large-chunk advisory.
- `npm.cmd run api:check` — PASS; Node emitted its existing `DEP0190` warning.
- CI — NOT RUN for local working-tree changes; pending push.

## Deferred

- No behavior is deferred from this enhancement.
- Approval and external publication behavior remain unchanged by design.
