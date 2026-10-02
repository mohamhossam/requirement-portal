# ADR-0053: Exact child citations with bounded retrieval context

## Status

Accepted as the next checkpoint of the reviewed document-knowledge enhancement.

## Context

The first library index embeds and cites isolated approved chunks. That keeps citations exact, but
an isolated policy sentence or table row can lose the heading and neighbouring conditions needed
to judge applicability. Changing child boundaries or embedding text would require a new chunking
policy, owner reapproval and a corpus-generation activation workflow that is not yet delivered.

## Decision

- Keep the indexed child text, child offsets, content hash and `structure-512-768-v1` identity
  unchanged. The exact child remains the only persisted `PublishedReference` excerpt.
- Build a deterministic context window from approved chunks sharing the same structural parent.
  Start with the retrieved child, add nearest neighbours without crossing the section boundary,
  and stop at 1,536 units from the configured `TokenCounterPort`.
- Excluded passages, another section and another publication can never enter the window. Search
  rebuilds the context projection from the current approved revision, so older stored chunk
  payloads gain the same safe behavior without re-embedding.
- `ReferenceProposerPort` receives a provider-neutral `ReferenceEvidence` containing the exact
  citation plus surrounding context. Provider output still resolves evidence numbers to the exact
  citation; context cannot become an uncited fact. The applicability prompt is versioned to v2.
- The API exposes context text, locations and budget count for owner preview and shared search.
  The UI labels the matching passage as exact and keeps context in a separate disclosure.

## Consequences

Existing publications and cached embeddings remain compatible because retrieval keys and embedding
inputs do not change. Applicability generation gains nearby approved wording while citation
currency, lineage and withdrawal checks remain exact-child checks.

This decision does not qualify the UTF-8 counter as a model tokenizer, change table/wide-row child
strategies, build corpus generations, or unify Requirement and document retrieval. Any future
change to child boundaries or embedding text must introduce a new chunking identity and the
owner-visible rebuild/activation path rather than reusing this policy name.
