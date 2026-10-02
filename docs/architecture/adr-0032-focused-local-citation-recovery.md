# ADR 0032 — Focused Local Citation Recovery

## Status

Accepted. The document-only support requirement is superseded by
[ADR-0044](adr-0044-human-answer-analysis-citations.md); bounded recovery and atomic publication
remain in force.

## Context

The local vision model repeatedly returned schema-valid analysis content while leaving
`evidence_citations` empty. It also generated placeholder question IDs when no active AI
questions existed. Structured packet analysis rejected both responses correctly, but its local
adapter deliberately bypassed the focused recovery used by the legacy text path, leaving no safe
way to recover usable content.

## Decision

Local structured analysis separates content normalization from evidence attachment. A complete,
valid first response remains a one-call path. When only citation validation fails, the adapter
freezes and numbers its normalized outputs, numbers the current packet's evidence blocks, and
makes one focused mapping request using a packet-specific schema: output numbers and evidence
block numbers have independent bounds, and decision count must equal the frozen output count.
The provider returns numbers only; the adapter restores exact application-owned subjects and
block IDs and applies the existing strict citation validator. If that mapping is malformed,
one additional citation-only correction call is allowed, using safe validation feedback and the
same frozen outputs, evidence and images. There are at most two mapping calls per packet.
Transport errors, refusals, truncation and explicit unsupported content never initiate correction.

The recovery must account for every output exactly once. Duplicate, missing, overlapping, or
out-of-range numbers fail. Any output reported as unsupported fails the entire generation rather
than being dropped or assigned fabricated evidence. Newly generated packet fragments are staged
in application memory and written through one adapter batch only after every packet,
consolidation stage, and final citation validation succeeds. The PostgreSQL adapter performs that
batch in one transaction, so a failed generation or cache write cannot leave a partial new cache.

Provider question reviews are discarded when no active AI question was supplied. Existing
numbered question reconciliation remains the recovery path when active AI questions exist and is
completed before citation recovery. Human-authored questions remain protected.

Open questions and ambiguities also require nonblank reviewer-facing rationales. When the initial
structured response omits only those rationales, one focused numbered request fills them before
question reconciliation and citation recovery. The adapter restores the frozen uncertainty kind
and subject, rejects missing, duplicate, or out-of-range numbers, and never accepts provider
rewrites of those fields.

The supported Ollama setup uses the project alias `smb-qwen3-vl:8b-16k`, derived from
`qwen3-vl:8b` with a 16K context and deterministic sampling. The alias is explicit local tooling,
not a domain or application dependency.

## Consequences

Local models can recover from the observed omitted-citation and rationale behavior without
regenerating or silently changing analysis content. Invalid evidence remains a provider failure,
and successful responses preserve exact document-version provenance. A failed first response can
add focused local inferences and therefore latency. Changing the model alias and prompt version
intentionally invalidates old fragment-cache keys.

## Alternatives Considered

- Accept uncited output: rejected because reviewers could not verify generated claims.
- Infer citations with string similarity: rejected because the application would fabricate
  semantic support.
- Regenerate the full analysis: rejected because facts could change and citations could still be
  omitted.
- Drop unsupported outputs: rejected because it would silently alter the candidate.


### Observed citation cardinality correction — 2026-09-18

An OpenRouter Gemini response correctly cited nine supplied layer headings for a statement
describing a nine-layer RAG architecture. The repair-only schema's fixed eight-reference limit
rejected this valid mapping, although the normal citation schema permits all necessary blocks.
Remove that arbitrary repair limit. Recovery remains bounded by the current packet: support
must be nonempty, references unique and every number within the supplied block range. No claim
or citation is truncated, fabricated or dropped. This shared correction applies to all providers.

### Attachment section context correction — 2026-09-18

A subsequent Word analysis succeeded in extraction and several section analyses but generated
an ambiguity asking how the user label "Test word" relates to BUC9. Citation recovery correctly
marked that question unsupported and rejected the generation. A title match is not a business
requirement: selected attachments are already associated by the application, and an empty typed
description is valid. Shared analysis guidance now states this association and the possibility
that evidence represents one section of a larger document. Real gaps such as a process marked
"To be Discussed" remain review questions. Prompt version analysis-v17-attachment-packet-context
invalidates earlier fragment cache identities. Citation validation and bounded recovery remain
unchanged; unsupported outputs are never dropped or assigned fabricated support.


### Bounded structural correction — 2026-09-18

A subsequent OpenRouter response numbered 24 outputs but referenced evidence block 13 when
only 12 blocks were supplied. Prompt bounds were already explicit. The recovery schema now
encodes the packet ranges and exact decision count, while local validation retains uniqueness,
complete coverage and nonempty support. All necessary references within the packet remain valid,
including statements requiring nine or more references.

Completed-response validation errors carry a typed infrastructure marker and sanitized feedback;
provider response text and arbitrary values are not echoed into correction instructions. An
explicit supported=false decision is terminal even when another mapping field is malformed.
Only structural mapping defects receive one extra call. Existing transport retry budgets are
unchanged, except legacy OpenRouter timeouts now stop without repeating a possibly billed call.
Invalid mappings remain explicit safe model_invalid_citations failures with job correlation IDs.
Attempt count, category and durations are traced; available usage stays in transport diagnostics.
The analysis-v18-bounded-citation-correction version invalidates earlier fragment identities.
Pending packet/cache entries still publish only after complete successful generation.

### Source obligation preservation — 2026-09-18

