# ADR-0052: Reference applicability remains an owner decision

## Status

Accepted for the next vertical slice of the approved document-knowledge plan.

## Context

An approved library passage is reviewed evidence, not proof that its policy applies to a new
Requirement. The existing IntentProposal already supports owner-only decisions and downstream
accepted rules. A second competing decision workflow would obscure this boundary.

## Decision

- Complete primary-document analysis first. A separate, focused reference operation receives
  labelled primary evidence, retrieved passages and existing human decisions. It appends only
  business-rule/constraint proposals, never primary facts. Existing provider profiles select the
  knowledge client; legacy providers and the offline fake have explicit implementations.
- PublishedReference is an immutable domain snapshot: document/file/extraction/publication IDs,
  fingerprint, exact excerpt/offsets, location and normalized content lineage hash. Model-selected
  evidence numbers resolve only to supplied snapshots. Missing/blank output, unknown citations,
  refusal and provider errors fail explicitly. An empty applicability result requires a reason.
- IntentProposal retains generation provenance, citations, conflict indication and every decision.
  An owner must supply a rationale for acceptance, edited wording or rejection. Accepted text
  participates in the existing backlog-generation input. Conflicting references do not acquire
  authority from retrieval score or date; the owner decides and records why.
- Current publication is revalidated at decision, analysis commit, confirmation and downstream
  generation boundaries. PostgreSQL publication metadata is share-locked in the surrounding
  transaction; withdrawal/replacement updates conflict with that lock. Generation resume guards
  reject source changes during provider work before generated writes commit.
- Staleness is evaluated lazily. Historical approvals and edits are never erased. Current review
  fingerprints include citation lineage/currency; stale references add a blocking source-action
  finding and prevent final approval. A confirmed analysis can be explicitly re-analysed; the owner
  can reject a stale carried proposal, preserving the prior decision in history. New publication
  identity permits a new decision even when the wording is unchanged.
- Existing snapshots default to no reference evidence; no new SQL migration is required for
  the analysis JSON payload. Existing non-reference review fingerprints remain unchanged.

## Consequences and boundaries

Retrieval is still document-only, bounded to 20 passages, three per document, four focused queries
and an 8,000-unit conservative UTF-8 budget. No parent expansion, bilingual quality claim or new
optimal-tokenizer claim is made. A published index incompatible with the configured generation
fails explicitly rather than looking like an empty corpus. Automatic reindex/activation remains
the subsequent index-generation work.

The older Requirement index cannot yet represent generalized lineage. It therefore excludes
reference-backed intent decisions and confirmed-analysis chunks derived in their presence from
shared indexing. Source-authored Requirement fields and attributed human answers remain eligible;
screening can still use its own subject context. This deliberately trades derived-copy recall for
avoiding false independent corroboration until unified lineage-aware retrieval is implemented.

The OpenAI adapter follows the documented parsed structured-output boundary, while validating
content and citations separately: [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
No live-provider quality certification is implied by deterministic adapter tests.

## Alternatives Considered

- Add a separate reference-decision aggregate/UI: rejected because existing IntentProposal owns
  the same applicability and human-review lifecycle and already feeds backlog generation.
- Promote retrieved statements into known facts: rejected because publication and relevance do
  not establish applicability.
- Erase confirmations or bulk rescreen all Requirements on withdrawal: rejected because immutable
  history must survive and lazy current-source guards avoid unbounded portfolio work.
- Index copied policy text as ordinary Requirement facts: rejected until the shared index can
  preserve generalized lineage, avoiding false independent corroboration.
