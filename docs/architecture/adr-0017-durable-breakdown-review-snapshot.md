# ADR 0017 — Durable breakdown review snapshot

## Status

Accepted

## Context

Slice 8 must assemble analysis uncertainty, architecture impact, and semantic
Story quality into one review surface. Story quality can require a provider
call, while decisions and flag resolutions must remain auditable and must not be
silently applied after their source evidence changes.

Computing this view on every read would make GET requests expensive and
nondeterministic. Storing only decisions would lose the exact evidence a
reviewer saw, while attaching flags directly to analysis, Feature, and Story
aggregates would spread governance behavior across unrelated domains.

## Decision

- Introduce a Requirement-scoped `BreakdownReview` aggregate behind a
  `BreakdownReviewRepositoryPort`.
- Generate or refresh the complete review explicitly. Reads return the last
  successful snapshot and never invoke an LLM.
- Derive flags, risks, dependencies, and recommendations in a versioned,
  deterministic application policy from existing analysis, architecture, and
  INVEST evidence. No general-purpose review LLM port is added.
- Store a canonical fingerprint of the evaluated evidence. Review mutations
  require that fingerprint to match current evidence, so changed content cannot
  inherit an old resolution silently.
- Derive flag IDs from source identity, rule code, and relevant evidence.
  Refresh carries decisions only for unchanged flags.
- Persist current review state in memory or PostgreSQL and include it in
  immutable breakdown revisions. Build a full candidate before saving so a
  provider failure preserves the last successful review.
- Record decision text, rationale, and time in Slice 8. Actor identity and
  attribution are added by Slice 8A rather than fabricated now.

## Consequences

Review GETs are cheap and repeatable, provider failures do not erase prior
results, and reviewers can audit the exact flags and decisions present in each
revision. Any backlog or analysis mutation can make a saved review stale without
requiring governance fields on the source aggregates.

The review snapshot duplicates selected derived evidence and requires a new
persistence port, migration, and backward-compatible revision mapping. A later
async-job implementation can execute the same explicit generation use case
without changing the domain contract.

## Alternatives Considered

- Compute on every GET: rejected because reads would call the semantic quality
  provider and could mutate cost/failure state.
- Add a review-generation LLM: rejected because the current structured evidence
  already supports the roadmap rules and a second AI interpretation could
  contradict it.
- Store flags on each source aggregate: rejected because it couples governance
  lifecycle and persistence to analysis, architecture, and backlog domains.

## Workflow update

ADR-0041 adds generation-time candidate checks and automatic evidence persistence. Existing
semantic/deterministic and architecture boundaries remain; current saved assessments are reused
on review refresh, and reading the review does not invoke a provider.
