# Architecture Decision Records

A structural decision that outlives the slice that made it belongs here, not in
a commit message and not only in a slice spec.

Record an ADR when a change:

- alters a layer boundary or the dependency direction,
- introduces or replaces a port,
- chooses between adapters or external providers,
- changes how the application is configured, wired, or started,
- reverses an earlier decision.

Do not write an ADR for ordinary implementation work inside an existing
boundary. The slice spec covers that.

## Format

One file per decision: `adr-NNNN-short-title.md`, numbered in sequence, using
`adr-template.md`. An ADR is immutable once accepted — to change a decision,
write a new ADR that supersedes it and update the older one's Status.

## Index

Search and AI grounding: [ADR-0064](adr-0064-unified-search-and-reference-answers.md), accepted.

Bounded contexts: [context map](context-map.md) and [ubiquitous language](ubiquitous-language.md), under [ADR-0103](adr-0103-bounded-context-packages-and-domain-events.md), accepted and implemented.

| ADR | Title | Status |
|---|---|---|
| [0001](adr-0001-composition-root-and-configuration.md) | Composition root and configuration | Accepted |
| [0002](adr-0002-central-error-translation.md) | Central error translation at the interface boundary | Accepted |
| [0003](adr-0003-epic-lifecycle-and-staleness.md) | Epic lifecycle and staleness | Accepted |
| [0004](adr-0004-derived-artifact-invalidation.md) | Derived-artifact invalidation | Accepted; mechanism superseded by ADR-0103 (semantics kept) |
| [0005](adr-0005-separate-generator-ports.md) | Separate generator ports per artifact | Accepted |
| [0006](adr-0006-local-openai-compatible-provider.md) | Local OpenAI-compatible LLM provider | Accepted |
| [0007](adr-0007-local-reasoning-and-operational-logs.md) | Local reasoning control and operational error logs | Accepted |
| [0008](adr-0008-human-clarification-context.md) | Preserve human clarifications as separate analysis context | Accepted |
| [0009](adr-0009-postgresql-revisions-and-context-memory.md) | PostgreSQL revisions and structured requirement memory | Accepted |
| [0010](adr-0010-explicit-analysis-confirmation-loop.md) | Explicit analysis confirmation loop | Accepted |
| [0011](adr-0011-durable-story-previews-and-provider-selection.md) | Durable Story previews and unified provider selection | Accepted |
| [0012](adr-0012-application-owned-worklist-read-model.md) | Application-owned worklist read model | Accepted |
| [0013](adr-0013-separate-resumable-requirement-drafts.md) | Separate resumable Requirement drafts | Accepted |
| [0014](adr-0014-immutable-source-document-versions.md) | Immutable source-document versions | Accepted |
| [0015](adr-0015-semantic-story-quality-boundary.md) | Semantic Story quality boundary | Accepted |
| [0016](adr-0016-deterministic-architecture-knowledge-mapping.md) | Deterministic architecture knowledge mapping | Accepted |
| [0017](adr-0017-durable-breakdown-review-snapshot.md) | Durable breakdown review snapshot | Accepted |
| [0018](adr-0018-identity-access-boundary.md) | Provider-neutral identity and Requirement access boundary | Accepted |
| [0019](adr-0019-collaborative-analysis-audit.md) | Stable clarification questions and immutable analysis rounds | Accepted |
| [0020](adr-0020-leased-durable-ai-jobs.md) | Leased durable AI jobs and actor notifications | Accepted |
| [0021](adr-0021-content-bound-approval-governance.md) | Content-bound approval governance | Accepted; amended by ADR-0103 |
| [0022](adr-0022-audit-derived-activity-reporting-and-private-saved-views.md) | Audit-derived activity/reporting and private saved views | Accepted |
| [0023](adr-0023-versioned-neutral-backlog-export.md) | Versioned neutral backlog export | Accepted |
| [0024](adr-0024-explicit-database-migrations.md) | Explicit database migrations outside API startup | Accepted |
| [0025](adr-0025-business-intent-proposals.md) | Owner-governed business intent proposals | Accepted |
| [0026](adr-0026-analysis-question-reconciliation.md) | Analysis-owned question reconciliation and provenance | Accepted |
| [0027](adr-0027-requirement-knowledge-grounded-suggestions.md) | Trusted requirement knowledge and grounded clarification suggestions | Accepted |
| [0028](adr-0028-automatic-dual-source-clarification-suggestions.md) | Automatic dual-source clarification suggestions | Accepted |
| [0029](adr-0029-structured-multimodal-brd-analysis.md) | Structured multimodal BRD analysis | Accepted |
| [0030](adr-0030-lazy-knowledge-screening-recovery.md) | Lazy knowledge screening and restart-safe recovery | Accepted |
| [0031](adr-0031-opt-in-sensitive-debug-trace.md) | Opt-in sensitive single-file debug trace | Accepted |
| [0032](adr-0032-focused-local-citation-recovery.md) | Focused local citation recovery | Accepted |
| [0033](adr-0033-openrouter-json-mode-provider.md) | OpenRouter JSON-mode provider | Accepted |
| [0034](adr-0034-authorization-and-concurrency-preconditions.md) | Application authorization and concurrency preconditions | Accepted |
| [0035](adr-0035-short-transactions-and-job-execution-ownership.md) | Short transactions and job execution ownership | Accepted |
| [0036](adr-0036-postgresql-document-blobs-and-bounded-extraction.md) | PostgreSQL document blobs and bounded extraction | Accepted |
| [0037](adr-0037-maintained-postgresql-worklist-projection.md) | Maintained PostgreSQL worklist projection | Accepted |
| [0038](adr-0038-derived-activity-and-knowledge-projections.md) | Derived activity and knowledge projections | Accepted; unverified implementation |
| [0039](adr-0039-postgresql-session-and-composition-ownership.md) | PostgreSQL session and composition ownership | Accepted; unverified implementation |
| [0040](adr-0040-keycloak-login-broker.md) | Keycloak login broker for password and company SSO | Accepted |
| [0042](adr-0042-business-need-attachments.md) | Business need attachments as prompt sources | Accepted |
| [0043](adr-0043-configured-llm-transports.md) | Configured LLM transports and isolated embedding generations | Accepted |
| [0044](adr-0044-human-answer-analysis-citations.md) | Human answer support in structured analysis | Accepted |
| [0045](adr-0045-focused-breakdown-workspace.md) | Focused Breakdown workspace | Accepted |
| [0051](adr-0051-reviewed-document-knowledge.md) | Reviewed document knowledge | Accepted; implementation in progress |
| [0052](adr-0052-reference-applicability-proposals.md) | Reference applicability remains an owner decision | Accepted |
| [0053](adr-0053-bounded-reference-context.md) | Exact child citations with bounded retrieval context | Accepted |
| [0054](adr-0054-table-corpus-builds.md) | Table children and explicit corpus member builds | Accepted |
| [0055](adr-0055-presentation-table-evidence.md) | Row-local presentation table evidence | Accepted |
| [0056](adr-0056-word-table-evidence.md) | Word table evidence preserves row exclusions | Accepted |
| [0057](adr-0057-delimited-row-evidence.md) | Delimited first records remain independently reviewable | Accepted |
| [0058](adr-0058-spreadsheet-merge-evidence.md) | Spreadsheet merged ranges remain row-local evidence | Accepted |
| [0059](adr-0059-text-section-evidence.md) | Text headings remain independently reviewed evidence | Accepted |
| [0060](adr-0060-word-prose-evidence.md) | Word prose corrections do not retain original metadata wording | Accepted |
| [0061](adr-0061-worksheet-name-evidence.md) | Worksheet names remain independently reviewed evidence | Accepted |

