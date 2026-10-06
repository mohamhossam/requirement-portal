# ADR 0102 — Historic Requirements and their Azure DevOps lineage

## Status

Accepted 2026-10-06. Amends ADR-0099 Amendment 1 (where the read-only Azure DevOps connector
lives, and how historic Requirements reach this service). Delivered in two slices: E1 in
knowledge-portal, E2 here (`docs/slices/enhancement-knowledge-center.md`, sub-slice E).

## Context

The Knowledge Center's sub-slice E imports the organisation's old BRDs as **historic
Requirements**: read-only reference knowledge, never live work. Each carries its delivered Azure
DevOps (ADO) breakdown, which gives lineage BRD → Epic → Feature → User Story, so requirement
work can show cited prior art on new Requirements.

ADR-0099 Amendment 1 placed:
- the import screens in knowledge-portal;
- the historic corpus, prior-art screening and the read-only ADO connector here, "next to ADO
  publication (Slices 12–13)";
- delivery "over a service-token route, as approved backlogs reach knowledge-portal".

E stayed unscheduled until four questions were answered. They were, on 2026-10-06:
- **ADO edition:** not decided yet. Build against a fake; the REST adapter follows once it is.
- **Process template:** Agile, so Epic → Feature → User Story.
- **IDs in BRDs:** sometimes. IDs found in a BRD's text are suggested; the curator confirms them.
- **Formats:** mostly DOCX, some PDF. Legacy `.doc` is refused with conversion guidance.

Planning the import showed two problems with the amendment's placement:
- **The connector would sit one hop away from everything that uses it.** Every preview, fetch
  and refresh is a knowledge-portal action. With the connector here, each would cross both
  services, and this service would hold durable import state it never shows.
- **A push route duplicates a channel that already exists.** This service already polls
  knowledge-portal's `knowledge_events` outbox (`GET /internal/events`), with a cursor, gap
  handling and retries (`ProjectKnowledgeEvents`). A second, push-shaped channel would need its
  own outbox, worker and failure handling in knowledge-portal.

## Decision

1. **The read-only ADO connector lives in knowledge-portal.**
   - `AdoWorkItemSourcePort.read_tree(root_ids, max_items)` is in knowledge-portal's application
     layer, with a fake adapter now.
   - It is read-only by construction: an architecture test asserts the port and its adapters
     expose no write-shaped method. **Nothing is ever written to ADO from an import.**
   - ADO **writes** stay here, in Slices 12–13 (`WorkItemPublisherPort`, external id mapping),
     behind their own explicit, authorised actions. The two credentials are separate: a
     read-only token there, a publishing token here.
   - **The REST adapter's shape is fixed now, its edition left open.** It runs a WIQL tree
     query from the root ids (work item links, Epic → Feature → User Story, Agile), then batch
     reads (`workitemsbatch`, 200 ids a call). It pages, throttles itself, and backs off on 429
     and `Retry-After`. Descriptions are sanitised from HTML to text and bounded. Services
     (`dev.azure.com`, API 7.1) and Server (a collection URL, 7.0) differ only in base URL and
     API version; the choice is a setting once the edition is known.
2. **Imports are durable jobs in knowledge-portal**, on their own queue (`historic_import_jobs`),
   with progress and a per-item error report on the historic Requirement itself. An import is
   bounded at 2,000 work items and 20 files a batch.
3. **Published historic Requirements reach this service as events it already polls.**
   - knowledge-portal appends `historic_requirement_changed` to `knowledge_events` on publish,
     on an accepted refresh and on withdrawal.
   - Like `reference_document_changed`, each event carries the subject's **whole current
     state**: BRD passages with block ids and labels, the work items, the lineage and the
     provenance. A withdrawal carries none.
   - This service projects it (E2) with **its own cursor, starting from 0**. The existing
     `ProjectKnowledgeEvents` skips unknown kinds and advances past them, so without its own
     cursor nothing published before E2 would be seen. Each event's whole state makes replay
     from 0 safe.
   - No push route and no new outbox are added. ADR-0101 Amendment 2's approved-backlog outbox
     stays the one channel from this service to knowledge-portal.
4. **The historic corpus is reference knowledge, never confirmed intent** (E2).
   - It is indexed under the source kinds `historic_brd` and `historic_backlog` in tables
     parallel to the live corpus. Every live corpus table keys on `requirements`, and a historic
     Requirement is not one.
   - It never enters ADR-0027's trusted corpus, and it never answers a clarification.
5. **Prior art is search, then the AI judge, and informational** (E2).
   - Hybrid search of the historic corpus against a live Requirement's text, then the
     relationship classifier with a new verdict, `similar_past_requirement`, and its rationale.
   - The results are stored as **prior-art records, not findings**. They never count toward
     `KnowledgeReview.ready`, never block confirmation and never appear in the portfolio's
     finding counts.
6. **Curation is any `knowledge_admin`'s**, as with Table 4's corpus actions. Each uploaded BRD
   starts its own draft; more BRDs can be added to a draft. Only Epic, Feature and User Story
   are imported; other types beneath them (Task, Bug) are counted as not imported.

## Consequences

- knowledge-portal gains an external read dependency. Production refuses the fake connector, so
  the import cannot be used in production until the edition is decided and the REST adapter is
  built. Reading and previewing BRDs works without it.
- This service needs no ADO code until Slice 12, as `AGENTS.md` §9 requires. The Knowledge
  Center's E is an explicit roadmap change for the read-only import only.
- Event payloads grow with a historic Requirement's size. They are bounded by the 2,000-item cap
  and the extractor's own limits, and only published state is ever sent.
- E2's projection replays every event once from 0. That is cheap: it reads only the
  historic kind, and each event supersedes the last for its subject.
- Prior art costs one classifier call per screen of a live Requirement when the historic corpus
  has candidates. It runs with the existing lazy screening (ADR-0030), under the same rate
  limits.

## Alternatives Considered

- **The connector here, as ADR-0099 Amendment 1 said.** Not chosen: every import step would
  cross both services, for no gain in safety, since the token is read-only either way.
- **A push route from knowledge-portal, as the amendment said.** Not chosen: it duplicates the
  polled event channel, with a new outbox and worker in knowledge-portal and new failure modes.
- **Prior art by search alone, with no judge.** Offered and declined on 2026-10-06: a ranked list
  without a reason invites over-reading the similarity.
- **Prior art as knowledge findings.** Not chosen: findings block confirmation and need a
  decision from the owner. Prior art is context, not a conflict.
