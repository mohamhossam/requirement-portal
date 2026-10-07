# Context map

The bounded contexts of requirement-portal, how they relate, and which current module belongs to
each. The decision is [ADR-0103](adr-0103-bounded-context-packages-and-domain-events.md), accepted
2026-10-07. The migration that produces this layout is
[`docs/slices/refactor-bounded-contexts.md`](../slices/refactor-bounded-contexts.md). The terms used
here are defined in [`ubiquitous-language.md`](ubiquitous-language.md).

Until the migration completes, the "current" column is where the code really is.

## Contexts

| Context | Type | Purpose | Aggregates and models |
|---|---|---|---|
| `requirements` | core | Capture a business need and its source evidence | `Requirement`, `RequirementDraft`, `SourceDocument` and its versions, `AttachmentUpload`/`AttachmentFile` |
| `analysis` | core | Separate what is known from what is assumed, and close the gaps with people | `RequirementAnalysis` (with `IntentProposal`), `ClarificationQuestion`, `AnalysisRound` |
| `breakdown` | core | Decompose a confirmed analysis into Epic → Feature → Story, with quality and architecture impact | `Epic`, `Feature`, `UserStory`, `StoryChangeProposal`, `FeatureQualitySnapshot`, `ArchitectureImpact` (value object) |
| `governance` | core | Review the whole breakdown, approve it against its exact content, keep its history, export it | `BreakdownReview` (with flags, decisions, dependencies, risks, recommendations), `RequirementRevision`, `BreakdownRevision`, approval fingerprints |
| `knowledge` | supporting | Ground requirements in the reviewed library, the architecture catalogue and historic requirements; holds the ACL to knowledge-portal | `KnowledgeFinding`, `KnowledgeScreen`, `CorpusMembership`, `PriorArtCheck`, historic state, reference document state, the architecture catalogue view |
| `identity` | generic | Who the actor is and what they may do with a Requirement | `RequirementAccess`, `DraftOwnership`; actor types from `smb_kernel` |
| `jobs` | generic | Durable, leased AI work and the notifications it produces | `AiJob`, `ActorNotification` |
| `reporting` | read side | Worklist, activity and saved views, derived from the other contexts | projections only; `SavedRequirementView` |
| `workflows` | orchestration | Commands and jobs that span several contexts | none (application only) |
| `shared_kernel` | shared kernel | The review lifecycle and identities every core context uses | `ReviewableGeneration`, `Approval`, `Staleness`, `Provenance`, `ActionAvailability`, `RequirementId`, `ActorSnapshot`, `SourceLineage`, `DomainEvent` |

## Relationships

```
                         knowledge-portal (separate service)
                          ▲ change-request outbox     │ event feed + HTTP (published language)
                          │                           ▼
 workflows ─► reporting ─► governance ─► breakdown ─► analysis ─► knowledge ─► requirements ─► {jobs | identity}
                                                                     (ACL)
          every context ───────────────────────────────────────────────────────► shared_kernel
          every context ───────────────────────────────────────────────────────► smb_kernel (conformist)
```

An arrow means "depends on". It runs from downstream to upstream.

- **Shared kernel.** `shared_kernel` is used by every context. A change to it is a change to all of them, so it needs agreement from every context and is kept small.
- **Customer/supplier along the chain.**
  - `analysis` is a customer of `requirements` and `knowledge`.
  - `breakdown` is a customer of `analysis` and `knowledge`.
  - `governance` is a customer of `breakdown`, `analysis` and `requirements`.
  - `reporting` is a customer of everything it projects.

  A supplier offers a published surface (`application/published.py`, `application/ports/`, `domain/`) and never imports its customer.
- **`knowledge` → knowledge-portal: anticorruption layer.**
  - `knowledge/infrastructure/knowledge_client.py`, today `infrastructure/knowledge_client.py` (ADR-0099), translates knowledge-portal's HTTP contract into this service's port types.
  - It is conformist to knowledge-portal's event feed (`knowledge_events`).
  - The contract lives in `contracts/knowledge-internal.openapi.json`.
- **knowledge-portal → this service: open host service.**
  - knowledge-portal reads `/internal/*` (`workflows`, via `internal_reads`) through `contracts/requirement-internal.openapi.json`.
  - Approved backlogs leave through the `approved_backlog_handoffs` outbox (ADR-0101 step 7), which the `knowledge` ACL delivers.
