# ADR 0082 — Architecture mapping uses the configured models

## Status

Accepted. Supersedes the local-only model line of ADR-0067 and its Qwen3 tokenizer windows.

## Context

ADR-0067 ran architecture embeddings and mapping reasoning only through dedicated local
endpoints (`KNOWLEDGE_PROVIDER=local`, `KNOWLEDGE_EMBEDDING_*`, `KNOWLEDGE_REASONING_MODEL`)
and sized evidence windows with the local model's `tokenizer.json`. Every other AI task —
analysis, generation, requirement knowledge, the document library, catalogue suggestions —
already follows `LLM_PROVIDER` or the model profiles, including hosted providers. The split
meant a second model server and a mounted tokenizer file just for architecture, and a
deployment could not choose the same provider everywhere.

A review of the journey also found that a requirement naming a system outright ("BCC") could
miss it when document passages outranked the system's own record, that Word documents were
indexed one paragraph at a time without their headings, and that the build step's state lived
only in the page.

## Decision

- **Models.** Architecture evidence is embedded with `LLMAdapters.knowledge_embedding` (the
  application's 768-dimension embedding) through `ArchitectureEmbeddings`, in batches of 32.
  Mapping and preview reasoning use `StructuredArchitectureReasoner` with the `knowledge` task's
  client and input budget, built in every provider branch of `composition/llm.py`. The
  `KNOWLEDGE_PROVIDER`, `KNOWLEDGE_EMBEDDING_*`, `KNOWLEDGE_REASONING_MODEL` and
  `KNOWLEDGE_TOKENIZER_PATH` settings and the tokenizer mount are removed.
  `KNOWLEDGE_EVALUATION_APPROVED=true` is still required in production, now for the configured
  models. Architecture jobs run inline with `LLM_PROVIDER=fake` and on the worker otherwise.
- **Windows.** `ApproximateTokenizer` counts words, cutting long words every four characters.
  It needs no model file and keeps a 500-span window inside every supported embedding model.
- **Index shape.** Migration `202609301000` stores 768-dimension vectors and drops indexes built
  with the former model. The index profile is `{embedding model}:approx-4c-v1:section-v2`, so a
  model or chunking change requires a new build before mapping or publishing.
- **Chunks.** The DOCX extractor reports heading paths (from `pStyle`, `outlineLvl` and
  `styles.xml` names) and table-row blocks. The index packs consecutive passages under the same
  headings up to 400 tokens, prefixes "title / heading / subheading", joins the cells of a table
  row, and never indexes a heading alone. System records list "Depends on" and "Used by" lines.
- **Named systems.** `gather_evidence` fetches the own record (`system_chunk`) of every system
  the text names by id, name, Arabic name or alias, then fills at least six slots from search.
  The rule-based addition therefore always finds its supporting record.
- **Build of record.** `GET /architecture-knowledge/releases/{id}/build` returns the latest
  index build. The page starts a build when its step opens on a stale index, and "Build and
  publish" publishes once that build succeeds; the confirmation names the changes.

## Consequences

One provider choice now covers the whole application, and the deployment needs no tokenizer
file. Architecture documents go wherever the configured provider sends them, so data residency
is decided by that choice (for example OpenRouter with `data_collection: deny`, or a local
server). The approximate window is conservative, so chunks are somewhat shorter than a real
tokenizer would allow. Existing architecture indexes must be rebuilt and published once after
upgrading, and again whenever the embedding model changes.

## Alternatives Considered

- **Keep a separate architecture provider.** Rejected: it duplicated configuration and blocked
  a single provider choice without adding a capability the shared adapters lack.
- **An untyped `vector` column for any dimension.** Rejected: every configured embedding is
  already 768-dimensional, and a typed column catches a mismatched model at write time.
- **Ship tokenizer files per provider.** Hosted providers publish none, and the window only
  needs a safe upper bound, not exact counts.
