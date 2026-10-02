# ADR 0012 — Application-owned worklist read model

## Status

Accepted

## Context

The desktop worklist needs a cross-aggregate view of Requirements, analyses,
Epics, Features, Stories, staleness, clarification counts, and latest activity.
These are review-navigation concerns, not invariants of the `Requirement`
aggregate. Loading each row through individual repository calls would also
produce an avoidable N+1 query pattern with PostgreSQL.

## Decision

The worklist classification and query policy live in Application under
`application/use_cases/requirement_worklist.py`. A
`RequirementWorklistSnapshotPort` supplies current cross-aggregate snapshots.
The in-memory adapter composes the existing repositories and revision history;
`PostgresStore` implements the same port with bounded bulk queries. Concrete
selection remains exclusively in `interfaces/api/container.py`.

Workflow status precedence, next-action selection, attention ranking, search,
filtering, sorting, and pagination are application policy. HTTP schemas remain
interface models. The `Requirement` domain aggregate is unchanged.

## Consequences

Dashboard needs can evolve without turning the source Requirement into a UI
projection. Both persistence modes expose one application contract, and the
PostgreSQL adapter avoids row-by-row loading. The current query implementation
classifies an in-memory snapshot after bounded reads; very large portfolios may
later require pushing search and pagination into a dedicated database
projection without changing the application result model.

The `reanalysing` and fully `approved` enum values are intentionally valid but
remain empty until durable async jobs (Slice 8C) and Story/full-backlog approval
(Slice 9) create truthful source state.

## Alternatives Considered

- Add dashboard fields to `Requirement`: rejected because artifact counts and
  next actions are cross-aggregate projections, not Requirement invariants.
- Assemble the worklist in the route: rejected because status precedence and
  next-action selection are application policy and require direct testing.
- Let the frontend join multiple endpoints: rejected because it would be
  inconsistent across pages, slow for portfolios, and unable to rank global
  attention items truthfully.
