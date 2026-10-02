# ADR 0028 — Automatic dual-source clarification suggestions

## Status

Accepted

## Context

ADR-0027 made answer suggestions an on-demand operation grounded only in trusted evidence from
other Requirements. That protects the trust boundary, but it leaves useful facts, business rules,
and constraints from the current analysis unused and makes reviewers request help question by
question. Suggestions must appear without delaying or weakening persistence of a new analysis
round, and unconfirmed analysis must never be confused with trusted cross-Requirement knowledge.

## Decision

- A new application scheduling port queues one durable automatic suggestion job for every active
  clarification question after an analysis round is persisted and after a human question is added.
  Scheduling participates in the caller's transaction and is idempotent for an active equivalent
  question/version job.
- The worker has an explicit automatic execution path. Manual refresh continues through the
  existing AI-job operation and enforces Requirement team membership.
- The focused suggester receives two separate evidence collections: current unconfirmed analysis
  facts/rules/constraints and accessible trusted chunks from other Requirements. Assumptions,
  ambiguities, open questions, and potential dependencies are excluded.
- Suggestion source is derived from validated citation ownership. Provider output cannot supply or
  override `current_analysis`, `trusted_knowledge`, or `combined`.
- Automatic failure is isolated to its durable job and does not roll back or block analysis review.
  A successful empty result is persisted distinctly from failure.
- Suggestion freshness includes question content and the fingerprints of every cited current or
  trusted chunk. No relational migration is required because stored citations already identify the
  owning Requirement; prior suggestion records therefore derive as trusted knowledge.

This supersedes ADR-0027 only where that ADR says suggestions are on demand and cite only trusted
chunks. Its wider corpus trust boundary and human-decision rules remain accepted.

## Consequences

Reviewers receive progressive suggestions without a click and can distinguish unconfirmed local
analysis from trusted organizational evidence. Analysis persistence stays fast because generation
runs asynchronously. A Requirement with several active questions creates several serialized jobs,
and current-analysis citations add an additional freshness dependency. The UI must represent
loading, empty-success, and failure/unavailable as different states.

## Alternatives Considered

- Include current analysis in the trusted index: rejected because unconfirmed generated content
  would become reusable evidence for other Requirements.
- Generate inline before saving analysis: rejected because provider latency or failure would block
  the human review workflow.
- Accept a provider-supplied source label: rejected because trust classification must follow
  validated application evidence, not model assertion.
- Auto-fill or auto-resolve the highest-ranked answer: rejected because generated suggestions are
  candidate wording, not confirmed business truth.
