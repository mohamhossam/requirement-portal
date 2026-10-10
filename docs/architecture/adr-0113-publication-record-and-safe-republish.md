# ADR 0113 — A publication record with external id mappings, and marker-based recovery

## Status

Accepted 2026-10-10 with Slice 13
(`docs/slices/slice-13-external-id-mapping-and-safe-republish.md`). It builds on ADR-0112 and
answers the safe re-publication that ADR-0112 left to this slice.

## Context

Slice 12 creates work items and forgets them, so a second publish duplicates the backlog. Slice 13
must make republishing idempotent, send changes as updates, and continue a publication that stopped
part-way. AGENTS.md §9 forbids external ids on Epic, Feature or Story. A create is never retried
(ADR-0112), yet a create whose answer is lost, or a process that stops between a create and saving
its result, leaves an item the portal does not know about.

The ontology and impact implementation plan also asks the record to keep the Requirement's
accepted product verdict and its version, so a delivery that closes in ADO can be traced to what
was promised. That verdict is decided by a later phase.

## Decision

- **One record per Requirement** (`BacklogPublication`, `governance/domain/publication/`), stored
  whole as JSON in `backlog_publications` with optimistic versioning: each save must advance the
  stored version by exactly one. It holds the target key, one `ExternalWorkItemMapping` per local
  item, every attempt (`PublicationResult`) with an outcome per item, and nullable
  `product_verdict` and `product_impact_version`, set together or not at all.
- **Saved after every item.** An attempt is saved when it starts and after each item's result, so
  at most the item in flight is unrecorded.
- **A marker on every created item.** `smb-rp-` and 20 hex digits of the SHA-256 of the
  Requirement id and the local key, added to the item's tags. It is stable across revisions.
  After an attempt that was interrupted or had an item fail, an unmapped item is first looked up by
  marker (WIQL in Azure DevOps) and, when found, updated and mapped instead of created. Several
  matches are refused, for a person to resolve.
- **Content fingerprint.** Each mapping keeps the SHA-256 of the item's kind, title, description
  and acceptance criteria as last sent. An equal fingerprint is not sent again; a different one is
  an update of those fields only. Area, iteration, tags and links stay as people left them.
- **A lease, not a lock.** A starting attempt takes a 15-minute lease. Another start inside it is
  refused (`publication_in_progress`); after it, the stale attempt is closed as interrupted.
- **One target per record.** The publisher names its target (`azure-devops:{org}/{project}`). A
  record for another target refuses publication (`publication_target_changed`) instead of
  duplicating the backlog in the new project.
- **Retry without a new confirmation**, only for the revision the latest attempt confirmed, and
  only while that revision is still the latest with final approval.

## Consequences

- A tracker item someone deletes by hand stays mapped; the next update of it is refused and
  reported, and the person resolves it. Detecting deletions would need a read per item on every
  publish.
- Items a newer revision removes are listed, not closed: closing work in someone's board is a
  decision for people.
- Moving the portal to a new ADO project needs the record cleared by an operator; the refusal
  says why.
- The record grows by one attempt per publish; the status route returns the latest 20.
- Removing someone's marker tag in ADO disables recovery for that item only.

## Alternatives Considered

- **External ids on the breakdown entities.** Forbidden by AGENTS.md §9, and it would tie
  revisions to one tracker.
- **A durable outbox with background retries.** The owner needs each refusal at once, and a retry
  of a create is exactly what causes duplicates; the marker makes a manual retry safe instead.
- **Looking up every unmapped item by marker on every publish.** One query per new item on the
  happy path, for a case the record already rules out.
- **Tables per mapping and attempt.** The record is read and written whole, by one writer at a
  time; one JSON document with a version keeps its invariants in the domain.
