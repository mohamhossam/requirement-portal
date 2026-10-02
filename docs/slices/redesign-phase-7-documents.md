# Redesign Phase 7 — Documents `/documents`, `/documents/:id`

`docs/ux-plan.md` §5 Phase 7, on Phases 0–6, governed by `docs/design-system.md`
and `DESIGN.md`. Presentation only (`CLAUDE.md`), with one data read approved
explicitly for this phase (below). Ends with build, lint, unit tests and the
Playwright smoke green.

> "What evidence does this project hold?" and "Is this file trustworthy, and
> should the AI see it?" — ux-plan §1. "Catalogue and detail. Detail is dense and
> information-rich, and mostly needs the new primitives rather than a rethink."

## Where it stood

Reviewed live on a seeded API (a Word brief with a table, an Excel workbook with
a hidden sheet, a PDF, a Markdown file, a plain-text file on a draft, and a Word
file that could not be read), at 1440 and 390, in Paper and Slate:

- **Catalogue.** A three-column grid of 176px cards, mostly empty, each showing
  the filename, the raw MIME type (`application/vnd.openxmlformats-…` over three
  lines), "v1" and "Included in analysis". A file that could not be read looked
  like one that could. Nothing said which requirement a file belonged to. No
  search, filter or sort (design-system §14, "No filtering"). Off-ladder 4px
  radius; the h1 said "Source documents" under a sidebar that says "Documents".
- **Detail, decision before evidence.** "Include in analysis" sat in the page
  header, above the extraction warnings that decide it, and apart from the grey
  provider disclosure that says what including it means.
- **Detail, raw values.** Tracked-uppercase labels ("MIME TYPE", "WARNING"), the
  enum `ready` / `failed`, sizes in bytes, a US-only date.
- **Detail, the unreadable file.** "Preview unavailable" in red *after* the
  metadata, "0 sections · 0 tables · 0 relevant images" as the summary, and no
  word on what to do.
- **Detail, the passages.** Every passage its own bordered box headed by a
  24-character id at the weight of the text, in the interface sans; the outline
  listed each heading's location — "Paragraph 1, Paragraph 3, Paragraph 5" —
  not its words. A draft's file offered no inclusion control and no reason.
- **Keyboard.** The "Upload new version" control was a visually hidden file
  input in the tab order: a stop whose focus ring nobody could see.

## Decisions taken before starting

| Question | Decision |
|---|---|
| Catalogue form | **A table**, the worklist's: search, filter pills, sortable File and Added columns, the row one link; folds below `md`. |
| "Attached to" | **The requirement's or draft's title, fetched** — approved by the product owner as a data-fetching change (see below). |

## As built

### Catalogue

- **"Documents"**, one sentence: "Every file attached to a requirement or a
  draft. Open one to see what was read from it and whether analysis uses it."
  Header links renamed *Shared library* and *Architecture knowledge*.
- **One table in a panel** (`Table` primitive), columns *File* (name, then
  "Word document · 845 B", plus the version when there is more than one),
  *Readiness* (Badge: Ready / Ready, with warnings / Could not be read, plus
  *Needs a decision* when the file requires attention), *Analysis* (✓ In
  analysis / Left out), *Attached to* (the requirement's or draft's title,
  linked to its Source step or to the draft), *Added*.
- **Toolbar:** search by file name, a count ("2 of 6 files"), and pills *All*,
  *Needs a decision*, *In analysis*, *Left out* — only those with a count.
  File and Added headers sort with `aria-sort`; below `md` a select stands in.
- **States:** skeleton rows, the shared error state, an empty state with *New
  requirement*, and "No files match" inside the table when a filter empties it.

### Detail

- **Header:** the filename; "Excel workbook · 5.3 KB · Version 1 · Attached to
  *High-speed business bundles*"; *Upload new version* as a real `Button`
  driving a file input taken out of the tab order.
- **"Use in analysis"** — one card, in the order a person decides: readiness
  and what was read ("Read 4 sections · 1 table."), then for an unreadable file
  "Nothing usable could be read from this file." with the reader's reason, then
  *What to check* (each warning a Badge — *Blocks analysis*, *Check this*,
  *Note* — its message, and *Show in the file*), then *Hidden worksheets*, then
  the decision: *Include in analysis* with the provider disclosure as its hint.
  The card takes the danger or warning tone when the file is unreadable or needs
  a decision. A file needing attention offers *Leave out of analysis* (the
  existing inclusion call, as on the Source step). A draft's file says the
  choice is made on the draft and links there.
- **"File record"** beside it at `lg`, inset: type, size, added, reading, passage
  count, the full checksum in mono, and the versions newest first with *Current*
  and a short checksum.
