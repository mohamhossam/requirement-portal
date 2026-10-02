# ADR 0067 — Versioned architecture knowledge and local hybrid retrieval

## Status

Accepted for Slice 14

## Context

ADR-0016 introduced deterministic mapping from a packaged YAML catalogue. That
catalogue cannot be administered without a code release, and phrase matching
alone cannot cite a maintained PDF, DOCX, or TXT source. A reviewer needs to
distinguish maintained ownership from AI-inferred impact and inspect the exact
source used by a Feature or Story mapping.

## Decision

- Maintain draft revisions and immutable published releases in PostgreSQL,
  seeding the packaged catalogue once. Keep document originals as immutable
  blobs and record selected versions, checksums, source locations, index
  profile, and content hash in a release.
- Build citable structured-record and located-document chunks for a frozen
  draft revision. Chunk by offsets from the matching local Qwen3 embedding
  `tokenizer.json` at 500 tokens with 75-token overlap; include its file hash
  in the index profile so a tokenizer change requires rebuilding. Store
  1,024-dimensional multilingual embeddings in pgvector and `simple` full-text
  terms in PostgreSQL. Retrieve lexical and exact-vector candidates and fuse
  them with reciprocal rank fusion. Keep deterministic in-memory adapters for
  offline development and tests.
- Pin one published release per mapping, retain the complete Feature/Story
  input, validate selected IDs and exact quoted passages, and recheck an input
  fingerprint before committing all mapping results. Store citation IDs,
  uncertainty, release/index identity, model, embedding, and prompt version.
- Catalogue ownership and constraints remain authoritative. Document-derived
  selections are AI inferences; unknown declared systems stay visible and
  unassigned. Old snapshots remain readable. Publication never automatically
  remaps existing backlog items.
- Run embeddings and structured reasoning through configured local endpoints.
  No hosted fallback, GraphRAG, LangChain, reranker, or graph database is used.
- Every build writes a new immutable index identity. Only a successful draft
  revision check attaches it to a release; a late build cannot replace
  published chunks. Migrations 025 and 026 preserve release and index identity.
- Retrieval, maintained ownership resolution, and impact assembly belong to
  application orchestration. Validated citations retain system ID, chunk ID,
  and exact quoted spans through snapshots and the reviewer interface.

## Consequences

Mapping gains cited, inspectable evidence while the Clean Architecture port
remains replaceable. Publishing is explicit and audited, and prior releases
remain accessible. PostgreSQL needs pgvector, and indexes must be rebuilt when
the embedding profile changes. A deterministic fixture supports CI but does not
prove Arabic semantic recall for a deployment's real model.

## Alternatives Considered

- GraphRAG or a graph database: the maintained directed relationships already
  cover the current impact question without additional operational burden.
- LangChain: focused ports and existing local clients cover the required flow.
- Vector-only search: exact identifiers and mixed-language terms also need
  lexical matching.
- Approximate vector indexing: defer until corpus scale and latency justify it.
