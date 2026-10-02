# ADR 0030 — Lazy knowledge screening and restart-safe recovery

## Status

Accepted

## Context

ADR-0027 scheduled an idempotent portfolio backfill during every API startup. Active-equivalent
deduplication prevented two queued copies at once, but it did not remember terminal attempts.
Consequently, failed or cancelled screens were recreated after every restart. A large portfolio
could fill the durable queue with slow automatic model calls, delay user work, and make API startup
perform many database operations unrelated to serving requests.

## Decision

API startup starts the durable worker and creates no new AI jobs. Existing queued work and expired
leases remain the worker's recovery responsibility.

Knowledge screening stays automatic after genuine Requirement and trusted-evidence changes. The
scheduler atomically reserves at most one attempt for the current evidence/trigger fingerprint.
An active equivalent is reused; a terminal equivalent requires explicit human retry. A new
evidence fingerprint is independently eligible. Related-Requirement scheduling includes the
triggering Requirement identity and version so a real linked change is distinct without weakening
per-Requirement worker serialization.

An owner or assigned reviewer entering Knowledge or Confirm may call an idempotent ensure use case.
It returns whether the screen is current, newly scheduled, already active, or needs manual retry.
Page refresh never converts a terminal attempt into a new automatic attempt. A manual retry is a
user-origin job, links to the prior attempt, and receives interactive queue priority.

Migration `012_cancel_queued_automatic_knowledge_screens.sql` is an operational cleanup applied
with workers stopped. It cancels only queued automatic knowledge-screen jobs; it does not delete
jobs or change running/user/suggestion work, screens, findings, Requirements, or decisions.

This ADR supersedes ADR-0027 only for startup portfolio backfill and automatic retry after terminal
attempts. ADR-0027's trust, retrieval, evidence, and human-decision boundaries remain accepted.

## Consequences

Restart time and queue size no longer scale with the Requirement portfolio. Failed work remains
visible and stable until a person chooses Retry, while meaningful source changes still receive a
new screen. The scheduler and durable job adapter now share an atomic reservation contract, and
operators must apply migration 012 before the first rollout restart to clear legacy queued
automatic work.

## Alternatives Considered

- Keep startup backfill and only prioritize user jobs: rejected because automatic work still
  consumes model capacity and database time after every restart.
- Retry failed screens on page entry: rejected because refresh would recreate the same storm at a
  smaller scope and obscure persistent provider/configuration failures.
- Delete queued automatic jobs: rejected because cancellation preserves audit history and explains
  why a manual retry is required.
- Cancel running jobs in migration: rejected because forced interruption risks duplicate provider
  work; lease recovery already governs abandoned running attempts.
