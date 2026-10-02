# ADR-0037: Maintained PostgreSQL worklist projection

## Status

Accepted

## Context

The portfolio endpoint reconstructed every Requirement workspace and revision-derived activity at
request time, so read cost grew with the whole corpus rather than the returned page.

## Decision

The existing pure Application projector remains the authority for classification and attention
precedence. PostgreSQL persists its current result in the same transaction as relevant business or
job lifecycle changes. Search, access filters, status counts, owner facets, stable ordering,
pagination, and attention selection execute against indexed projection columns. Full aggregates are
hydrated only for returned page and attention IDs.

Knowledge relationships are indexed as source/dependent Requirement versions. Source changes
refresh dependent projections without worklist-time corpus scans. Initial/recovery rebuild is an
explicit administrative backfill and never API-startup work.

## Consequences

Every mutation that changes visible classification must enroll its Requirement in the unit of work.
Projection rows are rebuildable current state and are not audit history.
