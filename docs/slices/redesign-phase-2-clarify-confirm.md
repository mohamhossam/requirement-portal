# Redesign Phase 2 — Clarify `/clarify` and Confirm `/confirm`

`docs/ux-plan.md` §5 Phase 2, on Phases 0–1, governed by `docs/design-system.md`,
`DESIGN.md` and the surface brief
`.impeccable/surfaces/frontend-src-features-analysis-analysispanel-tsx.md`.
Presentation only (`CLAUDE.md`). Every step ends with build, lint, `test:coverage`
and the Playwright smoke green.

> "Close the gaps the analysis found" (Clarify) and "sign off that the analysis
> is right before anything is generated from it" (Confirm) — ux-plan §1. The
> highest-value screen in the product.

## Decisions taken before starting

| Question | Decision |
|---|---|
| "Merge Clarify and Confirm into one coherent step" | **One screen, two modes.** Both routes and the six-step rail stay. `/clarify` leads with the questions; `/confirm` is the same screen in its sign-off mode, with the confirm gate and what is settled first. No URL, `journey.ts`, `stagePath.ts` or shared-link change (ux-plan §6 decisions 1–2). |
| The pinned resolve bar hides focused controls (WCAG 2.2 2.4.11) | **CSS `scroll-padding`, verified.** Technique C43: while the bar is pinned, the document scroller reserves the bar's height at the bottom — pure CSS through `:has()`, no script. Measured at every focus stop at 1440×900 and 390×844; if anything is still covered, the bar is unpinned in the same step. |

## Where it stands

Earlier passes rebuilt the screen as the brief's two columns: what is settled on
the left (sticky), what is still open on the right; rows collapse to a
two-line question with kind · severity · owner slots; rows open independently;
the row boundary is `--line-strong`; typed answers appear provisionally in the
settled column. The last critique (26/40) and the brief leave these open:

1. **2.4.11** — 8–9 controls covered by the pinned resolve bar at 1440×900, 5 at
   390×844.
2. **The first viewport holds no question.** Pending intent proposals — 400px
   cards — sit above the questions, and the gate's copy says "every proposal
   above".
3. **The accent is on the button you cannot press.** A gated Confirm renders at
   full indigo fill while the action you can take is quieter.
4. **`/confirm` is `/clarify`.** The Requirement Owner's one job sits at the foot
   of the open column under "What is still open".
5. **An open row loses its question.** Severity, blocker and assignee come before
   the answer, so the field is ~380px below the question it answers.
6. **Answers are typed in the interface face** under a question set in the
   document serif.
7. **The accent is spent on the settled outcome** (a 3px indigo edge on
   Indigo Wash) — settled understanding is not an action.
8. **The reconciliation summary is a sentence on a green wash** — green means
   approved, and "kept 3, retired 1, revised 1, new 2" is a count to scan, not
   prose to read.

## Steps

### 2.1 The loop: order, answer, send — done

- In the open column, questions come first — "Must be answered first", then
  "Worth answering" — and the owner's intent decisions follow, headed
  "Decisions you owe". The gate's copy stops saying "above".
- An open row reads top to bottom as the work: rationale and sources, the
  answer (Source Serif at the document size, as the question is), grounded
  suggestions, then the triage controls.
- The gated Confirm is a secondary button with its reason; the filled accent
  is kept for the resolve bar's send and an unblocked Confirm.

### 2.2 2.4.11 — the pinned bar — done

`:root:has([data-resolve-pinned])` reserves the bar's worst-case height as
`scroll-padding-bottom`, added to the shell's existing `scroll-padding-top`.
Verified by tabbing every stop; fallback as recorded above.

### 2.3 Confirm mode — done

`AnalysisView` passes its `view` to the panel. On `/confirm` the confirm gate
leads the open column, under a heading that names the job ("Sign off this
analysis"), and the questions follow; on `/clarify` the gate stays at the foot
of the list, where the work ends.

### 2.4 Settled understanding and the reconciliation summary — done

- The agreed outcome is a plain document block — serif lead, provenance glyph
  and label — with no accent edge or wash.
- The reconciliation summary becomes a neutral inset: "Since the last round"
  with four labelled counts (Kept · Retired · Revised · New), tabular, and a
  link to the round history. No status colour: it reports, it does not approve.

### 2.5 Verification

Unit tests for the new order, modes and summary; smoke specs that depend on
the moved copy. One batched visual pass in Paper and Slate at 1440 / 900 / 390
on both routes, the 2.4.11 measurement, and a check that the first viewport at
1440×900 shows a question.

## As built

- **Order.** The open column reads: must-answer questions, worth-answering
  questions, the send bar, "Decisions you owe", then (on Clarify) the gate.
  The first question at 1440×900 now sits at 481px (the critique measured it at
  1010px, below the fold). The source-impact panel moved below the analysis:
  above it, it stood between a person and the first question on every visit.
- **Rows.** An open row reads question, rationale and sources, the answer
  (already Source Serif at the document size), suggestions, save — then a
  "Triage" group with severity, blocker and assignee.
- **Gate.** Secondary while gated, with its reason; primary only when it can
  act. On `/confirm` it leads the screen as its own `h2` section, rendered
  once; on `/clarify` it is an `h3` at the foot of the open column.
- **Settled outcome** is a plain document block; **the reconciliation summary**
  is a neutral "Since the last round" strip with Kept · Retired · Revised · New
  and a link to the round history.
- **2.4.11, measured.** Each focusable control in the open column was parked
  inside the pinned bar's band and focused. With `scroll-padding-bottom` alone:
  **0 of 44 covered at 1440×900, 0 of 44 at 390×844.** With neither the padding
  nor the old per-control `scroll-margin`: 33 and 36 covered. The per-control
  `scroll-margin` was removed as redundant; the column keeps its bottom runway.
  The bar measures 98px at 390, inside the 112px reserve. (A sequential-Tab
  traversal could not tell fix from no-fix — questions-first ordering meant
  tabbing mostly triggered a scroll anyway — which is why the park-and-focus
  probe was used.)

## Follow-ups noted

- At 1280 the open column is narrow enough that a row's assignee slot
  truncates to "N." while the state ("Not started") holds the right edge.

## Not in Phase 2

- Merging the journey steps or changing URLs — declined above.
- The `busy` prop that conflates "no permission" with "request pending" — a
  state-logic change (surface brief, recorded concern).
- Expand-all / keyboard path between rows — interaction state on uncontrolled
  `<details>` that refetches remount; left for a later pass.
- Knowledge (`/knowledge`) — Phase 5.