- **"What was read"** — passages on one sheet divided by hairlines, the location
  ("Table 1, row 2", "Worksheet 1!2:2") quiet above each and the id faint at the
  end, text in the document serif at 16px/1.6 capped at 68ch. The outline, pinned
  beside them at `lg`, lists headings in their own words with the location under.
  A passage a warning points at carries the amber edge and *Check this*; the
  passage a link lands on (`:target`) carries the indigo edge. PDFs keep the safe
  iframe preview and *Open PDF*.

`#block-<id>` anchors, the "Upload new version" label and the "Include in
analysis" name are unchanged: Clarify's "Open this passage" links and the smoke
specs depend on them.

### Primitives, found on the way

- `Checkbox` with a `hint` is named by its label text alone. The hint sits inside
  the `<label>` so it is part of the target, which also made it part of the
  name — "Include in analysis When included, the text passages…" — and then the
  description again. This screen is the first caller that passes a hint.

### New presentation vocabulary

`features/documents/labels.ts`: `fileTypeLabel` (MIME → "Word document"),
`BLOCK_KIND`, `SEVERITY`, `dateTimeLabel`.

### CSS deleted

Every catalogue, metadata, preview, evidence-block, warning, worksheet and
version-history rule in `06-source-documents.css`, and `.include-control`. What
remains there is `.visually-hidden` and `.icon-button`, which other screens use.

### The one data change

