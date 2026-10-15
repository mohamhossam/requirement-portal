# ADR-0062 — Dedicated Requirement indexing and measured chunk qualification

Status: Accepted; locally implemented and qualified on synthetic fixtures, not a production release.

## Context

Document children already had durable embedding batches and explicit owner-approved corpus
activation (ADR-0054). Requirement screening and answer suggestions still embedded the dirty
portfolio in their own request/job. Long Requirement fields were sent as single embedding inputs.
The document counter measured UTF-8 budget units; no embedding-model token measurements existed.

## Decision

- A separate Requirement index worker consumes the existing authoritative source-change ledger.
  It processes at most 16 distinct texts per provider batch, with fair source pagination.
- Add an isolated derived progress store, keyed by embedding identity and Requirement. Memory and
  PostgreSQL adapters preserve cached vectors, progress, retry counts and expiring attempt leases.
  A live lease fences checkpoint writes; source-change compare-and-swap fences publication.
  Partial vectors remain outside the searchable index. A crash can resume the saved batch cache.
- Three provider failures stop automatic retries for that source. Backoff is 30/60/120 seconds;
  a member can retry explicitly. A new source change resets failures. Other sources still progress.
- Screening/suggestion jobs remain queued until the configured Requirement index is current.
  Other AI operations remain eligible. Direct synchronous calls fail with retryable HTTP 503
  instead of silently embedding the portfolio or treating an incomplete corpus as an empty one.
- Requirement source fields are split into deterministic, field-local children of at most 768
  UTF-8 budget units. Repeated fragments get distinct identities. Short-field identities remain
  compatible. Query embeddings use the first bounded span; lexical search and classification keep
  their existing full subject input. Generalized Requirement/document lineage remains separate scope.
- The additive migration creates only derived progress storage. It does not rewrite source change
  numbers or historical publications. Existing clean Requirement indexes adopt the new children on
  source change or explicit configured-generation rebuild. No automatic bulk migration is performed.
- Keep runtime document budget accounting unchanged. A separate, explicit qualification command
  calls the selected Google embedding model's own `countTokens` endpoint and embeds the same
  synthetic samples. Neither a chat tokenizer nor byte counts stand in for measured model tokens.
- Model rollout still requires coordinated owner activation (ADR-0054), with a maintenance window
  while documents use mixed identities. Rollback restores the previous configuration and rebuilds
  each owner's current reviewed content; old citations stay stale. No cross-owner approval power
  is introduced. Existing Requirement generation activation rejects incomplete/stale generations.

## Evidence and consequences

`enhancement-chunking-indexing.md` records the commands and failures. On 2026-09-22, the actual
`gemini-embedding-001` endpoint measured 64 synthetic child/context/Requirement samples at
18–528 model tokens, all within its 2,048-token limit; embedding requests accepted every sample.
This is dated fixture safety evidence, not proof of universal tokenizer equivalence, optimal
packing, semantic relevance or production capacity. Runtime counters still report budget units.

Two synthetic owners completed live `gemini-embedding-001` → `gemini-embedding-2` → original-model
rollout/rollback in an isolated in-memory corpus. The corresponding deterministic contract also
runs against PostgreSQL/pgvector. No saved application configuration or application database was
changed by these qualifications. Deployed maintenance, representative customer documents, human
retrieval evaluation, load/restore evidence and green CI remain required for the wider enhancement.
