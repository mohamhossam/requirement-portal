---
version: 1
slug: "frontend-src-features-analysis-analysispanel-tsx"
primary_target: "frontend/src/features/analysis/AnalysisPanel.tsx"
related_targets: ["frontend/src/app/requirement/AnalysisView.tsx","frontend/src/features/analysis/AnalysisSources.tsx"]
---

# Clarify — the requirement's open questions

**Scope.** `/requirements/:id/clarify` and `/requirements/:id/confirm`, which render one component. Visitor mode: **Operate**.

**Audience and job.** The BA drives, several sessions per requirement; the business owner answers in business language; the Requirement Owner confirms. The job is batch triage — scan everything open, answer what is easy, come back to what is hard, resolve the whole batch in one re-analysis. Confirmed with the user: batch triage, not a one-at-a-time queue.

**Constraints.** `CLAUDE.md` presentation-only, widened by the user to allow exactly two non-presentation additions: a status/action label map in the presentation layer (`ux-plan.md` §4), and registering typed answers with the existing `useUnsavedGuard`. No routing change — `/clarify` and `/confirm` both stay, one component serves both (`ux-plan.md` §6 open decision 2 keeps URLs out of scope). Visual authority is `docs/design-system.md` + `tokens.css`; `DESIGN.md` records the retired Standards Bureau identity and is not an input (`ux-plan.md` §0).

## Direction contract

**THESIS.** One document mid-completion. Settled understanding on the left, everything still open on the right, and answering moves an item across. It refuses the arrangement this screen ships today — two equal finding columns under a status strip and an AI-intent section, where the questions are the third thing on the page and the extracted facts get first position for no reason a reviewer can act on.

**OWN-WORLD.** Paper `#f6f6f3` ground, white panels, `#dcdcd5` hairlines; Signal Indigo `#4338ca` spent once, on the open side; amber `#8a4b08` for attention and a 3px `--warning-edge` on blockers. Public Sans for every control and label in sentence case; Source Serif 4 at 16/1.6 for every question, fact and answer, capped at 68ch; IBM Plex Mono for IDs. Flat — a hairline and a tone step separate, never a shadow. The one emphasis device is a 3px left edge.

**STORY.** The reviewer sees in one glance how much of this requirement is already agreed and exactly what is still in the way. They answer down the right column, accepting grounded suggestions where they hold, and resolve the batch once. The left column is visibly longer than when they arrived.

**FIRST VIEWPORT.** A one-line provenance and progress strip spans the top: AI candidate or human-confirmed, answered-of-active, and a hairline bar. Below it two columns, `minmax(0,5fr) minmax(0,7fr)`. Left, under a sentence-case heading, the requirement as currently understood — confirmed outcome, facts, business rules, constraints, answers already given — set in Source Serif, each with its sources control. Right, the work: blocking questions first, each a card carrying kind, severity, assignee, evidence, grounded suggestions and a serif answer field. AI intent proposals sit at the head of the right column, because they are open decisions, not settled understanding. The resolve bar pins to the foot of the right column with a live ready count; the confirm gate replaces it when no blocker remains. Below `lg` the columns stack, open first.

**SIGNATURE INTERACTION.** Answering. A question with text in its field marks itself ready and increments the resolve bar's count; resolving the batch is the one moment the screen moves, and the item's destination — the left column — is where it will be on the next round. Motion is 150–200ms, transform and opacity only, and under `prefers-reduced-motion` the state change survives as a persistent mark rather than a transition.

**FORM.** The Converting Brief, index 7 of seven grounded structures, dealt as the lead. Seed key `0bf91471`; answered `converting-brief`, code-led.

**FINISH.** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

**FINISH — discharged by critique, 2026-09-21.** The shipped finish reviewer was spawned and killed twice mid-run by API rate limits, so it never returned a verdict. On the user's decision it was not resumed: `/impeccable critique` covered the same ground with two isolated assessments plus independent re-verification in the parent, and returned a harder finding list than the finish review would have. The review of record is
`.impeccable/critique/2026-09-21T10-13-11Z__frontend-src-features-analysis-analysispanel-tsx.md` — **22/40, Acceptable**, 1 P0 and 3 P1. That file, not this line, is the list to work from. DESIGN.md is untouched and stays that way: this was an extension inside the committed world, not a new one.

## Unresolved

## Reference applicability extension — 2026-09-21

THESIS: A reference is a proposal, not a fact. Extend existing owner decisions rather than adding a parallel review page.

OWN-WORLD: Inherit the current indigo, paper, serif evidence and plain control styles; no new palette, layout or navigation.

