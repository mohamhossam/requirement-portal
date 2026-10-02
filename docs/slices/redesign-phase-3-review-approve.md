# Redesign Phase 3 — Review and approve `/review`

`docs/ux-plan.md` §5 Phase 3, on Phases 0–2, governed by `docs/design-system.md`
and `DESIGN.md`. Presentation only (`CLAUDE.md`). Every step ends with build,
lint, `test:coverage` and the Playwright smoke green.

> "Is this backlog safe to approve?" — ux-plan §1. The Product Owner's screen,
> and the worst-structured one.

## Decisions taken before starting

| Question | Decision |
|---|---|
| How evidence comes before approval | **One column, sign-off last.** The screen reads as a document in the order the work happens. A sticky sign-off aside was declined: it puts the buttons beside the evidence again, and it needs `ApprovalWorkflowPanel` split across two rendered regions (a portal, or two instances of its mutations) — too close to the no-logic-change rule. |
| Promote Review to journey step 6 | **Already done** in Phase 0 (`journey.ts`). Nothing to change here. |
| Scope | `features/review/*` (the two panels, a new `labels.ts`, their tests), the review rules in `styles/09-breakdown-review.css`, the review description in `RequirementPage.tsx`, and `tests/review-flow.spec.ts`. `StoryQualityPanel` stays as it is — it is shared with the Backlog (Phase 4). |

## Where it stood

- **Approval above evidence** (§3.6). `ApprovalWorkflowPanel` mounted first:
  stepper, completion counts, blockers, Submit / Final approval, per-Story
  approve/reject, approval history and comments — and only then the concerns
  and the evidence they are meant to be decided on.
- **Thirteen stacked sections**, two `h2`s competing with the requirement's
  own `h1` ("Review and approval", "Remaining concerns"), eyebrows reading
  "Formal governance" and "Governance evidence".
- **Raw enums as copy** (§3.7): `.replaceAll("_", " ")` on the lifecycle, the
  effective status and each Story's state; filters labelled `all` / `blocking`
  / `warning` / `resolved`; severity, flag status and `potential` /
  `catalogued` as uppercase chips; "story: …" and "flag: …" in the comment
  target.
- **Two accents where none could act.** Submit for review and Final approval
  were both filled primary, gated or not.
- **Pre-primitive markup.** Raw inputs, a bespoke stylesheet with off-ladder
  radii (5/7px), 4px edges, tracked uppercase chips, and a `confirm-dialog`
  modal.

## As built

- **Order.** Where this review stands → Concerns to resolve → Evidence → Story
  quality → Decision log → Sign off this backlog → History and comments. Every
  section is an `h2` under the requirement's `h1`; a unit test pins the order.
- **Where this review stands** is a neutral sunken strip, like Clarify's
  "Since the last round": the status badge, three labelled counts (only an
  owed count takes status colour, and then with a glyph), the refresh time and
  ruleset, and Refresh review. The stale notice and mutation errors sit
  directly under it.
- **Concerns** are cards with the status edge and wash, a severity badge that
  names the consequence ("Blocks approval" — the backend's
  `strict-all-blockers-v1` policy makes every open blocker gate final
  approval — or "Worth resolving"), the category, the title, the detail in the
  document serif, and the source link. Filters are `Pill`s with counts, shown
  only when non-zero (except the active one).
- **Evidence** is one panel of up to three lists, with "Inferred" / "In the
  catalogue" and "Serious" / "Moderate" badges. Passing Stories sit behind a
  `Disclosure`.
- **Sign-off.** The lifecycle marks its current stage by glyph, weight and
  `aria-current="step"` — not the accent. Completion reads "1 of 1". Gate
  reasons are a warning card, referenced by the gated buttons through
  `aria-describedby`. Per-Story rows carry the Story in the serif and a badge
  (Approved by … / Needs revision / Awaiting a decision). Submit and Final
  approval come last; **the filled accent goes only to the one that can be
  taken**, the Phase 2 gate rule. Dialogs use the `Modal` dialog variant with
  `ModalHeader` / `ModalBody` / `ModalFooter`.
- **History and comments**: approvals as "Story approved by … · date", one
  timestamp format for the screen, comment target labelled "About" with
  "Whole backlog" / "Story: …" / "Concern: …".
