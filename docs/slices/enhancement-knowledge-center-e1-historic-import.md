# Enhancement — Knowledge Center E1: historic BRDs and their Azure DevOps lineage

> **Status:** in progress on `feat/knowledge-center-historic-import` (knowledge-portal) and
> `docs/knowledge-center-historic-adr` (this repository, docs only), 2026-10-06. The two are
> independent; either may merge first.
> **Parent:** the Knowledge Center re-plan, sub-slice E
> ([enhancement-knowledge-center.md](enhancement-knowledge-center.md)), decisions 10–13 and
> [ADR-0102](../architecture/adr-0102-historic-requirements-and-ado-lineage.md). E2 follows here.

## Objective

Bring the organisation's old BRDs in as **historic Requirements**: read-only reference knowledge,
each carrying the Epics, Features and User Stories it was delivered as in Azure DevOps, so that
requirement work (E2) can show cited prior art on new Requirements. Nothing is ever written to
Azure DevOps.

## Knowledge-portal

| Part | What the curator gets |
|---|---|
| Import | Up to 20 BRDs at once (Word .docx or PDF, 10 MB each). Each starts its own draft and is read by the document pipeline, or is refused with why (a Word 97–2003 `.doc` is refused with "save it as .docx"; a file already imported names the record that holds it). |
| Work-item ids | Ids the BRD mentions (`#48213`, `AB#48213`, "Epic 48213", `_workitems/edit/48213`) are suggested with the passage they came from, for the curator to confirm. They are never linked on their own (decision 10). |
| Breakdown | The curator names 1–50 root work items and the breakdown beneath them is read from Azure DevOps on a durable job, with progress ("140 of 212 work items") and a per-item report (not found, no access, not an Agile type, over the limit). Only Epic, Feature and User Story are imported; Tasks and Bugs beneath are counted. At most 2,000 work items (`ADO_IMPORT_MAX_ITEMS`). |
| Lineage | BRD → Epic → Feature → User Story as numbered rows (1, 1.1, 1.1.1), each linking to its work item in Azure DevOps, with state, iteration and area, and its description and acceptance criteria on request. |
| Publish | Once a BRD is read and at least one root's breakdown is read. It records a `historic_requirement_changed` event with the whole published state. |
| Refresh | A published record is read again; the changes wait, field by field, to be accepted (published again, another event) or discarded. |
| Withdraw | With a reason; the event then carries no state, so requirement work stops reading it. |
| Table 4 | A fourth page, Historic, with the list by state; the front page counts drafts and published records. |

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The read-only ADO connector lives in knowledge-portal; ADO writes stay in Slices 12–13 here. | Agreed in session (2026-10-06), ADR-0102: the import that uses it is there. |
| 2 | Published historic Requirements reach this service as events on the outbox it already polls. | Agreed in session (2026-10-06), ADR-0102: no second channel. E2 projects them with its own cursor from 0, so nothing published before E2 is lost. |
| 3 | The connector is a packaged fake for now, `ADO_PROVIDER=none|fake`; production refuses `fake`. | The ADO edition is not decided (decision 10); the REST adapter's shape is fixed in ADR-0102. |
| 4 | Any knowledge admin curates; each BRD starts its own draft, and more BRDs can be added to a draft. | Defaults, as with Table 4's corpus actions. |
| 5 | Reading a BRD and reading a breakdown run on their own queue (`historic_import_jobs`), never in a request. | The bounded extractor is slow and shared with the library; a queue that `claim`s any kind must not be shared. |
| 6 | Draft titles come from the file name, keeping hyphens ("BRD-2025-014 …"). | BRD references are what people search by. |

## Tests (knowledge-portal)

- `tests/unit/test_historic_requirements.py`:
  - id suggestions and their citations;
  - lineage and the refresh diff;
  - rich text to plain text;
  - batch import with refusals;
  - progress and the per-item error report;
  - the item bound;
  - no ADO connection;
  - publish, refresh, accept and withdraw with their events;
  - publish preconditions;
  - read again;
  - an architecture test that nothing can write to ADO;
  - settings;
  - the routes' bounds and roles.
- `tests/integration/test_historic_requirements_postgres.py`: the record's round trip, a publication committing with its event, optimistic versions, and the import queue on its own table.
- `frontend/src/historic/historic.test.tsx`: wording and ranks, Table 4's counts, the list and import results, suggestions and id validation, the numbered lineage, refresh acceptance and withdrawal with focus handling.
