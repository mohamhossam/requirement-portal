# ADR 0091 — Output-aware catalogue reading

## Status

Accepted. Extends ADR-0081. Refines the batching recorded in
`docs/slices/enhancement-catalogue-reading-retry.md`.

## Context

`SMB_Product_Architecture_Explorer_v4.md` (35,000 characters) lost most of its content when read
for suggestions. The file holds:
- 8 domains;
- 39 systems, each with an ID, a function, an integration list and aliases;
- one product, with its components and their system responsibilities;
- one journey, with activities, flow rules and integration details.

That is well over 250 catalogue suggestions. Calls were sized only by how much text fits the
model's input, so all 35,000 characters went in one call. That call's answer was limited to 80
suggestions and to `OPENROUTER_MAX_OUTPUT_TOKENS=8192`, about 55 suggestions once each carries
its quote and fields. So either:
- the model stopped early, and most of the document was silently left out; or
- the answer was cut off or over the item cap, and the whole part failed after its one retry.

Asking again for the same text cannot fix this.

Two more defects sat on the same path:
- **Under `LLM_PROVIDER=profiles`, the retry was skipped.** The configured transport raises
  `ModelTransportError`, which is not a `StructuredOutputError`, so the extractor's retry never
  saw it and one bad answer failed the run. The system matcher let the same error escape after
  the document had been read.
- **Same-system integration rows became suggestions that could not be accepted.** A row such as
  "60 → 70", both steps in RTF, became the suggestion "RTF depends on RTF", which
  `SystemRelationship` refuses when accepted.

## Decision

- **A call covers only what one answer can hold.**
  - `StructuredCatalogueExtractor` takes `max_output_tokens`, wired per provider in
    `interfaces/api/composition/llm.py`:
    - profiles: `output_tokens`;
    - local: `LOCAL_LLM_MAX_OUTPUT_TOKENS`;
    - OpenRouter: `OPENROUTER_MAX_OUTPUT_TOKENS`;
    - OpenAI: unset, which assumes 16,384.
  - A call's text is the smallest of three limits:
    - 48,000 characters;
    - the input room;
    - one character per answer token, with a floor of 1,600 characters.
  - One answer can hold `max(10, 0.8 × output tokens / 150)` suggestions, which is 43 at 8,192.
- **A cut-off or full answer splits its part.**
  - Each transport marks an answer stopped at the token limit with `OutputTruncatedError`, raised
    as the cause of its own error, and `truncated()` recognises it. Asking for the same text again
    would be cut off again, so a truncated answer is not retried whole.
  - A part whose answer is cut off, or holds as many suggestions as an answer can, is split in
    half, by passages or else at line breaks, and each half is asked for on its own. The full
    answer is set aside so its suggestions are not offered twice.
  - Splitting stops at four levels, at passages under 400 characters, or when the run's calls run
    out. The budget is three per initial part plus four, and never takes the calls that parts
    still waiting need.
  - A part that cannot be split further keeps its full answer and gets the warning "… may not be
    read completely". A part whose answer is still cut off fails with "the model's answer was too
    long, even for a small part".
- **Larger limits.** The structured answer accepts up to 200 suggestions. Batching, not the
  schema, limits volume, so a valid long answer is never refused. A document may have up to 1,200
  passages, up from 600.
- **Transport failures are retried.** The extractor's retry catches `ModelTransportError`.
  Authentication, configuration and payment failures are still not asked again. The matcher turns
  the error into `SystemMatchingError`, so the run keeps its suggestions and notes that similar
  systems could not be checked.
- **Self-dependencies are left out before review.** `ProposeCatalogueChanges` drops a dependency
  whose source and target are the same system and adds the note "N dependency suggestion(s) were
  left out because they linked a system to itself." `CandidateContent` keeps accepting them, so
  stored suggestions from earlier readings still load.

## Consequences

- A dense document is read in more, smaller calls. Each part can surface everything it states,
  instead of a model-chosen sample.
- Prose documents also make more calls than before, roughly one per 8,000 characters at an
  8,192-token limit instead of one per 48,000. That costs more requests and more time per
  reading. Raising the provider's output limit, where the model allows, brings the count back
  down.
- A full answer is discarded when its part is split, which spends those tokens. In return, a
  half-read part is never offered alongside its complete halves.
- The suggestion-count heuristic assumes about 150 answer tokens per suggestion. A model that
  writes much longer suggestions is caught by the truncation split instead.
- This slice does not change how Markdown is cut into passages, the prompt, or the catalogue
  model. Those follow in slices 1b–3e of the structured-document plan.

## Alternatives Considered

- **Raise the output-token setting only.** It depends on the model, does not help local models,
  and still leaves one answer covering a whole document.
- **Ask a truncated answer again whole.** It is cut off again at the same length.
- **Keep a full answer alongside its halves.** It would offer the same rows twice, often with
  differently worded descriptions that the merge cannot recognise as duplicates.
- **Refuse self-dependencies inside `CandidateContent`.** Suggestions stored by earlier readings
  are validated when loaded, so drafts that already hold one would stop loading.
- **Make the configured transport raise `StructuredOutputError`.** Other adapters rely on
  `ModelTransportError` reaching the public `model_*` codes unchanged.