- [ADR-0062: Dedicated Requirement indexing and measured chunk qualification](0062-requirement-indexing-and-chunk-qualification.md)
- [ADR-0063: Library ownership and dependency visibility](adr-0063-library-ownership-and-dependencies.md)

- [ADR-0065: Scoped ingestion warnings, source previews and async attachments](adr-0065-document-ingestion-completion.md)

- [ADR-0066: Recorded source lineage and indexed impact reconciliation](adr-0066-source-lineage-and-impact-index.md)
- [ADR-0067: Versioned architecture knowledge and local hybrid retrieval](adr-0067-versioned-architecture-knowledge-and-local-rag.md)
- [ADR-0068: Architecture knowledge roles and release-scoped jobs](adr-0068-architecture-knowledge-roles-and-jobs.md)
- [ADR-0069: PostgreSQL connection pool and worker process separation](adr-0069-connection-pool-and-worker-process-separation.md)
- [ADR-0070: Requirement commands own their unit of work](adr-0070-requirement-command-units-of-work.md) — amended by ADR-0103
- [ADR-0071: The composition root is a package](adr-0071-composition-root-package.md) — amended by ADR-0103
- [ADR-0072: OpenAI runs on the shared structured-generation adapters](adr-0072-openai-on-shared-structured-adapters.md)
- [ADR-0073: Review action availability is a domain rule the API reports](adr-0073-review-action-availability.md)
- [ADR-0074: Production packaging and operability](adr-0074-production-packaging-and-operability.md)
- [ADR-0075: Submitted Requirements are readable workspace-wide](adr-0075-workspace-wide-read-visibility.md)
- [ADR-0076: Architecture job attempts commit only while they hold the lease](adr-0076-fenced-architecture-job-commits.md)
- [ADR-0077: Supply-chain gates in CI](adr-0077-supply-chain-gates.md)
- [ADR-0078: One authorization pattern for Requirement-scoped actions](adr-0078-one-requirement-authorization-pattern.md)
- [ADR-0079: Operational data retention and bounded polled lists](adr-0079-operational-data-retention.md)
- [ADR-0080: A static organisation catalogue, separate from versioned architecture releases](adr-0080-organisation-catalogue.md)
- [ADR-0081: Building the architecture catalogue from documents and catalogue files](adr-0081-catalogue-from-documents-and-files.md)
- [ADR-0082: Architecture mapping uses the configured models](adr-0082-configurable-architecture-models.md)
- [ADR-0083: Catalogue browser, shared sample requirements and the embedding cache](adr-0083-catalogue-browser-samples-and-embedding-cache.md)
- [ADR-0084: Named catalogue versions, one draft, and team-owned remapping](adr-0084-named-versions-and-team-owned-remap.md)
- [ADR-0085: Matching document names to catalogue systems, and inferred dependencies](adr-0085-catalogue-name-matching-and-inferred-dependencies.md)
- [ADR-0086: Spreadsheets as catalogue source documents](adr-0086-spreadsheet-sources-for-catalogue-documents.md)
- [ADR-0087: Connected systems in architecture impact mapping](adr-0087-connected-systems-in-impact-mapping.md)
- [ADR-0088: Typed system relationships](adr-0088-typed-system-relationships.md)
- [ADR-0089: Capability domains](adr-0089-capability-domains.md)
- [ADR-0090: Markdown as a catalogue source document](adr-0090-markdown-sources-for-catalogue-documents.md)
- [ADR-0091: Output-aware catalogue reading](adr-0091-output-aware-catalogue-reading.md)
- [ADR-0092: System components](adr-0092-system-components.md)
- [ADR-0093: Reading catalogue tables without a model](adr-0093-catalogue-table-reader.md)
- [ADR-0094: Landscape domains and system descriptions](adr-0094-landscape-domains-and-system-descriptions.md)
- [ADR-0095: Product offerings](adr-0095-product-offerings.md)
- [ADR-0096: Journeys and their derived flow](adr-0096-journeys.md)
- [ADR-0097: Product and journey context on impacts](adr-0097-product-and-journey-context-on-impacts.md)
- [ADR-0098: A three-repository platform beside the original application](adr-0098-three-repo-platform.md)
- [ADR-0099: The knowledge service boundary and its own database](adr-0099-knowledge-service-boundary.md)
- [ADR-0100: The platform kernel holds mechanisms, never meaning](adr-0100-platform-kernel.md)
- [ADR-0101: The product architecture explorer lives on the knowledge catalogue](adr-0101-product-architecture-explorer-on-the-catalogue.md)
- [ADR-0102: Historic Requirements and their Azure DevOps lineage](adr-0102-historic-requirements-and-ado-lineage.md)
- [ADR-0103: Bounded-context packages and in-process domain events](adr-0103-bounded-context-packages-and-domain-events.md) — Accepted; implemented 2026-10-08 (PRs 1–16)
- [ADR-0104: Independent portals with optional links](adr-0104-independent-portals-with-optional-links.md)
- [ADR-0105: Model-backed work runs only as a durable job](adr-0105-durable-only-provider-work.md) — Accepted; implemented 2026-10-09 (production hardening PR 4a and PR 4b)
- [ADR-0106: Provider limits shared by every process, a daily token budget, and edge limits](adr-0106-shared-provider-limits.md) — Accepted; implemented 2026-10-09 (production hardening PR 7)
- [ADR-0108: Signed releases deployed by tag, backups, and expand/contract migrations](adr-0108-releases-backups-and-migrations.md) — Accepted; implemented 2026-10-09 (production hardening PR 6)
- [ADR-0109: Frontend logic changes during the UI redesign are recorded exceptions](adr-0109-frontend-logic-exceptions.md) — Accepted; recorded 2026-10-09 (production hardening PR 5)
- [ADR-0110: Optional tracing: requests, jobs, SQL and calls, with trace context only for peers](adr-0110-optional-tracing.md) — Accepted; implemented 2026-10-10 (production hardening PR 14)
- [ADR-0111: Accepted risks](adr-0111-accepted-risks.md) — Accepted 2026-10-10 (production hardening PR 16)
- [ADR-0112: Azure DevOps publication through a REST adapter](adr-0112-ado-publication-adapter.md) — Accepted 2026-10-10 (Slice 12)
- [ADR-0113: A publication record and marker-based recovery](adr-0113-publication-record-and-safe-republish.md) — Accepted 2026-10-10 (Slice 13)