The user's 16:23 retry generated both the supported fact that an IP phone is mandatory for
every user line and an invented variant requiring one only where no soft client exists.
Neither the supplied packet nor the human answer mentions a soft client. Focused recovery
correctly marked frozen output 6 unsupported; this is a content failure, not a missing human
answer reference or a citation number defect. Unsupported outputs remain terminal.

Shared generation guidance now explicitly preserves the scope and force of source obligations
and forbids unsupported conditional exceptions, with this observed example. Prompt version
`analysis-v20-preserve-source-obligations` invalidates prior fragment identities. No automatic
regeneration, output deletion, fabricated reference, or relaxed citation validation is introduced.
Prompt guidance reduces this failure mode but cannot guarantee compliant live model output.

### Complete supported content cardinality — 2026-09-18

The 16:32 user retry returned 15 known facts. The initial analysis schema rejected them because
its source-backed lists had a fixed limit of 12. The complete-replacement rule requires all
supported information to survive; reviewer question limits do not justify truncating facts.
Remove the arbitrary maximum from known facts, constraints and business rules. Retain the
existing uncertainty/proposal limits and content/evidence validation.

Citation recovery must cover the resulting frozen outputs, including packets with more than
64 items. Its dynamic schema continues to require exactly the observed output count, with
separate bounded output, document and human-answer number spaces. Remove only the fixed
64-output ceiling. Configured input/context and output-token budgets still bound provider
requests; sources and outputs are never silently truncated to fit a list limit.
`analysis-v21-complete-source-content` invalidates earlier fragment identities.

Completed-response structural validation also carries an existing safe `invalid_output` error
as its cause. Internal sanitized feedback remains available for bounded mapping correction;
public error translation can describe invalid model output without exposing provider/source
text. The shared analyzer wraps both legacy and configured transport failures consistently.
Unsupported outputs, provider failures and atomic publication retain their existing behavior.

### Governed intent before packet citation validation — 2026-09-18

The 16:39 user retry successfully repaired earlier packets, then failed on an add-on section.
Its only unsupported output was a new-proposal echo of the requirement-wide business outcome
already accepted by the owner. The initial prompt simultaneously required a desired-outcome
proposal whenever the typed outcome was absent and required preserving accepted intent.
Application analysis construction already excludes these generated echoes while carrying the
original decisions forward, but this happened after packet citation validation.

Extract that existing selection rule into a deterministic domain predicate shared by analysis
construction and provider-boundary normalization. Before freezing outputs, exclude generated
proposals that the existing rule would never add: source/accepted/edited outcome replacements
and exact original/effective statements of decided proposals, including rejected repeats.
Exclude only their proposal citation entries, retaining entries needed by any remaining proposal
with the same subject. All genuinely new facts, uncertainties and eligible proposals still
require complete support. No citation repair reported as unsupported is bypassed or rewritten.

Original carried decisions retain identity, owner attribution, version, decision history, measures
and source provenance. They are not new document-extracted findings and are not re-cited against
unrelated section evidence. The prompt requires an outcome proposal only when neither source
nor accepted/edited owner intent supplies one, and explicitly instructs the model not to re-emit
prior decisions. Version `analysis-v22-governed-intent-context` invalidates prior fragments.
No new evidence type, API response, database migration, provider retry or approval rule is added.

### Operation-context citations for missing decisions — 2026-09-18

One explicitly authorized live verification passed the earlier failures, then recovery rejected
two questions about failure handling and auditing for the documented add/delete add-on flow.
The analysis prompt requires checking relevant failure/audit dimensions, while citation recovery
already defines uncertainty support as a source-exposed gap or stated business context. The
model incorrectly demanded an explicit failure/audit statement as support for asking whether
those decisions exist. This is distinct from asserting a new failure or audit business rule.

Clarify recovery guidance with concrete positive and negative examples: a documented add/delete
flow supports questions about its unspecified failure handling and whether it requires auditing.
The flow alone does not support a fact requiring an audit record, a new regulatory rule or a
question about an unrelated operation. Fact/rule support and reference validation remain strict;
unsupported decisions remain terminal. Prompt version `analysis-v23-uncertainty-context-citations`
invalidates earlier fragments. This is prompt guidance, not deterministic semantic proof, and
the final guidance has not been validated with a second live retry.

### Preserve business context in focused citation recovery — 2026-09-18

The subsequent user-triggered 16:54 retry passed the add-on section, then rejected a question
about financial/billing implications of an external account shift. Its generated rationale
explicitly linked the question to the accepted financial-reporting outcome. Generation receives
that owner intent, but the focused recovery request omitted both it and the question rationale.
The supporting shift operation was in the current evidence packet; the business reason for
asking its missing financial decision was lost between stages.

Pass requirement business need, structured source context and accepted/edited effective owner
intent into recovery as explicitly unnumbered relevance context. Include the existing question
and ambiguity rationales alongside their frozen subjects. Judge question relevance against
the documented operation and confirmed intent; cite only the supplied operation evidence or
human answer, not the unnumbered context. Context alone cannot prove a fact, rule, constraint
or proposed answer, create a document/answer reference, or support an unrelated operation.
Rationales are generated explanations, not evidence, and must be checked against source/context.

Structural correction reuses the identical base prompt including context, rationales, evidence
and frozen outputs. Exact coverage, bounded references, unsupported-terminal behavior and atomic
publication remain unchanged. Version `analysis-v24-citation-business-context` invalidates earlier
fragments. This fixes a concrete input-wiring omission without a new domain/API provenance type,
provider configuration, migration or automatic failed-job retry. Live semantic compliance remains
unverified after the change; deterministic transport fixtures cannot establish it.
