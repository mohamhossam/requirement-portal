---
target: Knowledge step (/knowledge), Phase 5 baseline
total_score: 14
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\requirement\\KnowledgeView.tsx"
target_fingerprint: "sha256:8839059956c0d2b0c9b49710f371d08166a74bde7f4909eb3e7e64ebeeb41670"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\requirement\\KnowledgeView.tsx"
timestamp: 2026-09-26T10-28-22Z
slug: frontend-src-app-requirement-knowledgeview-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence). Live seeded Knowledge: 42a131e6 with an open contradiction and an open duplicate (subject side); dd2874eb with a resolution-pending contradiction. 1440 light/dark, 390.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 2 | Panel says "Owner decision required", NEXT says "Analyse", no "0 of 2 decided" |
| 2 | Match System / Real World | 1 | Linked requirement shown as an 8-char hash; "trusted requirement knowledge", "precedence statement"; raw field and status enums |
| 3 | User Control and Freedom | 1 | Close as duplicate is one click, no confirmation, no consequence |
| 4 | Consistency and Standards | 1 | Eyebrows, bare uppercase 10.9px badge with no CSS rule for action_required, h2 to h4, green for pending |
| 5 | Error Prevention | 1 | Destructive action enabled and filled; safe path disabled; shared textarea dropped silently on Close |
| 6 | Recognition Rather Than Recall | 1 | Must recall what 2715601d is; evidence not labelled by side |
| 7 | Flexibility and Efficiency | 2 | Every link leaves the screen; no count, no jump between findings |
| 8 | Aesthetic and Minimalist Design | 2 | Status said three times; provenance above findings |
| 9 | Error Recovery | 2 | Error at the panel foot; disabled buttons give no reason and leave tab order |
| 10 | Help and Documentation | 1 | Nothing says what each decision does or who must accept |
| **Total** | | **14/40** | **Poor** |

## Design Specificity Verdict
A data-record dump, not The Working Paper. Detector CLI clean on all files (styling lives in legacy CSS). Browser: side-tab on .journey-panel-heading, undersized .workflow-badge 10.88px; text-occlusion on closed provenance details = false positive. Measured: h2 to h4 skip; native-disabled Mark distinct / Propose leave tab order with no description; eyebrow 11.52px tracked uppercase; legacy CSS in 01-foundation, 05-intake-stages, 10-portfolio-reports with off-token radii and sizes.

## Priority Issues
- [P0] Close as duplicate unguarded: one click, filled red, safe path disabled, typed rationale silently dropped. Fix: explicit choice (same need / different needs), confirmation naming both requirements and the consequence.
- [P1] A finding cannot be read as a comparison: hash IDs, quotes unlabelled by side, sans-serif, raw field names. Fix: title from the evidence, "This requirement" vs linked title, serif quotes, field labels, kind in an h3.
- [P1] Status vocabulary breaks DESIGN.md: eyebrows, sub-12px uppercase badge, colour+words only. Fix: Badge with a verdict map; say status once; count decided.
- [P2] Pending resolution shown in Approved Green; proposer hidden in collapsed history. Fix: neutral/amber, "Proposed by X · needs Y".
- [P2] Reference notices are unstyled bare sections competing with the panel h2; gated buttons silent. Fix: warning notices; blockedReason.

## Persona Red Flags
BA: cannot compare sides; links leave; no count. Keyboard/SR: disabled buttons skipped and unexplained; heading skip; error far from cause. Business owner: "trusted requirement knowledge", "embedding model", "passages prepared", raw enums.

## Minor Observations
"0 current owner approval(s)"; native details triangle; provenance outranks findings; linked-requirement link ink-coloured; "Open evidence" 15px tall.

## Questions to Consider
Is Knowledge a step or a verdict on Clarify/Confirm? Does the person closing a duplicate know which requirement survives?
