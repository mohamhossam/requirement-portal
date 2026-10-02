# ADR 0068 — Architecture knowledge roles and release-scoped jobs

## Status

Accepted for Slice 14

## Context

Knowledge administration requires authorization, while local embedding and
reasoning can exceed a browser request lifetime. The repository already has a
provider-neutral identity boundary and Requirement-scoped durable AI jobs.
Architecture release builds are not Requirement-scoped and need their own
release identity, diagnostics, and publication preconditions.

## Decision

- Extend `ActorProfile` with provider-neutral global roles and read those roles
  from the configured OIDC claim. Reuse the existing browser OIDC session and
  `/identity/me`; do not introduce a second authentication implementation.
- Require `knowledge_reader` for published evidence and
  `knowledge_maintainer` for draft, build, publication, and audit operations.
  The deterministic fake identities provide offline reader/maintainer paths.
- Store architecture build and mapping jobs with queued, running, succeeded,
  failed, and cancelled states. Claim jobs with leases, bounded attempts,
  attempt-aware heartbeats, explicit retry/cancel, and idempotent fingerprints.
- Keep these jobs behind an architecture-specific port because builds are
  release-scoped, while the existing generic AI-job aggregate is owned by a
  Requirement. Both use short transaction boundaries and keep model calls
  outside write transactions.
- Preserve the synchronous mapping endpoint for compatibility. Both paths use
  the same mapping orchestration, capture a source fingerprint, and commit only
  after rechecking both source state and the pinned knowledge release.

## Consequences

Knowledge changes and evidence are attributable, architecture jobs survive
worker restarts, and the UI shares one authenticated session. Production needs
OIDC role claims, PostgreSQL, and local model endpoints. Operators must monitor
job failure and lease recovery; architecture jobs do not add a second
notification system.

## Alternatives Considered

- A parallel architecture login flow: rejected because it duplicates session,
  token-renewal, and 401 handling already owned by the identity boundary.
- Reuse Requirement AI jobs unchanged: rejected because release builds have no
  Requirement owner or Requirement generation context.
- Process-local tasks: rejected because work would be lost on restart.
- Synchronous-only processing: rejected because long local-model operations
  need durable progress and recovery.
