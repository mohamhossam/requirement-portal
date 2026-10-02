# ADR-0035: Short transactions and job execution ownership

## Status

Accepted

## Context

Request-wide transactions held database resources during provider calls. Job leases did not fully
prove that the worker committing a result still owned the attempt.

## Decision

Mutations own explicit short units of work. Model-backed work is prepared from a coherent snapshot,
generated outside a write transaction, and committed only after locking and rechecking state and
authorization. Memory mode models the same atomic boundary with one reentrant lock and coordinated
store snapshots.

Each Requirement has one execution lease. Every claim gets a fresh attempt token. All worker writes
are fenced by job, worker, attempt, and live lease. The executor owns artifact writes, one final
revision, terminal job state, and notifications in one commit. User cancellation uses actor
authorization and job version. Shutdown stops claims, continues heartbeats while draining for a
configurable 150 seconds, then fences unfinished attempts before closing resources.

## Consequences

Provider latency does not extend write transactions and a former worker cannot publish, fail, or
report progress after ownership changes.
