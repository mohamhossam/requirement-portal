# ADR-0010 — Explicit analysis confirmation loop

## Status

Accepted

## Context

Saving a human answer already caused one LLM re-analysis, but the workflow had
no explicit completion state. A reviewer could see “No unresolved items remain”
without being able to attest that the resulting analysis was accepted. It was
also unclear that another answer round should follow whenever re-analysis found
new uncertainty.

## Decision

- Each clarification submission persists the new human answers and immediately
  re-runs analysis using the complete saved clarification set.
- New unresolved items remain in the same answer form, forming an explicit
  answer → re-analyse → answer loop.
- `RequirementAnalysis.confirmed_at` records Requirement Owner confirmation.
  Confirmation is allowed only when `unresolved_keys()` is empty.
- A normal re-analysis or any new clarification produces a replacement analysis
  with no confirmation, so confirmation never silently carries onto new AI text.
- Requirement edits continue to delete the current analysis. Immutable database
  revisions preserve the previously confirmed state.

## Consequences

“No questions” is no longer treated as human approval. The UI shows whether the
analysis is an AI candidate or explicitly human-confirmed, and revision history
records both answer rounds and the final confirmation.
