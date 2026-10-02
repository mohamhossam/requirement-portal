# Enhancement — Knowledge Center (architecture, requirement and reference knowledge)

> Status: **planned; not started.** Decisions recorded 2026-09-26. Implementation
> must not begin until this spec (or its first sub-slice) is scheduled in
> `ROADMAP.md`. Sub-slice E reads from Azure DevOps. `AGENTS.md` allows ADO
> integration only through its roadmap slice, so scheduling E is an explicit
> roadmap change. Delivered as sub-slices A–F.

## Objective

Give knowledge administrators one place, the **Knowledge Center**, to:
- manage all the knowledge the application reasons with: architecture
  knowledge, the Requirement knowledge base, and the shared reference library;
- **bring in the organization's existing knowledge**:
  - historic BRDs, with their delivered Epic → Feature → Story breakdown
    imported from Azure DevOps for lineage;
  - architecture Word and Markdown documents;
- make sure every **new** Requirement, whether written as text or supplied as a
  document, is ingested into the Requirement knowledge base.

## User Outcome

- A knowledge administrator opens the Knowledge Center and sees what the
  application knows, what is stale or failing, and what needs a decision.
- They import a folder of old BRDs, link each to its root work item in Azure
  DevOps, and the application pulls the delivered breakdown. That history is
  then searchable and cited as prior art, with full lineage from BRD to Epic,
  Features and Stories.
- They bulk-upload the architecture Word and Markdown documents into a draft
  release.
- They retire obsolete Requirements so they stop producing duplicate warnings.
- Every six months owners are asked to re-confirm their knowledge.

## Recorded decisions

| # | Question | Decision |
|---|---|---|
| 1 | "Already existing knowledge" | Knowledge that exists **outside** the application and must be imported |
| 1a | Requirement sources | Old BRDs (documents), plus Azure DevOps for the delivered breakdown, giving lineage |
| 1b | Architecture sources | Word and Markdown files |
| 2 | Form | A separate area inside the same application, sharing sign-in and deployment |
| 3 | Authority | A new `knowledge_admin` role that can act across all knowledge, including overriding document owners |
| 4 | Requirement knowledge | Retiring obsolete Requirements from the corpus: yes. Importing historic Requirements as reference knowledge: yes |
| 5 | Review cycles | Yes, every 6 months (configurable) |
| 6 | Existing pages | Move `/architecture-knowledge` and `/documents/library` into the Knowledge Center |
| 6a | New Requirements | Every new Requirement, text or document, must be ingested into the Requirement knowledge base |

## Current state (as found)

**Architecture knowledge (Slice 14)**
- Versioned releases of the systems catalogue: systems, capabilities, squads and
  ownership, relationships, constraints.
- Supporting documents with an evidence index.
- Drafts, YAML import/export, build, preview, publish, reactivate and audit, at
  `/architecture-knowledge`, for `knowledge_maintainer`.
- Document extraction (`LocatedDocumentExtractor`) handles PDF, UTF-8 TXT
  (40-line windows) and DOCX paragraphs. **Markdown is not supported**, and
  legacy `.doc` is not either.

**Requirement knowledge (11A/11A.1/11B)**
- A trusted corpus with `KnowledgeSourceKind` values `source`, `clarification`,
  `intent_decision`, `current_analysis`, `confirmed_analysis` and
  `conflict_resolution`.
- Screening finds possible duplicates and contradictions. Findings are handled
  **one Requirement at a time, by its owner**. There is no portfolio-wide view of
  the corpus, index health or open findings, and no way to retire a Requirement
  from the corpus.
- **Gap:** content from **attached business-need documents is not part of the
  corpus**. A Requirement supplied as a document, with attachment-only
  analysis, contributes almost nothing to duplicate detection or suggestions
  until its analysis is confirmed, and even then only the extracted facts.

**Shared reference library**
- Reviewed documents with passage selection, owner approval, builds, activation
  and source impact, at `/documents/library`.
- Governed **only by each document's owner**, with no cross-document
  administration.

**Azure DevOps**
- `ADO_ORGANIZATION`, `ADO_PROJECT` and `ADO_TOKEN` are documented placeholders.
  No code reads them. ADO publication (Slices 12–13) is planned and not built.

