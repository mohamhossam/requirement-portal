# ADR-0063 — Library ownership transfers and dependency visibility

## Status
Accepted for the user-selected ownership transfer and dependency-view checkpoint.

## Decision
Keep one current document owner. Append attributed transfers to library metadata, guarded by the
existing optimistic version and transaction. Preserve immutable upload/review/publication actors.
Submission identity belongs to the uploader, not the current owner; old submission retries cannot
return private documents after handover. Update PostgreSQL owner_id with the payload in one write.

A focused application use case reads current analysis plus immutable earlier rounds through
existing ports. It exposes recorded reference applicability proposals and exact citations, not
inferred Feature/Story dependencies. Current decisions supersede the initial snapshot of that same
round. Return only Requirement memberships visible to the document owner, without hidden counts.
Publication currency is a current-publication identity comparison; it is not applicability or a
replacement for the existing exact-citation guards used by confirmation/generation/approval.

## Consequences
No new identity provider, lineage store or schema migration is needed. Old JSON lacks transfer
history and loads with an empty history. Existing source-staleness guards continue to apply.
Read-time dependency assembly is suitable for the current workspace; a maintained reverse index
is required before claiming large-portfolio query performance. Notifications, delegated reviewers
and copied-content lineage are separate product decisions.