- **Every context → `smb_kernel`: conformist** (ADR-0100). Only its pure contract modules are visible to domain and application code.
- **`identity` → `smb_kernel.identity`: conformist.** OIDC and fake adapters live in the kernel.

### Reverse dependencies that exist today, and their replacements

| Today (upstream calls downstream) | After ADR-0103 |
|---|---|
| `requirements` (`UpdateRequirement`, document commands) calls `InvalidateDerivedArtifacts`, which reaches `analysis`, `breakdown` and `governance` | Publishes `RequirementRevised`; each consumer's handler reacts |
| `breakdown` (Epic, Feature, Story, mapping commands) calls `InvalidateApprovalWorkflow` in `governance` | Publishes `EpicChanged`, `FeatureChanged`, `FeaturesReplaced`, `StoriesChanged`, `ArchitectureImpactChanged`; governance's handler resets the review |
| `requirements` (`CreateOwnedRequirement`, `PromoteOwnedRequirementDraft` in `owned_requirements.py:46,156`, `UpdateRequirementWithImpact` in `requirement_impact.py:98`) and `analysis` (`analysis_collaboration.py:356,637`) call the knowledge-screen scheduler | `analysis` is downstream of `knowledge` and keeps calling the scheduler through `knowledge`'s published surface. `requirements` is upstream, so it calls a `ScreeningRequestPort` that it owns, which the composition root implements with `knowledge`'s scheduler. This is dependency inversion rather than an event, because the three call sites schedule screening but the other `RequirementRevised` publishers (the document commands) do not. An event would change that behaviour |
| `breakdown` imports `governance` in three places: `feature_review.py:25-26` (`approval_policy`, `approval_workflow`), `generation_checks.py:25,231` (`RefreshSavedBreakdownReview`) and `generation_checks.py:117` (`BreakdownReviewPolicy` scoring unsaved candidates) | The split is: (1) `ApproveFeature` and `approve_epic` move to `governance`, so `breakdown` keeps edit and generate only. (2) `breakdown` owns a `CandidateReviewPort`, which returns feedback on unsaved candidates and is implemented in the composition root by governance's review policy. (3) The saved-review refresh after Stories are saved becomes a governance handler on `StoriesChanged`, ordered after the approval reset. Its exact position is confirmed by the characterisation tests in PR 1 |

## Module mapping

Paths are relative to `src/smb_requirement_agent/`. Ports move with the use cases that own them; a port that another context implements or calls goes in the owner's `application/ports/`.

### Domain packages

| Current | Target |
|---|---|
| `domain/shared/*` | `shared_kernel/` |
| `domain/requirement/value_objects.py` `RequirementId` | `shared_kernel/` (the rest stays in `requirements/domain/`) |
| `domain/requirement/*` | `requirements/domain/` |
| `domain/document/{entities,attachment,ingestion,value_objects,errors}.py` | `requirements/domain/` |
| `domain/document/lineage.py` | `shared_kernel/` (used by `ReviewableGeneration`) |
| `domain/document/reference.py` | `knowledge/domain/`; its `to_payload`/`from_payload` go to `knowledge/infrastructure/` |
| `domain/analysis/*` | `analysis/domain/` |
| `domain/epic/*`, `domain/feature/*`, `domain/story/*` | `breakdown/domain/` |
| `domain/architecture/entities.py` (impact) | `breakdown/domain/` |
| `domain/architecture/knowledge.py` (catalogue) | `knowledge/domain/`; its duplicate `InvalidKnowledgeError` is merged with `domain/knowledge/errors.py` |
| `domain/review/*`, `domain/revision/*` | `governance/domain/` |
| `domain/knowledge/*` | `knowledge/domain/`; the payload parsing in `historic.py` goes to `knowledge/infrastructure/` |
| `domain/identity/*` | `identity/domain/`; `ActorSnapshot` goes to `shared_kernel/` |
| `domain/jobs/*` | `jobs/domain/` |

### Use cases (`application/use_cases/`)

