# ADR 0024 — Explicit database migrations outside API startup

## Status

Accepted

## Context

The PostgreSQL adapter originally applied every pending schema migration while
`build_container()` assembled the API object graph. A database outage or locked
DDL statement therefore looked like a hung web server, multiple API replicas
could race to migrate, and the runtime process implicitly held schema-change
authority. Database migration also could not be operated independently from
LLM configuration.

## Decision

Schema migration is an explicit infrastructure operation invoked with:

```text
python -m smb_requirement_agent.infrastructure.persistence.migrate
```

The command resolves only `PERSISTENCE_PROVIDER` and `DATABASE_URL`, applies
pending packaged migrations, and exits. `build_container()` selects and wires
PostgreSQL adapters but never changes the database schema. Deployments run the
migration command before starting the API. The combined local launchers may
orchestrate that same command before creating the API process; migration still
does not occur inside API construction or lifespan.

The local launcher may start the repository's Compose PostgreSQL service only
when configuration targets localhost, then test readiness and invoke the
explicit migration command. External databases are never replaced by a local
container. `-CheckOnly` is non-mutating. Memory mode requires neither a database
nor migrations.

## Consequences

API startup has no schema-mutation side effect, database permissions can be
separated between deployment and runtime identities, and migrations run once
as an observable deployment step. A fresh or outdated database is now an
operator error until the explicit command runs; the API does not repair it.

PostgreSQL-backed application behavior still depends on PostgreSQL being
available. This decision separates schema lifecycle from process lifecycle; it
does not introduce degraded database-free operation for durable mode.

## Alternatives Considered

- Continue migrating in every API process: rejected because it couples DDL to
  web startup and creates concurrency and operational ambiguity.
- Silently start against an outdated schema: rejected because later requests
  would fail unpredictably and could partially execute business actions.
- Add a separate migration framework now: rejected because the ordered,
  recorded SQL runner already provides the required behavior.
