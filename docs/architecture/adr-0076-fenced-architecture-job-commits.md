# ADR 0076 — Architecture job attempts commit only while they hold the lease

## Status

Accepted. Amends ADR-0068 (architecture jobs): the lease model is unchanged;
who renews it and what a commit checks are new.

## Context

ADR-0068 gave architecture jobs leases, bounded attempts and attempt-aware
heartbeats. Two gaps remained:

- **Double writes.** An attempt whose heartbeat failed stopped renewing but
  kept working. Once its five-minute lease expired, another worker could
  reclaim the job and run it again. Only `finish` checked the attempt, so the
  stale attempt's mapping or index writes still landed. Its conflict with the
  new attempt then marked the job **failed**, even though the work was done.
- **Threading and error codes.** The application use case owned the heartbeat
  thread, and it recorded failures as raw exception class names instead of the
  public error codes AI jobs use.

## Decision

- `ArchitectureJobs.execute_claimed` runs one claimed attempt. Just before each
  write, it renews the lease inside the commit:
  - inside the mapping's commit transaction;
  - before the index is stored;
  - before the release is marked built.

  The attempt number is the fencing token. A successful renewal proves no one
  has reclaimed the job and holds it for another five minutes, far longer than
  the commit takes. A failed renewal raises `ArchitectureJobLeaseLostError`,
  and the attempt stops without writing and without recording an outcome.
- `ArchitectureJobWorker` (infrastructure) owns the renewal thread. Renewal
  errors are logged and retried until the lease would lapse, because the
  commit-time renewal is what decides whether the attempt may write. The
  inline path, `run_once`, needs no thread, since it runs inside the starting
  request.
- Failures are recorded as `describe_public_error(exc).code`, for example
  `architecture_knowledge_conflict`, or `internal` for an unexpected error.
  Provider and internal details never reach the job record.

## Consequences

- A stalled attempt cannot overwrite, or fail, the attempt that replaced it.
- The fence depends on the repositories' `heartbeat` refusing a stale attempt
  number, which both the in-memory and PostgreSQL adapters do. Leases are
  timed with the application clock, so hosts need synchronised clocks. That was
  already true for AI job leases.
- Recorded error codes changed from class names (`KnowledgeConflictError`) to
  public codes (`architecture_knowledge_conflict`).
- There is no `retryable` flag. The job record has no such column, and a
  manual retry is always offered.

## Alternatives Considered

- **Lock the job row inside the write transaction.** Rejected. The job table is
  written through its own connection, not the unit of work, and renewing the
  lease gives the same guarantee without enrolling it.
- **Cancel work cooperatively as soon as a renewal fails.** Deferred. Model
  calls are not interruptible, so the commit-time fence is the point that
  matters.
