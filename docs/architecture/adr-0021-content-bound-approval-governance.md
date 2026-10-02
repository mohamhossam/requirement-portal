# ADR 0021 — Content-bound approval governance

## Status

Accepted

## Context

The backlog already had editable Epic and Feature lifecycle states and a durable
`BreakdownReview`, but approvals did not identify an actor, timestamp, rationale,
or exact content. Story review had no approval/rejection transition. A later
publication boundary cannot safely rely on a mutable `approved` label, especially
after source, architecture, clarification, or flag evidence changes. Existing
approved snapshots must remain readable without inventing audit history.

## Decision

Artifact approval history is stored with each Epic, Feature, and Story. Submission
state, final approvals, and append-only comments are stored with
`BreakdownReview`. The application reuses the existing aggregate repositories and
revision boundary; there is no separate approval repository.

Every approval attests to one canonical SHA-256 subject generated from canonical
JSON. Artifact subjects cover visible content, parent identity, provenance,
staleness, acceptance criteria, and architecture evidence. The complete breakdown
subject also covers Requirement version, confirmed analysis round, ordered
artifact subjects, review ruleset/evidence, and flag-resolution state. Approvals
and comments are excluded so recording them cannot invalidate their own subject.

The persisted workflow states are `GENERATED`, `UNDER_REVIEW`, `NEEDS_REVISION`,
and `APPROVED`. A required strict application policy permits final approval only
for the exact submitted/current subject with no open blocking flags or active
blocking clarification questions. Warnings remain advisory. The Requirement
Owner alone submits and finally approves; the Owner and assigned reviewers may
approve/reject artifacts and comment.

Source and evidence mutation invokes `InvalidateApprovalWorkflow`; submitted or
approved work moves to `NEEDS_REVISION`. Governance commands recompute and compare
fingerprints inside their transaction as a concurrency backstop. Editing stale
content clears staleness only with explicit source-reconciliation acknowledgement.

Pre-Slice-9 approved Epic/Feature payloads deserialize with their status and
content intact but with empty audit history. They are not current formal approvals
until an authorized actor explicitly reaffirms their current fingerprint.

## Consequences

Final approval is durable, attributable, and safe to use as a future export or ADO
publication guard. Revision snapshots preserve the audit trail without a new join
model, and PostgreSQL JSONB payloads need no schema migration. Any visible content
or evidence change invalidates the applicable attestation, so reviewers may need
to refresh the review and reapprove changed items before resubmission.

Legacy clients may keep sending bodyless Epic/Feature approval requests; the
server binds those requests to the current artifact. New clients send the
displayed fingerprint and receive a conflict if it changed.

## Alternatives Considered

- Store every decision in a new approval repository: rejected because it adds a
  cross-aggregate join and a second history mechanism where aggregate JSONB and
  immutable revisions already provide the required durability.
- Trust lifecycle status without a content fingerprint: rejected because a stale
  or edited subject could retain a misleading approval.
- Fabricate actors for legacy approvals: rejected because unavailable provenance
  must remain explicit.
- Introduce configurable quorum/four-eyes modes: deferred until a concrete policy
  is approved; Slice 9 has one strict, required policy.
