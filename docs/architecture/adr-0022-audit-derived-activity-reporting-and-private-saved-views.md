# ADR 0022 — Audit-derived activity/reporting and private saved views

## Status

Accepted

## Context

Slice 10A needs a portfolio activity feed and operational measures without
creating a second history that can drift from immutable Requirement,
clarification, job, access, review, and approval records. It also needs durable
reusable worklist filters, but those filters are private user preferences rather
than Requirement or governance state.

The memory and PostgreSQL deployments must expose equivalent behavior. Historic
records can legitimately lack actor metadata, and reporting results must retain
evidence that a reviewer can navigate back to.

## Decision

Application owns three focused boundaries:

- `ActivityReadPort` returns normalized `ActivityEvent` projections with a
  deterministic ID and one or more `AuditSourceReference` values.
- `ReportingReadPort` returns current blocker evidence; `GetOperationalReport`
  aggregates only normalized activity and blocker evidence using an injected
  clock.
- `SavedViewRepositoryPort` persists actor-scoped `SavedRequirementView`
  resources with optimistic versions.

`RepositoryActivityProjection` composes existing worklist snapshots, immutable
Requirement/breakdown revisions, analysis audit rows, and durable AI jobs. It
does not write projection output. Events repeated in later snapshots are
deduplicated by IDs derived from their action and persisted source identity.
Only terminal AI job outcomes are milestones. Missing actor snapshots remain
`None`; neither adapters nor UI infer attribution.

The PostgreSQL saved-view adapter owns a separate
`saved_requirement_views` table because a reusable private query is new mutable
preference state, not duplicated audit state. Its JSONB criteria contain only
search, workflow statuses, sort, owner, and assigned-to-me. Pagination and UI
expansion state never cross this boundary.

All concrete choices remain in `interfaces/api/container.py`. No new setting or
external service is introduced.

## Consequences

Activity and reports cannot disagree with a separately maintained dashboard
event table, and every returned measure can identify its evidence. New event
types require a deliberate mapping to an existing persisted source. Projection
cost grows with retained audit history, so PostgreSQL indexes support ordered
revision reads and adapters must use bounded bulk source reads as the portfolio
grows.

Historic attribution stays honest but produces explicit “Actor unavailable”
rows. Saved views survive restarts and support concurrency, at the cost of one
small actor-owned persistence resource and migration.

Custom reporting ranges, materialized analytics, shared views, export, and BI
integration are ruled out by this decision for Slice 10A; they require a later
decision if scale or product policy justifies them.

## Alternatives Considered

- **An activity-event table written by every mutation.** Rejected because it
  duplicates existing evidence, creates dual-write failure modes, and cannot
  reconstruct missing historic events consistently.
- **Build reports directly from every repository in the use case.** Rejected
  because metric definitions would couple orchestration to persistence shapes
  and would not share one normalized evidence vocabulary with Activity.
- **Store saved views in browser local storage.** Rejected because views would
  not survive browser/device changes, could not enforce actor ownership, and
  would lack optimistic concurrency.
- **Store saved views on the Requirement aggregate.** Rejected because private
  portfolio queries do not belong to any Requirement and would pollute business
  revisions.
