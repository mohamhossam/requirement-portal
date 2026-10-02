# ADR-0066 — Recorded source lineage and indexed impact reconciliation

Status: Accepted (user-requested completion, 2026-09-23)

## Context

Reference proposals preserved exact citations, but selected answers and derived backlog content
could lose their document origin. Governance scanned analysis histories and could not offer a
complete, access-filtered reverse dependency view. Copied Requirement evidence could consequently
appear independent of the document that supplied it.

## Decision

Carry a provider-neutral `SourceLineage` value with an immutable `PublishedReference` and the
recorded input path. An empty path identifies a direct citation; a nonempty path identifies an
indirect dependency. Accepted/edited proposals and selected suggestions preserve file version,
extraction revision, publication, approval fingerprint, block, exact excerpt and character range.
Analysis generation records its supplied origins; Epic, Feature and Story generation append the
actual parent/input identities. Manual edits and Story splits/merges retain origins. These paths
describe generation inputs, not sentence-level proof or inferred applicability.

Maintain reverse dependencies in the same transaction as each authoritative Requirement mutation
and revision checkpoint. Migration 024 adds the rebuildable index and append-only impact decisions.
Memory transactions snapshot the index; PostgreSQL updates it through the existing commit projection
callback. The explicit maintenance command backfills recorded immutable revisions under Requirement
locks and restores the current projection. Request-time queries never scan Requirement histories.
Readiness requires migration 024 and a completed maintenance marker; startup performs no backfill.

The index pages/filter-searches current or historical rows by document/Requirement. PostgreSQL joins
current owner/reviewer membership before pagination. Results have no workspace totals. A document
owner sees only their accessible Requirements; Requirement membership permits reading its impact
view, while only its owner may decide. Document ownership grants no Requirement decision authority.

An impact decision binds the exact content/lineage identity to the displayed document version and
publication state, with actor, time, rationale and compare-and-swap version. A stale form conflicts.
Retain permits continued use of that historical source for that content; revise remains unresolved
until replacement or another explicit decision. A new content identity or document state requires
fresh review. Repeated withdrawal cannot revive an earlier retained decision. Historical content
and approvals are never rewritten by this operation.

Confirmation checks analysis inputs. Generation checks analysis plus its actual parent/source
artifacts, allowing old descendants to be replaced. Final breakdown review checks all active
dependencies. Provider-result guards recheck source currency after external work.

Requirement knowledge chunks carry recorded origins. Screening and answer suggestion retrieval
exclude document-derived copies as independent Requirement evidence. Unified search prefers the
original document over its copies and groups remaining copies by document origin; withdrawn copies
are excluded from fresh search. Similar wording never establishes a dependency.

## Consequences

- The former history-scan debt in ADR-0063 is retired. Search is over maintained dependency rows,
  with indexed document/current/Requirement scope; portfolio-scale load qualification remains separate.
- Stored legacy content without recorded origins remains unattributed. Backfill does not invent
  origins from wording or rewrite immutable approval/history snapshots.
- Retained historical evidence is scoped to existing content. New generated content inherits the
  origin and requires its own review before approval if the source is still historical.
- Same-document grouping is conservative: separate passages are not independent corroboration.
- Existing HTTP conflict/authorization/document validation mappings are reused (409/403/422).
- Test-only PostgreSQL browser infrastructure uses synthetic scanner results and fake providers;
  it does not change production scanning rules or qualify malware/OCR/model quality.
