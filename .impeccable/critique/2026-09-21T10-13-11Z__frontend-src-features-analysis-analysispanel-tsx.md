---
target: requirement clarification screen
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\analysis\\AnalysisPanel.tsx"
target_fingerprint: "sha256:297e4260b6f1dd9664ea0fdb3e170da3626b652a59b9fda3e2ba076848dfc911"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\analysis\\AnalysisPanel.tsx"
timestamp: 2026-09-21T10-13-11Z
slug: frontend-src-features-analysis-analysispanel-tsx
closed: true
---
Method: dual-agent — Assessment A (design review) and Assessment B (detector + browser evidence) ran as isolated sub-agents. Both were interrupted twice by API rate limits and resumed from transcript. Contradictions between them were re-measured in the parent against the live DOM.

Note: this screen was built earlier in the same session by the agent running the critique; the two isolated assessments and independent re-verification exist to offset that.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | "Answer ready" is a 13px --ink-muted word top-right, same size/colour/position as the "Not started" it replaces |
| 2 | Match System / Real World | 3 | labels.ts is a real fix, but Assumption / Ambiguity / Potential dependency are undefined RE method words |
| 3 | User Control and Freedom | 2 | No un-pick for a suggestion; no review before batch send; unsaved guard covers navigation only |
| 4 | Consistency and Standards | 2 | Focus ring computes rgb(20,23,26) (--ink) while --focus (#4338ca) is defined and unused. Two controls named "Re-analyse" do opposite things |
| 5 | Error Prevention | 2 | Top-right Re-analyse discards typed answers; its dialog never mentions them |
| 6 | Recognition Rather Than Recall | 2 | Severity/blocker/assignee each behind a per-card details; severity badge renders only when high |
| 7 | Flexibility and Efficiency | 2 | No shortcuts, no multi-select, no filter/sort, no next-unanswered on a 4,355px page |
| 8 | Aesthetic and Minimalist | 2 | Empty suggestions apparatus on every card; card-to-canvas separation 1.06:1 tone + 1.27:1 hairline |
| 9 | Error Recovery | 2 | One shared error string for all mutations, rendered once at the column foot |
| 10 | Help and Documentation | 2 | Nothing defines the finding kinds; nothing says what re-analysis does to answers; /confirm never explains the gate |
| **Total** | | **22/40** | **Acceptable** |

## Design Specificity Verdict

IA authored for this product; the QuestionCard is a stock enterprise card (badge row, heading, muted rationale, collapsed disclosure, textarea, dashed box, footer button).

Direction contract unmet on four checkable points:

- "blocking questions first" in first viewport -> first viewport contains zero questions
- "a serif answer field" -> Public Sans 14px against a Source Serif 16px question (verified)
- "capped at 68ch" -> max-width 595px inside a 472px column; cap never binds
- "Signal Indigo spent once" -> six accent sites in the first viewport

Deterministic scan: CLI detector returned an empty array, exit 0, on the target files and on components + features/analysis. A control run on the legacy CSS layers produced 5 side-tab findings, confirming the detector was live.

Runtime overlay: 15 findings on /clarify, 16 on /confirm — nested-cards x4, heading-rhythm x2, skipped-heading x1, layout-transition x1, first-viewport-column-overflow x1, low-contrast x1. Source-clean, runtime-dirty.

## Priority Issues

### [P0] "Re-analyse" silently destroys every typed, unsent answer

Answers live in local state keyed by question.id; a new round issues new IDs. useUnsavedGuard intercepts navigation only, so it never fires. Dialog copy discusses backlog items, never the answers. Breaches PRODUCT.md Principle 4 ("Nothing human is silently lost"). Name collision with "Send N answers and re-analyse".

Fix: rename to "Start a new analysis"; when readyAnswers.length is above zero, lead the dialog with the loss, primary "Send them first", danger "Discard and re-analyse".

Command: /impeccable harden

### [P1] The pinned resolve bar hides focused controls (WCAG 2.2 2.4.11)

Verified in the parent with an answer typed so the bar pins: 12 of 68 controls obscured when focused. Three are 100% covered — "Accept as written" (38 of 38px), "Reject" (38 of 38px), "Look again" (24 of 24px). A suggestion button loses 63 of 81px. Assessment B's "zero obscured" was measured at rest, before the bar pins. scroll-mb-20 sits on the Card, not on its focusable descendants.

Fix: scroll-padding-bottom on the scroll container equal to bar height plus 8px, matching the existing scroll-padding-top pattern. Re-run tab traversal with an answer typed.

Command: /impeccable audit

### [P1] /confirm offers no way to confirm and no reason why

Verified live with 4 blockers: no confirm button; "Confirm this analysis", "Ready to confirm", "One thing first" and "Not ready to confirm" are all absent from the page body, while the page description reads "...before confirmation". confirmGate is gated on the absence of blockers. Violates design-system.md section 11 (a gated primary action stays visible and explains why).

Fix: render confirmGate whenever the analysis is unconfirmed, with a third "Not ready to confirm" state naming the obstacle, and the disabled button carrying it as blockedReason.

Command: /impeccable harden

### [P1] One question is 1,801px, so batch triage is structurally impossible

Placeholder cards measure 674-707px; page 4,355px. One realistic 400-character question with rationale and three realistic suggestions grows a single card to 1,801px. The work column is 472px on a 1440px screen. No overview, sort, filter, collapse or next-unanswered, and the three triage attributes are each behind a disclosure.

Fix: a collapsed row as the default state for the open column (about 64px per question), expanding one at a time.

Command: /impeccable layout

### [P2] Chosen suggestion renders no visible state; answer field breaks the type register

Verified: aria-pressed becomes true and border-accent bg-accent-wash land in the class list, but the computed background is unchanged (rgb(25,28,32) before and after) and the border stays --line-strong. border-line-strong in the base class list wins the cascade. The answer textarea is Public Sans 14px against a Source Serif 16px question, fixed at 3 rows with internal scroll.

Fix: move border-line-strong into the unpicked branch; add a check glyph beside "Using this"; give the textarea font-serif text-document and field-sizing: content.

Command: /impeccable polish

## Persona Red Flags

Alex (BA, power user): no keyboard shortcuts, 68 focusables tab-only; no bulk classify or assign; severity badge only when high, so Minor and Significant are invisible; empty suggestions box on every card; "Ask someone else" permanently expanded mid-column.

Sam (accessibility-dependent): three controls 100% covered by the pinned bar; focus ring computes --ink rather than the defined --focus token; SourceLinks returns null with no evidence, so unsourced is indistinguishable from missed.

Dana (business owner, non-agile, the person who confirms): Assumption / Ambiguity / Potential dependency undefined; the classification disclosure puts BA levers in her reading path; /confirm gives her no button and no reason; two buttons named "Re-analyse", one of them destructive.

## Minor Observations

- Heading skip h1 to h3 on both routes (22 headings, one h1, one skip)
- nested-cards x4: the dashed suggestions box inside each question card
- Heading rhythm inverted on settled-heading and open-heading: 16px above, 29px below
- transition: width on the progress bar
- notification-count fails dark at 2.26:1 (09-breakdown-review.css:103 hardcodes color: white instead of --on-accent) — outside this surface, one-token fix
- Disabled secondary buttons compute 4.43:1 (--ink-faint on --surface-sunken, the system's own documented forbidden pair)
- The 3px --warning-edge is applied to all four cards under a heading that already says "Must be answered first (4)"
- A suggestion's rationale and evidence render only after it is picked
- Likely false positive: side-tab on the live routes flags 2.667px token-driven accent borders, which are the sanctioned emphasis device. The 04/05/06 CSS findings are real drift and deliberately unsuppressed
- Corrected in-run false positives: Assessment B's first "0 reduced-motion blocks" and "52 controls without focus ring" were measurement artifacts; motion is handled and every control does ring

## Questions to Consider

1. If the questions are why this route exists, why does the first viewport contain none of them?
2. Which of "Save as a draft", "Send N answers and re-analyse" and "Re-analyse" is the button a user should press?
3. The thesis says answering moves an item across, but nothing moves until a server round-trip. Is the left column a live promise or a screenshot of the last round?
4. What is the longest real question this layout has been tested against, and has that number been written down?