STORY: Read the proposed rule, inspect the exact published passage, explain applicability, then accept, edit or reject. Withdrawn evidence remains auditable but cannot support current work.

FIRST VIEWPORT: Reference proposals occupy the existing open-decisions column. Citation, excerpt and conflict warning precede wording and rationale controls. Desktop uses existing columns; narrow screens retain the existing open-first stack.

FORM: Narrow code-led extension of seed `0bf91471`; no concept roll. The signature interaction is the existing open-to-decided transition, now preserving its reference lineage.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

### Reference applicability extension completion — 2026-09-21

The extension's finish disposition is **ship**, limited to reference applicability in `AnalysisPanel.tsx` and its `AnalysisView.tsx` integration. Approved library passages appear with exact publication/version lineage and excerpts before the owner's rationale and accept/edit/reject controls. Changed reference evidence requests reconciliation and blocks acceptance and confirmation until resolved.

The finish review's state-copy finding is corrected: decided proposals say “owner decision recorded”; pending or reopened proposals request an owner decision; stale proposals say “reconciliation required”. The conflict prompt appears only while a decision is pending or being edited. Existing Working Paper tokens, evidence typography, columns and narrow-screen stacking remain the visual authority; no new visual system or raster asset was introduced.

Evidence supplied and inspected in the parent review: `.impeccable/review/reference-desktop.png`, `reference-mobile.png`, `reference-decided-desktop.png` and `reference-decided-mobile.png` (all under `.impeccable/review/`). The handoff records one detector run returning `[]`, two passing reference browser tests and four passing library browser tests. Documentation checks confirmed the evidence files exist and the corrected state copy is present in the implementation.

This closes documentation for this extension only. The earlier whole-surface critique and concerns below remain open; this is not a whole-surface accessibility clearance or production-readiness claim. `docs/design-system.md` and `frontend/src/styles/tokens.css` remain authoritative, and the pre-existing retired `DESIGN.md` drift is unchanged.

## Previously recorded unresolved concerns

- ~~Merging `/clarify` and `/confirm` into one journey step~~ — **decided 2026-09-26: one screen, two modes.** Both routes and the six-step rail stay; `/confirm` leads with the sign-off gate, `/clarify` with the questions (`docs/slices/redesign-phase-2-clarify-confirm.md`).
- The `busy` prop conflates "no permission" with "request pending", so a read-only viewer sees disabled controls without a reason. Out of the agreed scope; raise as follow-up.
- ~~**OPEN — WCAG 2.2 2.4.11, the pinned resolve bar.**~~ — **resolved 2026-09-26 (Phase 2).** Technique C43 in pure CSS: `:root:has([data-resolve-pinned])` sets `scroll-padding-bottom` to the bar's worst case. Measured by parking each focusable control in the bar's band and focusing it — 0 of 44 covered at 1440×900 and at 390×844 with the padding; 33 and 36 without. The earlier diagnosis (no scroll for an in-viewport control) holds for `scroll-margin` alone on older structure; `scroll-padding` on the scroller changes what counts as in view. The per-control `scroll-margin` is removed.
- **Card character.** The critique's verdict was that the IA is authored for this product but the QuestionCard is a stock enterprise card. The user's decision: do not pursue card character as its own exercise — take it only if it falls out of the collapsed-row structural fix. This is an Operate surface, where earned familiarity is a legitimate destination.
- **The contract's own unmet points**, from the critique. Phase 2 closed three: the first viewport now shows the questions (first row at 481px of 900); the answer field is Source Serif; the accent is off the settled outcome and off a gated Confirm. Still open: the `68ch` cap never binds inside the column.

## Search/grounding checkpoint — 2026-09-22

Selected answer suggestions expose the exact published passage, version and location through
the existing evidence typography and indigo links. The publication identity remains in the
citation URL; visible copy requests applicability confirmation independently of publication.
KnowledgeView adds plain-language reference-conflict and changed-source notices with links
back to owner review. Existing Public Sans controls, flat surfaces and evidence styling remain.

Independent documentation verification inspected AnalysisPanel.tsx, KnowledgeView.tsx, current
tokens and both final `grounding-answer-chromium.png` and
`grounding-answer-responsive-chromium.png` captures under `.impeccable/review/`. Citation wrapping
and stacked answer controls preserve the 390px layout. The handoff records two passing browser
tests including the overflow assertion, detector output `[]`, and ship at the single responsive
fix scope. This does not close the previously recorded whole-surface concerns above. No new
visual system or shipping raster asset was introduced; DESIGN.md and its sidecar remain
unchanged, including their pre-existing Archivo Narrow/oxblood and geometry drift.
