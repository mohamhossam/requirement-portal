---
target: requirement clarification screen
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\analysis\\AnalysisPanel.tsx"
target_fingerprint: "sha256:55222b8d39822b4c19061dfc960bd38d5ef0bfd563fcb0cf49f670cc8561afab"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\analysis\\AnalysisPanel.tsx"
timestamp: 2026-09-21T12-07-35Z
slug: frontend-src-features-analysis-analysispanel-tsx
---
Method: dual-agent — Assessment A (design review) and Assessment B (detector + browser evidence) ran as isolated sub-agents. Contradictions with the parent's own earlier claims were re-measured in the parent against the live DOM.

Second critique of this surface. Four rounds of fixes (harden / audit / layout / polish) were applied between the 22/40 snapshot and this one.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Progress, counts and per-row ready state are honest; the conversion the screen promises is never shown in-session |
| 2 | Match System / Real World | 4 | labels.ts is exemplary; no enum reaches a user; sentence case throughout |
| 3 | User Control and Freedom | 3 | Drafts save, unsaved guard registered, destructive control named and its dialog leads with the loss; no undo after a re-analysis round |
| 4 | Consistency and Standards | 2 | ConfirmDialog is a different product (eyebrow, uppercase 12.16px buttons, off-token red #c4260e); three accent-filled buttons in one 472px column |
| 5 | Error Prevention | 3 | Gated-but-visible confirm with reason in aria-describedby; version-checked mutations; dialog names the loss |
| 6 | Recognition Rather Than Recall | 2 | Exclusive accordion makes comparing two questions impossible |
| 7 | Flexibility and Efficiency | 2 | Batch submit exists; no expand-all, no multi-select, no keyboard path between rows |
| 8 | Aesthetic and Minimalist | 2 | First viewport contains zero questions; first question row top = 1010px on a 900px viewport |
| 9 | Error Recovery | 3 | ErrorNotice sits beside the work; nothing wipes a typed answer |
| 10 | Help and Documentation | 2 | Good microcopy; the single persistent help affordance (WCAG 3.2.6) is still absent from this route |
| **Total** | | **26/40** | **Acceptable** |

Previous: 22/40. Trend: 22 -> 26.

## Design Specificity Verdict

Moved from "IA authored, card generic". The collapsed row is now authored: 68px, question in Source Serif semibold leading, muted meta line, answered-state right, amber 3px edge on blockers.

Three things hold it short:
- The expansion is a stock form, and its order is wrong — severity select, blocker checkbox, assignee select, then the answer field fourth.
- The thesis does not fire. "Answering moves an item across" never happens in-session; the settled column is byte-identical before and after answering all four.
- The accent is spent on the action you cannot take: Confirm this analysis renders at full #4338ca fill while aria-disabled, while the action you can take is grey.

Deterministic scan: CLI detector returned an empty array on the five target files and on components + features/analysis. A control run on legacy CSS produced 6 side-tab findings, confirming the detector was live. Runtime overlay found 36, of which 20 were a single false-positive class (text-occlusion on content inside closed details elements).

Exit-code caveat: the cmd //c wrapper swallows the real exit code, returning 0 even for a 6-finding run and for a nonexistent path. Do not gate CI on it.

## Priority Issues

### [P0] The exclusive accordion throws the row you clicked off the top of the screen
Measured reproducibly at 1440x900: rows 2, 3, 4 jump -656, -689, -689px. The clicked question's summary lands 207-240px above the viewport top; what remains on screen is the middle of a form with no question text.
Introduced by the collapsed-row change and not tested for: the accordion's toggling was verified, its resulting scroll position was not.
Fix: on toggle, summary.scrollIntoView({block:"start"}), or drop name="clarify-question" and let rows open independently — the exclusivity buys nothing here.
Command: /impeccable layout

### [P1] 8-9 controls remain obscured by the pinned resolve bar (WCAG 2.2 2.4.11)
Measured in the parent: 9 obscured with rows collapsed, 8 with a row open, at 1440x900; 5 at 390x844. Every one carries the 112px scroll-margin and sits in the open column.
A previously reported "12 -> 1" result was measured against the old always-expanded card structure, which the collapsed-row change then replaced; that verification was stale and was carried forward incorrectly.
scroll-margin only affects the scrolled case. Controls already inside the viewport when focused never trigger a scroll, so no CSS value reaches them.
Fix: a focusin handler that scrolls the focused element clear of the bar. This is a logic change and needs explicit authorisation under the presentation-only rule.
Command: /impeccable audit

### [P1] The collapsed row's boundary fails 3:1 in both themes, and its meta line truncates on real data
Boundary: the row uses --line. Light #dcdcd5 on #ffffff = 1.38:1, on canvas = 1.27:1. Dark #2b3036 = 1.40:1. --line-strong measures 3.71:1 and is already used by the suggestion buttons. Non-blocking rows have no amber edge, so no 3:1 boundary at all.
Truncation: the meta box is 337px at 1440; placeholder content measures exactly 337px. Real content ("Potential dependency · Critical · Amina Owner · Revised last round") measures 395px and truncates. Ellipsis cuts the end, so the first casualties are the assignee and "Revised last round" — the one signal that a question changed under the reviewer (PRODUCT.md Principle 4). At 390px three of four rows already truncate on placeholder content.
Fix: swap the row border to --line-strong; replace the concatenated meta string with a fixed three-slot grid so severity sits at a constant x and can be scanned vertically.
Command: /impeccable harden

### [P1] First viewport contains zero questions, and the accent is on the disabled button
First question row top = 1010px on a 900px viewport. The six panel controls in view are the intent card's two textareas and three decision buttons plus "Start a new analysis". Confirm this analysis renders at full accent fill while aria-disabled; Send answers and re-analyse is grey.
Fix: put the question list above the pending intent proposals and collapse the proposal to the same 68px row vocabulary; render a gated primary as secondary-outline plus reason, reserving the accent fill for the resolve bar.
Command: /impeccable shape

### [P2] Opening a row loses the question; the two-line clamp loses the deciding clause
An open row measures 723-791px in a 900px viewport, with the answer field ~380px below the question, so the question is off-screen while being answered. A realistic 190-character question clamps to 51px of its 154px natural height.
Fix: repeat the question as a serif heading at the top of the expansion, or make the summary sticky within its open row; consider three lines for the clamp.
Command: /impeccable polish

## Persona Red Flags

Alex (BA, power user): thrown 656px on every row after the first, eleven times on a twelve-question requirement; nine controls to tab past between questions; severity at a different x-offset on every row so no column can be scanned; no expand-all, no multi-select.

Sam (screen reader / keyboard): row boundary 1.27-1.40:1 in both themes; four identical h4 "Suggested answers, from the evidence" headings make a rotor useless once more than one row is open; outline-color is in the summary's transition-colors list, so the focus ring fades in from --ink. Good: closed rows inert, two named landmarks, heading outline with no skips, aria-describedby on the gated confirm.

Priya (non-agile business owner, from PRODUCT.md): lands on /confirm where her one job sits 1400px down under a heading reading "What is still open"; sees a bright indigo Confirm button that looks live and does nothing; first asked to choose between Accept as written / Save my wording / Reject with no stated default; "Blocks confirmation" is a bare checkbox with no explanation of what confirmation is; answers four questions and nothing on screen looks more finished.

## Minor Observations

- ConfirmDialog's confirm button is #c4260e; --danger is #b3231d. A hardcoded hex in a component, and two dangers in one product.
- "What is settled — 3 recorded" counts only facts + rules + constraints but heads a section that also contains the outcome and prior answers.
- Verified fixed since the last critique: heading outline (h1-h2-h3-h4, no skips), progress bar animating scaleX, column heading rhythm 32px above / 20px below, picked-suggestion treatment (border-accent + bg-accent-wash + check glyph + inline rationale), classification out of the nested disclosure, exclusive-accordion toggling, zero horizontal overflow at 390px, all 82 animated elements carrying a motion-reduce guard.
- Two contrast failures at 4.43:1 — "Save my wording" and "Add this question", both in their disabled state (--ink-faint on --surface-sunken, which tokens.css itself calls the system's one forbidden pair). WCAG exempts inactive controls; the design system does not.
- The settled column's items carry no sources control in this seed because the fake provider emits no evidence references; the contract's first-viewport promise of "each with its sources control" is unverified rather than discharged.
- Assessment B discarded three of its own contrast readings as stale-recalc artifacts and re-measured; its final numbers are post-correction.
- False-positive class worth recording: the in-browser overlay reports text-occlusion on content inside closed details elements, 20 times on this screen. It does not treat closed-details content as non-rendered.

## Questions to Consider

1. If answering never moves anything across, why are there two columns? The left column is 424px of text that does not change for the entire session.
2. What is the exclusive accordion buying? It costs 656px per open, prevents comparing two questions, and the page height it saves was already solved by collapsing.
3. Why is the pending intent proposal a 400px card when every other open item is a 68px row?
4. What would a confident /confirm look like — not the same page with a box further down?
5. If a business owner answers four questions and nothing on screen looks more finished, what did the product show them?
