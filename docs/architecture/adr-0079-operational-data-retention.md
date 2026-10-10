# ADR 0079 — Operational data retention and bounded polled lists

## Status

Accepted (2026-09-25, fourth review remediation; the retention command's form
was the user's choice).

## Context

The fourth review found two tables that only ever grow, both read by lists
the browser polls:

- `ai_jobs`: every job a Requirement has run. `GET /requirements/{id}/ai-jobs`
  returned all of them, and the browser polls it while work runs. Each
  re-analysis adds automatic suggestion jobs, one per question.
- `actor_notifications`: `GET /notifications` returned every unread
  notification, polled every ten seconds in each open tab.

Nothing pruned either table.

## Decision

- **Bounded reads.** Both routes take `limit`, defaulting to 100, at most 500,
  newest first.
  - The job list always includes every active job, then fills with the
    newest finished jobs. A job the browser is watching can never drop out.
  - The limit is an optional repository argument (a bound SQL `LIMIT`).
    Readers that need everything, such as the activity projection, pass none.
  - The browser calls without `limit` and gets the default.
- **AI jobs are kept, not pruned.** They are the activity feed's record of AI
  work (succeeded, failed, cancelled). The automatic-screen reservation also
  relies on a finished job to know that a manual retry is required. Pruning
  them would silently rewrite history and re-trigger screening.
- **Read notifications are pruned.** `python -m
  smb_requirement_agent.interfaces.retention` deletes notifications read more
  than `NOTIFICATION_RETENTION_DAYS` ago (default 90).
  - It is safe with the API and workers live. That is why it is not part of
    the offline `maintenance` command.
  - It runs from cron or the `retention` compose profile.
  - Unread notifications are kept until read; the read-side bound covers them.

## Consequences

- A long-lived Requirement's job list costs the same to poll as a new one's.
- The browser's job history panel shows the newest 100 jobs. Older ones stay
  in the activity feed.
- Operators must schedule retention; the deployment guide says so. If it is
  never scheduled, only read notifications accumulate, and they are not
  polled.
- `ai_jobs` still grows with use. Archiving old jobs out of the hot table is a
  future option, recorded in AGENTS.md §19, if the table becomes large enough
  to matter.

## Alternatives Considered

- **Prune old finished jobs.** Rejected; it would erase activity history (see
  above).
- **Prune inside the worker on a timer.** Rejected by the user in favour of an
  explicit command. A timer would add another background loop to the worker's
  readiness and shutdown.
- **Paginate with cursors, with the browser following.** Deferred. The
  browser needs only the newest page. A cursor API is a frontend data-fetching
  change the redesign can take on.

## Amendment — Finished jobs' inputs are pruned (2026-10-10, production hardening PR 13)

The owner chose this. Job rows stay; what grew without bound was each job's stored
inputs (`ai_jobs.command`), which can carry whole answer sets and edited drafts.

- **What is cleared.** The same `retention` command clears `command` of jobs that
  **succeeded or were cancelled** more than `AI_JOB_PAYLOAD_RETENTION_DAYS` ago
  (default 90), and sets `payload_pruned_at` (an additive migration). It works in
  batches of 500, one short transaction each, skipping rows another transaction holds.
- **What is kept.**
  - The job row, its status, failure, timestamps and `result_resources`, so the
    activity feed and the job lists read as before.
  - Failed jobs' inputs: a retryable failure can still be retried.
  - Knowledge screens' inputs: the automatic-screen reservation and its manual
    retry still need them (the reason this ADR first kept every job).
- **Consequence.** A cancelled job past the window can no longer be retried. Retry
  refuses with `ai_job_inputs_pruned` (409); the person starts the action again.
  A pruned clarification job reports no `item_count`.
- **Blob report.** Each run also prints how many document blobs are stored, their
  size, and how many no document version (removed ones included) or attachment
  upload refers to. It deletes nothing; the `DatabaseSizeGrowth` runbook starts there.
- **No new metric.** Database size is already exported and alerted
  (`pg_database_size_bytes`, `DatabaseSizeGrowth`).
- **Rejected:** deleting old job rows (it would still erase activity history), and
  pruning failed jobs too (it would take away a retry the person was offered).
