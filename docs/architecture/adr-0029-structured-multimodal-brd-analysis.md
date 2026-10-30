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

## Amendment — one pass when the model holds the document (2026-10-29)

Section packets were sized for local and small-output models, and every document went through
them, so a hosted model with a large window paid for at least three calls, each with its own
citation repairs. With OpenRouter's GPT-5.1, analysing a 41,000-character BRD with 5 images
(two packets: the images exceed three per packet) took 641 s of model time over 7 calls: two
section calls, one citation repair, consolidation, a question-reconciliation recovery and two
citation repairs. Time is set by output: the model writes about 100 tokens a second, and
consolidation alone wrote 26,656. The same BRD in one call took 345 s over 2 calls (the call and
one citation repair), wrote half the tokens, kept every open question and ambiguity, and found
three contradictions between sections that consolidation had missed. A second run, of the
shipped code, took 435 s over 4 calls: its first answer was malformed and was asked for once
more, as a section packet's would be.

- **One pass when both limits allow it.** `PlanSinglePass` sends every source block and the
  active questions in one call when the evidence fits the consolidation budget (the model's
  window less the prompt reserve) and the model's output limit can write three times the
  evidence's characters. GPT-5.1 wrote about 2.65 times its evidence for that BRD. The output
  limit comes from the analysis profile, the local model, `OPENROUTER_MAX_OUTPUT_TOKENS` or
  `OPENAI_MAX_OUTPUT_TOKENS`; with none known (the offline fake), the section packets stay.
- **Small-output models keep their packets.** Gemini Flash-Lite's 8,192-token limit allows one
  pass only for evidence under about 11,000 characters, so the reason section packets keep their
  budget, above, still holds for it.
- **At most ten images in one pass.** A section packet holds three; one pass bounds its single
  request at ten, and a document with more keeps its section packets.
- **What one pass records.** One stage, `evidence_single_pass`, cached like a packet and
  committed only with an accepted analysis. Progress reports planning, analysing and validating;
  there is no consolidation phase. Figure support is not needed: the call reads the figures in
  the source itself.

A single call is one larger request: an output limit too small for it would truncate the whole
analysis, which is why the output limit, not only the window, decides. No migration, prompt or
API change.

## Amendment — structured items bypass the consolidation model (2026-10-30)

ADR-0120 adds business use cases, a multi-field record, to the analysis. Consolidation re-emits
findings from one synthetic sentence per cited passage, which would have rewritten or dropped such a
record. `ConsolidateEvidenceAnalysis` now merges use cases deterministically by normalised name,
holds them and their references aside before the first round, emits no synthetic blocks for them,
and re-attaches them to the model's result or to the merged fallback, where a held record wins
over a rewrite under the same key. Non-functional requirements are held the same way, keyed by
statement, so their type survives. The planner's `BUC n` packet boundaries make a use case
section-local, and the packet stage already validated both kinds' citations. The fragment cache key
moves to `evidence-fragment-v4`.
