# ADR 0099 — The knowledge service boundary and its own database

## Status

Accepted 2026-10-02. Follows ADR-0098. Amends ADR-0066 (source lineage) and ADR-0053 (bounded
reference context) where they assume one database.

## Context

In the snapshot, the library and the catalogues share a process and a database with requirements.
The coupling was inventoried before the split.

**The catalogues are fairly clean:**
- their tables are their own;
- their adapters use their own connections, not the requirement transaction;
- impact mapping reaches them through one method, `ArchitectureKnowledgePort.match`.

**The library is entangled:**
- **Attachments are library rows.** Requirement attachments are `library_documents` rows with
  `attachment_target` set. They are written in the same transaction as the requirement.
- **Requirement transactions lock library rows.** Currency checks (`require_current`,
  `stale_analysis`) take `FOR SHARE` locks on `library_documents` inside requirement transactions.
- **Grounding uses a concrete class.** `ReferenceGrounding` depends on the concrete
  `ReferenceKnowledge` class, not a port.
- **Storage and workers are shared.** One `document_blobs` table and one ingestion worker serve
  attachments, library sources and catalogue documents.
- **Joins cross the boundary.** Library governance joins requirement tables to list dependents.
  Mapping statistics run SQL over features and stories.
- **Mapping jobs live in catalogue tables.** MAPPING jobs, which write requirement backlogs, sit
  in `architecture_jobs`.

## Decision

**Each service owns its own database.**

| Knowledge database (knowledge-portal) | Requirements database (requirement-portal) |
|---|---|
| Library rows of `library_documents`, `library_submissions`, `library_chunks`, `library_embedding_cache` | Requirements, analyses, backlog, revisions, reviews, drafts, `source_documents` |
| Every `architecture_*` table except mapping jobs | `document_blobs`, for attachments only |
| `organisation_catalogue`, `organisation_audit` | The requirement knowledge index, `source_dependencies`, `source_impact_decisions`, `ai_jobs` |
| Its own `document_blobs`, and a `knowledge_events` transactional outbox | New tables: `requirement_attachment_ingestions`, architecture-mapping jobs, the `reference_publication_state` and `active_architecture_release` projections, and the `approved_backlog_handoffs` outbox (ADR-0101 Amendment 2) |

**The requirements service talks to knowledge only through ports.** Each port has an HTTP
adapter and a deterministic fake.

| Need | Port | Remote call |
|---|---|---|
| Map an item to systems | `ArchitectureKnowledgePort` | `POST /internal/architecture/match` |
| Search, cite and check publications | `ReferenceKnowledgePort` (new; replaces the concrete class) | `POST /internal/library/search` (query text), `GET /internal/library/documents/{id}` |
| The active release and publication currency | Local projections | Fed from `GET /internal/events?after=` |
| Hand an approved backlog to the catalogue (ADR-0101 Amendment 2) | `ChangeRequestInboxPort` | `POST /internal/change-requests`, from the `approved_backlog_handoffs` outbox |

**The knowledge service reads requirement data only through requirement-portal's internal API:**
- `GET /internal/references/{document}/dependents`;
- `GET /internal/architecture-mapping/stats`;
- `GET /internal/actors`.

**Internal calls carry a service token.** In fake identity mode it is a shared secret. In OIDC mode
it comes from Keycloak client credentials. nginx never routes `/internal/*`.

**Currency is checked against local state.** The knowledge service writes an event to its outbox
in the same transaction as each of these:
- publishing, withdrawing or superseding a library publication;
- activating a release.

The requirements worker polls the outbox into `reference_publication_state` and
`active_architecture_release`. Requirement transactions lock and check those local rows, where the
snapshot locked `library_documents`.

**Requirement-portal has an outbox too** (ADR-0101 Amendment 2). A breakdown's final approval
writes an `approved_backlog_handoffs` row in its own transaction, and a worker delivers it to the
knowledge service's change-request inbox, idempotently by approval. It is the one call from
requirement work that hands data to the knowledge service rather than reading from it.

**Attachments leave the library.** They get their own `requirement_attachment_ingestions` table and
their own worker. Both services reuse the kernel's scanner and extractor (ADR-0100). Each service
stores blobs in its own database.

**MAPPING jobs become requirement jobs**, run by the requirements worker.

**The order of work.** The untangling is done inside requirement-portal, behind these ports, while
everything still runs in one process. The knowledge code is removed only after that. Each
repository runs alone offline with fakes for the other service.

## Consequences

- **Withdrawal is eventually consistent.** A withdrawn or superseded publication reaches
  requirement-portal after one event poll (target ≤ 5 seconds), not under a database lock. An
  analysis confirmed inside that window may cite a publication withdrawn moments before. It is
  marked stale on the next poll, as any later withdrawal is. Tests that asserted "withdrawal during
  re-analysis" now assert "withdrawal observed during re-analysis".
- **No cross-database joins.** Dependent lists and mapping statistics cost a network call, and their
  privacy filtering happens in requirement-portal.
- **The services can be down separately.** If knowledge-portal is down:
  - mapping and reference search fail with a translated error;
  - requirement work that needs neither keeps going.
- **Data is seeded once.** The new platform is seeded from a backup of the original database. A
  `knowledge-portal import --verify` command copies the owned tables and blobs with their ids.
  After that, the moved tables are dropped from the requirements database.
- **Two OpenAPI contracts to keep.** Consumers pin the provider's published snapshot and run
  contract tests, and no request or response models are shared as code.

## Alternatives Considered

- **A separate service on a shared database.** It was rejected because the product owner asked for
  the knowledge service to own its data.
- **Keep the cross-service lock with a distributed transaction or a synchronous currency call.**
  It was rejected: either couples requirement commits to knowledge-portal availability. A local
  projection keeps requirement transactions local.
- **Send embedding vectors instead of query text.** It was rejected because both services would
  then have to stay on the same embedding model. knowledge-portal embeds the text it receives.
