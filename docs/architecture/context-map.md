# Context map

The bounded contexts of requirement-portal, how they relate, and which current module belongs to
each. The decision is [ADR-0103](adr-0103-bounded-context-packages-and-domain-events.md), accepted
2026-10-07, with its Amendment 1 (the same day), which splits `references` from `knowledge` and
places the modules PR 1's dependency report found. The migration that produces this layout is
[`docs/slices/refactor-bounded-contexts.md`](../slices/refactor-bounded-contexts.md). The terms used
here are defined in [`ubiquitous-language.md`](ubiquitous-language.md).

Until the migration completes, the "current" column is where the code really is.
`python scripts/context_dependency_report.py` lists the imports that still run against the
order below.

## Contexts

| Context | Type | Purpose | Aggregates and models |
|---|---|---|---|
| `requirements` | core | Capture a business need and its source evidence | `Requirement`, `RequirementDraft`, `SourceDocument` and its versions, `AttachmentUpload`/`AttachmentFile` |
| `references` | supporting | Read the reviewed library, the architecture catalogue and historic requirements published by knowledge-portal; holds the ACL to it | reference document state, historic requirement state, the architecture catalogue view, embeddings |
| `analysis` | core | Separate what is known from what is assumed, and close the gaps with people | `RequirementAnalysis` (with `IntentProposal`), `ClarificationQuestion`, `AnalysisRound` |
| `knowledge` | supporting | Screen a Requirement against its own corpus, the library and historic work; findings, answer suggestions, prior art, source impact | `KnowledgeFinding`, `KnowledgeScreen`, `CorpusMembership`, `PriorArtCheck`, `AnswerSuggestion` |
| `breakdown` | core | Decompose a confirmed analysis into Epic → Feature → Story, with quality and architecture impact | `Epic`, `Feature`, `UserStory`, `StoryChangeProposal`, `FeatureQualitySnapshot`, `ArchitectureImpact` (value object) |
| `governance` | core | Review the whole breakdown, approve it against its exact content, keep its history, export it and hand it off | `BreakdownReview` (with flags, decisions, dependencies, risks, recommendations), `RequirementRevision`, `BreakdownRevision`, approval fingerprints |
| `identity` | generic | Who the actor is and what they may do with a Requirement | `RequirementAccess`, `DraftOwnership` |
| `jobs` | generic | Durable, leased AI work and the notifications it produces | `AiJob`, `ActorNotification` |
| `reporting` | read side | Worklist, activity and saved views, derived from the other contexts | projections only; `SavedRequirementView` |
| `workflows` | orchestration | Commands, jobs, access checks and views that span several contexts | none (application only) |
| `shared_kernel` | shared kernel | The review lifecycle, identities and citations every core context uses | `ReviewableGeneration`, `Approval`, `Staleness`, `Provenance`, `ActionAvailability`, `RequirementId`, `ActorId`/`ActorProfile`/`ActorSnapshot`, `SourceLineage`, `PublishedReference`, `DomainEvent` |

## Relationships

```
                                         knowledge-portal (separate service)
                                          ▲ change-request outbox   │ event feed + HTTP (published language)
                                          │                         ▼
 workflows ─► reporting ─► governance ─► breakdown ─► knowledge ─► analysis ─► references ─► requirements ─► {jobs | identity}
                                                                               (ACL)
          every context ──────────────────────────────────────────────────────────────► shared_kernel
          every context ──────────────────────────────────────────────────────────────► smb_kernel (conformist)
```

An arrow means "depends on". It runs from downstream to upstream.

- **Shared kernel.** `shared_kernel` is used by every context. A change to it is a change to all of them, so it needs agreement from every context and is kept small.
- **Customer/supplier along the chain.**
  - `analysis` is a customer of `requirements` and `references`.
  - `knowledge` (screening) is a customer of `analysis`, `references` and `requirements`.
  - `breakdown` is a customer of `analysis`, `knowledge` and `references`.
  - `governance` is a customer of `breakdown`, `analysis` and `requirements`.
  - `reporting` is a customer of everything it projects.

  A supplier offers a published surface (`application/published.py`, `application/ports/`, `domain/`) and never imports its customer.
