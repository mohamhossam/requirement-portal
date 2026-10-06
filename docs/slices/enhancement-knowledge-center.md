# Enhancement — Knowledge Center (architecture, requirement and reference knowledge)

> **Status: re-planned 2026-10-06 for the three repositories.**
> - **Decisions:** recorded 2026-09-26, then amended by ADR-0098 (the split), ADR-0099
>   Amendment 1 (the Knowledge Center across the split) and this re-plan.
> - **Delivered:** A is mostly delivered by the split itself, and F was delivered early.
> - **Next:** B1, attachments in the requirement corpus.
> - **Not scheduled:** each later sub-slice needs `ROADMAP.md` scheduling before it starts.
>   E reads from Azure DevOps, so scheduling it is an explicit roadmap change (`AGENTS.md`
>   allows ADO integration only through its roadmap slice), and it waits on four open questions.
>
> Every sub-slice below names the repository it is built in.

## Objective

Give knowledge administrators one place, the **Knowledge Center**, to:
- manage all the knowledge the platform reasons with: the architecture and squad catalogues, the
  Requirement knowledge base, and the shared reference library;
- **bring in the organisation's existing knowledge**:
  - historic BRDs, with their delivered Epic → Feature → Story breakdown imported from Azure
    DevOps for lineage;
  - architecture Word and Markdown documents;
- make sure every **new** Requirement, whether written as text or supplied as a document, is
  ingested into the Requirement knowledge base.

Since the split (ADR-0098), the Knowledge Center is **knowledge-portal**, served at
`/knowledge/` to `knowledge_admin`. The Requirement knowledge base stays in requirement-portal,
with its data and its rules (ADR-0099). Knowledge-portal's screens reach it over service-token
routes (ADR-0099 Amendment 1).

## User Outcome

- A knowledge administrator opens knowledge-portal and sees what the platform knows, what is
  stale or failing, and what needs a decision. That covers the library, the catalogues and the
  Requirement corpus.
- A Requirement supplied only as a document is screened for duplicates and contradictions from
  its content, as a typed one is.
- They retire obsolete Requirements so they stop producing duplicate warnings, and nudge owners
  about findings that have been open too long.
- They administer any library document, upload a folder of architecture documents into a draft
  at once, and compare any two catalogue versions side by side.
- Owners re-confirm their knowledge every six months (configurable), and see in the portal what
  is due.
- Later (E): they import a folder of old BRDs, link each one to its root work item in Azure
  DevOps, and that delivered history becomes searchable prior art with full lineage.

## Recorded decisions

| # | Question | Decision |
|---|---|---|
| 1 | "Already existing knowledge" | Knowledge that exists **outside** the application and must be imported |
| 1a | Requirement sources | Old BRDs (documents), plus Azure DevOps for the delivered breakdown, giving lineage |
| 1b | Architecture sources | Word and Markdown files |
| 2 | Form | ~~A separate area inside the same application, sharing sign-in and deployment~~ **Superseded 2026-10-02 by ADR-0098:** a separate service, database, UI and repository, `knowledge-portal`, at `/knowledge/`. **Refined 2026-10-06 (decision 7):** each sub-slice is built where its data lives |
| 3 | Authority | A `knowledge_admin` role that can act across all knowledge, including overriding document owners |
| 4 | Requirement knowledge | Retiring obsolete Requirements from the corpus: yes. Importing historic Requirements as reference knowledge: yes |
| 5 | Review cycles | Yes, every 6 months (configurable) |
| 6 | Existing pages | ~~Move `/architecture-knowledge` and `/documents/library` into the Knowledge Center~~ **Done by the split:** both moved to knowledge-portal. requirement-portal's old URLs redirect to its own Documents page, and evidence links go to its read-only viewers (`frontend/src/app/legacyKnowledgeLinks.tsx`). This stays: members without the role can't open the portal |
| 6a | New Requirements | Every new Requirement, text or document, must be ingested into the Requirement knowledge base |
| 7 | Where B lives (2026-10-06) | **Split.** Rules, data and attachment indexing stay in requirement-portal. The admin screens (corpus browser, portfolio findings, bulk retry, retire and reinstate) live in knowledge-portal and call new service-token routes on requirement-portal |
| 8 | Review reminders (2026-10-06) | **knowledge-portal's own**: its own reminder list and badge. Nothing crosses the services, and there is no email |
| 9 | Sub-slice E (2026-10-06) | Re-planned with its new homes, **left unscheduled** until the four open questions are answered |

