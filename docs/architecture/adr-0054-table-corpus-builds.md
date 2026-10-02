# ADR-0054: Table children and explicit corpus member builds

## Status

Accepted for the next bounded checkpoint of the approved document-knowledge plan.

## Context

ADR-0053 preserved the original child policy. Changing its behavior in place would change
approved citations. Library owners govern their documents individually; the application has
no corpus administrator authorized to reapprove every owner's evidence.

## Decision

The corpus is a set of independently activated publication generations. Each generation is
an immutable source selection and approval, identified by publication ID, extraction revision,
fingerprint, chunk policy, counter/normalizer identity and embedding configuration identity.
An owner builds one document at a time through a preview, approve-and-build, and activate flow.
There is no global privileged activation that overrides other owners' approvals.

`table-fields-512-768-v2` is opt-in. TABLE_ROW and WORKSHEET_RANGE children pack adjacent rendered
fields within the existing 768-unit ceiling. Oversized fields split at bounded sentence/character
positions; their approved field label accompanies embedding input separately from the exact
excerpt. Delimiters are layout hints, not inferred table schema. Source offsets cover every
character once; corrected text is authoritative. Other passages retain the original strategy.
`structure-512-768-v1` remains executable and its bytes and IDs are unchanged.

An explicit build pins its index identity before provider work. Durable batches and the existing
lease/version fence support recovery. Completion records a sorted chunk-ID/content-hash manifest,
count and time. Ready builds stop polling the worker and are invisible to search. Activation
requires owner authorization, document version, exact manifest, current source revision, unchanged
previous publication and the complete persisted chunk set. Discard affects only a pending build.
The old publication stays active until activation or document withdrawal.

Activation is an explicit new publication decision: old approvals and citations remain in history,
but their current applicability becomes stale under ADR-0052. The UI explains this before activation.
A rebuild of the same source/policy gets a new publication ID; it never rewrites the prior approval.

Search interleaves the two supported chunk-policy branches for the same configured embedding
identity, then applies existing diversity and live-source checks. Different model identities are
never compared. An unsupported active model generation still fails explicitly. Model changes require
coordinated rebuilds by the affected owners and an operational search maintenance window; this
checkpoint does not claim zero-downtime multi-model serving or a cross-owner atomic corpus switch.

Publication metadata is additive JSON in the existing memory/PostgreSQL repositories. Legacy
approvals retain their original automatic publication path. No relational migration is required.

## Consequences

Child changes become reviewable and recoverable without editing original files or extraction
history. The corpus contract supports incremental owner-approved rollout and exact build audit.
Model tokenizer qualification, table extraction quality, large-corpus benchmarks, unified Requirement
indexing, restore qualification and CI remain tracked release work.