- **`references` → knowledge-portal: anticorruption layer.**
  - `references/infrastructure/knowledge_client.py`, today `infrastructure/knowledge_client.py` (ADR-0099), translates knowledge-portal's HTTP contract into this service's port types.
  - It is conformist to knowledge-portal's event feed (`knowledge_events`).
  - The contract lives in `contracts/knowledge-internal.openapi.json`.
- **knowledge-portal → this service: open host service.**
  - knowledge-portal reads `/internal/*` (`workflows`, via `internal_reads`) through `contracts/requirement-internal.openapi.json`.
  - Approved backlogs leave through the `approved_backlog_handoffs` outbox (ADR-0101 step 7). `governance` writes it, and the `references` ACL delivers it.
- **Every context → `smb_kernel`: conformist** (ADR-0100). Only its pure contract modules are visible to domain and application code.
- **`identity` → `smb_kernel.identity`: conformist.** OIDC and fake adapters live in the kernel.

### Reverse dependencies that exist today, and their replacements

| Today (upstream calls downstream) | After ADR-0103 |
|---|---|
| `requirements` (`UpdateRequirement`, document commands) calls `InvalidateDerivedArtifacts`, which reaches `analysis`, `breakdown` and `governance` | Publishes `RequirementRevised`; each consumer's handler reacts |
| `breakdown` (Epic, Feature, Story, mapping commands) calls `InvalidateApprovalWorkflow` in `governance` | Publishes `EpicChanged`, `FeatureChanged`, `FeaturesReplaced`, `StoriesChanged`, `ArchitectureImpactChanged`; governance's handler resets the review |
| `requirements` (`CreateOwnedRequirement`, `PromoteOwnedRequirementDraft` in `owned_requirements.py:46,156`, `UpdateRequirementWithImpact` in `requirement_impact.py:98`) and `analysis` (`analysis_collaboration.py:356,637`) call the knowledge-screen scheduler | Both are upstream of `knowledge`, so each calls a `ScreeningRequestPort` it owns, which the composition root implements with `knowledge`'s scheduler. This is dependency inversion rather than an event: those call sites schedule screening, but the other `RequirementRevised` publishers (the document commands) do not, and an event would change that |
| `analysis` (`analysis_collaboration`, `confirm_requirement_analysis`) calls screening for answer suggestions, the confirmation gate and suggestion provenance | `analysis` owns `AnswerSuggestionRequestPort`, `KnowledgeGatePort` and `SuggestionProvenancePort`, implemented in the composition root by `knowledge`'s classes (Amendment 1, F1) |
| `breakdown` imports `governance` in three places: `feature_review.py:25-26` (`approval_policy`, `approval_workflow`), `generation_checks.py:25,231` (`RefreshSavedBreakdownReview`) and `generation_checks.py:117` (`BreakdownReviewPolicy` scoring unsaved candidates) | The split is: (1) `ApproveFeature` and `approve_epic` move to `governance`, so `breakdown` keeps edit and generate only. (2) `breakdown` owns a `CandidateReviewPort`, which returns feedback on unsaved candidates and is implemented in the composition root by governance's review policy. (3) The saved-review refresh after Stories are saved becomes a governance handler on `StoriesChanged`, ordered after the approval reset |
| `analysis`, `breakdown` and `jobs` import `generation_context` (`workflows`) | They depend on an `ExpectedContextPort` in the shared `application/`, implemented by `GenerationContextTokens` (Amendment 1, F2) |

## Module mapping

Paths are relative to `src/smb_requirement_agent/`. Ports move with the use cases that own them; a port that another context implements or calls goes in the owner's `application/ports/`.

### Domain packages

