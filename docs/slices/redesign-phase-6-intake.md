# Redesign Phase 6 — Intake `/requirements/new`

`docs/ux-plan.md` §5 Phase 6, on Phases 0–5, governed by `docs/design-system.md`
and `DESIGN.md`. Presentation only (`CLAUDE.md`). Ends with build, lint,
`test:coverage` and the Playwright smoke green.

> "Get my business need into the system without learning the method." —
> ux-plan §1, the business owner's screen: "the product's first impression for
> one of its four users… Bring the worked example out of the closed `<details>`
> for the person who most needs it."

## Where it stood

A baseline `/impeccable critique` (dual assessment on the live seeded page: a
blank intake, a fully filled draft, a draft with one readable and one corrupt
file, and the same form in the Source drawer; 1440 and 390, Paper and Slate;
snapshot `.impeccable/critique/2026-09-26T11-11-36Z__…newrequirementpage…`)
scored **18/40**:

- **Focus hidden behind the sticky action bar** (P0, WCAG 2.4.11). Tabbing to
  "Desired outcome" at 1440×900 left it wholly under the bar; at 390 the bar was
  180px — a fifth of the screen — and hid Attach files, Channels and Known
  systems. Nothing reserved its height in the scroll padding.
- **Readiness in the wrong place, colour and words** (P1). "Analysis is not
  ready / Missing: title, business need text or a ready attachment" sat in a card
  *below* the button it explained, edged in indigo whatever it said (the success
  border was overridden). The primary was `disabled`, so its reason was never
  reached and the form's linked error summary could not appear in create mode.
- **The worked example did not help while writing** (P1): after the form and its
  buttons, a title and one sentence, under the eyebrow "Worked example"; field
  examples lived in placeholders that vanish on the first keystroke.
- **The chrome broke DESIGN.md** (P2): four eyebrows, "01/02/03" twice (filled
  indigo, read aloud), "Draft New Requirement", h1 → h3, raw inputs, 43 lines of
  off-token CSS, three different step models on one page, eight fields that all
  looked required.
- **Save state misled** (P3): "Preparing draft…" with nothing being prepared, a
  "Changes not saved" flash on every pause, a time with no date.

## Decisions taken before starting

| Question | Decision |
|---|---|
| Where the example lives | **Beside the form.** A complete filled example in a sticky column at `lg` (`#example`, which the Help menu links to); a "See an example" disclosure under the business need below it. |
| The optional fields | **One optional section**, "Add detail if you know it (optional)", open whenever any of them has a value — a resumed draft and the Source drawer's edit form never hide content. |
| The main button | **Pressable, not disabled.** Pressing it runs the form's existing validation, which shows the linked summary. Gated by the readiness line only while attachments are processing or unreadable — the cases the submit handler already refuses. |

## As built

- **Header.** "New requirement", no eyebrow, one sentence in the owner's words:
  "Describe what you need in your own words. Only a title and the need itself are
  required, and your draft saves as you go."
- **The need first.** Title and business need on the `Input` / `Textarea`
  primitives with persistent hints ("A short name people will recognise, like
  'High-speed business bundles'."), then the attachment list (Phase 5's
  `DocumentPanel`, its heading an `h2` here). "Business need" stops being
  required once a ready file is included — the required marker and
  `aria-required` both follow `hasIncludedAttachment`.
- **The example** (`IntakeExample`): every field under the form's own labels,
  filled in, in the document serif, and one line on what happens next — "the
  analysis reads what you wrote, lists what it understood, and asks about
  anything unclear. Nothing is generated until you confirm it." It replaces the
  guidance list, the one-sentence example and the "What happens next" 01/02/03.
  Opening `/requirements/new#example` below `lg` opens the inline one.
- **Optional detail** in one disclosure with plain labels: *Desired outcome*,
  *Who is affected*, *Channels*, *Systems involved*, *Rules that must hold*,
  *Deadlines and limits*. Two columns on the page, one in the drawer. No
  placeholders: every example is a hint that stays.
- **The action bar.** One readiness line beside the buttons — glyph, colour and
  words: *Ready for analysis*; *Not ready for analysis · Add a title and describe
  the need.*; *…A file could not be read. Retry it, or leave it out of
  analysis.*; *Files are still processing…*. Under it the save state: "Not saved
  yet. Your draft saves as you type." / "Your changes save automatically." /
  "Saving draft…" / "Saved 15:03" (with the date on another day) / "Draft save
  failed. What you typed is still here." + Retry save. The accent goes to "Save
  and analyse" only when it will go through.
