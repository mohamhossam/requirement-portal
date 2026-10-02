# ADR-0034: Application authorization and concurrency preconditions

## Status

Accepted

## Context

Shared Requirement reads are useful, but mutations previously relied on uneven endpoint behavior
and mutable state could be overwritten after a user or queued job acted on an old view.

## Decision

Authenticated actors may read shared Requirements. Owners and assigned reviewers may perform
content mutations; owner-only governance includes source edits, access administration, intent
decisions, analysis confirmation, submission, and final approval. Unowned Requirements are
read-only until explicitly claimed. Drafts remain private to their owner.

Application authorization is authoritative. Public mutations require the displayed positive
version and, for content decisions, its fingerprint. Collection changes require a set version.
Generation requires an opaque server token binding every relevant source and target version; it is
checked at acceptance and commit. Stale preconditions return `409`. This is an intentional breaking
API change.

## Consequences

Clients must refresh and deliberately reconcile conflicts. They must preserve unsaved input and
must never replay a stale command automatically. Historical snapshots are not rewritten.
