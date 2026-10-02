# ADR-0038: Rebuildable activity and knowledge projections

## Status

Accepted by the user for the production-readiness remediation. Implementation is added;
execution and validation are explicitly deferred.

## Decision

Supersede the read-time reconstruction requirement in ADR-0022. Immutable revisions, analysis
rounds, questions, decisions, and job records remain authoritative. Activity events and current
blockers are derived PostgreSQL projections with stable event IDs and audit-source references.
SQL performs activity filtering, counting and paging; operational reports aggregate weekly actions,
clarification cohorts, and median durations over a bounded window.
Worklist reads select the latest indexed event instead of hydrating portfolio audit history.

Every transaction flushes changed authoritative revisions before activity and worklist projections.
Revision counters and source-version cursors identify new revisions, rounds, and changed questions,
jobs, access records, and findings. Current blockers retain their original round timestamps. Stable
event IDs prevent duplicate history and preserve already-recorded event payloads.
Projections can be rebuilt explicitly in bounded Requirement batches. A maintenance marker gates
readiness after a coordinated migration and backfill. API startup never performs maintenance.

Knowledge indexing consumes durable dirty-source versions. Embeddings are generated without a
database transaction. Replacement compares the original dirty-source version, so older work cannot
replace an index derived from newer source content. Incomplete catch-up is an explicit failure,
not an empty successful screen. Citation freshness reads only the referenced Requirements.

Generation-context format v2 binds source documents and all affected descendants/proposals.
Evidence-cache namespace v2 binds the complete semantic provider input. Existing cache entries and
job histories remain durable; unfinished v1 generation commands are cancelled by an explicit
release migration, retaining idempotency records.

## Verification

The remediation ledger records the implementation and deferred checks. Incremental maintenance and
SQL report aggregation have source-level regression cases, but none has been executed. Projection
parity, query behavior, migration compatibility, and recovery remain unverified.
