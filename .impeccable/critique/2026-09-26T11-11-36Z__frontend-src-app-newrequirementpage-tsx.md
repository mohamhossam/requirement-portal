---
target: Intake (/requirements/new), Phase 6 baseline
total_score: 18
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\NewRequirementPage.tsx"
target_fingerprint: "sha256:558dde96587343767cd3df3d030e1bfa317842b176e886771a5d12a75af1687a"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\NewRequirementPage.tsx"
timestamp: 2026-09-26T11-11-36Z
slug: frontend-src-app-newrequirementpage-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence). Live seeded intake: blank /requirements/new, a fully filled draft, a title-only draft with one readable and one corrupt attachment, and the same form in the Source drawer's edit mode. 1440 light/dark, 390.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 2 | "Preparing draft…" before any draft; readiness card below the button it explains |
| 2 | Match System / Real World | 2 | "Draft New Requirement", "Record boundaries", "eligibility", "Missing: attachment review" |
| 3 | User Control and Freedom | 3 | Resumable drafts; URL does not follow the draft (logic) |
| 4 | Consistency and Standards | 1 | Eyebrows, 01/02/03 twice, indigo edge meaning "not ready", raw inputs, h1 to h3 |
| 5 | Error Prevention | 2 | Primary disabled, not explained |
| 6 | Recognition Rather Than Recall | 1 | Examples live in placeholders; worked example 1,500px below the field |
| 7 | Flexibility and Efficiency | 2 | Optional sections always expanded |
| 8 | Aesthetic and Minimalist Design | 2 | 52rem column leaves 40% empty while guidance is pushed below |
| 9 | Error Recovery | 1 | Validation summary unreachable in create mode (primary disabled) |
| 10 | Help and Documentation | 2 | Three different step models on one page |
| **Total** | | **18/40** | **Poor** |

## Design Specificity Verdict
A legacy slice-5C form in the new tokens. Detector CLI clean; overlay: line-length on the intro, two kickers, h1 to h3 skip. Measured: 11.52px section numbers and eyebrows; legend numbers filled accent (3 fills with the primary disabled); eligibility card's success border overridden by accent; sticky bar 83px (180px at 390) with no scroll-padding-bottom.

## Priority Issues
- [P0] Focused fields fully hidden behind the sticky action bar (2.4.11): Desired outcome at 1440, Channels / Known systems / Attach files at 390.
- [P1] Readiness in the wrong place and the wrong colour; primary disabled so the reason is never reached and the validation summary is dead.
- [P1] The worked example does not help while typing; examples in vanishing placeholders.
- [P2] Eyebrows, 01/02/03, title case, jargon, raw inputs, off-token CSS; eight fields that look required.
- [P3] Save state: "Preparing draft…" when nothing exists; "Changes not saved" flash; time without date.

## Persona Red Flags
Business owner: method words, no example beside the field, unexplained grey button. Keyboard/SR: focus hidden, disabled primary skipped, live card announces on every keystroke, "01" read aloud. BA: no compact mode; same form in the drawer carries the badges and a card in a card.

## Minor Observations
Decorative lightbulb and arrow; guidance written for the reviewer; hints 12.16px; channels/systems grid two columns at 390.

## Questions to Consider
Should the analysis propose the optional fields back instead of asking the owner to pre-classify? Does the owner need to see save mechanics at all?