**Reviews:** there is no periodic review or staleness concept for any
knowledge.

## Roles

| Client role (on `requirement-api`) | Keycloak group | Grants |
|---|---|---|
| `knowledge_admin` (new) | `requirement-ai-knowledge-admins` | Everything in the Knowledge Center: imports, retire and reinstate, bulk reindex, library owner override and withdrawal, review-cycle management |
| `knowledge_maintainer` (existing) | existing | Architecture knowledge editing, as today |
| `knowledge_reader` (existing) | existing | Read-only Knowledge Center dashboards and published knowledge |

- `knowledge_admin` also carries `app_user` and `knowledge_reader`. It is added
  to the fixed group set managed by the admin portal (sub-slice C there).
- Fake identity: the `fake-admin` persona (from the admin portal spec) also
  gains `knowledge_admin`. Otherwise add one knowledge-admin persona.
- Every `knowledge_admin` override and bulk action is audited: actor, reason,
  before/after.

## Sub-slices

### A — Knowledge Center foundation

- The `knowledge_admin` role (Keycloak via 8A.2, and fake identity).
- A top-level **Knowledge Center** area at `/knowledge-center`, with its own
  navigation, in the same application.
- **Move the existing pages**, with permanent redirects from the old URLs:
  - `/architecture-knowledge` → `/knowledge-center/architecture`;
  - `/documents/library` → `/knowledge-center/library`.

  The Requirement attachments page, `/documents`, stays in the main
  application. **Evidence deep links** used by Feature and Story impact panels
  (`/architecture-knowledge/releases/:id/evidence/:chunk`) keep working through
  redirects.
- **Inventory and health dashboard** (read-only):
  - counts and freshness per knowledge body;
  - Requirement corpus coverage (indexed, pending, failed, retired);
  - failed builds, ingestions and indexing;
  - open duplicate and contradiction findings, and how long they have been
    open;
  - items due or overdue for review (once D ships);
  - import runs (once E ships).

### B — Requirement knowledge base: completeness and management

- **Every new Requirement is ingested, text or document (decision 6a):**
  - Add a knowledge source kind, `attachment`, for the evidence blocks of
    attachments included in analysis.
  - They are chunked with citations to the document block, the same way
    library passages are cited.
  - They are indexed and screened by the existing fingerprinted jobs, when the
    Requirement is promoted and whenever an included attachment's version or
    inclusion changes.
  - Typed source fields continue to be indexed as today.
  - A document-only Requirement is therefore screened for duplicates and
    contradictions from the moment it is promoted.
- **Corpus browser:** per Requirement, which sources are in the corpus, index
  status, last screen and findings. Filter by status, owner and age.
- **Portfolio findings view:** all open possible duplicates and contradictions
  across Requirements, with age, owners and a link to the Requirement's
  Knowledge step. Decisions stay with the Requirement owners, as today.
  Knowledge admins can nudge (notify) the owners.
- **Bulk reindex and retry** for failed or stale Requirement indexes.
- **Retire and reinstate (decision 4):**
  - A knowledge admin retires an obsolete or cancelled Requirement from the
    corpus, with a reason.
  - A retired Requirement is excluded from screening and suggestions but stays
    fully readable. Its history is untouched.
  - Open findings that cite it are closed as "source retired", and the closure
    is recorded.
  - Reinstating re-indexes and re-screens it.
  - Retiring is a new domain rule: a new corpus-membership state with an audit
    trail.

### C — Library and architecture curation

- **Library across all documents:**
  - one list with owner, status, age, last review and citation count;
  - a review queue.
  - **Admin overrides:** reassign document ownership and withdraw a document,
    with a reason. Today both are owner-only. These are new domain behaviours
    that record the administrator and the reason, like Requirement ownership
    administration in the admin portal.
  - Bulk retry and rebuild.
- **Architecture documents (decision 1b):**
  - add **Markdown** support to architecture extraction, heading-aware, reusing
    the library's TXT/Markdown section extractor, so citations point to
    headings, not 40-line windows;
  - **bulk upload** of Word and Markdown files into a draft release, with
    per-file results;
  - legacy `.doc` files are refused with guidance to convert them to `.docx`.
