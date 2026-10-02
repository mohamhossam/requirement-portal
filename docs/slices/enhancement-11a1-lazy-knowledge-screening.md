# Enhancement 11A.1 — Lazy Knowledge Screening and Restart-Storm Prevention

> Status: **complete locally; CI pending push**.

## Objective

Prevent API restarts and browser refreshes from recreating portfolio-wide or repeatedly failed
knowledge-screening work while preserving automatic screening for genuine evidence changes.

## User Outcome

The service restarts quickly without flooding the AI queue. Owners and assigned reviewers receive
one lazy screen when Knowledge or Confirm needs it, see whether work is queued/running/current, and
must deliberately retry a failed, cancelled, or anomalous terminal attempt.

## In Scope

- Worker-only restart recovery with no startup scheduling.
- Change-driven and lazy team-authorized screening.
- Evidence/trigger fingerprint idempotency across active and terminal attempts.
- User-origin manual retry priority and legacy automatic-queue cancellation.
- API, generated client, UI states, migration, tests, operational documentation, and ADR.

## Out of Scope

- Cancelling running jobs, deleting job history, or changing persisted Requirements/findings.
- Changing trusted-corpus membership, relationship classification, or suggestion automation.
- Increasing worker concurrency or provider context limits as a substitute for queue policy.

## Domain

- Reuse immutable `AiJob` status/origin/retry linkage, Requirement version, and evidence
  fingerprint concepts.
- Terminal attempts remain auditable; manual retry creates a new linked user-origin job.
- No infrastructure or provider concept is added to the Domain.

## Application Use Cases

- `EnsureKnowledgeScreen` requires current Requirement team membership and returns `current`,
  `scheduled`, `already_scheduled`, or `manual_retry_required`.
- `KnowledgeScreenScheduler` keeps genuine change triggers, derives fingerprints server-side,
  suppresses every equivalent terminal attempt, and includes linked trigger ID/version.
- `AiJobs.retry` keeps `retry_of_job_id`, treats the human action as user-originated, and permits
  explicit recovery of an anomalous successful knowledge job that produced no current screen.

## Ports

- `KnowledgeScreenSchedulerPort.ensure` exposes the four scheduling outcomes.
- `AiJobRepositoryPort.reserve_automatic` atomically returns an existing equivalent attempt or
  persists one new automatic attempt.

## Adapters

- The in-memory adapter reserves under its existing lock.
- PostgreSQL reserves under a transaction-scoped advisory lock for the Requirement/fingerprint.
- Migration `012` cancels only queued, automatic `screen_requirement_knowledge` rows and is
  repeat-safe.

## API

- Add authenticated, team-member-only
  `POST /requirements/{requirement_id}/knowledge-screen/ensure`.
- Return the ensure outcome and applicable job ID without accepting a client fingerprint.
- Retain existing AI-job retry endpoints and regenerate OpenAPI/TypeScript contracts.

## UI

- Knowledge and Confirm call ensure only for a required/stale review with no active screen and only
  for a current team member.
- A component mount issues one request per evidence fingerprint; rerenders do not loop.
- Queued, running, current, terminal/manual-retry, and provider-error states remain distinct.
- Confirmation stays disabled until the current screen is clear and findings are resolved.

## Business Rules

- Startup may recover durable queued/leased jobs but must create zero new jobs.
- Automatic eligibility requires a live nonduplicate Requirement, no current review, no active
  equivalent, and no terminal equivalent for the same fingerprint.
- Failed, cancelled, and succeeded-without-current-screen attempts require a human retry.
- A new evidence fingerprint is eligible independently of prior terminal attempts.
- User-origin jobs retain dispatch priority; clarification suggestions are unchanged.

## Tests

- Startup has no Requirement scan or scheduling side effect.
- Creation/change/analysis/clarification/intent/linked triggers remain idempotent.
- Current, active, failed, cancelled, anomalous-success, new-fingerprint, duplicate, and linked
  cases are covered.
- In-memory/API and PostgreSQL concurrent ensures create one attempt.
- Migration selection and repeat execution preserve every excluded job category.
- API covers authentication/team authorization and every ensure outcome.
- UI covers one lazy request, fingerprint change, queued/running/manual-retry/current states,
  explicit Retry, and confirmation gating.

## Acceptance Criteria

- [x] Restart creates no screening job and starts the durable worker only.
- [x] Genuine evidence changes still schedule one eligible automatic screen.
- [x] Page refresh or repeated ensure cannot retry a terminal fingerprint.
- [x] Manual Retry is user-originated, prioritized, and linked to its prior attempt.
- [x] Migration 012 cancels only queued automatic knowledge jobs.
- [x] API/UI/OpenAPI expose lazy screening without weakening confirmation gates.
- [x] Automatic clarification suggestions remain intact.

## Validation Evidence

- Focused backend tests — PASS, 44 tests.
- Focused frontend tests — PASS, 3 files and 14 tests.
- `TEST_DATABASE_URL=postgresql://smb:smb_dev@127.0.0.1:5432/smb_requirements pytest` — PASS, 646 tests.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 375 files formatted.
- `mypy src tests` — PASS, 302 source files.
- `lint-imports` — PASS, 2 contracts kept and 0 broken.
- PostgreSQL integration tests — PASS, 18 tests, including migration selection/idempotency,
  concurrent reservation, and rollback.
- `npm test -- --run` — PASS, 24 files and 118 tests.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run build` — PASS (non-blocking bundle-size advisory only).
- `npm run api:check` — PASS.
- `npm run test:smoke` on isolated ports — PASS, 16 Playwright cases across desktop and
  responsive Chromium, including one lazy ensure without a rerender loop.
- Operational verification — PASS: migration 012 is recorded, no queued automatic knowledge jobs
  remain, no API/UI worker was running during cleanup, and one pre-existing expired running job is
  preserved for normal lease recovery as designed.
- CI — pending push; local success is not CI authority.

## Deferred

- None. No roadmap field was dropped.
