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
