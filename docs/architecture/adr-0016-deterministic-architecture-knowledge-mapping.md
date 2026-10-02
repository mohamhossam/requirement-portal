# ADR 0016 — Deterministic architecture knowledge mapping

## Status

Accepted

Slice 14 adds versioned administration and a cited local RAG adapter under
ADR-0018. The packaged deterministic adapter remains the seed/offline path.

## Context

Slice 7 must map Feature and Story text to changeable SMB system knowledge without
hardcoding keywords in the domain or turning another provider prompt into the source
of truth. Mapping is reviewable generated metadata: it must survive refresh and
restarts, retain the catalogue version that produced it, and never invent a squad
where the source reference supplies none.

## Decision

- `ArchitectureKnowledgePort` accepts provider-neutral item text and explicitly
  declared systems and returns system, capability, squad, dependency, and knowledge-
  version references.
- The initial adapter loads a packaged YAML catalogue once at startup and performs
  deterministic, case-insensitive phrase matching. Matching phrases live only in the
  catalogue. A malformed catalogue fails startup with `ConfigurationError`.
- Reviewers explicitly map or refresh the whole current breakdown. The operation
  refuses unconfirmed or stale input, calculates every result before writing, and
  persists Feature and Story impacts in one application transaction.
- An uncatalogued system declared by the Requirement Owner remains visible as a
  non-catalogued reference. Missing squad ownership is displayed as unassigned.
- Item edits and replacements clear their mapping. Upstream staleness preserves the
  prior mapping for audit but blocks refresh until the content is reconciled.

## Consequences

Offline and production deployments produce explainable, repeatable results without an
LLM call. Existing JSONB snapshots remain backward-compatible and immutable revisions
capture mapping changes. Catalogue quality limits recall, so reviewers may see a
successful empty mapping; semantic/RAG adapters can later implement the same port.

The packaged catalogue is read-only application data. Administrative maintenance and
verified squad ownership remain Slice 14 concerns.

## Alternatives Considered

- LLM-selected systems: rejected for this slice because it adds cost, provider failure,
  and semantic provenance when an auditable catalogue is sufficient for the initial
  capability.
- Automatic remapping on every edit: rejected because it couples human content changes
  to generated metadata and obscures the revision checkpoint.
- Treat architecture domains as squads: rejected because the source does not establish
  that equivalence.


## Workflow update

ADR-0041 adds generation-time candidate checks and automatic evidence persistence. Existing
semantic/deterministic and architecture boundaries remain; current saved assessments are reused
on review refresh, and reading the review does not invoke a provider.