| Current | Target |
|---|---|
| `domain/shared/*` | `shared_kernel/` |
| `domain/shared/{identifiers,actors,citation,lineage}.py` (PR 2: `RequirementId`; actors re-exported from `smb_kernel`; `PublishedReference` and `normalize_search`; `SourceLineage` and `merge_lineage`) | `shared_kernel/` |
| `domain/requirement/*` | `requirements/domain/` |
| `domain/document/{entities,attachment,ingestion,value_objects,errors}.py` | `requirements/domain/` |
| `domain/document/lineage.py` (`ImpactDecision`, after PR 2) | `knowledge/domain/` (source impact) |
| `domain/document/reference.py` | `references/domain/`; its `to_payload`/`from_payload` move to infrastructure in PR 2 |
| `domain/analysis/*` | `analysis/domain/` |
| `domain/epic/*`, `domain/feature/*`, `domain/story/*` | `breakdown/domain/` |
| `domain/architecture/entities.py` (impact) | `breakdown/domain/` |
| `domain/architecture/knowledge.py` (catalogue) | `references/domain/`; its duplicate-named error becomes `InvalidRelationshipKindError` in PR 2 |
| `domain/review/*`, `domain/revision/*` | `governance/domain/` |
| `domain/knowledge/historic.py` | `references/domain/`; its codec moves to infrastructure in PR 2, and its content-page parsing to the ACL in PR 15a |
| `domain/knowledge/{entities,membership,prior_art}.py` | `knowledge/domain/` |
| `domain/knowledge/errors.py` | split: `InvalidKnowledgeError` to `references/domain/`; the finding, review, retirement and membership errors to `knowledge/domain/` |
| `domain/identity/*` | `identity/domain/` |
| `domain/jobs/*` | `jobs/domain/` |

### Use cases (`application/use_cases/`)

| Target | Modules |
|---|---|
| `identity` | none. `identity_access` moves to `workflows` (F4); `identity` publishes `RequirementAccessPort` |
| `jobs` | `leased_jobs`, `job_execution_context`, `provider_call_rate`, `retention` |
| `requirements` | `create_requirement`, `update_requirement`, `get_requirement`, `requirement_drafts`, `owned_requirements`, `requirement_sources`, `documents`, `attachment_ingestion`; plus `application/document_upload_validation.py` |
| `references` | `historic_corpus`, `knowledge_event_cursor`, `knowledge_views`, `qualify_chunk_tokens`, `reference_currency` (its citation half); plus `application/{grounding,retrieval}_evaluation.py` |
| `analysis` | `analyze_requirement`, `get_requirement_analysis`, `clarify_requirement_analysis`, `confirm_requirement_analysis`, `analysis_collaboration`, `analysis_mapping`, `analysis_reconciliation`, `evidence_analysis`, `generation_effects`, `reference_grounding`, and the analysis half of `reference_currency` |
| `knowledge` | `requirement_knowledge`, `requirement_indexing`, `rebuild_knowledge_index`, `knowledge_portfolio`, `corpus_actions`, `unified_knowledge_search`, `prior_art`, `source_impact`, `answer_suggestions`; plus `application/prior_art_evaluation.py` |
| `breakdown` | `generate_epic`, `edit_epic`, `get_epic`, `generate_features`, `feature_review` (`GetFeatures`, `EditFeature`), `story_workflow`, `story_change_proposals`, `story_quality`, `generation_checks` (through `CandidateReviewPort`), `architecture_mapping`, `architecture_mapping_jobs` |
| `governance` | `breakdown_review`, `breakdown_review_evidence`, `approval_workflow`, `approve_epic`, `feature_review` (`ApproveFeature`), `revision_history`, `export_breakdown`, `knowledge_handoff` (F7); plus `application/exports.py`. `approval_policy` (fingerprints, blocker policy) and `breakdown_review_policy` (flags, risks, recommendations) become governance domain code |
| `reporting` | `requirement_worklist`, `activity_reporting`, `saved_views`, `dependency_projection` |
| `workflows` | `requirement_commands`, `ai_job_execution`, `ai_job_scheduling`, `ai_jobs` (F3), `identity_access` (F4), `generation_context` (behind `ExpectedContextPort`, F2), `source_lineage`, `requirement_impact` (F6), `internal_reads` |
| becomes event handlers | `invalidate_derived_artifacts`, `invalidate_approval_workflow` |
| shared technical `application/` | `application/errors.py` (base errors only; context errors move to their context, F5), `ports/transaction_manager.py`, `ports/external_work.py`, new `events.py`, new `ExpectedContextPort` |
| interfaces | `application/public_errors.py` moves beside `interfaces/api/error_handlers.py` (F5) |

### Ports (`application/ports/`)