`features/documents/useDocumentOwners.ts` reads requirement titles
(`api.getRequirement` under `queryKeys.requirement(id)`, one request per distinct
requirement, shared with the workspace's cache) and draft titles
(`api.listRequirementDrafts` under `queryKeys.requirementDrafts()`, as the
worklist does). Read-only; a title that cannot be read falls back to a working
"Requirement" / "Draft" link. Approved for this phase by the product owner.
Every other query, mutation, variable and hook on both pages is unchanged.

## Verification

- `npm run build` and `npm run lint` green. `vitest run`: 499 of 500 pass; the
  one failure, `client.test.ts › downloads an authenticated export`, fails
  identically on a clean checkout — `Response` from MSW under this container's
  Node 22 — and is unrelated. New: `DocumentsPage.test.tsx` (rows in words,
  newest first; filter; search; header sort with `aria-sort`; empty state) and
  six detail tests (warnings before the decision and its description; owner and
  type in words; outline in the document's words; hidden sheets through the
  existing call; the unreadable file; a draft's file).
- Smoke on a fresh API, 1440 and 740: the source-documents journey in
  `review-flow`, `analysis-sources`, `attachment-flow`, `ingestion-completion`,
  `content-security-policy` and `responsive-layout` — 19 passed, 5 skipped by
  design. Spec changes are copy only: the h1 is "Documents" and the versions
  list reads "Version 2".
- Live, seeded: no horizontal overflow at 1440 and 390 in Paper, or at 1440 in
  Slate; a Tab walk through both pages at 1440×900 and 390×844 leaves no focused
  element under the fixed header.

## Critique pass

A baseline `/impeccable critique` of the build above (dual assessment on the
live seeded app; snapshots `.impeccable/critique/2026-09-26T15-50-03Z__…`)
scored **24/40**, no P0, three P1s. The detector was clean on the source; its
in-page findings were line length at the 80ch interface measure, the danger
card's edge (the One Edge Rule, intended) and a table header read as a nested
card (false positive). All five priority issues were then addressed:

- **"What was read" matched what the AI reads** (P1). Passages from a hidden
  sheet nobody ticked sit on the margin ground with *Not sent · hidden sheet*,
  and the outline says "not sent"; the hidden-sheet checkbox uses the sheet's
  own name ("Margin model", hint "Worksheet 2 in the workbook"); PDFs show
  *What analysis reads* under the *Original*; a draft's file says *In analysis
  on the draft* or *Left out on the draft*. The section is now titled *What
  analysis reads*, and the include hint mentions hidden sheets only where
  there are some.
- **Amber is kept for what needs a person** (P1). Six warning codes that
  describe how a file *type* is read (`isReadingNote`, an explicit list in
  `labels.ts`) move to a quiet *How this file type is read* disclosure, and a
  file whose only warnings are those notes reads *Ready* on both pages
  (`readinessView`). Everything else — a referenced file that was not opened,
  hidden sheets, merged cells, OCR, images — stays under *What to check*.
- **The unreadable file has a way forward** (P1). One plain sentence ("often a
  scan or photo with no text in it…"), *Upload a readable version* inside the
  card as the page's one primary action, the draft or *Leave out of analysis*
  beside it, the accepted formats under it, the reader's own message in a
  disclosure, and no empty passage section. The catalogue says *Not usable*
  and *Needs a decision* on that row.
- **Passages look like the file** (P2). Runs of Word table rows and worksheet
  ranges are drawn as tables (`passages.ts`, `groupPassages`), column letters
  for a sheet, row numbers down the side, cells in the serif; a run with any
  row the parser cannot read stays as written. The hex id is gone; the
  location ("Paragraph 2") is a link to the passage. A flagged passage offers
  *Back to what to check*. The outline needs two headings. Below `lg` the
  passages come before the file record.
- **The catalogue knows the requirement** (P2). Search covers requirement
  titles, an *Attached to* select narrows to one requirement, *Added* is
  relative (exact time in the tooltip), the count sits beside the pills, and
  below `md` the select is the one sort control.

Found on the way: the worklist's search box was 54px, not 36px — `py-0` lost to
CONTROL's `py-2` on utility order. `SEARCH_FRAME` / `SEARCH_INPUT` in
`dashboard/controls.ts` fix it on both pages. The new *Attached to* select
widened the toolbar's grid track past 375px on long titles; the toolbar is now
one constrained column (`responsive-layout` caught it).

Not taken: bulk include from the catalogue (a new mutation call site, a logic
change); rendering Markdown syntax in passages (the reader sends the text
literally, so it is shown literally); changing warning severities at the source
(backend).

Verification: build and lint green; `vitest run` 507 of 508 (the pre-existing
Node 22 export test); new tests for reading notes, hidden-sheet naming and
not-sent marking, table rendering with its anchors, the PDF's extracted text,
the unreadable file's action, catalogue requirement search and filter, and
`passages.test.ts`. Smoke on a fresh API: the source-documents journey,
`analysis-sources`, `attachment-flow`, `ingestion-completion`,
`content-security-policy` and `responsive-layout` green at 1440 and 740. The
spec now asserts the Word table's row as a table cell rather than the raw
`R2C1: …` string, and *What analysis reads* rather than an outline its
one-heading fixture no longer shows.

## Re-critique, and the second pass

A re-run of the critique on the fixed build, with neither assessment shown the
first result (snapshots `.impeccable/critique/2026-09-26T16-22-01Z__…`), scored
**28/40** (from 24), two P1s. Both P1s and all three P2s were addressed:

- **The catalogue's File column collapsed at laptop widths** (P1, a regression
  of this phase): five columns, four of them fixed, left File 0px wide at 920
  and 50px at 1100. Now four columns — File, *Status* (readiness over what
  analysis does with the file), *Attached to* at 30%, *Added* folding into the
  File cell below `lg` — measured 233–471px from 920 to 1440, no overflow at
  375–1440.
- **"Needs a decision" led to a page with no decision** (P1). The backend's
  `requires_attention` is set when someone asks for a file that turns out
  unreadable, and it blocks the requirement's analysis until a new version is
  uploaded or the file is explicitly left out. One name for it everywhere:
  **Blocks analysis** — the pill, the row (red, with a glyph, pinned first, with
  the one edge), and the card: "It blocks analysis of this requirement until you
  upload a readable version or leave it out", with *Upload a readable version*
  and *Leave out of analysis* (or *Leave it out on the draft*) side by side. It
  is no longer counted under *Left out*, and "Not usable" is gone.
- **Which version analysis reads** (P2). The record says *Analysis reads:
  Version 1* / *None, it is left out* / *None yet, it blocks analysis*, and the
  versions list marks *Used by analysis* beside *Current*
  (`included_version_id`). The checksum says what it is for. Upload's accepted
  formats, and that a new version is left out until included, are in the record.
- **A left-out file's passages no longer look sent** (P2): the section reads
  *What analysis would read*, says nothing below is sent, and every passage is
  on the margin ground. PDFs show the original and the passages side by side at
  `lg`, with the page image one click away.
- **The power-user path** (P2): rows that block analysis are pinned first
  whatever the sort; same-titled requirements in the *Attached to* select carry
  the start of their id. Passage locations are plain text again (a link on every
  passage was a tab stop per paragraph), and a heading says it is one. Word and
  worksheet tables sit in the passage without a second frame, and cells break
  between words. The not-found page says the document isn't here, without its
  id or a retry.

Not taken: keeping the catalogue's filters in the URL, so they survive opening a
file. The worklist keeps its filters in component state too, so this is a
product-wide convention rather than a Documents fix — raised, not built.

## Follow-ups noted

- **The PDF preview is blocked by the app's own Content-Security-Policy.**
  `frontend/contentSecurityPolicy.ts:64` sets `frame-src 'none'` (since
  258c5a3), so the blob iframe under *Original* is refused in the built app —
  before and after this phase. A security-policy change, not a presentation one.
- **Filters that survive navigation**, for the worklist and this catalogue alike
  (above).
- **A draft's file cannot be included or excluded from its detail page.** The
  draft inclusion call exists (`setDraftDocumentInclusion`) but this page only
  ever wired the requirement one; the page says so and links to the draft.
  Wiring it is a logic change.
- **Hidden sheets are named by position in the API** ("Worksheet 2"); the page
  recovers each sheet's own name from its heading passage. Returning both from
  the API would make that mapping unnecessary.
