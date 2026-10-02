# ADR-0009 — PostgreSQL revisions and structured requirement memory

## Status

Accepted

## Context

The in-memory adapters lose the human requirement, clarification answers, and
generated review state whenever the API stops. Slice 10 also requires immutable
history and comparison. The local Ollama model reports a 4096-token context and
does not provide stateful OpenAI Responses semantics, so replaying an unlimited
chat transcript is neither durable nor safe.

The existing invalidation flow can write analysis, Epic, and Features in one
business action. Committing those repositories independently would permit a
partially invalidated breakdown and revisions of intermediate state.

## Decision

- PostgreSQL is the production persistence adapter; memory remains the offline
  and deterministic test adapter.
- Current Requirement, analysis, Epic, and Feature aggregates are stored behind
  the existing application ports. JSONB payloads preserve the domain-owned
  structure without making SQL rows the domain model.
- One request-local PostgreSQL transaction covers the complete application
  action. Dirty requirements are checkpointed once before commit.
- `RequirementRevision` and `BreakdownRevision` are append-only. Database
  triggers reject updates and deletes, including accidental infrastructure
  code paths.
- `BreakdownRepositoryPort` exposes explicit checkpoint, history, and version
  retrieval. Approval data remains inside the current Epic/Feature review state,
  so a separate Approval repository is not justified by the current model.
- Human clarifications are persisted in the analysis snapshot as structured,
  provenance-distinct decisions. LLM calls rebuild a focused prompt from the
  current requirement, current analysis fields, and those answers; historical
  chat is not replayed.
- Local calls reserve configurable output space from the configured context
  window. If the prompt plus JSON schema will not fit, the adapter fails before
  calling the model and never truncates a human decision.

## Consequences

The API can restart without data loss, and every material human/generated state
is traceable. Cross-repository invalidation and checkpoint creation are atomic.
PostgreSQL must be running when `PERSISTENCE_PROVIDER=postgres`; startup applies
packaged migrations and fails clearly when the database is unavailable.

JSONB makes snapshot immutability and rehydration simple at this stage, but
future query-heavy reporting may justify additional indexed projection columns.
That optimization must not replace the append-only source snapshots.
