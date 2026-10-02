# Redesign Phase 1 — Worklist and shell `/`

`docs/ux-plan.md` §5 Phase 1, on the Phase 0 foundation
(`docs/slices/redesign-phase-0-foundation.md`), governed by `docs/design-system.md`
and `DESIGN.md` ("The Working Paper"). Presentation only (`CLAUDE.md`), with the
one small state read approved below. Every step ends with build, lint,
`test:coverage` and the Playwright smoke green.

> "What needs me today, and where do I resume?" — ux-plan §1, the BA's and PO's
> screen, opened every morning and walked many times a day (Flow A).

## Decisions taken before starting

| Question | Decision |
|---|---|
| Multi-select and bulk action | **Deferred to a backend slice.** There is no bulk API; looping the per-requirement endpoints from the browser is new mutation logic. The worklist moves onto the `Table` primitive now, so selection and `TableBulkBar` drop in when a bulk-assign endpoint exists. |
| "Resume where you left off" | **Allowed, worklist data only.** Read `localStorage.lastRequirementId` (written on every requirement visit, read nowhere) and offer "Resume *title*" only when that requirement is in the loaded worklist. No new request; absent otherwise. |
| Where a row goes | Unchanged: `stagePath(item)`. The `features`/`stories` → `/review` question is ux-plan §6 decision 1, a product call. |

## Where it stands

Phase 0 already delivered the shell: `AppShell`, the 56px `AppTopBar` (brand,
search, notifications, help, account, the primary "New requirement"), the
240/56px `AppSidebar`, the skip link and scroll clearance. What is left is the
screen inside it:

- **The worklist is a list of links dressed as a table.** Four columns, headings
  `aria-hidden`, tracked uppercase header labels, and sort only through a
  dropdown (§3.12). The `Table` primitive — sortable `aria-sort` headers, 44px
  rows, sticky header — exists and is unused here.
- **The accent is spent on every row.** Each row's next action is bold indigo,
  so a page of fifteen rows has fifteen accents (§4.4 rule 1: one, once).
- **Needs attention is a thin collapsible band** of look-alike rows, not the
  entry point the plan asks for.
- **The toolbar and the Views popover predate the primitives:** square 1px
  boxes, uppercase "Filter by", status chips inverted to near-black, a `▾`
  character as the disclosure icon (an icon-system ban), a hard-coded
  `z-index` and shadow (fixed in 0.6), and no radius on the ladder.

## Steps

### 1.1 The worklist on the `Table` primitive — done

A real `<table>`: Requirement · Owner · Stage · Updated · Next action. The title
is a link stretched over the whole row, so the row stays one click (the product's
interaction worth keeping) while the table keeps cell semantics; the row shows
the focus ring when its link has keyboard focus. **Requirement** and **Updated**
are sortable header buttons driving the existing `sort` state (`title_*`,
`updated_*` — the only orders the API has); the Sort select remains below `md`,
where the Updated column folds away. Below `md` the Owner, Stage and Updated cells
fold into the Requirement cell as secondary lines, so there is one DOM at every
width and nothing scrolls sideways. The next action moves from indigo to ink:
the accent is reserved for the one Next block (1.3). `Table` gains a `framed`
option so it can sit inside the worklist panel without a second border.

### 1.2 Toolbar on the primitives — done

Search, owner, "Assigned to me", sort and Views on the field recipe (36px, Rule
Line, 6px radius); status filters become `Pill`s (only non-zero counts, active
= filled accent), "Clear filters" and "N more" become text buttons, labels go to
sentence case, and the total reads as meta text with tabular numerals.

### 1.3 Needs attention as the entry point — done

The highest-priority item becomes the page's one `NextAction` — "Next · Answer
open questions — *High-speed business bundles*", linking to its stage — and the
rest follow as a compact "Also waiting on you" list with their status, owner and
age. Still collapsible, still absent when nothing needs attention.

### 1.4 Resume — done

"Resume *title* · *stage*" beside the existing draft resume, from
`lastRequirementId` when that requirement is in the loaded worklist.

### 1.5 Saved views — done

The Views popover on the primitives: a real button with a `lucide` chevron,
`--radius-lg`, `--elev-2` plus a border, `Select`/`Input` field recipe, and the
existing Save / Update / Delete actions unchanged.

### 1.6 Verification

Unit and smoke tests move from list to table roles. One batched visual pass in
Paper and Slate at 1440 / 900 / 375, a keyboard pass through the worklist (row
links, sort headers, pills, Views), and a check that each screen spends the
accent once.

## As built

- **Table.** Columns are Requirement · Owner · Status · Updated · Next action.
  Status took the badge out of the title line — a badge beside a long title
  wrapped the row onto two starts — and holds the stage and the amber
  "N unresolved · N stale" line; artifact counts appear only once a backlog
  exists (they were a line of zeros). About 38rem of fixed columns leaves the
  title roughly 335px at 1280 and 560px at 1440, clamped to two lines. The link
  is named by the title and described by the status and "Next: …" (the space is
  its own text node — inside the hidden span it was trimmed, and screen readers
  heard "Next:Analyse requirement"). Below `md` every other column folds into
  the Requirement cell; the Sort select serves there.
- **Status tones** live beside the labels (`app/dashboard/labels.ts`,
  `statusBadge`): amber for anything waiting on judgement, green only for
  approved, neutral for work in hand, each with its own glyph.
- **Accent.** Row next actions are ink. Indigo on this screen is the Next
  block, links and text buttons, the current navigation item, the header's one
  primary action, and an active sort or filter.
- **Toolbar** shares `app/dashboard/controls.ts` with the Views popover. The
  owner select needed an explicit `w-auto`: base.css gives every `select`
  `width: 100%`, which put it on a row of its own.
- **Attention.** The top item is `NextAction` (which gained an optional
  `detail`, the requirement's title); the rest are two-line rows below `md` —
  one line at 375px had left the title a single letter. Heading and toggle use
  the disclosure pattern (the button inside the `h2`).
- **Resume** reads `lastRequirementId` once and makes no request; it is a
  24px target like the draft resume beside it.
- **Keyboard.** Every stop on the worklist shows a ring: the row for its title
  link, the bordered box for the search input.
- **Narrow widths.** The attention section and the table's cell grids use
  `grid-cols-[minmax(0,1fr)]`. An implicit auto column takes its minimum from
  its widest item, and a truncated one-line title still counts at full width —
  `min-w-0` does not lower that contribution — so a long title in the Next
  block stretched the page to 481px at 375. It only showed with the smoke
  suite's data (titles like "Attachment source chromium 1790383226511"); a
  probe run after the other specs found it.

## Not in Phase 1

- Bulk selection and actions — waits for a bulk-assign API (backend slice).
- Row destination (`stagePath`) and URL changes — ux-plan §6 decisions 1–2.
- Screens other than `/` — Phases 2–9.
