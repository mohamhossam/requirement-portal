# ADR 0020 — Leased durable AI jobs and actor notifications

## Status

Accepted

## Context

Analysis, decomposition, Story proposal, quality, and review generation called
model providers inside HTTP requests. Navigation or a lost client connection
made progress invisible, users could submit duplicates, and failures had no
durable retry/cancel record. Multiple API replicas also need to avoid executing
the same job or concurrent model mutations for one Requirement.

## Decision

- Represent every model-backed action as a provider-neutral `AiJob` with a
  stable identity, explicit lifecycle, actor snapshot, command fingerprint,
  attempt history, failure category, and result links.
- Accept starts through one typed API and require an actor-scoped
  `Idempotency-Key`. Reuse equivalent active work and serialize execution per
  Requirement.
- Define application job repository/queue and notification ports. Use a
  thread-safe in-memory adapter offline and PostgreSQL rows leased with
  `FOR UPDATE SKIP LOCKED` in durable deployments.
- Run bounded in-process polling workers from the FastAPI lifespan. Workers
  heartbeat leases; an expired running lease is reclaimable after process loss.
- Keep existing synchronous endpoints during migration. The browser starts
  durable jobs for model-backed journeys and polls persisted state.
- Treat cancellation as cooperative. Queued jobs cancel immediately; running
  work rolls back at the next safe boundary and becomes cancelled without
  committing generated artifacts.
- Persist completion/failure notifications for the initiating actor. In-app
  notifications are always available; operating-system browser notifications
  require an explicit stored opt-in and browser permission.
- Persist Feature-level Story quality snapshots with a source fingerprint so
  asynchronous evaluations remain readable and become visibly stale when the
  Story set changes.

## Consequences

AI work survives navigation and PostgreSQL-backed process restarts, repeated
actions are safe, and users can inspect, cancel, retry, or return through result
links. The worklist's `reanalysing` state now comes from live durable job state.
No external message broker is required for the current deployment shape.

Provider calls occupy an in-process worker and an application transaction until
their generated changes and terminal job state can commit atomically. Worker
concurrency, polling, lease, and heartbeat values therefore require operational
tuning. A future dedicated worker service or broker can implement the existing
ports without changing the domain or HTTP contract.

## Alternatives Considered

- Keep synchronous requests and add a spinner: rejected because browser state
  cannot provide restart durability, idempotency, or reliable retry/cancel.
- Add Celery/Redis immediately: rejected because a second production service is
  unnecessary while PostgreSQL can provide safe leased claims at current scale.
- Allow independent parallel jobs for the same Requirement: rejected because
  analysis and generated aggregates share invariants and revision history.
- Deliver only browser notifications: rejected because permission may be
  denied and operating-system delivery is not a durable audit surface.

## Amendment — A capped number of attempts (2026-10-08)

Slice `fix-ai-job-trace-gaps` (G1). The text above stays as accepted; where it differs, this
amendment governs.

A lease that expires returns its job to the queue, and the next claim counts a new attempt. Until
now nothing bounded that loop: a job whose attempt reliably kills its worker (an out-of-memory
crash, a process killed by its host) was reclaimed forever, holding its Requirement's lease every
time and never telling its creator.

- `AI_JOB_MAX_ATTEMPTS` (default 3, minimum 1) caps the attempts one job may start. It is read
  only by the settings module and handed to `ExecuteAiJob` as a required keyword argument.
- `ExecuteAiJob` checks the cap after it has honoured a pending cancellation and before it
  dispatches anything. A claim whose `attempt_count` exceeds the cap ends at once as `failed`,
  with the code `attempts_exhausted`. No provider is called.
- The failure is `retryable`. A retry starts a new job with a fresh count, so the user, who can
  see the failure, decides whether to spend more attempts. The creator is notified as for every
  other failure.
- A deferred attempt (index pending, prior-art budget spent) is not consumed (`AiJob.defer`), so
  waiting never counts towards the cap. A cancellation request is still honoured before the cap
  is checked.

The PostgreSQL claim now also resets the attempt's progress (`phase`, `completed_units`,
`total_units`, `current_section_label`) and clears `failure`, as `AiJob.claim` always has in
memory (G7). A reclaimed job no longer shows the dead attempt's progress. No migration is needed.

## Amendment — Retry with backoff (2026-10-09)

Slice `production-hardening` (PR 2). The text above and the capped-attempts amendment stay as
accepted; where they differ, this amendment governs.

A provider rate limit or outage, or a platform service (ADR-0099) that cannot be reached, passes on
its own, but the attempt that met it failed the job at once and left the retry to its creator.

- **A transient failure requeues the job.** When an attempt fails with `model_rate_limit`,
  `model_unavailable` or `platform_service_unavailable` and attempts remain under
  `AI_JOB_MAX_ATTEMPTS`, the job returns to `queued` with `next_attempt_at` set, through the new
  `AiJob.requeue` transition. Unlike `defer`, the attempt stays spent, so retries count toward the
  cap. The attempt that reaches the cap fails with the outage's own code, retryable, and its
  creator is notified as before.
- **Timeouts and unusable output are not retried.** The call may already have been billed, and a
  second one is likely to fail the same way.
- **Backoff.** `AI_JOB_RETRY_FIRST_SECONDS` (30), doubling per attempt up to
  `AI_JOB_RETRY_MAX_SECONDS` (300).
- **Order holds.** No claim takes a job before its `next_attempt_at`, and while one waits, its
  Requirement's other jobs wait behind it (migration `202610091400_ai_job_retry_backoff.sql`, an
  additive column and index). Cancelling a waiting job works as for any queued job.
- **Visible.** The job API returns `next_attempt_at`; the job panel says the job will try again and
  when. `smb_ai_jobs_total` labels a requeued attempt `retrying` and a job failed at the cap
  `attempts_exhausted`, and the `AiJobsFailing` alert counts both failures.
