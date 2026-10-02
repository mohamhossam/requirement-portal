# ADR 0019 — Stable clarification questions and immutable analysis rounds

## Status

Accepted

## Context

Analysis uncertainty was embedded only as text in the latest analysis. Answers
were submitted by kind and subject, current analysis could be overwritten by a
repeat POST, and neither generation provenance nor collaborative work survived
as an independently auditable history. Identity introduced in Slice 8A makes
actor attribution possible, but assignment, partial answers, and concurrency
need a stable aggregate and persistence boundary.

ADR-0010 also blocked confirmation on every unresolved analysis item. Teams
need to retain useful non-blocking questions through breakdown review without
allowing AI defaults alone to relax confirmation policy.

## Decision

- Give every new analysis an `AnalysisId`, ordered round number, source
  Requirement version, document references, applied clarifications, and
  adapter-reported `Provenance`. Provider output cannot choose the model or
  prompt-version audit fields.
- Persist each generated analysis as an insert-only `AnalysisRound`. Preserve
  legacy analyses with deterministic IDs and explicitly unavailable provenance.
- Promote uncertainty to stable `ClarificationQuestion` aggregates. Exact
  normalized kind-and-subject matches retain identity, assignment, and draft
  state across forced re-analysis. Source edits supersede active questions;
  history is never deleted.
- Use `open`, `in_progress`, `resolved`, and `superseded` states. Drafts move a
  question between open and in-progress; terminal questions are immutable.
  Every mutation uses an optimistic version.
- Default AI and migrated questions to medium/blocking and human questions to
  medium/non-blocking. Owner/reviewer classification changes are attributed.
- Limit question management to the Requirement owner/reviewers. Assignment
  targets must remain in that team. The assignee or owner may draft and resolve;
  team removal clears active assignments with an audit event and retains work.
- Resolve synchronously: call the provider before the transaction, then recheck
  Requirement version, current analysis identity, and question version. Commit
  the answer, reconciled questions, current analysis, round, and revision in one
  transaction. Provider failure commits nothing.
- Require `force=true` to analyse when current analysis exists. Preserve the
  kind/subject batch clarification route only as a compatibility boundary;
  stale or ambiguous matches return conflict.
- Amend ADR-0010: only active questions designated as blockers prevent owner
  confirmation. Non-blocking questions remain visible and feed breakdown-review
  warning flags by stable question ID.

## Consequences

Question URLs, assignments, drafts, review flags, and answer attribution remain
stable across analysis rounds. Reviewers can inspect what model/prompt and
source version produced each candidate, while legacy data stays readable
without fabricated metadata. PostgreSQL needs insert-only round storage,
versioned question updates, and terminal-state triggers. In-memory and database
adapters implement the same audit port.

Resolution still waits for the provider response. Durable background jobs,
retry/cancel behavior, polling, and notifications remain Slice 8C. Analysis
confirmation is not formal backlog approval; approval governance remains Slice 9.

## Alternatives Considered

- Keep questions inside the current analysis JSON: rejected because assignment,
  optimistic concurrency, and cross-round history would be unstable.
- Use provider-generated question IDs: rejected because external content is not
  trusted to control durable identity or reconciliation.
- Make every open question a permanent blocker: rejected because an authorized,
  attributed human classification is a safer and more useful policy boundary.
- Re-analyse asynchronously now: rejected because it would pull Slice 8C job
  lifecycle and notification concerns into this slice.
