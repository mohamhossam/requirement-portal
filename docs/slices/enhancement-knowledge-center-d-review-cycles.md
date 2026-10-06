# Enhancement — Knowledge Center D: review cycles

> **Status:** delivered 2026-10-06: knowledge-portal#45 merged first, then
> requirement-portal#45, which pins the fields it adds.
> **Parent:** the Knowledge Center re-plan, sub-slice D
> ([enhancement-knowledge-center.md](enhancement-knowledge-center.md)), decisions 5 and 8.

## Objective

Keep trusted knowledge honest over time:
- library documents and catalogue systems are re-confirmed on a cycle, 180 days by default;
- whoever answers for them sees what is due in knowledge-portal's own reminders;
- overdue knowledge is flagged where it is used, and never removed from retrieval.

## Knowledge-portal

| Part | What it does |
|---|---|
| Setting | `KNOWLEDGE_REVIEW_CYCLE_DAYS`, 180 by default, at least 1. The reminder window, 14 days, is fixed. |
| Library documents | Approving the version in service counts as a review. Its owner confirms "it is still right" with an optional note; a knowledge admin confirms on the owner's behalf with a reason, recorded in C's admin record. Nothing in service means nothing to confirm (409). |
| Catalogue systems | Any `knowledge_maintainer` confirms one system or all of them; an admin who is not a maintainer confirms with a reason. Confirmations are kept in their own append-only table, keyed by system id, because published versions are immutable. |
| Reminders | `GET /reviews/reminders`: the signed-in person's own documents and, for a maintainer, every system in service, that are overdue or due within 14 days. Nothing is sent anywhere. |
| Screens | A reminders page (systems grouped by the day they fall due) with a count in the masthead, a "Last review" column on the library list, review lines and confirm actions on documents and systems, and overdue rows on the front page. |

## Requirement-portal

- **Contract.** `contracts/knowledge-internal.openapi.json` is re-pinned. Two optional,
  additive fields:
  - `CitedPassage.review_due_on`, on the cited-passage read;
  - `ArchitectureEvidence.system_review_due_on`, on the evidence read, set only for a system's
    own catalogue record.
- **Local copy.** `ReferenceDocumentState` (the projection of knowledge-portal's
  `reference_document_changed` events) carries `review_due_on`. Events written before D carry
  none and still read.
- **Overdue is worked out when read**, from the due date and today
  (`ReferenceDocumentState.review_overdue`, `ReferenceCurrency.overdue_reviews`), so a label
  never goes stale and nothing needs re-projecting when a day passes.
- **Where it shows.**
  - The analysis workspace and the answer suggestions carry `overdue_reference_reviews`:
    `{document_id: review_due_on}` for the documents their citations name that are past their
    review date.
  - "Review overdue since {date}" appears on the read-only passage and evidence viewers, beside
    a reference proposal's citations, and beside a suggested answer's citations
    (`frontend/src/components/ReviewOverdue.tsx`).
- **A flag, never a block.** Accepting, rejecting and confirming are unchanged, and retrieval
  still returns overdue knowledge.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | A system's reminder goes to every catalogue maintainer, and any of them may confirm it. A library document's reminder goes to its owner. | Agreed in session (2026-10-06). |
| 2 | Requirement-portal flags overdue sources on the read-only viewers and beside inline citations. | Agreed in session (2026-10-06). |
| 3 | A knowledge admin confirms on anyone's behalf directly, with a reason. | Agreed in session (2026-10-06). Confirming reveals no content, so C's grant is not needed. |
| 4 | A document's clock starts at the approval of its version in service, and a new approval resets it. | Approving is a review. |
| 5 | A system never confirmed counts from the publication of the version in service. | Publishing a version reviews what it holds. |
| 6 | Unpublished documents and draft-only systems have no review cycle. | Nothing relies on them yet. |
| 7 | The label reads "Review overdue since {due date}". | Requirement-portal knows only the due date, not who last reviewed it or when. |
| 8 | Several systems are confirmed together only per due-day group, naming them, and with a required note of what was checked. There is no confirm-everything control. | Agreed in session (2026-10-06), after the design critique: one click should not attest to 26 systems unseen. The API still takes an optional note. |
| 9 | The cycle keeps the word "review", but its statuses read "Re-confirmation overdue" and "Re-confirmation due soon". | Agreed in session (2026-10-06): kept apart from passage review's "Awaiting your review". |

## Tests

- `tests/unit/test_reference_currency.py`: the due date round-trips through the event payload,
  an old payload without it still reads, and a document is overdue from its due date, not the
  day before.
- `tests/unit/test_knowledge_views.py`: the client decodes both new fields.
- `tests/unit/test_internal_api.py`: a cited document past its review date is flagged beside
  its proposal in the analysis response.
- `frontend/src/components/ReviewOverdue.test.tsx` and `AnalysisPanel.test.tsx`: the label
  shows from its due day, says nothing otherwise, and leaves the decision enabled.
