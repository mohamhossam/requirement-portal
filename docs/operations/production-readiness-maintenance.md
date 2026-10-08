# Production-readiness maintenance runbook

This is a coordinated maintenance-window release. Do not run any step while an API, worker,
scheduler, script, or older binary can write to the database. Record the database backup identifier,
legacy-document backup identifier, migration output, both backfill manifests, reconciliation output,
and release versions in the change record.

## Prerequisites

- Backend and frontend artifacts were built from the same reviewed revision.
- All automated quality gates, including PostgreSQL/pgvector integration coverage, are green.
- A restore rehearsal has established the database and legacy document restore time.
- Operators have the explicit migration command, blob importer, projection backfill, and read-only
  reconciliation queries available from the release artifact.

## Maintenance sequence

1. Enable maintenance mode, disable new mutations and job starts, stop all schedulers, and stop
   claims on every worker. Drain every API and worker instance. Verify that no writer remains.
2. Back up PostgreSQL and the complete legacy document-storage root. Record immutable backup IDs.
3. Apply migrations through the existing explicit command:
   `python -m smb_requirement_agent.infrastructure.persistence.migrate`.
4. Preserve legacy job history but mark every unfinished legacy job cancelled with the upgrade
   reason. Never execute commands that lack the new concurrency context. Users retry from refreshed
   state with new idempotency keys.
5. Preserve existing idempotency rows and their fingerprint-format markers. Treat reuse of a legacy
   key for a different command or Requirement as a conflict.
6. Backfill missing positive current-record versions and Feature/Story set versions. Do not modify
   immutable Requirement or breakdown revision payloads.
7. Run the document import for every version referenced by current metadata or any historical
   revision with
   `python -m smb_requirement_agent.requirements.infrastructure.backfill_document_blobs`.
   Use its resumable manifest, verify source and stored byte count and SHA-256, and stop on a
   missing or mismatched file. Do not delete legacy files.
8. Run `python -m smb_requirement_agent.interfaces.maintenance`.
   Reconcile projection count to current Requirement count and inspect missing/extra IDs. The API
   must never perform this rebuild during startup.
9. Start the coordinated backend and frontend release only after every prerequisite and
   reconciliation succeeds. Verify fake-provider startup and the production identity/provider
   health checks before disabling maintenance mode.

## Rollback

Before writes reopen, stop the new application, restore the database and legacy storage backups,
and deploy the old backend and frontend together. After any new-version write is accepted, do not
start an incompatible old binary. Keep maintenance mode enabled and deploy a forward correction.

## Legacy-file cleanup

Keep the legacy document tree after a successful release. Deletion is a separate destructive change
requiring explicit authorization, an agreed retention period, and a second checksum/reachability
audit.

## This implementation session

On 2026-09-08 the migration, blob-import, and projection-maintenance commands were rehearsed against
a fresh disposable PostgreSQL 16/pgvector database. All 21 migrations were recorded, the empty
legacy manifest imported zero blobs, and projection maintenance rebuilt zero Requirements twice,
confirming an idempotent empty-database run. Read-only reconciliation returned 21 migration rows,
zero worklist rows, and zero blob-import rows. This was not a production maintenance window: target
backups, non-empty legacy reconciliation, restore timing, and deployment remain required.
# Second-review follow-up release

The follow-up implementation has passed the local validation matrix and the disposable-database
rehearsal recorded above. Do not deploy based on local evidence alone; CI and the environment-specific
maintenance prerequisites remain authoritative.

After completing the finding ledger, stop every writer and worker and take a recoverable database
backup. Apply migrations 016–021 after 013–015. They add literal casefold search, a durable knowledge
index catch-up queue, activity/current-blocker projections, and retirement of unfinished v1
generation commands, and revision/audit-input projection cursors. Historical jobs and idempotency
bindings are retained. Migration 021 removes the previous projection-completion marker so the
explicit rebuild is mandatory even if an earlier version of the backfill was already applied.

Run `python -m smb_requirement_agent.interfaces.maintenance` in the maintenance environment.
It constructs only persistence and deterministic projection collaborators, processes Requirements
in batches of 200, and records `activity-worklist-v2` only after completion. It does not initialize
an LLM client, identity client, extractor, or worker. The rebuild clears each Requirement's derived
event/cursor state before reconstructing it from authoritative records. Re-running is idempotent. Writers must remain
stopped until this completes. Knowledge indexing catches up in batches of 100 sources and refuses
to publish a successful screen while catch-up remains incomplete.

Deploy matching backend/frontend versions together. `/health` is liveness; `/ready` reports
accepting-requests, persistence/schema/backfill readiness, and worker health. A busy worker remains
healthy while its lease heartbeats succeed. Readiness performs no paid provider calls.

For a public deployment, run `python -m smb_requirement_agent.interfaces.deployment_preflight`
with the intended release configuration. It requires OIDC, validates settings, and creates no
network clients. Separately verify the intended shared-workspace access policy before opening
traffic. Fake identity remains the local development path. This remediation does
not introduce tenant isolation or ADO publication.

Retain the pre-release backup and legacy document files. Before accepting new writes, rollback
uses the matching old application and restored database. After accepting new writes, use a forward
fix or a separately reviewed recovery procedure that preserves those writes.
