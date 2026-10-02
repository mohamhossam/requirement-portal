# ADR 0071 — The composition root is a package

## Status

Accepted. Amends AGENTS.md §4.4.1 ("wired in exactly one module").

## Context

`interfaces/api/container.py` had grown to about 2,500 lines, with one
`_build_container` function of roughly 1,250 lines. Beyond wiring use cases it
also held LLM provider selection for five providers, the commit-time
PostgreSQL projection refresh, and operational entry points (projection
rebuild, model qualification, smoke checks) used by CLI commands rather than by
the running application. AGENTS.md required all of it to stay in that one module.

The rule exists so that exactly one place names concrete adapters. It did not
require one file to do so.

## Decision

- The composition root is the package `interfaces/api/composition/` together
  with its entry module `interfaces/api/container.py`. Only these modules may
  name a concrete adapter; everything else still receives ports and use cases.
- `composition/llm.py` — LLM provider selection (`LLMAdapters`,
  `build_llm_adapters`).
- `composition/projections.py` — `refresh_postgres_projections`, the commit-time
  read-projection refresh.
- `composition/operations.py` — `build_projection_rebuild`,
  `reference_model_qualification`, `qualify_embedding_tokens`,
  `smoke_llm_profiles`: offline entry points built from the same adapters.
- `composition/persistence.py` — `build_persistence` returns
  `PersistenceAdapters`, every repository and port for the configured backend
  (memory or PostgreSQL). The few decisions that depend on the backend beyond
  plain repositories travel with that set instead of re-testing the provider
  later: index progress, the readiness probe, and a `worklist(review)` factory
  that returns the backend's worklist reader and projection maintainer.
- One builder per bounded context, each returning a frozen dataclass:
  `composition/identity.py` (`build_identity`, which also seeds fake actors),
  `composition/analysis.py` (`build_requirement_analyzer`, the evidence-packet
  pipeline around the provider analyzer), `composition/architecture.py`
  (`build_architecture_retrieval`, `build_architecture_knowledge`,
  `build_architecture_jobs`), `composition/knowledge.py`
  (`build_requirement_knowledge`) and `composition/documents.py`
  (`build_documents`).
- `container.py` keeps `Container`, `BackgroundWorker` and `build_container`.
  It calls the builders in dependency order and assembles `Container` from
  their results, field by field, so every field stays type-checked.
- **Amended by the third review remediation:** the backlog use-case graph that
  `container.py` used to build inline moved into builders of its own:
  - `composition/requirements.py` (`build_requirement_intake`): create, draft,
    promote, edit;
  - `composition/analysis_workflow.py` (`build_analysis_workflow`):
    collaboration, clarification, confirmation, the generation-context tokens;
  - `composition/review.py` (`build_review`): review, approval, revisions,
    export;
  - `composition/breakdown.py` (`build_breakdown`): Epic → Feature → Story
    generation, editing, quality and architecture mapping;
  - `composition/jobs.py` (`build_ai_jobs`): job start, execution, workers.

  Review is built before the breakdown, because approving an Epic, Feature or
  Story goes through its approval recorder. `container.py` is now about 750
  lines, most of them the `Container` fields and their assembly.
- Nothing in the package is constructed at import time; the §4.4.1 import-time
  rule is unchanged.

## Consequences

- `container.py` fell from 2,528 to about 1,100 lines, and most of what is left
  is the `Container(...)` field assembly. Provider, persistence, identity,
  architecture, knowledge and document wiring can each be read and changed in a
  module of under 700 lines.
- The provider is tested once. `PersistenceProvider`, `IdentityProvider` and
  `KnowledgeProvider` no longer appear in `container.py`.
- Some builders depend on others' results, so the call order in
  `_build_container` matters. Architecture jobs need the breakdown mapper from
  the backlog graph, and document ingestion needs reference knowledge. These
  dependencies are explicit parameters, not shared locals.
- Callers import these names from their new modules; there are no re-export
  aliases.

## Alternatives Considered

- **Keep one module.** Rejected: the size itself was the review finding, and the
  rule's purpose (one place names adapters) survives a package.
- **Split by bounded context in one pass.** Done in two steps instead. The
  persistence branches leaked backend-specific locals (the PostgreSQL store,
  activity projection, memory lock) into the worklist and knowledge wiring, so
  persistence was extracted first. Those locals now stay behind
  `PersistenceAdapters`.
- **Move the backlog use-case graph into a builder too.** Rejected: it uses
  nearly every other context's output and fills most `Container` fields. A
  builder would only rename the same list of locals.
