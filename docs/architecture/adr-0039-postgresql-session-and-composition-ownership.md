# ADR-0039: PostgreSQL session and composition ownership

## Status

Accepted within the approved production-readiness remediation. Implementation added; execution
and validation deferred by user instruction.

## Context

Aggregate facades forwarded SQL to one oversized PostgreSQL store. Projection refresh depended on
a deferred binding step, obscuring missing collaborators until commit. Provider clients constructed
inside adapters also made failed startup and maintenance resource ownership unclear.

## Decision

PostgresStore owns connections, transaction nesting, rollback, Requirement locks, and commit order.
Aggregate repositories, document metadata, revision persistence, and current-snapshot readers own
their SQL through the narrow PostgresSession protocol. Shared snapshot and activity codecs preserve
persisted representations. A test-only compatibility facade keeps legacy integration fixtures usable;
it is not part of the runtime graph.

The composition root supplies immutable checkpoint and projection callbacks when constructing the
store. After authoritative checkpoints, the projection callback composes a small read/projection
graph over PostgresCommitSession and the same active connection. That session cannot mark source
state dirty or own a separate commit. There is no deferred binder or partial runtime object graph.

External provider work closes the physical transaction connection and releases locks. A successful
response resumes on a new connection, reacquires authorization/concurrency fences, and commits only
accepted output. Provider failures propagate without attempting a reconnect that could mask them.

Memory mode uses explicit snapshot participants and a shared reentrant lock for transactions, jobs,
and knowledge state. Suspending external work releases the entire nesting depth and refreshes the
rollback baseline afterward so independent progress and indexing are retained.

Provider and identity clients are injected by the composition root and owned by ExitStack. Partial
construction and lifespan startup failures release acquired resources. Shutdown retains clients
until fenced worker threads return. Maintenance constructs persistence and deterministic projection
collaborators only; public-deployment preflight resolves settings without initializing clients.

## Consequences

SQL changes stay with their aggregate or read model. Commit wiring is explicit and projections
remain atomic with authoritative writes. Maintenance can rebuild projections without provider,
identity, extraction, or worker resources. Regression cases are written, but no runtime, typing,
architecture, migration, or integration result is claimed.
