---
target: Review & approve screen (/review)
total_score: 20
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\review\\BreakdownReviewPanel.tsx"
target_fingerprint: "sha256:df845cbb13718025a6b8eadb55ed352f0f31b77efc213df66e84ca6dd34b4d8c"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\review\\BreakdownReviewPanel.tsx"
timestamp: 2026-09-26T06-01-25Z
slug: features-review-breakdownreviewpanel-tsx-a6d8d684
---
Method: dual-agent (A: design review · B: detector + browser evidence). Live page at 1440 and 390, Paper and Slate; blocking state judged from source (fake model emits none).

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 2 | "Blocks approval 0" above the fold while approval is gated; real reason ~2400px down |
| 2 | Match System / Real World | 2 | INVEST, ruleset in mono, "current attributed approval", log-line concern prose |
| 3 | User Control and Freedom | 2 | One-click Story Approve beside dialog-guarded Reject |
| 4 | Consistency and Standards | 3 | Evidence prose sans vs serif elsewhere; textareas narrower than inputs |
| 5 | Error Prevention | 2 | Story approval without quality in view; final-approval dialog recaps nothing |
| 6 | Recognition Rather Than Recall | 1 | Anonymous quality cards; History "Feature approved" unnamed; gate lists nothing |
| 7 | Flexibility and Efficiency | 1 | 3755px column, no section index; Features not approvable here |
| 8 | Aesthetic and Minimalist Design | 3 | Calm; repeated "spans 2 systems"; two always-open empty forms |
| 9 | Error Recovery | 2 | resolve/answer/record errors render under the strip, far from cause |
| 10 | Help and Documentation | 2 | No explanation of Resolve-with-decision vs Record-a-decision |
| **Total** | | **20/40** | **Acceptable** |

## Design Specificity Verdict
Authored in the details (consequence-named severity, separate risk scale, Inferred/In the catalogue, lifecycle without accent, accent never on a gated button). Skeleton is still a generic review page; not shaped around "can I approve?". Concerns, quality and Story decisions describe the same Stories in three disconnected places.
Detector: CLI clean. Runtime: line-length x3 (strip meta ~123ch, two descriptions ~98ch vs 80ch), side-tab x4 on StoryQualityPanel success cards (edge is sanctioned by DESIGN.md; green-on-unapproved is the real issue), low-contrast x6 on disabled buttons (false positive, WCAG exempt). 390: cards 364px in a 358px column (select intrinsic width).

## Priority Issues
- [P1] First viewport misstates approvability ("Blocks approval 0"; gate ~500px above buttons, ~2400px down). Fix: relabel counts as concerns, jump link, gate reasons beside buttons. Lifting approval status into the strip needs a data-fetching change: raise.
- [P1] Lapsed approvals shown as current; History unnamed and contradicts completion. Fix: name target from artifacts, mark "No longer current", gate lists missing items + link to Backlog for Features.
- [P1] Story quality anonymous and disconnected from Story decisions. Fix: pass quality_assessments as a prop, per-row quality badge, optional title on StoryQualityPanel, plain disclosure copy.
- [P1] Focus lost on inline form open/cancel (2.4.3). Fix: focus first field; restore to trigger.
- [P2] Errors far from cause; identical accessible names; dialog "Confirm" and no recap; 390 overflow. Fix: per-form errors, aria-describedby per row, act-named confirm, recap line, min-w-0.

## Persona Red Flags
PO: first viewport implies yes; approves without quality; History contradicts completion; rail NEXT points back. Sam: focus drop; 8 unnamed Approve/Reject; 4 identical regions; no completion announcement. Alex: no section index; Features elsewhere; no Story links. Business owner: INVEST, SPIDR, ruleset mono, "current attributed approval".

## Minor Observations
Neutral badge vanishes on sunken strip; textarea measure; evidence prose in sans; risks repeat concerns; mt-5 in gap-4; open empty Decision form; 4-5 accent uses (1 on-screen owned: active pill); amber slabs in Slate.

## Questions to Consider
Lift one read-only query for the strip? Features rows on this screen? Emphasis follow what gates approval?
