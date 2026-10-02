# ADR 0044 — Human answer support in structured analysis

## Status

Accepted for the user-authorized clarification-resolution fix, 2026-09-18.

## Context

Resolving one question failed because a completed OpenRouter analysis repeated a human answer
as a finding with empty document block IDs. Parsing failed before citation recovery. The answer
was valid human context but had no document source. ADR-0008 requires that origin to remain
distinct from source extraction; ADR-0032's document-only mapping cannot express it.

## Decision

Extend analysis citation mapping with separate one-based `clarification_numbers`, bounded to the
human answers supplied to the call. Every structured output requires document support, human
support, or both. An empty document list is a parseable boundary shape, never proof of support.
Shared mapping and application validation reject missing, duplicate, and unknown references.
Existing bounded citation recovery receives numbered answers alongside numbered document blocks.
Unsupported outputs, transport errors, refusals and truncation retain their terminal behavior.

`RequirementAnalysis.clarification_evidence` records output keys and answer numbers against its
immutable ordered `clarifications` tuple. Existing answer identity, actor, time and suggestion
origin remain authoritative. A human-supported finding is visibly labelled as supported by a
human answer; it is not presented as extracted document evidence or automatically approved.
This extends ADR-0008's source distinction, and supersedes ADR-0032's document-only support
requirement. Its bounded recovery and failure-atomic publication decisions remain unchanged.

Consolidation carries human-supported intermediate findings in temporary evidence blocks, then
restores their original answer references before final validation. Temporary document identities
never reach persisted results. JSON snapshots and API responses add optional/default-empty
human evidence; legacy rounds remain readable without invented attribution or links.
The `analysis-v19-human-answer-citations` prompt version invalidates earlier fragment identities.

## Consequences

Question resolution can incorporate human-only facts without fabricating document support.
The browser displays answer attribution and text beside supported findings. No relational
migration, new provider, port implementation, automatic retry or external publication is added.
Semantic support is still assessed by the model and reviewed by a human; valid reference shape
does not prove the interpretation is correct. Answer numbers are scoped to an immutable round,
not global question identifiers.

## Alternatives Considered

- Permit empty citations as success: hides unsupported generated content.
- Assign the answer to a nearby document block: falsely attributes evidence.
- Drop the human-supported finding: loses a usable reviewed interpretation.
- Rewrite source documents with answers: destroys the distinction required by ADR-0008.
