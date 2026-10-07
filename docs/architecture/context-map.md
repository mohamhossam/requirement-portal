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
| `analysis` (`analysis_collaboration`, `confirm_requirement_analysis`) calls screening for answer suggestions, the confirmation gate and suggestion provenance | `analysis` owns `AnswerSuggestionRequestPort`, `KnowledgeGatePort` and `SuggestionProvenancePort`, implemented in the composition root by `knowledge`'s classes (Amendment 1, F1; done in PR 10) |
| `breakdown` imports `governance` in three places: `feature_review.py:25-26` (`approval_policy`, `approval_workflow`), `generation_checks.py:25,231` (`RefreshSavedBreakdownReview`) and `generation_checks.py:117` (`BreakdownReviewPolicy` scoring unsaved candidates) | The split is: (1) `ApproveFeature` and `approve_epic` move to `governance`, so `breakdown` keeps edit and generate only (`ApproveFeature` is `application/use_cases/approve_feature.py` since PR 11). (2) `breakdown` owns a `CandidateReviewPort`, which returns feedback on unsaved candidates and is implemented in the composition root by governance's review policy. (3) The saved-review refresh after Stories are saved becomes a governance handler on `StoriesChanged`, ordered after the approval reset |
| `analysis`, `breakdown` and `jobs` import `generation_context` (`workflows`) | The shared `ExpectedContextPort` (`application/ports/expected_context.py`) holds only the context-agnostic `guard`. Each context owns a port extending it with the tokens it reads, because those take its own types: analysis's `AnalysisContextPort` (PR 10) and breakdown's `BreakdownContextPort` (PR 11). `GenerationContextTokens` implements them all (Amendment 1, F2, refined in PR 11) |

## Module mapping

Paths are relative to `src/smb_requirement_agent/`. Ports move with the use cases that own them; a port that another context implements or calls goes in the owner's `application/ports/`.

### Domain packages

| Current | Target |
|---|---|
| `shared_kernel/*`: done in PR 3, formerly `domain/shared`. Since PR 2 it also holds `RequirementId`, the actor types re-exported from `smb_kernel`, `PublishedReference`, `normalize_search`, `SourceLineage` and `merge_lineage` | `shared_kernel/` |
| `domain/requirement/*` | `requirements/domain/requirement/` (done in PR 9) |
| `domain/document/{entities,attachment,ingestion,value_objects,errors}.py` | `requirements/domain/document/` (done in PR 9) |
| `domain/document/lineage.py` (`ImpactDecision`, after PR 2) | `knowledge/domain/` (source impact) |
| `domain/document/reference.py` | `references/domain/`; its `to_payload`/`from_payload` move to infrastructure in PR 2 |
| `domain/analysis/*` | `analysis/domain/` (done in PR 10, with `lineage.py`, formerly `application/use_cases/source_lineage.py`) |
| `domain/epic/*`, `domain/feature/*`, `domain/story/*` | `breakdown/domain/{epic,feature,story}/` (done in PR 11) |
| `domain/architecture/{entities,errors,events}.py` (impact) | `breakdown/domain/architecture/` (done in PR 11) |
| `domain/architecture/knowledge.py` (catalogue) | `references/domain/`; its duplicate-named error becomes `InvalidRelationshipKindError` in PR 2 |
| `domain/review/*`, `domain/revision/*` | `governance/domain/` |
| `domain/knowledge/historic.py` | `references/domain/`; its codec moves to infrastructure in PR 2, and its content-page parsing to the ACL in PR 15a |
| `domain/knowledge/{entities,membership,prior_art}.py` | `knowledge/domain/` |
| `domain/knowledge/errors.py` | split: `InvalidKnowledgeError` to `references/domain/`; the finding, review, retirement and membership errors to `knowledge/domain/` |
| `domain/identity/*` | `identity/domain/` (done in PR 7) |
| `domain/jobs/*` | `jobs/domain/` (done in PR 8) |

### Use cases (`application/use_cases/`)

