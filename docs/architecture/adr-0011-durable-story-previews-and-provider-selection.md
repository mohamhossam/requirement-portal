# ADR 0011 — Durable Story previews and unified provider selection

## Status

Accepted

## Context

Story split and merge can be produced by an LLM, but applying an unseen result
would destroy reviewer trust and human edits. A browser refresh must not lose a
pending review, and an old preview must not overwrite Stories edited after the
preview was generated. Slice 5 also introduced the fourth focused LLM adapter;
the composition root was repeating the same provider switch for analysis,
Epic, Feature, and Story generation.

## Decision

AI Story split/merge results are durable `StoryChangeProposal` records. They
contain candidate drafts, ordered source Story IDs, and a fingerprint of the
source content. Creating a proposal never changes Stories or breakdown
revisions. Application is atomic, compares the current fingerprint, replaces
the sources only when unchanged, deletes the applied proposal, and checkpoints
the resulting breakdown in the same transaction. A mismatch returns a conflict
without changing either Stories or the proposal.

The four domain-focused generator ports remain separate, as required by
ADR-0005. `interfaces/api/container.py` now makes the provider decision once in
`build_llm_adapters(settings)` and returns an `LLMAdapters` bundle. The bundle
is composition-root wiring only; it is not exposed to application use cases.

Provider-, repository-, and missing-resource failures are application errors.
Domain error modules retain only invariant and lifecycle failures.

## Consequences

Reviewers can recover pending previews after refresh, explicitly apply or
discard them, and cannot unknowingly overwrite a changed source. PostgreSQL and
in-memory adapters must both implement proposal durability and the transaction
boundary. Proposals occupy storage until applied or discarded and require a
stable fingerprint algorithm.

Adding another focused generator requires extending one provider-selection
branch rather than copying a new switch, while application code continues to
depend on the narrow port it needs.

## Alternatives Considered

- Apply LLM split/merge immediately: rejected because it bypasses human review
  and can destroy human-owned content.
- Keep previews only in browser state: rejected because refresh loses the
  decision and another editor can change the source unnoticed.
- Replace focused generator ports with one provider-shaped interface: rejected
  because it couples application operations and reverses ADR-0005.

