# Enhancement — Knowledge Center C: library and catalogue curation

> **Status:** in progress on `feat/library-citation-counts` (requirement-portal) and
> `feat/knowledge-center-library-curation` (knowledge-portal), 2026-10-06.
> **Parent:** the Knowledge Center re-plan, sub-slice C
> ([enhancement-knowledge-center.md](enhancement-knowledge-center.md)). C is built in
> knowledge-portal; requirement-portal adds one batched read for the library list.

## Objective

Let a knowledge admin curate the library and the architecture catalogue as a whole, not one
owner's document at a time:
- act on any library document on its owner's behalf, with a reason that is recorded;
- retry the library's failed readings and stopped indexing in bulk;
- upload several Word and Markdown files into a catalogue draft at once;
- compare any two catalogue versions;
- see on the library list how many Requirements cite each document.

## Requirement-portal: citation counts

- **`GET /internal/references/citation-counts?document_id=…`**, repeated for 1–100 library
  document ids, each at most 200 characters. It answers `{counts: {document_id: n}}`: how many
  Requirements cite each document now. An id nothing cites answers 0.
- **What counts.** Distinct Requirements with a current, active row in `source_dependencies` for
  the document. Superseded rows, rejected proposals and Requirements closed as duplicates are
  inactive, so they are not counted, and a Requirement citing a document many times counts
  once.
- **Privacy.** It is a count across the whole portfolio, never which Requirements, as with the
  mapping statistics and the corpus summary (`application/use_cases/internal_reads.py`). "Who
  cites it" keeps listing only the Requirements the viewer may see.
- **Reaches no provider.** It reads the index only, so the rate-limit architecture test holds.

## Knowledge-portal

| Part | What the admin gets |
|---|---|
| Admin overrides | On a document they don't own, "Act as admin on this document" with a reason opens an 8-hour grant. While it lasts they see the owner's view and may review, approve, reassign or withdraw on the owner's behalf; each is recorded with the grant's reason. Builds, activation and discard stay with the owner. |
| Library bulk retry | "Retry the N documents whose reading failed" and "Retry the N whose indexing stopped", each confirmed in place and audited. |
| Multi-file upload | Up to 20 files into a draft, each added or refused with its reason; each added file starts reading within the per-minute model budget. A Word 97–2003 `.doc` is refused with "save it as .docx". |
| Compare | Any two catalogue versions, side by side, from the Versions page. |
| Library list | A "Cited by" column from the read above. Last review waits for D. |

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | A knowledge admin may reassign, withdraw, **and review and approve** a document they don't own, on its owner's behalf, each with a reason that is recorded. | Agreed in session (2026-10-06): wider than the spec's reassign and withdraw. |
| 2 | Reviewing someone else's document needs an explicit grant with a reason, lasting 8 hours. Without one, an admin who is not the owner sees only what is published, as today. | Review means reading excluded passages and original previews, which stay owner-only unless an admin says why they need them. |
| 3 | The citations column counts Requirements across the whole portfolio, as a number only. | Agreed in session (2026-10-06). |
| 4 | A multi-file upload starts reading each added file, within the per-minute model budget; one the budget refuses waits with a "Read it" button. | Agreed in session (2026-10-06). |
| 5 | Last-review columns wait for D. | They need D's review dates. |

## Tests

- `tests/unit/test_internal_api.py`: two owners' Requirements both count; analysing again does
  not count twice; unknown ids answer 0; no token answers 401; no ids, 101 ids or an id over
  200 characters answer 422.
- `tests/integration/test_source_lineage_postgres.py`: the Postgres count, across the portfolio.
- `tests/unit/test_requirement_internal_contract.py`: the path is in the pinned contract.