| Target | Modules |
|---|---|
| `identity` | none. `identity_access` moves to `workflows` (F4); `identity` publishes `RequirementAccessPort` |
| `jobs` | `job_execution_context`, `provider_call_rate`, `retention` (in `jobs/application/use_cases/` since PR 8). `leased_jobs` is breakdown's (PR 8 correction) |
| `requirements` | `create_requirement`, `update_requirement`, `get_requirement`, `requirement_drafts`, `owned_requirements`, `requirement_sources`, `documents`, `attachment_ingestion`; plus `application/document_upload_validation.py` (all in `requirements/application/` since PR 9) |
| `references` | `historic_corpus`, `knowledge_event_cursor`, `knowledge_views`, `qualify_chunk_tokens`, `reference_currency` (its citation half); plus `application/{grounding,retrieval}_evaluation.py` |
| `analysis` | `analyze_requirement`, `get_requirement_analysis`, `clarify_requirement_analysis`, `confirm_requirement_analysis`, `analysis_collaboration`, `analysis_mapping`, `analysis_reconciliation`, `evidence_analysis`, `generation_effects`, `analysis_documents` (`AssembleAnalysisDocuments`, split from `documents` in PR 9), `reference_grounding`, `discard_analysis` (the `RequirementRevised` handler, PR 4), all in `analysis/application/use_cases/` since PR 10; and the analysis half of `reference_currency` (`stale_analysis`, `stale_proposals`; split in PR 15a) |
| `knowledge` | `requirement_knowledge`, `requirement_indexing`, `rebuild_knowledge_index`, `knowledge_portfolio`, `corpus_actions`, `unified_knowledge_search`, `prior_art`, `source_impact`, `answer_suggestions`; plus `application/prior_art_evaluation.py` |
| `breakdown` | `generate_epic`, `edit_epic`, `get_epic`, `generate_features`, `feature_review` (`GetFeatures`, `EditFeature`), `story_workflow`, `story_change_proposals`, `story_quality`, `generation_checks` (through `CandidateReviewPort`), `architecture_mapping`, `architecture_mapping_jobs`, `leased_jobs` (the mapping queue's lease logic, reassigned from `jobs` in PR 8), `mark_backlog_stale` (the staleness handler, PR 4); all in `breakdown/application/use_cases/` since PR 11 |
| `governance` | `breakdown_review` (with `GovernanceCandidateReview`, which implements breakdown's `CandidateReviewPort`), `reset_approval_workflow` (the review-reset handler, PR 5), `breakdown_review_evidence`, `approval_workflow`, `approve_epic`, `approve_feature` (`ApproveFeature`, split from breakdown's `feature_review` in PR 11), `revision_history`, `export_breakdown`, `knowledge_handoff` (F7); plus `application/exports.py`. Governance domain code since PR 6: `domain/review/{fingerprints,evidence,policy,readiness}.py` (formerly `approval_policy`, `breakdown_review_evidence`, `breakdown_review_policy`, and the readiness helpers of `approval_workflow`) |
| `reporting` | `requirement_worklist`, `activity_reporting`, `saved_views`, `dependency_projection` |
| `workflows` | `requirement_commands`, `ai_job_execution`, `ai_job_scheduling`, `ai_jobs` (F3), `identity_access` (F4), `generation_context` (behind `ExpectedContextPort`, F2), `requirement_impact` (F6), `internal_reads`. `source_lineage` is analysis domain code instead (PR 10 correction to F6: pure functions over `RequirementAnalysis`) |
| removed in PR 5 | `invalidate_derived_artifacts` and `invalidate_approval_workflow`. Use cases publish domain events; the handlers are `discard_analysis`, `mark_backlog_stale` and `reset_approval_workflow` |
| shared technical `application/` | `application/errors.py` (base errors only; context errors move to their context, F5), `ports/transaction_manager.py`, `ports/external_work.py`, `ports/domain_events.py` and `events.py` (the dispatcher, PR 4), `ports/expected_context.py` (`ExpectedContextPort`, PR 10) |
| interfaces | `application/public_errors.py` moves beside `interfaces/api/error_handlers.py` (F5) |

### Ports (`application/ports/`)

| Target | Ports |
|---|---|
| `identity` | `access_repository`, `actor_directory`, `identity` (in `identity/application/ports/` since PR 7), new `RequirementAccessPort` (PR 14, with `identity_access`) |
| `jobs` | `ai_jobs`, `notifications` (in `jobs/application/ports/` since PR 8) |
| `requirements` | `attachment_ingestions`, `document_repository`, `requirement_draft_repository`, `requirement_repository`, `screening_requests` (`ScreeningRequestPort`, PR 5); in `requirements/application/ports/` since PR 9 |
| `references` | `architecture_knowledge` (returning its own match type, F8), `embedding`, `historic_corpus`, `knowledge_events`, `knowledge_views`, `reference_publications`, the outbox and inbox ports of `knowledge_handoff`, the citation half of `reference_grounding` |
| `analysis` | `analysis_audit_repository`, `requirement_analysis_repository`, `requirement_analyzer`, `requirement_evidence_analyzer`, `reference_analysis` (the analysis half of `reference_grounding`), `knowledge_screening` (`AnswerSuggestionRequestPort`, `KnowledgeGatePort`, `SuggestionProvenancePort`); all in `analysis/application/ports/` since PR 10. Analysis asks for a screen through requirements' `ScreeningRequestPort` rather than a copy of it |
| `knowledge` | `source_dependencies` (the reverse evidence index and `ImpactDecision`s; reassigned from `requirements` in PR 9), `corpus_membership`, `corpus_summary`, `knowledge_portfolio`, `knowledge_index_generations`, `requirement_indexing`, `requirement_knowledge`, `prior_art` |
| `breakdown` | `architecture_jobs`, `architecture_mapping_stats`, `epic_generator`, `epic_repository`, `feature_generator`, `feature_repository`, `generation_guidance`, `story_generator`, `story_quality_evaluator`, `story_quality_repository`, `story_repository`, `candidate_review` (`CandidateReviewPort`, PR 5), `breakdown_context` (`BreakdownContextPort`, PR 11); all in `breakdown/application/ports/` since PR 11 |
| `governance` | `backlog_export`, `breakdown_repository`, `breakdown_review_repository` |
| `reporting` | `activity`, `requirement_worklist`, `saved_views` |

### Infrastructure

| Current | Target |
|---|---|
| `infrastructure/persistence/{postgres_store,postgres_session,migrate,migration_runner,in_memory_transaction,postgres_values}.py`, `migrations/` | stays in shared `infrastructure/persistence/` |
| `infrastructure/persistence/*_payloads.py` and per-aggregate repositories | the owning context's `infrastructure/` (for example `analysis_payloads.py` → `analysis/infrastructure/`, done in PR 10 with the analysis repositories, now `postgres_analysis.py`, and the evidence-fragment caches) ; and `backlog_payloads.py`, the in-memory backlog repositories, the mapping queue and stats adapters and `story_quality_repository.py` to `breakdown/infrastructure/` in PR 11, with the PostgreSQL backlog repositories, now `postgres_backlog.py` |
| `infrastructure/persistence/{activity_projection,postgres_worklist,in_memory_worklist}.py` | `reporting/infrastructure/` |
| `infrastructure/persistence/{historic_corpus,reference_publications,knowledge_payloads}.py` | `references/infrastructure/` |
| `infrastructure/persistence/{knowledge_portfolio,postgres_requirement_knowledge}.py` | `knowledge/infrastructure/` |
| `infrastructure/knowledge_client.py` | `references/infrastructure/` (the ACL) |
| `infrastructure/documents/attachment_worker.py`; `infrastructure/persistence/{attachment_ingestions,document_payloads,in_memory_document_repository,in_memory_requirement_draft_repository,in_memory_requirement_repository,postgres_document_metadata,postgres_document_repository,requirement_snapshot}.py`; `PostgresRequirementRepository` and `PostgresRequirementDraftRepository` from `postgres_repositories.py` | `requirements/infrastructure/` (done in PR 9; the PostgreSQL pair is now `postgres_requirements.py`) |
| `infrastructure/documents/ingestion_loop.py` | stays shared: the polling loop the requirements, references and knowledge workers all run (PR 9) |
| `infrastructure/persistence/backfill_document_blobs.py` | stays: operators run it by its module path (`docs/operations/production-readiness-maintenance.md`) |
| `infrastructure/persistence/source_dependencies.py` | `knowledge/infrastructure/`, with its port (PR 9 correction) |
| `infrastructure/identity/`, `infrastructure/persistence/{identity_payloads,in_memory_identity}.py`, and `PostgresAccessRepository` and `PostgresActorDirectory` from `postgres_repositories.py` | `identity/infrastructure/` (done in PR 7; the PostgreSQL pair is now `postgres_identity.py`) |
| `infrastructure/persistence/{in_memory_ai_jobs,postgres_ai_jobs}.py` | `jobs/infrastructure/` (done in PR 8) |
| `infrastructure/jobs/` (PR 8 correction: these workers run other contexts' work, so `jobs` cannot hold them) | `architecture_job_worker.py` → `breakdown/infrastructure/` (done in PR 11); `polling_worker.py` (drives `ExecuteAiJob`) → `workflows/infrastructure/`; `prior_art_gate.py`, `requirement_index_worker.py` → `knowledge/infrastructure/` |
| `infrastructure/exports/` | `governance/infrastructure/` |
| `infrastructure/llm/` adapters for one context's port | that context's `infrastructure/llm/`; the shared transport and provider selection helpers stay in `infrastructure/llm/`. Done as one step after PR 11: `candidate_mappers.py` and the OpenAI and OpenRouter adapter modules mix analysis and breakdown |
| `infrastructure/config/`, `infrastructure/text/` | unchanged |

### Interfaces

These do not move: `interfaces/api/{routes,schemas,dependencies.py,error_handlers.py,container.py}`, the worker and the CLI. `application/public_errors.py` joins them (F5).

The composition builders become one per context:

| Current builder | Target |
|---|---|
| `composition/requirements.py`, `composition/documents.py` | merged into `requirements.py` (done in PR 9) |
| `composition/analysis.py`, `composition/analysis_workflow.py` | merged into `analysis.py` (done in PR 10) |
| `composition/breakdown.py` | `breakdown.py` (it also holds the mapping-job wiring since PR 11) |
| `composition/review.py` | `governance.py` |
| `composition/knowledge_service.py` | `references.py` |
| `composition/architecture.py` | merged into `breakdown.py` in PR 11: by then it held only the mapping jobs (`build_architecture_jobs`); catalogue retrieval is in `knowledge_service.py`, which becomes `references.py` |
| `composition/knowledge.py` | `knowledge.py` |
| `composition/identity.py` | `identity.py` |
| `composition/jobs.py` | `jobs.py` |

New: `composition/events.py`, the only place handlers are subscribed. Unchanged: `persistence.py`, `llm.py`, `projections.py` and `operations.py`, which are technical and are not contexts.