- **Release comparison:** a side-by-side diff of two releases (systems,
  ownership, relationships, constraints, documents).

### D — Review cycles (decision 5)

- Architecture systems and library documents carry `last reviewed` and `review
  due` dates.
- The cycle length is configurable. The default is 180 days: a startup setting
  now, and a live setting once the admin portal's live settings ship.
- **Who confirms:**
  - architecture systems: a `knowledge_maintainer` confirms per system, or per
    release when every system is reconfirmed;
  - library documents: the document owner confirms;
  - a `knowledge_admin` can confirm on anyone's behalf, with a reason.
- **When a review is due:**
  - owners are notified through the existing notifications (8C) 14 days before,
    and again when the review is overdue;
  - overdue items are flagged on the dashboard and **marked in citations** ("not
    reviewed since …"). They are never silently removed from retrieval.
- Confirming records the actor and time in the knowledge audit.

### E — Import historic Requirements: BRDs and Azure DevOps lineage (decisions 1, 1a, 4)

**A historic Requirement.** A new, read-only reference concept, distinct from a
live Requirement: no workflow, no ownership, no approvals. It holds:
- one or more **BRD documents**, stored and extracted with the existing document
  pipeline (DOCX and PDF; `.doc` is refused with conversion guidance);
- an **ADO breakdown snapshot**: the linked root work item(s) and their whole
  hierarchy (Epic, Feature, User Story or PBI). For each item:
  - ADO ID, type, title, description and acceptance criteria (HTML sanitized to
    text);
  - state, area and iteration paths, tags;
  - parent and child links, revision number, and a URL back to ADO;
- **lineage links**: BRD → root work item(s), and on down the hierarchy;
- **provenance**: who imported it, when, the source file checksums, and the ADO
  revisions.

**Import flow (curator-driven)**
1. Upload BRDs in bulk as a batch, with per-file extraction results.
2. For each BRD, enter or pick its root ADO work item ID(s). Matching BRDs to
   ADO items automatically is a later option.
3. The application fetches the hierarchy **read-only** from ADO.
4. The curator reviews the combined preview (BRD and breakdown) and **publishes
   it as reference knowledge**.

Import runs are durable jobs, with progress, retry and a per-item error report.

**Azure DevOps read-only connector**
- An `AdoWorkItemSourcePort` with a REST adapter:
  - WIQL and work-item batch reads with relations;
  - pagination and throttling handling.
- A **deterministic fake adapter**, required by `AGENTS.md` §4.5.
- Configuration: organization or collection URL, project, and a read-only
  personal access token (scope *Work Items: Read*). The token is a secret: it
  lives in the environment and is shown in the admin portal only as present or
  missing.
- **Nothing is ever written to ADO.** ADO publication remains Slices 12–13.

**Refresh from ADO.** Re-fetch a historic Requirement's hierarchy and show a
diff: added, removed and changed items. The curator accepts it to publish a
new snapshot; old snapshots stay readable.

**Reference corpus**
- Published historic Requirements feed the knowledge base under new source
  kinds, `historic_brd` and `historic_backlog`, **marked lower-trust
  reference**. They never count as confirmed intent.
- Screening a new Requirement against them yields **"similar past requirement"
  (prior art)**. It is shown with its lineage, so the owner can see how similar
  work was broken down and delivered. It is informational and **does not block
  analysis confirmation**. Duplicate and contradiction gating still applies
  only between live Requirements.
- Unified search and answer suggestions can cite historic BRD passages and ADO
  items, labelled as historic.
- Historic Requirements can be retired like live ones.

### F — AI-assisted architecture catalogue extraction (optional, after C)

> Delivered early on 2026-09-29 for Word, PDF, text and images, without owners (ownership moved to
> the organisation catalogue): see `enhancement-squad-and-architecture-catalogues.md` and
> ADR-0081.

- Propose catalogue changes (systems, owners, relationships, constraints) from
  uploaded Word and Markdown architecture documents, as **reviewable candidates
  in a draft release**, each with citations.
- Nothing is published without a maintainer accepting each candidate. AI
  content is always a review candidate.

## Out of Scope

- Writing to Azure DevOps (Slices 12–13).
- Connectors that crawl SharePoint, Confluence or file shares. Import is by
  upload.
- Automatically matching BRDs to ADO items (a later option within E).
- Using historic breakdowns as generation examples for new Epics and Features.
  This is a generation-quality change that needs its own evaluation.
- OCR for scanned BRDs beyond the existing optional `document-ocr` path.
- A separate web application or hostname (decision 2).

## Domain

- **Corpus membership:** active or retired, with reason, actor and time
  (live and historic Requirements).
- **`KnowledgeSourceKind`:** add `attachment`, `historic_brd` and
  `historic_backlog`, plus a trust level (trusted or reference).
- **`KnowledgeRelationshipKind`:** add `similar_past_requirement`
  (informational, never blocking).
- **Historic Requirement:** BRD documents, ADO snapshot items with hierarchy and
  lineage links, provenance, snapshot versions.
- **Review state** on architecture systems and library documents:
  `last_reviewed_at`, `review_due_at`, reviewer.
- **Library document:** administrative owner reassignment and withdrawal,
  recording the admin and the reason.

## Application Use Cases

- `GetKnowledgeInventory`, `ListCorpus` and `ListPortfolioFindings` (A, B).
- `RetireFromCorpus`, `ReinstateToCorpus` and `BulkReindexRequirements` (B).
- `AdministerLibraryDocument` (reassign, withdraw), `BulkUploadArchitectureDocuments`
  and `CompareArchitectureReleases` (C).
- `ConfirmKnowledgeReview` and `ScheduleReviewReminders` (D).
- `StartHistoricImport`, `LinkBrdToWorkItems`, `FetchAdoHierarchy`,
  `PublishHistoricRequirement` and `RefreshHistoricRequirement` (E).
- `ProposeCatalogueChanges` and `DecideCatalogueCandidate` (F).
- Every admin action authorizes `knowledge_admin` (or the stated role) in the
  application layer and writes an audit entry in the same transaction.

## Ports

- `AdoWorkItemSourcePort`: new, with REST and fake adapters.
- `HistoricRequirementRepositoryPort`: new.
- Extensions to the existing knowledge index, screening, library and
  architecture repository ports for membership, trust level and review state.
- Existing document storage, extraction, embedding, job and notification ports
  are reused.

## Adapters

- PostgreSQL migrations (timestamped names) for:
  - corpus membership;
  - historic Requirements, snapshots and lineage;
  - review state;
  - import runs;
  - the new source and relationship kinds.
- A Markdown section extractor for architecture documents, reusing the
  library's.
- The ADO REST adapter (Azure DevOps Services and Server, selected by base URL)
  and a fake ADO adapter with a deterministic sample hierarchy.

## API

- `/knowledge-center/...` routes: inventory, corpus, findings, retire and
  reinstate, library administration, architecture bulk upload and comparison,
  reviews, historic imports and refresh.
- Existing architecture and library routes are unchanged, for compatibility.
- Import, reindex, rebuild and catalogue-extraction routes use the provider
  rate limit, and are added to `tests/architecture/test_provider_rate_limit.py`.
- OpenAPI and generated TypeScript types are regenerated.

## UI

- The Knowledge Center area, with its own navigation:
  - Overview;
  - Requirement knowledge (corpus, findings);
  - Historic Requirements (imports, lineage viewer: BRD → Epic → Features →
    Stories);
  - Architecture;
  - Library;
  - Reviews.
- Moved pages keep their behaviour; old URLs redirect.
- On a live Requirement's Knowledge step, prior-art matches appear as an
  informational section, clearly labelled historic, with a link to the
  lineage.
- Governed by `docs/ux-plan.md`, `docs/design-system.md` and WCAG 2.2 AA. This
  is feature work (new API client code, hooks and state), outside the
  redesign's presentation-only rule in `CLAUDE.md`, and must be scheduled as
  such.

## Business Rules

- Every promoted Requirement is ingested into the knowledge base: its typed
  fields and its analysis-included attachments. Ingestion status is visible,
  and failures are retryable.
- Historic knowledge is reference, never trusted intent. It informs but never
  blocks confirmation, and is always labelled historic, with provenance.
- Imports are read-only against ADO. Nothing in this slice writes to ADO.
- Retiring removes an item from screening and suggestions, never from storage
  or history. It requires a reason, and is reversible.
- `knowledge_admin` overrides (library ownership, withdrawal, retirement, review
  confirmation) always record the administrator and the reason.
- Knowledge overdue for review stays retrievable but is visibly marked in
  citations.
- AI-proposed catalogue changes are candidates until a maintainer accepts them.

## Tests

- **Domain:**
  - corpus membership transitions;
  - the new source kinds and trust level;
  - historic snapshot and lineage invariants (acyclic hierarchy, a single
    parent);
  - review-state transitions;
  - administrative library overrides record the admin and reason.
- **Application, per use case:** role authorization and refusals, audit
  entries, concurrency conflicts, idempotent re-imports (same file checksum and
  ADO revision).
- **Ingestion:**
  - a document-only Requirement is indexed from its attachment evidence on
    promotion, and re-indexed when the attachment's version or inclusion
    changes;
  - the screen finds a duplicate between two document-only Requirements.
- **Screening:**
  - a match with a historic item yields `similar_past_requirement` and never
    blocks confirmation;
  - a retired Requirement is never a candidate;
  - reinstating restores it.
- **ADO:**
  - the fake adapter drives the import tests;
  - the REST adapter is tested against recorded responses: hierarchy
    traversal, pagination, throttling (429 with `Retry-After`), HTML
    sanitization, missing or removed items;
  - no write methods exist (an architecture test).
- **Markdown extraction:** heading-based locations and citations.
- **Review cycles:** due and overdue calculation, reminder notifications,
  citation marking.
- **API:** role-based 403s, contract snapshots, OpenAPI and type
  synchronization, rate-limit coverage.
- **Frontend:**
  - component tests for every screen and state, including an accessibility
    check;
  - Playwright journeys:
    - import a BRD, link a fake ADO root, publish, see lineage, and see prior
      art on a new Requirement;
    - retire and reinstate;
    - review confirmation;
    - old URLs redirect.

## Acceptance Criteria

- [ ] The Knowledge Center shows inventory, health, coverage, open findings, review status and imports; only authorized roles see and act.
- [ ] `/architecture-knowledge` and `/documents/library` live under the Knowledge Center, and old URLs and evidence links still work.
- [ ] A new Requirement supplied only as a document is indexed and screened from its attachment content.
- [ ] Knowledge admins retire and reinstate Requirements, reassign or withdraw library documents, and bulk reindex, all audited.
- [ ] Architecture Word and Markdown files bulk-upload into a draft release, with heading-level citations for Markdown.
- [ ] Review reminders fire at 6 months (configurable); overdue knowledge is flagged in the dashboard and citations.
- [ ] Old BRDs import with their ADO breakdown read-only; the lineage BRD → Epic → Feature → Story is viewable, and prior art appears informationally on new Requirements.
- [ ] Everything runs offline with fake identity, a fake ADO and fake AI, except PostgreSQL-only rebuilds.
- [ ] All backend and frontend quality gates and CI are green.

## Dependencies

- **8A.2** (Keycloak roles) for the real `knowledge_admin` role; fake identity works
  without it.
- **Admin portal** (sub-slice C) to manage the new group; its audit log and live
  settings, if present, are reused for review-cycle length.
- **Notifications (8C)** for review reminders.
- **Roadmap change** for sub-slice E (read-only ADO ingestion ahead of Slices
  12–13).
- A new ADR covering: historic reference knowledge and trust levels, attachment
  content in the corpus, corpus retirement, and read-only ADO ingestion.

## Open questions (before sub-slice E starts)

- Azure DevOps Services (cloud) or Azure DevOps Server (on-premises), and its
  version?
- Which ADO process template (Agile, Scrum, CMMI) and hierarchy? This decides the
  work item types and whether stories are "User Story" or "Product Backlog Item".
- Do BRDs mention their ADO IDs (which would enable later auto-linking), or is
  linking always manual?
- BRD formats in practice (DOCX, PDF, legacy `.doc`?), and volume: roughly how
  many BRDs and work items?

## Suggested delivery order

A, then B (closes the new-Requirement ingestion gap), then C, then D, then E, then F.

## Validation Evidence

None yet; not started.
