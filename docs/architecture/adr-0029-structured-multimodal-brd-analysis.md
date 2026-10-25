# ADR 0029 — Structured Multimodal BRD Analysis

## Status

Accepted.

## Context

Flattening a DOCX into one string loses headings, table relationships, and images. It also
causes otherwise valid BRDs to exceed a local model's context window. Raising that window is
not a reliable or scalable document-analysis strategy, and referenced workbooks must never be
fetched or interpreted implicitly.

## Decision

Immutable source-document versions may carry ordered evidence blocks, safe raster assets,
extraction warnings, and an extraction-format version while retaining `extracted_text` for
compatibility. Analysis items cite exact block IDs together with document version and checksum.

Application services plan bounded section-aware packets, validate all provider citations, cache
successful fragments by source/prompt/model/extraction fingerprints, and hierarchically
consolidate validated packet findings. A failed packet or consolidation does not commit a partial
analysis. Concrete DOCX/XLSX, model, cache, and persistence implementations remain adapters
selected by the composition root.

XLSX formulas are never executed, hidden sheets are opt-in, external relationships and OLE
objects are never followed, and meaningful image evidence blocks analysis when the configured
provider cannot accept images. HTTP asset access is authenticated and checksum-bound to an
immutable source version.

## Consequences

Large structured documents can be analyzed within provider budgets with exact source links and
retryable cached work. Cross-section contradictions receive a focused consolidation pass instead
of a string concatenation merge. Storage and provider traffic increase, extraction is more
complex, and legacy uploads require a new immutable version to gain structured evidence.

## Alternatives Considered

- Increase the local context window: useful as a temporary workaround but still loses document
  structure and does not scale to larger inputs.
- One Requirement per BUC: rejected because source sections are traceability boundaries inside
  one initiative, not independent business requirements.
- Automatically fetch linked workbooks: rejected for security, provenance, and authorization
  reasons.

## Amendment — consolidation budget and fallback (2026-10-25)

An analysis of a structured BRD with OpenRouter's GPT-5.1 analysed every section, then failed
with "Evidence findings could not be consolidated within the provider context budget".
Consolidation re-packs every validated finding, once for each passage it cites, into packets of
the same fixed 60,000 characters used for document sections. Hosted models had no way to raise
it: a model profile's window could only lower it. GPT-5.1 writes more findings, each citing more
passages, so one consolidation round produced as many packets as it started with, and the run
stopped with every valid finding discarded.

- **Consolidation follows the model's window.** It plans packets with the analysis model's
  context minus its output limit (four characters a token): the model profile's, the local
  model's, or `OPENROUTER_CONTEXT_TOKENS` with `OPENROUTER_MAX_OUTPUT_TOKENS`. It is never
  smaller than a section packet. Without a known window it keeps 60,000 characters.
- **Section packets keep their budget.** Their findings grow with their input, and a model with
  a large window but a small output limit (the bundled Gemini Flash-Lite profile: 1M tokens in,
  8192 out) would otherwise truncate a whole document's analysis.
- **A round that cannot shrink falls back to a merge.** When a round yields as many results as
  it was given, or the hierarchy reaches its depth, the last round's validated results are
  merged deterministically instead of failing. Exact duplicates are kept once with their
  references. No model reviews the active questions in that case: each AI question is retained,
  and one no finding repeats is carried without a new citation (`carried_questions`), keeping
  its earlier support. A finding that repeats a human question is dropped. A warning is logged.

The fallback does not reconcile contradictions between sections, which the focused pass above
exists for, so it is a last resort rather than a substitute. No migration, prompt or API change.
