# ADR 0013 — Separate Resumable Requirement Drafts

## Status

Accepted

## Context

Slice 5C must persist incomplete intake, including a blank title or description,
without weakening the non-blank invariants of the `Requirement` aggregate used
by analysis and backlog generation. Autosave also needs optimistic concurrency,
while current Requirements and immutable revisions must remain readable.

## Decision

Incomplete intake is represented by the separate `RequirementDraft` aggregate
in `domain/requirement/entities.py`. It stores normalized partial strings,
structured context, a version, and an update timestamp. The application reaches
it through `RequirementDraftRepositoryPort`; the composition root selects the
in-memory or PostgreSQL adapter.

Promotion builds a validated `Requirement` through `CreateRequirement` and then
removes the draft. A promoted draft with no desired outcome remains ineligible
for analysis. For backward compatibility, the legacy direct Requirement-create
contract and snapshots created before Slice 5C derive desired outcome from the
existing description. New draft promotion does not apply that compatibility
fallback.

Both Requirement source updates and draft autosaves use monotonically increasing
versions. Adapters reject a write whose stored predecessor version no longer
matches. Source edits with derived artifacts require an application-owned impact
preview and acknowledgement; the impact is recomputed inside the commit
transaction.

## Consequences

The domain can persist arbitrary partial intake without passing invalid content
to an analyzer. Offline and durable modes share the same behavior, and stale
browser tabs receive an explicit HTTP 409 instead of overwriting newer text.

The cost is a second source aggregate and promotion lifecycle. Drafts do not
appear in the Requirement worklist; the dashboard queries and displays them as a
separate resumable-intake band. Multi-user ownership remains deferred to Slice
8A, so the current dashboard resumes the most recently updated draft.

## Alternatives Considered

- Make `Requirement.title` and `Requirement.description` optional. Rejected
  because every analysis and generation use case would then need to defend an
  invariant that currently holds at construction.
- Store incomplete drafts only in browser local storage. Rejected because it
  is not durable across browsers or devices and cannot provide server-side
  optimistic concurrency.
- Save every partial edit as a Requirement revision. Rejected because immutable
  historical revisions describe validated source/backlog states, not keystroke
  autosaves.
