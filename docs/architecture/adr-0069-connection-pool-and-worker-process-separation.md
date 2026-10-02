# ADR 0069 — PostgreSQL connection pool and worker process separation

## Status

Accepted

## Context

The 2026-09-24 architecture review found two production blockers in the process
layout:

- Every unit of work, every `external_call` resume, and every call on the
  architecture knowledge, evidence-index and job adapters opened a new
  PostgreSQL connection. Behind TLS to a managed database that is a handshake
  per repository call, and connection churn the server must absorb.
- Every API process always ran the AI-job, document-ingestion and
  requirement-index workers (`AI_JOB_WORKER_CONCURRENCY` had to be at least 1).
  HTTP and background work could not be scaled or deployed independently, and
  CPU-heavy extraction competed with request latency. Architecture jobs needed
  a separate process, `infrastructure/architecture/worker.py`, which imported
  the composition root from `interfaces` — infrastructure depending outward.

## Decision

- **One pool per long-running process.** `PooledPostgresConnector`
  (`infrastructure/persistence/postgres_connector.py`, `psycopg_pool`) is
  created and opened by `build_container` and closed by `close_resources` after
  every worker has stopped. `PostgresStore` and the architecture adapters take a
  `PostgresConnector`; none calls `psycopg.connect`. The pool opens without
  waiting, so an unreachable database is reported by `/ready`, not a crash loop.
  Sizing: `DATABASE_POOL_MIN_SIZE`, `DATABASE_POOL_MAX_SIZE`,
  `DATABASE_POOL_TIMEOUT_SECONDS`; an exhausted pool fails the unit of work with
  `PersistenceError` after the timeout instead of hanging it.
- **Direct connections for one-shot commands.** `DirectPostgresConnector` serves
  the projection rebuild and test fixtures, which have no process to pool for.
  Both connectors give identical transaction semantics; each has its own tests.
- **Workers are a named set chosen by the composition root.**
  `Container.background_workers` maps readiness-check names to workers. The
  architecture job poller (`infrastructure/jobs/architecture_job_worker.py`)
  joins the set when `KNOWLEDGE_PROVIDER=local`.
- **API replicas may run HTTP only.** `API_BACKGROUND_WORKERS=false` starts no
  workers and omits them from `/ready`; it requires PostgreSQL because another
  process cannot see an in-memory queue.
- **A dedicated worker entrypoint.** `python -m smb_requirement_agent.interfaces.worker`
  runs the same set without HTTP, stops on SIGINT/SIGTERM, and exits non-zero
  when a worker turns unhealthy so a supervisor restarts it. It replaces
  `infrastructure/architecture/worker.py`; an import-linter contract now forbids
  infrastructure from importing interfaces.
- Worker start/stop/drain lives in `interfaces/runtime.py`, shared by the API
  lifespan and the worker process. Workers stop in reverse start order; one that
  fails to stop keeps shared resources open until it has actually returned.

## Consequences

- Units of work reuse sessions; the transaction and external-call semantics of
  ADR-0001-era code are unchanged, and pooled sessions carry no session state
  (all `SET`s are `LOCAL`, all advisory locks transaction-scoped).
- Operators must size each process's pool: concurrent requests plus worker
  threads, and the sum across processes within the server's `max_connections`.
- The default remains a single process running everything, so local and demo
  runs are unchanged. A split deployment is opt-in.
- Architecture jobs now also run in the API process under local knowledge,
  which lifts the temporary Phase 1 rule that local knowledge needed PostgreSQL.
- Architecture jobs keep their own release-scoped queue (ADR-0068); only the
  runtime that polls them is shared.

## Alternatives Considered

- **A hand-written pool.** Rejected: `psycopg_pool` already provides health
  checks, bounded waits, and reset of returned connections.
- **Setting `AI_JOB_WORKER_CONCURRENCY=0` to mean "no workers".** Rejected: it
  would only cover one of three worker types and overload a sizing setting with
  a deployment role.
- **Folding architecture jobs into the Requirement-scoped `AiJobs` aggregate.**
  Deferred: ADR-0068 keeps release-scoped builds out of a Requirement-owned
  aggregate for domain reasons this change does not revisit.