- **Labels.** `features/review/labels.ts` maps every enum the screen renders; a
  unit test asserts none of the raw strings reach the page.
- **CSS.** The review and approval rules in `09-breakdown-review.css` are
  deleted; the screen is primitives and utilities. The file keeps the AI job,
  notification and architecture rules, which belong to other screens.
- **Logic untouched.** No query, mutation, variable, invalidation or local
  draft changed in either panel.

## Verification

- `npm run build`, `npm run lint`, `npm run test:coverage` green.
- `tests/review-flow.spec.ts` green at 1440 and 740 (18/18), plus the
  content-security-policy spec. Spec changes are selectors and moved copy
  only: role-based locators for the Story decisions list, the concerns
  region and the lifecycle's current step.
- Full-page captures at 1440 and 740 from the journey spec. The first pass
  caught stray side borders on list rows — `divide-solid` without Preflight
  leaves the other sides at `medium` — fixed with an explicit sibling
  `border-top`.

## Critique pass

`/impeccable critique` (dual assessment, live page at 1440 and 390, Paper and
Slate; snapshot in `.impeccable/critique/`) scored the first build **20/40**
with four P1s. Fixed, presentation only:

- **The strip no longer says "yes" early.** Its counts are named as what they
  count ("Concerns blocking approval", "Concerns worth resolving"), the backlog
  status is plain text (a neutral badge vanished on the sunken strip), and a
  "Sign-off status" link jumps to the sign-off. Showing real approvability in
  the strip would mean this panel reading the approval-workflow query — a
  data-fetching change, declined.
- **Story quality sits on the Story's decision row**: a verdict badge ("Ready
  to build" / "Split recommended · 2 of 6 checks failed") and the full checks
  behind "Readiness checks", titled with the Story. The separate section of
  four anonymous cards is gone. `StoryQualityPanel` gained an optional `title`
  (Backlog renders as before) and skips its empty findings list.
- **What stands in the way sits directly above Submit / Final approval**, and
  links to Backlog when the Epic or Features still need approving — this
  screen cannot approve them.
- **History names each approval's item and marks lapsed ones "No longer
  current"**, with one line on why; it no longer contradicts the completion
  counts.
- **Focus** moves into an inline form's first field and back to its trigger on
  cancel (WCAG 2.4.3), for concerns and the decision form.
- **Errors sit beside their cause**: a concern's save in that concern, a
  decision in the decision form, a Story approval under the list, dialog acts
  in the dialog, a comment in the comment form. Only a failed refresh stays at
  the top.
- **Names and dialogs.** Approve / Reject and Resolve with decision are
  described by their Story or concern; the Reject gate says why ("once the
  backlog is submitted"); dialog buttons name the act ("Submit backlog",
  "Grant final approval", "Reject Story") and Submit / Final approval recap
  what is approved and what is still open.
- **Smaller.** Evidence prose in the document serif; the decision form closed
  until asked for, with a line distinguishing it from resolving a concern;
  descriptions capped at the document measure; the 390px column overflow
  (a long select option sizing the grid track) fixed with `minmax(0,1fr)`.

Verified: 467 unit tests, build and lint green; `review-flow` and CSP smoke
20/20 at 1440 and 740; focus and overflow measured on the live page.

## Follow-ups noted

- **From the critique, not taken:** one-click Story Approve has no undo (a
  workflow question); risks repeat concern text verbatim (both are API data);
  the live region announces "Saving" but not completion (needs mutation-state
  wiring); the rail's Next still points at Backlog on this screen
  (`journey.ts` deliberately stops at Backlog — ux-plan §6); Textarea's
  measure cap leaves it narrower than a sibling Input (a primitive decision).

- ~~**Dark (Slate) visual pass not yet run**~~ — done in the critique pass. It uses tokens only,
  so no new pair is introduced, but it has not been looked at.
- The active filter pill is a filled accent (the `Pill` primitive, Phase 1),
  so the screen spends the accent there as well as on the rail's Next block.
  A primitive-level question, not this screen's.
- The toast stack covers part of the content in the journey captures at both widths.
  That's the global `Toaster`, not this screen.

## Not in Phase 3

- Merging the lifecycle into the stage rail, or any URL change (ux-plan §6).
- `StoryQualityPanel` — Phase 4, with the Backlog.