- **Focus never hidden.** The bar pins from `sm` up only (below it, it sits at
  the end of the form), and `:root:has([data-intake-actions])` reserves 128px of
  `scroll-padding-bottom` — the Clarify screen's C43 technique.
- **Errors.** The summary is a labelled group that takes focus, not a third
  `role="alert"` on top of each field's own.
- **"Your requirement is saved. Nothing was lost."** — the analysis-failure
  state is a warning card with Retry analysis first.

### Primitives, found on the way

- `Button` takes `blockedBy`: the same gate as `blockedReason` (`aria-disabled`,
  tab stop kept, click swallowed) when the reason is already on screen beside the
  button — described by that element, nothing rendered twice.
- `Disclosure` takes `defaultOpen` and `id`.

### CSS deleted

`05-intake-stages.css` (the whole file); `.intake-card`, `.intake-form`,
`.field-group`, `.field-heading`, `.field-hint`, `.field-error` and the
`.intake-form .form-actions` rules in `01-foundation.css`; the `.what-next`
media rule in `09-breakdown-review.css`.

### Logic untouched

No query, mutation, variable or hook changed. The autosave queue, draft
promotion, analysis start, retry and navigation are line-for-line. The form's
submit handler and validation are unchanged; what changed is that the primary
button no longer blocks the handler from running when fields are missing — the
handler then refuses and says why, as it always did in edit mode. Its guards for
busy and blocked attachments are unchanged.

## Verification

- `npm run build`, `npm run lint`, `npm run test:coverage` green: 490 unit tests
  (new: the example beside the form, readiness beside a pressable button and the
  summary it opens, the gate by the readiness line while files process, the
  optional section opening when a draft carries detail, the need not required
  once a file carries it, the Help link keeping an open draft).
- Smoke on a fresh API: `review-flow`, `attachment-flow`, `responsive-layout`,
  `content-security-policy`, `focused-breakdown`, `ingestion-completion` and
  `library-spreadsheet-merges` at 1440 and 740 — 45 passed, 5 skipped; after
  the critique fixes `review-flow`, `attachment-flow` and the CSP spec re-ran
  24/24. Spec changes are copy only, plus opening the optional section before
  filling "Systems involved".
- Live, seeded, at 1440 in Paper and Slate and at 390: overflow 0; a real Tab
  walk through every stop on all three pages at 1440×900 and 390×844 leaves no
  focused element under the bar or the header; Help → "Read the worked example"
  from an open draft keeps it and opens the example at both widths.

## Critique pass

A verification `/impeccable critique` (dual assessment on the built page;
snapshot `.impeccable/critique/2026-09-26T…newrequirementpage…`, the second of
two) scored **30/40** (from 18), every baseline P0 and P1 resolved. The detector
was clean on all three files. It found regressions of this build, all fixed
before this doc:

- the Help menu's "Read the worked example" linked to a bare
  `/requirements/new#example`, which opened a blank form over an open draft —
  it now keeps the draft's query on the intake page;
- below `lg` the same link did nothing once on the page — the page now opens
  and scrolls to whichever example is on screen when the hash is `#example`;
- the folded example had no frame and could read as part of the form;
- the gated button's reason was described twice (`aria-describedby` and
  `blockedBy` named the same element) — `Button` now deduplicates;
- every autosave was announced ("Saving draft…", "Saved 15:04") — only a
  failure is, as an alert;
- the sticky example could push its closing note below a short screen — it
  scrolls within itself;
- the tab title said "Draft new requirement" under an h1 of "New requirement".

Not taken: the overlay's line-length flags are hints at the 80ch interface
measure DESIGN.md sets; the scrollable example column being a Tab stop is the
browser's own keyboard access to a scroll area.

## Follow-ups noted

- **The URL does not follow the draft.** After the first autosave the address
  stays `/requirements/new`, so a reload opens a blank form (the draft is safe,
  and resumable from the worklist). `navigate({ search: "?draft=" + id }, {
  replace: true })` on the first save is a page-logic change, raised.
- Enter in a text field submits the form through its first submit button, "Save
  draft and exit" — unchanged behaviour, worth a product decision.
- Pressing a gated "Save and analyse" (files unreadable) does nothing visible;
  the reason is beside it and read with it, but the click has no response.
- The Source drawer's edit form ends 1,600px down with its actions unpinned;
  pinning them needs scroll padding inside the drawer too.
