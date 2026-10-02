# Redesign Phase 4 — Backlog `/breakdown/*`

`docs/ux-plan.md` §5 Phase 4, on Phases 0–3, governed by `docs/design-system.md`,
`DESIGN.md` and the surface brief
`.impeccable/surfaces/features-breakdown-breakdownworkspace-tsx-864a79cb.md`.
Presentation only (`CLAUDE.md`). Ends with build, lint, `test:coverage` and the
Playwright smoke green.

> "Read and shape the generated backlog. Navigate Epic → Feature → Story, edit,
> approve each level" — ux-plan §1, the Product Owner's second-most-frequent
> flow (Flow D).

## Where it stood

Phase 4's stated goal — "fold it into the shared frame; keep the tree; drop the
second header, the second nav, and the drawer-only Source and People" — was
already met by the Phase 0 shell: one frame on every route, the Epic → Feature →
Story tree portalled into the rail under step 5, Source / People / History the
same everywhere. So this phase is about the content, not the frame.

A baseline `/impeccable critique` (dual assessment, live seeded Backlog at 1440
and 390, Paper and Slate; `.impeccable/critique/`) scored **21/40** — one up on
the 2026-09-20 critique — with four P1s:

1. **Approval was invisible as a human act.** Every Epic, Feature and Story
   response carries `current_approval` (who, when); the Backlog printed a green
   "Approved" and nothing else. Approve was one click with no word on what it
   binds.
2. **"What needs me?" could not be answered** from the Epic page or the rail:
   rows printed provenance, so a Feature edited after approval read as a quiet
   grey "Edited".
3. **Focus fell to `<body>`** on every inline Edit and Cancel, and gated
   controls were natively `disabled`, which removed them from the tab order and
   silenced `blockedReason`.
4. **The Story route spent its accent on leaving** ("Continue reviewing", a
   filled link to Review & approve on every Story) and overflowed to 397px at
   390.

Plus: staleness under three names with no remedy; architecture two
disclosures deep and still on retired styling; eyebrows; unchecked Stories
indistinguishable from passing ones.

## Decisions taken before starting

| Question | Decision |
|---|---|
| Scope | All six priority issues and the minor items, presentation only. |
| A recap before approving | **Inline, no dialog.** One line beside Approve says what the signature covers; Approve stays one click. |
| Shell | The rail scrolls the viewed step into view below `lg` (`StageRail.tsx`). The dead `focused={false}` branches stay — structural, not this phase. |

## As built

- **Verdicts, not provenance.** `features/breakdown/labels.ts` computes each
  item's verdict from data it already carries — *Out of date*, *Approved*,
  *Needs approval*, *Needs approving again* (an approval that lapsed on edit),
  and for Stories *Not yet approved* (neutral: Stories are approved on Review &
  approve). `BacklogStatus` puts it on each card; `VerdictText` on every row —
  rail tree, Feature list, Story list — with a glyph, never colour alone.
- **The signature.** "Approved by Amina Owner · 26 Sep 2026, 10:20" on every
  approved Epic, Feature and Story, and in the Feature list.
- **What approving covers**, in one line beside Approve on the Epic and the
  Feature, before the click.
- **What needs me.** The Features card says "1 of 2 needs approval" and its
  primary is "Review next Feature" (the name on hover), or "Go to Review &
  approve" when nothing here is owed.
- **The Story route.** Its one filled action is the way on: *Next Story*, then
  *Next Feature*, then *Go to Review & approve* at the very end. The card says
  "Stories are approved on Review & approve, not here" — the answer to "why is
  there no Approve?". The action row wraps (`min-w-0`): no overflow at 390.
  "Previous" at the first Story is a real disabled button, not a dimmed link
  that stayed keyboard-activatable at 3.35:1.
- **Focus and gating.** `useEditFocus` sends focus into an editor's first field
  and back to Edit on close, on Epic, Feature and Story. Approve and
  Regenerate all are gated through `blockedReason` (tab stop kept, reason
  read); the merge buttons stay disabled until two Stories are selected.
- **Out of date, one name.** `backlogItemLabel`, the notice and the shell
  banner all say it; the notice now names the remedy ("Read it against … then
  edit or regenerate it. Earlier versions stay in History.").
- **Quality, honestly.** The Story list says *Not checked* per row until an
  assessment exists, *N to check* or *Ready to build* after; its prompt tells
  "never checked" from "checked before the Stories changed".
- **Architecture.** The Feature card says "Touches BCRM, CPP · Crosses
  systems" on its face; Map / Refresh architecture moved inside System impact,
  beside its result. `ArchitectureImpactPanel` rebuilt on utilities: sentence
  case, one timestamp format, "Not in the catalogue", "Team", "Matched from the
  architecture catalogue". Its query is unchanged.
- **Smaller.** The rail tree marks the viewed item with StageRail's viewing
  ring instead of a second accent wash; Feature rows carry their full name on
  hover. "2 Stories" and "Acceptance criteria" are headings. The merge
  checkbox's accessible name starts with its visible label (WCAG 2.5.3).
  Breadcrumb links reach 24px. The AI proposal panel and the locked-backlog
  notice lost their eyebrows and moved to the primitives. "MVP / Later drop"
  reads "First release / Later release"; "Manual split / AI split" reads
  "Split by hand / Suggest a split"; "Portfolio outcome" is gone.
- **CSS deleted:** `.breakdown-locked`, every `.architecture-*` rule,
  `.proposal-*`, `.field-label`.

## Verification

- 473 unit tests (new: verdict and signature rules, Epic signature and recap,
  focus return), build and lint green.
- Smoke: `review-flow`, `focused-breakdown`, `responsive-layout` and the CSP
  spec, 33/33 at 1440 and 740 on a fresh API. (A first run reused the dev API
  and failed four unrelated specs on documents and saved views left by earlier
  runs; clean on a fresh server.)
- Live, seeded, at 1440 in Paper and Slate and at 390: overflow 0 on every
  route; focus into the editor on Edit and back to Edit on Cancel; the rail's
  viewed step on screen at 390; the accent spent on the rail's current step,
  the Next block and one action per screen — the tree no longer spends it.

## Follow-ups noted

- **Out-of-date Story counts on the Epic page and in the banner** need the
  Stories of collapsed Features, which are not loaded there — a data-fetching
  change, raised not made.
- The breadcrumb's last crumb is still "Story"; the Story's position ("Story 1
  of 2") sits directly below it.
- The Next block reads "Review the generated backlog" on the Backlog itself
  (`journey.ts`, deliberately stopped at Backlog — ux-plan §6).
- Dead `focused={false}` branches in the cards, `StoryList` and
  `FeatureTree.tsx`.
- A verification `/impeccable critique` run on the finished Backlog, to put a
  number on this pass.
