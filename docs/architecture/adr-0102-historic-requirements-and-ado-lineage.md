# ADR 0102 — Historic Requirements and their Azure DevOps lineage

## Status

Accepted 2026-10-06. Amends ADR-0099 Amendment 1 (where the read-only Azure DevOps connector
lives, and how historic Requirements reach this service). Delivered in two slices: E1 in
knowledge-portal, E2 here (`docs/slices/enhancement-knowledge-center.md`, sub-slice E).
Amendment 1 (2026-10-07) records E2 as built.

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

## Amendment 1 — E2 as built (2026-10-07)

Agreed in session while planning E2. Where this amendment and the decision above differ, the
amendment wins.

1. **A light event and a paged read.** A historic Requirement with 2,000 work items could make
   one event tens of megabytes. The event now names the publication only: its number,
   fingerprint, title, root ids, counts, and who published it and when. This service reads the
   content from two service-token routes on knowledge-portal,
   `GET /internal/historic-requirements/{id}/passages` and `.../items`, at most 200 entries a
   page. Each page carries the publication's fingerprint. An older publication answers 409 and
   a withdrawn one 404; both mean a newer event says what to read instead. The pinned example,
   `contracts/historic-requirement-changed.example.json`, is written by knowledge-portal's tests
   and parsed by this service's.
2. **The consumer reads every kind.** `/internal/events` has no kind filter, and the cursor's
   gap handling needs contiguous sequence numbers, so the historic consumer reads every event
   from 0 and steps over the ones it does not handle. It runs on its own loop, so a slow page of
   historic content never holds up reference currency.
3. **Its own judge and its own enums.** Prior art has its own port (`PriorArtJudgePort`), prompt
   (`prior-art-v1`) and verdict enum (`PriorArtVerdict`), and historic chunks their own
   `HistoricSourceKind`. The relationship classifier, `KnowledgeRelationshipKind` and
   `KnowledgeSourceKind` are unchanged: that kind types `KnowledgeFinding.kind` and the
   published `/internal/knowledge/findings?kind=` filter, and the classifier's prompt treats
   similar topics as unrelated. An architecture test holds this.
4. **The corpus version belongs to the index.** It advances only when a publication's chunks
   become searchable, all at once, after every chunk is embedded. A prior-art check records the
   version it saw; a later version makes it out of date. A withdrawal does not advance it: a
   withdrawn match is filtered out when a check is read, at once.
5. **Guards.** `PRIOR_ART_ENABLED` is off by default and stays off in production until an
   operator has run `scripts/evaluate_prior_art.py` against the configured provider. The
   historic corpus projects and indexes either way. `PRIOR_ART_JUDGE_CALLS_PER_HOUR` caps checks
   portal-wide; the job gate holds prior-art jobs queued while the hour's checks are spent.
   `HISTORIC_EMBED_CHUNKS_PER_HOUR` caps embedding per historic Requirement. Prior-art jobs are
   claimed after every other queued job.
6. **Re-checking is lazy.** A check runs when the Requirement changes or the Knowledge step is
   opened and its prior art is missing or out of date. There is no mass re-screening when the
   historic corpus changes, and a failed check is not queued again for the same input.
7. **Where each historic Requirement is cited.** `GET /internal/knowledge/historic/citation-counts`
   and `GET /internal/knowledge/historic/{id}/citations` serve knowledge-portal. Like B2's corpus
   list, they give identity and state only (the Requirement, its owner, when it was checked,
   whether that check is current), never a rationale or a passage.

