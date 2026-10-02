# ADR 0025 — Owner-governed business intent proposals

## Status

Accepted

## Context

Analysis previously required an author-entered desired outcome. That made the
intake contract stricter than the real business starting point: authors often
know the need before they can responsibly state an outcome. Treating an LLM
inference as a normal extracted fact would erase provenance and allow invented
rules to silently influence generated backlog items.

## Decision

Analysis eligibility requires title and business need only. Author-entered
desired outcome, rules, and constraints remain immutable source evidence.

Unsupported LLM suggestions enter the domain as stable intent proposals, never
as source-backed findings. Each proposal has a kind, rationale, original text,
optimistic version, and append-only owner decision history. Only the Requirement
Owner may accept, edit, reject, or revise a decision. Decisions become immutable
when the analysis is confirmed.

Effective confirmed intent is a projection: the source-authored desired outcome
has precedence; otherwise an accepted or edited outcome proposal is used.
Accepted or edited rule and constraint proposals join source-backed context for
downstream generation. Pending and rejected proposals are excluded.

The analyzer receives prior terminal decisions during same-source re-analysis
and must respect them. A Requirement source-version change invalidates the
current analysis and active proposal decisions while immutable analysis and
breakdown revision history retain the prior evidence.

Proposal payloads and their decisions are serialized in the existing versioned
analysis JSON snapshots. Legacy snapshots default to no proposals and retain
their existing Requirement outcome. No relational schema migration is added.

## Consequences

Authors can analyze an early business need without inventing a target. Reviewers
can distinguish source evidence, AI candidates, and owner-confirmed context.
Backlog generation has a single governed input projection, and rejected ideas
cannot leak into Epic, Feature, or Story prompts.

The Requirement Owner must resolve every proposal and every blocker before
confirmation. Adapter normalization must reject unsupported numeric targets and
unusable structured output rather than presenting it for approval.

## Alternatives Considered

- Keep desired outcome mandatory: rejected because it blocks valid discovery
  work and encourages authors to provide placeholder outcomes.
- Store accepted AI text directly on Requirement: rejected because it would
  rewrite source evidence and lose proposal/decision provenance.
- Persist proposals in new relational tables: rejected because analysis is
  already an immutable, versioned JSON aggregate and no cross-analysis proposal
  query requires a separate schema.
