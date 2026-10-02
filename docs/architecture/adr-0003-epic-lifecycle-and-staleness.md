# ADR 0003 — Epic lifecycle and staleness

## Status

Accepted

## Context

Slice 03 introduced the first aggregate carrying human approval. `Requirement`
and `RequirementAnalysis` are both create-and-read; an Epic can be edited,
approved, and invalidated by an upstream change, and `AGENTS.md` §8 forbids
silently destroying approved content or letting regeneration overwrite it.

Three questions had no obvious answer, and each admits a defensible opposite.

## Decision

**Three statuses**: `GENERATED`, `EDITED`, `APPROVED`. `is_human_owned` is true
for the latter two and is the single predicate gating forced regeneration.

**Editing approved content revokes the approval.** The approval attested to
specific content; once that content changes the attestation is no longer about
anything. The alternative — refusing edits until an explicit un-approve — needs
a fourth operation for no gain, since revocation is exactly what un-approving
would do.

**Editing clears staleness.** A stale Epic cannot be approved, so without this
a Business Owner who fixes a stale Epic by hand could never approve their own
correction; the only route to approval would be regeneration, which discards
the very work they just did. Treating a deliberate edit as an assertion that
the content reflects the current requirement is the rule that keeps the
lifecycle traversable. The cost is real and should be named: a human who edits
one word without re-reading the changed requirement clears the flag. Slice 09
(Review/Approval) should revisit whether clearing needs to be an explicit
acknowledgement rather than a side effect of any edit.

**A stale Epic cannot be approved** (`StaleEpicApprovalError`). This is the
invariant the slice exists to protect: approving content whose source has
already moved on is precisely the silent-drift failure that human review is
supposed to catch.

**Marking stale is idempotent and preserves status and content**, including
`APPROVED`. The first divergence is the one worth recording, so a repeated
requirement edit does not keep resetting the timestamp.

## Consequences

Approved work survives upstream change, flagged rather than destroyed, and the
approval record stays intact for audit. Regeneration cannot quietly discard
human effort. The lifecycle is small enough to hold in one's head: three
statuses, one staleness reason, four transitions.

The costs: an edit is now overloaded — it changes content *and* asserts
currency. `Epic` is meaningfully larger than the anemic `RequirementAnalysis`,
which is an inconsistency between two sibling aggregates until analysis catches
up. And "stale" is binary, so an Epic cannot express *how* far its source has
drifted.

## Alternatives Considered

**Delete the Epic on upstream change**, matching how analysis is invalidated
today. Rejected: it destroys human-approved work as a side effect of editing a
typo in a requirement.

**Block requirement edits while an approved Epic exists.** Safest for the data
and the worst to use — fixing a spelling mistake would require discarding an
approved Epic first.

**Regeneration always produces a new candidate alongside the old.** The most
auditable option and probably where this ends up, but it pulls candidate
history, selection, and diffing into a slice that does not otherwise need them.
Deferred, not rejected.
