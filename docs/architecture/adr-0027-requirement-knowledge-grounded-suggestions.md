# ADR 0027 — Trusted requirement knowledge and grounded clarification suggestions

## Status

Accepted; suggestion timing/evidence-source portion superseded by ADR-0028 and startup-backfill/
automatic-retry portion superseded by ADR-0030

## Context

Independently authored Requirements can duplicate or contradict trusted decisions, while reviewers
answering clarification questions may already have relevant confirmed evidence elsewhere. LLM-only
memory is neither durable nor auditable, and unconfirmed generated content must not become a
cross-Requirement source of truth.

## Decision

- The trusted corpus is Requirement-derived and allowlisted: promoted source fields, attributed
  clarification answers, accepted/edited intent decisions, confirmed analysis facts/rules/
  constraints, and completed conflict resolutions. Drafts, pending/rejected proposals,
  unconfirmed AI analysis, and duplicate Requirements as canonical candidates are excluded.
- Evidence is independently chunked with Requirement/version identity, owner metadata, content
  fingerprint, source kind/field, and application-relative evidence reference.
- Candidate retrieval combines PostgreSQL full-text search and 768-dimensional pgvector cosine
  search through reciprocal-rank fusion. Retrieval is deterministic and capped before semantic
  classification.
- Embedding, retrieval, relationship classification, and answer suggestion are provider-neutral
  application ports. Fake mode stays fully offline; OpenAI and local modes follow configured model
  selection. Every adapter rejects wrong dimensions and unusable or incomplete output.
- The classifier may only advise possible duplicate or possible contradiction relationships and
  must cite supplied evidence. Humans alone mark distinct, close a subject as duplicate, or agree
  how a contradiction is scoped/resolved.
- Duplicate closure is append-preserving: it adds a canonical link and blocks new analysis/backlog
  generation without deleting history or changing the canonical source.
- Contradiction resolution is one versioned shared statement accepted by both current owners.
  Revision clears approvals; ownership transfer invalidates incomplete former-owner approval;
  completed resolution is immutable.
- Fingerprinted durable screening jobs are scheduled after knowledge-bearing mutations and by an
  idempotent startup backfill. Analysis can continue, but confirmation requires the latest screen
  and all current findings resolved. Existing confirmed analyses are not revoked.
- Queue adapters dispatch user-originated work before automatic backfill work. This keeps
  analysis and review actions responsive when a startup backfill contains many Requirements;
  FIFO order is retained within each origin.
- Suggestions are on demand, zero-to-three, and cite only current trusted chunks. Selection fills
  an editable draft and may be recorded as influence, but the resulting answer remains a separate,
  attributed human confirmation.

## Consequences

Reviewers gain visible, auditable cross-Requirement memory without giving the model decision
authority. Related Requirement changes make findings/suggestions stale instead of silently carrying
old evidence. PostgreSQL development and deployment now require pgvector, a 768-dimensional local
embedding model is mandatory in local AI mode, and screening adds asynchronous work before new
analysis confirmation.

## Alternatives Considered

- Exact-text matching only: rejected because paraphrased duplicates and contradictions are missed.
- Vector retrieval only: rejected because exact business terms, identifiers, and channels benefit
  from lexical ranking.
- Treat all AI analysis as knowledge: rejected because assumptions and generated candidates are not
  confirmed business truth.
- Automatically merge, close, or rewrite Requirements: rejected because relationship findings are
  semantic advice and ownership remains human.
- Let either owner resolve a contradiction alone: rejected because the statement governs two
  independently owned Requirement records.