## Current state (surveyed 2026-10-06)

**Knowledge-portal (`/knowledge/`)**
- **Access.** Every public route requires `knowledge_admin`
  (`application/use_cases/identity_access.py`;
  `tests/unit/test_knowledge_admin_gate.py`). The exceptions are the explorer's read routes,
  which anyone signed in may use (ADR-0101 Amendment 1). Catalogue and squad edits also check
  `knowledge_maintainer`, and squad reads check `knowledge_reader`.
- **Front page** (`frontend/src/app/HomePage.tsx`, `home/derive.ts`): three numbered tables with
  what needs a curator.
  - Library: awaiting review, extraction failed, quarantined, being read, index build failed.
  - Catalogue: drafts with suggestions to decide.
  - Squads: systems that no squad owns.
  - Totals, the version in service, and "Valid as of".
  - Not shown: freshness per body, catalogue build or extraction failures, anything about the
    Requirement corpus.
- **Library** (`frontend/src/library/LibraryPage.tsx`): lists every document with its status,
  owner and date. Citations are shown per document ("Who cites it"), with no count in the list.
  Governance actions are **owner-only**: handover in `library_governance.py` ("Only the document
  owner can manage its governance") and withdrawal through `document_library.py`. Retry is per
  document only.
- **Catalogue:**
  - documents are read heading-aware for Markdown (`infrastructure/architecture/markdown_passages.py`,
    ADR-0090);
  - suggestions come with citations, and nothing is published without acceptance (F);
  - a draft's changes are compared only with the version in service
    (`GET /architecture-knowledge/releases/{id}/changes`);
  - documents are uploaded **one at a time**;
  - `.doc` is refused, but only with the generic type-mismatch message.
- **No review state** on documents or systems, and **no notifications**. Its only output to
  others is the `knowledge_events` outbox (`application/ports/knowledge_events.py`).

**Requirement-portal**
- **Corpus.** The Requirement knowledge base is `requirement_knowledge_index` with its chunks,
  screens, findings and finding revisions (`010_requirement_knowledge.sql`).
  - Source kinds: `source`, `clarification`, `intent_decision`, `current_analysis`,
    `confirmed_analysis`, `conflict_resolution` (`domain/knowledge/entities.py`).
  - Findings are `possible_duplicate` or `possible_contradiction`. Their owners decide them,
    one Requirement at a time (`interfaces/api/routes/knowledge.py`).
- **Gap: attachment content is not in the corpus.** `RequirementKnowledgeCorpus.chunks()`
  (`application/use_cases/requirement_knowledge.py`) indexes typed fields, clarifications, intent
  decisions, confirmed analysis and conflict resolutions. Attachment passages
  (`requirement_attachment_ingestions`, migration `202610021000`) are scanned and extracted but
  never indexed. A document-only Requirement contributes almost nothing to duplicate detection.
- **Missing:** a portfolio view of the corpus or findings, bulk retry of failed indexes (only
  per Requirement, or the operator command `llm rebuild`), and any retirement. The only
  exclusion is an owner marking a Requirement a duplicate.
- **Notifications (8C)** exist, but `actor_notifications.job_id` is `NOT NULL REFERENCES
  ai_jobs` (migration `008_async_ai_jobs.sql`), so only AI jobs can notify.
- **Service-token routes** for knowledge-portal: only `/internal/references/{id}/impact`,
  `/internal/references/{id}/dependents` and `/internal/architecture-mapping/stats`
  (`interfaces/api/routes/internal.py`).
- **Identity.** The realm role `knowledge_admin` and the group `knowledge-admins`
  (`deploy/keycloak/realm-requirement-ai.json`). The `fake-owner` and `fake-reviewer` personas
  hold it, matching knowledge-portal's personas.

**Azure DevOps:** no code reads ADO. ADO publication (Slices 12–13) is planned and not built.

## Roles

| Role | Where | Grants |
|---|---|---|
| `knowledge_admin` (realm role; group `knowledge-admins`) | Both services | knowledge-portal itself and every Knowledge Center action: library override and withdrawal, bulk work, retire and reinstate, nudges, review confirmation on anyone's behalf, imports. In requirement-portal it only shows the link to the portal |
| `knowledge_maintainer` | knowledge-portal | Catalogue and squad editing, and confirming a system's review |
| `knowledge_reader` | knowledge-portal | Squad catalogue reads |

- **Offline:** the `fake-owner` and `fake-reviewer` personas hold `knowledge_admin` in both
  services, and `fake-observer` holds no knowledge role.
- **Audit:** every `knowledge_admin` override and bulk action records the actor, the reason, and
  the state before and after.
- **Writes into requirement-portal:** those that knowledge-portal makes on an admin's behalf carry
  the admin's actor id. requirement-portal records that id; the service token alone is never
  the actor.

## Sub-slices

Delivery order: **B1 → A′ → B2 → B3 → C → D**, then E once it is scheduled. F is done.

### B1 — Attachments in the requirement corpus (requirement-portal) — next
- **A new source kind, `attachment`**, for the passages of attachments that analysis includes.
  They are chunked with citations to the document block, the way library passages are cited.
- **When they are indexed and screened.** They go through the existing fingerprinted index and
  screening jobs:
  - when the Requirement is promoted;
  - whenever an included attachment's version or inclusion changes. A new source-change trigger
    on the attachment and inclusion tables feeds `knowledge_source_changes`.
- **Document-only Requirements are covered.** A Requirement with almost no typed text is
  screened from its attachment content.
- Typed source fields are indexed as today.
- **ADR-0099 Amendment 1** records that attachment content joins the trusted corpus.

### A′ — Knowledge Center front page (knowledge-portal, with a requirement-portal read)
- **The front page gains:**
  - freshness per body (when each last changed);
  - catalogue build and extraction failures, beside the library's;
  - a fourth table, **Requirement corpus**: indexed, pending, failed and retired counts, and open
    findings by age. It is read from requirement-portal over `/internal/knowledge/corpus/summary`.
- **Later rows on the same page:** review due and overdue (D) and import runs (E).

### B2 — Corpus and portfolio findings (requirement-portal queries, knowledge-portal screens)
> Requirement-portal half delivered on `feat/knowledge-corpus-browser`
> ([enhancement-knowledge-center-b2-corpus-and-findings.md](enhancement-knowledge-center-b2-corpus-and-findings.md)).
- **Requirement-portal's internal reads**, paged and filtered, with the data that's needed and
  nothing more:
  - `/internal/knowledge/corpus`: each Requirement, what is indexed, its index status, its last
    screen and its findings, filtered by status, owner and age;
  - `/internal/knowledge/findings`: every open possible duplicate and contradiction across
    Requirements, with its age and owners.
- **Knowledge-portal screens:** a corpus browser and a portfolio findings table, under a new
  "Requirement knowledge" table.
- **Nudges.** An admin nudges the owners of a finding. Requirement-portal sends the notification
  through `POST /internal/knowledge/findings/{id}/nudge`. Notifications then need to exist
  without an AI job: `job_id` becomes nullable, and a new kind, `knowledge_findings_nudge`, is
  added. Decisions stay with the Requirement owners.

### B3 — Admin actions on the corpus (requirement-portal rules, knowledge-portal buttons)
- **Retire and reinstate (decision 4):**
  - An admin retires an obsolete or cancelled Requirement, live or historic, from the corpus,
    with a reason.
  - A retired Requirement is excluded from screening and suggestions, stays fully readable, and
    keeps its history untouched.
  - Open findings that cite it close as "source retired", and the closure is recorded.
  - Reinstating re-indexes and re-screens it.
  - This is a new domain rule: corpus membership, active or retired, with an audit trail.
- **Bulk reindex and retry** for failed or stale indexes.
- **Routes:** each is a requirement-portal internal write route that takes the admin's actor id
  and a reason (`/internal/knowledge/requirements/{id}/retirement`, `/reinstatement`,
  `/internal/knowledge/reindex`). Knowledge-portal offers them as actions on the B2 screens.

### C — Library and catalogue curation (knowledge-portal)
- **Admin overrides on any library document:** reassign ownership and withdraw, each with a
  reason, recording the admin. Today both are owner-only.
- **Bulk retry and rebuild** for failed library readings and index builds.
- **Multi-file upload** of Word and Markdown files into a draft, with a result for each file.
  Legacy `.doc` is refused with "convert it to .docx".
- **Compare any two catalogue versions side by side:** systems, connections, domains,
  offerings, journeys and documents. Today a draft is compared only with the version in service.
- **Library list columns:** last review (after D) and the number of citations, from a batched
  requirement-portal read, `/internal/references/citation-counts`.

### D — Review cycles (knowledge-portal) (decisions 5 and 8)
- **Review dates.** Library documents and catalogue systems carry `last_reviewed_at`,
  `review_due_at` and the reviewer.
  - The cycle is a setting, 180 days by default.
- **Who confirms:**
  - the owner, for a library document;
  - a `knowledge_maintainer`, for a system, or for a whole version when every system is
    reconfirmed;
  - a `knowledge_admin`, on anyone's behalf, with a reason.
  - Confirming is recorded in the knowledge audit.
- **Reminders are the portal's own.**
  - A reminders list, with a count in the masthead, shows what is due within 14 days and what is
    overdue, for the signed-in person.
  - They are computed from the due dates, with no email and nothing sent to requirement-portal.
- **Overdue knowledge is flagged:**
  - on the front page;
  - in citations, as "not reviewed since …". This is an additive field on the
    `/internal/library/*` and evidence responses, and requirement-portal's read-only viewers show
    the label.
- Overdue knowledge is **never** removed from retrieval.

### E — Historic BRDs and Azure DevOps lineage (split; not scheduled)
- **A historic Requirement.** A read-only reference concept, distinct from a live Requirement:
  no workflow, no ownership, no approvals. It holds:
  - one or more BRD documents, read with the existing document pipeline (DOCX and PDF; `.doc`
    refused with conversion guidance);
  - an ADO breakdown snapshot: the linked root work items and their whole hierarchy. For each
    item, its ID, type, title, sanitised description and acceptance criteria, state, area and
    iteration paths, tags, parent and child links, revision and URL;
  - lineage links from the BRD to its root work items and down the hierarchy;
  - provenance: who imported it and when, file checksums, and ADO revisions.
- **Where each part is built:**
  - **knowledge-portal:** the curator's import flow. That is bulk BRD upload with per-file
    results, entering each BRD's root work-item IDs, previewing the BRD with its breakdown,
    publishing it as reference knowledge, refreshing from ADO with a diff, and a lineage viewer.
  - **requirement-portal:**
    - the historic corpus, under the source kinds `historic_brd` and `historic_backlog` with a
      trust level of reference, which never counts as confirmed intent;
    - the `similar_past_requirement` relationship. It is informational and never blocks
      confirmation;
    - prior art on a live Requirement's Knowledge step;
    - the read-only ADO connector (`AdoWorkItemSourcePort` with REST and fake adapters: WIQL,
      batch reads, paging, throttling), next to ADO publication (12–13).
  - Published historic Requirements reach requirement-portal over a service-token route, as
    approved backlogs reach knowledge-portal (ADR-0101 Amendment 2).
- **Nothing is ever written to ADO.** Import runs are durable jobs, with progress, retry and a
  per-item error report.
- It needs the open questions below answered, and a roadmap change.

### F — AI-assisted architecture catalogue extraction (knowledge-portal) — delivered
- **Delivered early** (2026-09-29, `enhancement-squad-and-architecture-catalogues.md`,
  ADR-0081). It has since grown in knowledge-portal (ADR-0101).
- **What it does.** Suggested systems, connections, constraints, offerings and journeys come
  from Word, PDF, Markdown, Excel and images, as reviewable suggestions in a draft, with
  citations. Nothing is published until a person accepts each suggestion.
- **No owner suggestions:** ownership lives in the squad catalogue.

## Out of Scope

- Writing to Azure DevOps (Slices 12–13).
- Connectors that crawl SharePoint, Confluence or file shares. Import is by upload.
- Automatically matching BRDs to ADO items (a later option within E).
- Using historic breakdowns as generation examples for new Epics and Features. That is a
  generation-quality change that needs its own evaluation.
- OCR for scanned BRDs beyond the existing optional `document-ocr` path.
- Email or any other delivery of review reminders (decision 8).
- Knowledge-admin screens inside requirement-portal (decision 7).

## Domain

- **requirement-portal:**
  - `KnowledgeSourceKind` gains `attachment` (B1), and later `historic_brd` and
    `historic_backlog` with a trust level (E);
  - corpus membership, active or retired, with reason, actor and time (B3);
  - a finding closed as "source retired" (B3);
  - `KnowledgeRelationshipKind` gains `similar_past_requirement` (E).
- **knowledge-portal:**
  - administrative reassignment and withdrawal of library documents, recording the admin and
    the reason (C);
  - review state on documents and systems (D);
  - historic import runs and snapshots (E).

## Application Use Cases

- **requirement-portal:**
  - **B1:** index attachment sources.
  - **A′ and B2:** `GetCorpusSummary`, `ListCorpus`, `ListPortfolioFindings`,
    `NudgeFindingOwners`.
  - **B3:** `RetireFromCorpus`, `ReinstateToCorpus`, `BulkReindexRequirements`.
  - **C:** `CountCitations` for the library list.
  - **E:** `ReceiveHistoricRequirement` and prior-art screening.
- **knowledge-portal:**
  - **A′:** `GetKnowledgeInventory`.
  - **C:** `AdministerLibraryDocument` (reassign, withdraw), `BulkRetryLibrary`,
    `UploadArchitectureDocuments` (multi-file), `CompareArchitectureReleases` (any two).
  - **D:** `ConfirmKnowledgeReview`, `ListReviewReminders`.
  - **E:** `StartHistoricImport`, `LinkBrdToWorkItems`, `PublishHistoricRequirement`,
    `RefreshHistoricRequirement`.
- **Every admin action** authorizes `knowledge_admin` (or the stated role) in the application
  layer and writes its audit entry in the same transaction.
- **Writes made through internal routes** authorize the service token and record the admin's
  actor id passed with the call.

## Ports

- **requirement-portal:**
  - extensions to the knowledge index, screening and notification ports, for attachment
    sources, corpus membership and notifications that don't come from an AI job;
  - `AdoWorkItemSourcePort` (E).
- **knowledge-portal:**
  - `RequirementKnowledgePort`, with an HTTP adapter and a deterministic fake, for the B2 and B3
    reads and writes and for citation counts;
  - extensions to the library and catalogue repository ports for review state and admin
    overrides.
- **Both:** existing document storage, extraction, embedding and job ports are reused.

## Adapters

- **PostgreSQL migrations** (timestamped names) in each service's own database:
  - **requirement-portal:**
    - the attachment source-change trigger (B1);
    - corpus membership (B3);
    - nullable `actor_notifications.job_id` and the new kind (B2);
    - historic sources (E);
  - **knowledge-portal:**
    - review state (D);
    - import runs and snapshots (E).
- **HTTP adapters** for the new internal routes, held to the pinned contracts
  (`requirement-internal.openapi.json`, and `knowledge-internal.openapi.json` for the
  "not reviewed since" field).
- **ADO:** a REST adapter (Azure DevOps Services or Server, selected by base URL) and a fake with
  a deterministic sample hierarchy (E).

## API

- **requirement-portal internal routes** (service token; additive to its internal contract):
  - `GET /internal/knowledge/corpus/summary`;
  - `GET /internal/knowledge/corpus`;
  - `GET /internal/knowledge/findings`;
  - `POST /internal/knowledge/findings/{id}/nudge`;
  - `POST /internal/knowledge/requirements/{id}/retirement` and `/reinstatement`;
  - `POST /internal/knowledge/reindex`;
  - `GET /internal/references/citation-counts`;
  - E's historic intake.
- **knowledge-portal public routes** (`knowledge_admin`): they back the screens above. Reindex,
  rebuild and import routes use the provider rate limit.
- OpenAPI contracts and generated TypeScript types are regenerated in each repository.

## UI

- **knowledge-portal (Timetable Book, `DESIGN.md`, WCAG 2.2 AA, a critique of each screen):**
  - the front page tables (A′);
  - a "Requirement knowledge" table with the corpus browser and portfolio findings, and the
    retire, reinstate, reindex and nudge actions (B2, B3);
  - library admin actions and bulk work, multi-file upload and the any-two comparison (C);
  - review status, confirmation and the reminders list (D);
  - historic import and the lineage viewer (E).
- **requirement-portal:** no new admin screens.
  - B1 shows attachment-sourced findings on the existing Knowledge step.
  - D adds "not reviewed since …" in the read-only citation views.
  - E adds prior-art matches on the Knowledge step, labelled historic.
  - These are feature work, outside the redesign's presentation-only rule, and are scheduled as
    such.

## Business Rules

- Every promoted Requirement is ingested into the knowledge base: its typed fields and its
  analysis-included attachments. Ingestion status is visible, and failures are retryable.
- Historic knowledge is reference, never trusted intent. It informs but never blocks
  confirmation, and is always labelled historic, with provenance.
- Imports are read-only against ADO.
- Retiring removes an item from screening and suggestions, never from storage or history. It
  requires a reason, and is reversible.
- `knowledge_admin` overrides always record the administrator and the reason: library ownership,
  withdrawal, retirement and review confirmation.
- Knowledge overdue for review stays retrievable, and is visibly marked in citations.
- AI-suggested catalogue changes are suggestions until a person accepts them.
- Requirement data never moves to knowledge-portal: its screens read and act over internal
  routes.

## Tests

- **B1:**
  - a document-only Requirement is indexed from its attachment evidence on promotion, and
    re-indexed when the attachment's version or inclusion changes;
  - screening finds a duplicate between two document-only Requirements;
  - Postgres covers the trigger.
- **B2 and B3:**
  - corpus membership transitions;
  - a retired Requirement is never a candidate, and reinstating restores it;
  - findings close as "source retired";
  - a nudge notifies without an AI job;
  - internal routes refuse calls without the token, and record the actor id.
- **C:**
  - administrative overrides record the admin and the reason;
  - a multi-file upload gives a result for each file;
  - comparing any two versions;
  - the `.doc` message.
- **D:**
  - due and overdue calculation;
  - reminders for the signed-in person;
  - confirmation by role, with audit;
  - citation marking across the contract.
- **E:**
  - the fake ADO adapter drives the import tests;
  - REST adapter tests replay recorded responses (hierarchy, pagination, `429` with
    `Retry-After`, sanitisation, missing items);
  - an architecture test holds that no write methods exist.
- **Contracts:** each new internal route is added to the pinned contract and tested on both
  sides.
- **Frontend:**
  - component tests for every screen and state;
  - Playwright on the combined stack for the Knowledge Center journeys.
- **Gates:** each repository's gates, and both CIs green.

## Acceptance Criteria

- [ ] A new Requirement supplied only as a document is indexed and screened from its attachment content (B1).
- [ ] The knowledge-portal front page shows inventory, freshness, failures, Requirement-corpus health, review status and imports; only `knowledge_admin` sees it.
- [ ] Knowledge admins browse the corpus and portfolio findings, nudge owners, retire and reinstate Requirements, and bulk reindex, all audited, without Requirement data leaving requirement-portal.
- [ ] Knowledge admins reassign or withdraw any library document and bulk retry, all audited; architecture files upload several at a time, with per-file results; any two catalogue versions compare side by side.
- [ ] Reviews come due after 6 months (configurable); the portal reminds its owners; overdue knowledge is flagged on the front page and in citations.
- [x] Old URLs and evidence links still work. requirement-portal redirects them to its Documents page and read-only viewers (`legacyKnowledgeLinks.tsx`, `KnowledgeViews.test.tsx`).
- [x] Architecture Markdown is read heading-aware, with heading citations (ADR-0090).
- [x] AI-suggested catalogue changes are reviewable suggestions with citations (F).
- [ ] (E, when scheduled) Old BRDs import with their ADO breakdown read-only; the lineage BRD → Epic → Feature → Story is viewable, and prior art appears informationally on new Requirements.
- [ ] Everything runs offline with fake identity, a fake ADO and fake AI, except PostgreSQL-only rebuilds.
- [ ] All backend and frontend quality gates and CI are green in both repositories.

## Dependencies

- **ADR-0099 Amendment 1** (this re-plan): the Knowledge Center across the split.
- **8A.2** (Keycloak roles) for the real `knowledge_admin` role in production; fake identity
  works without it.
- **Admin portal** (sub-slice C there): manages the `knowledge-admins` group. Its live settings,
  if present, could hold the review-cycle length; until then it is a startup setting.
- **Roadmap change** for sub-slice E (read-only ADO ingestion ahead of Slices 12–13).
- **A new ADR before E:** historic reference knowledge and its trust levels, and read-only ADO
  ingestion.

## Open questions (before sub-slice E starts)

- Azure DevOps Services (cloud) or Azure DevOps Server (on-premises), and which version?
- Which ADO process template (Agile, Scrum, CMMI) and hierarchy? This decides the work item
  types, and whether stories are "User Story" or "Product Backlog Item".
- Do BRDs mention their ADO IDs (which would enable later auto-linking), or is linking always
  manual?
- Which BRD formats are used in practice (DOCX, PDF, legacy `.doc`?), and at what volume:
  roughly how many BRDs and work items?

## Validation Evidence

- **2026-10-06, the re-plan:** a read-only survey of requirement-portal `main` (`c465e5b`) and
  knowledge-portal `main` (`633cb59`). The current state and the delivered acceptance criteria
  above cite what was found.
- **B1 and later sub-slices:** not started.