| Target | Modules |
|---|---|
| `identity` | `identity_access` |
| `jobs` | `ai_jobs`, `ai_job_scheduling`, `leased_jobs`, `job_execution_context`, `provider_call_rate`, `retention` |
| `requirements` | `create_requirement`, `update_requirement`, `get_requirement`, `requirement_drafts`, `owned_requirements`, `requirement_impact`, `requirement_sources`, `documents`, `attachment_ingestion`, `source_lineage`; plus `application/document_upload_validation.py` |
| `knowledge` | `requirement_knowledge`, `requirement_indexing`, `rebuild_knowledge_index`, `qualify_chunk_tokens`, `unified_knowledge_search`, `knowledge_views`, `knowledge_portfolio`, `corpus_actions`, `historic_corpus`, `prior_art`, `knowledge_event_cursor`, `reference_currency`, `source_impact`, `knowledge_handoff`; plus `application/{grounding,retrieval,prior_art}_evaluation.py` |
| `analysis` | `analyze_requirement`, `get_requirement_analysis`, `clarify_requirement_analysis`, `confirm_requirement_analysis`, `analysis_collaboration`, `analysis_mapping`, `analysis_reconciliation`, `answer_suggestions`, `evidence_analysis`, `generation_effects`, `reference_grounding` |
| `breakdown` | `generate_epic`, `edit_epic`, `get_epic`, `generate_features`, `feature_review` (`GetFeatures`, `EditFeature`), `story_workflow`, `story_change_proposals`, `story_quality`, `generation_checks` (through `CandidateReviewPort`), `architecture_mapping`, `architecture_mapping_jobs` |
| `governance` | `breakdown_review`, `breakdown_review_evidence`, `approval_workflow`, `approve_epic`, `feature_review` (`ApproveFeature`), `revision_history`, `export_breakdown`; plus `application/exports.py`. `approval_policy` (fingerprints, blocker policy) and `breakdown_review_policy` (flags, risks, recommendations) become governance domain code |
| `reporting` | `requirement_worklist`, `activity_reporting`, `saved_views`, `dependency_projection` |
| `workflows` | `requirement_commands`, `ai_job_execution`, `generation_context`, `internal_reads` |
| becomes event handlers | `invalidate_derived_artifacts`, `invalidate_approval_workflow` |
| shared technical `application/` | `application/errors.py` (base errors), `application/public_errors.py`, `ports/transaction_manager.py`, `ports/external_work.py`, new `events.py` |

### Infrastructure

| Current | Target |
|---|---|
| `infrastructure/persistence/{postgres_store,postgres_session,migrate,migration_runner,in_memory_transaction,postgres_values}.py`, `migrations/` | stays in shared `infrastructure/persistence/` |
| `infrastructure/persistence/*_payloads.py` and per-aggregate repositories | the owning context's `infrastructure/` (for example `analysis_payloads.py` → `analysis/infrastructure/`) |
| `infrastructure/persistence/{activity_projection,postgres_worklist,in_memory_worklist}.py` | `reporting/infrastructure/` |
| `infrastructure/persistence/{historic_corpus,knowledge_portfolio,postgres_requirement_knowledge}.py` | `knowledge/infrastructure/` |
| `infrastructure/knowledge_client.py` | `knowledge/infrastructure/` (the ACL) |
| `infrastructure/documents/` | `requirements/infrastructure/` |
| `infrastructure/identity/` | `identity/infrastructure/` |
| `infrastructure/jobs/` | `jobs/infrastructure/` |
| `infrastructure/exports/` | `governance/infrastructure/` |
| `infrastructure/llm/` adapters for one context's port | that context's `infrastructure/llm/`; the shared transport and provider selection helpers stay in `infrastructure/llm/` |
| `infrastructure/config/`, `infrastructure/text/` | unchanged |

### Interfaces

These do not move: `interfaces/api/{routes,schemas,dependencies.py,error_handlers.py,container.py}`, the worker and the CLI.

The composition builders become one per context:

| Current builder | Target |
|---|---|
| `composition/requirements.py`, `composition/documents.py` | merged into `requirements.py` |
| `composition/analysis.py`, `composition/analysis_workflow.py` | merged into `analysis.py` |
| `composition/breakdown.py` | `breakdown.py` |
| `composition/review.py` | `governance.py` |
| `composition/knowledge.py`, `composition/knowledge_service.py`, `composition/architecture.py` | `knowledge.py` |
| `composition/identity.py` | `identity.py` |
| `composition/jobs.py` | `jobs.py` |

New: `composition/events.py`, the only place handlers are subscribed. Unchanged: `persistence.py`, `llm.py`, `projections.py` and `operations.py`, which are technical and are not contexts.