| Target | Ports |
|---|---|
| `identity` | `access_repository`, `actor_directory`, `identity`, new `RequirementAccessPort` |
| `jobs` | `ai_jobs`, `notifications` |
| `requirements` | `attachment_ingestions`, `document_repository`, `requirement_draft_repository`, `requirement_repository`, `source_dependencies`, new `ScreeningRequestPort` |
| `references` | `architecture_knowledge` (returning its own match type, F8), `embedding`, `historic_corpus`, `knowledge_events`, `knowledge_views`, `reference_publications`, the outbox and inbox ports of `knowledge_handoff`, the citation half of `reference_grounding` |
| `analysis` | `analysis_audit_repository`, `requirement_analysis_repository`, `requirement_analyzer`, `requirement_evidence_analyzer`, the analysis half of `reference_grounding`, new `ScreeningRequestPort`, `AnswerSuggestionRequestPort`, `KnowledgeGatePort`, `SuggestionProvenancePort` |
| `knowledge` | `corpus_membership`, `corpus_summary`, `knowledge_portfolio`, `knowledge_index_generations`, `requirement_indexing`, `requirement_knowledge`, `prior_art` |
| `breakdown` | `architecture_jobs`, `architecture_mapping_stats`, `epic_generator`, `epic_repository`, `feature_generator`, `feature_repository`, `generation_guidance`, `story_generator`, `story_quality_evaluator`, `story_quality_repository`, `story_repository`, new `CandidateReviewPort` |
| `governance` | `backlog_export`, `breakdown_repository`, `breakdown_review_repository` |
| `reporting` | `activity`, `requirement_worklist`, `saved_views` |

### Infrastructure

| Current | Target |
|---|---|
| `infrastructure/persistence/{postgres_store,postgres_session,migrate,migration_runner,in_memory_transaction,postgres_values}.py`, `migrations/` | stays in shared `infrastructure/persistence/` |
| `infrastructure/persistence/*_payloads.py` and per-aggregate repositories | the owning context's `infrastructure/` (for example `analysis_payloads.py` → `analysis/infrastructure/`) |
| `infrastructure/persistence/{activity_projection,postgres_worklist,in_memory_worklist}.py` | `reporting/infrastructure/` |
| `infrastructure/persistence/{historic_corpus,reference_publications,knowledge_payloads}.py` | `references/infrastructure/` |
| `infrastructure/persistence/{knowledge_portfolio,postgres_requirement_knowledge}.py` | `knowledge/infrastructure/` |
| `infrastructure/knowledge_client.py` | `references/infrastructure/` (the ACL) |
| `infrastructure/documents/` | `requirements/infrastructure/` |
| `infrastructure/identity/` | `identity/infrastructure/` |
| `infrastructure/jobs/` | `jobs/infrastructure/` |
| `infrastructure/exports/` | `governance/infrastructure/` |
| `infrastructure/llm/` adapters for one context's port | that context's `infrastructure/llm/`; the shared transport and provider selection helpers stay in `infrastructure/llm/` |
| `infrastructure/config/`, `infrastructure/text/` | unchanged |

### Interfaces

These do not move: `interfaces/api/{routes,schemas,dependencies.py,error_handlers.py,container.py}`, the worker and the CLI. `application/public_errors.py` joins them (F5).

The composition builders become one per context:

| Current builder | Target |
|---|---|
| `composition/requirements.py`, `composition/documents.py` | merged into `requirements.py` |
| `composition/analysis.py`, `composition/analysis_workflow.py` | merged into `analysis.py` |
| `composition/breakdown.py` | `breakdown.py` |
| `composition/review.py` | `governance.py` |
| `composition/knowledge_service.py` | `references.py` |
| `composition/architecture.py` | split: catalogue retrieval and knowledge to `references.py`, mapping jobs (`build_architecture_jobs`) to `breakdown.py` |
| `composition/knowledge.py` | `knowledge.py` |
| `composition/identity.py` | `identity.py` |
| `composition/jobs.py` | `jobs.py` |

New: `composition/events.py`, the only place handlers are subscribed. Unchanged: `persistence.py`, `llm.py`, `projections.py` and `operations.py`, which are technical and are not contexts.
