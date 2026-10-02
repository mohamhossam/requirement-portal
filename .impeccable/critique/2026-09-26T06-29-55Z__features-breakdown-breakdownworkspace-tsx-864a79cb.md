---
target: Backlog step (/breakdown/*), Phase 4 baseline
total_score: 21
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\breakdown\\BreakdownWorkspace.tsx"
target_fingerprint: "sha256:39422a9026e4ee5a3304da0e7c3d8efad6b64ce31efdf70fa7e4498a53dfa217"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\breakdown\\BreakdownWorkspace.tsx"
timestamp: 2026-09-26T06-29-55Z
slug: features-breakdown-breakdownworkspace-tsx-864a79cb
---
Method: dual-agent (A: design review · B: detector + browser evidence). Live seeded Backlog: approved Epic, approved Feature with an edited Story, a Feature edited after approval with out-of-date Stories, quality unassessed. 1440 light/dark on all four routes; Feature and Story at 390.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 2 | Feature 2 reads a muted "Edited"; no approver/date anywhere |
| 2 | Match System / Real World | 2 | Portfolio outcome, Later drop, Needs reconciliation, Squad, uppercase ARCHITECTURE IMPACT |
| 3 | User Control and Freedom | 2 | One-click Approve, no recap; focus lost on Edit/Cancel |
| 4 | Consistency and Standards | 2 | Three names for staleness; two meanings of Continue reviewing; mixed gating |
| 5 | Error Prevention | 3 | Regeneration confirms; Approve silent about stale children |
| 6 | Recognition Rather Than Recall | 2 | Rail Feature rows truncate with no title |
| 7 | Flexibility and Efficiency | 2 | No next-Feature from the last Story |
| 8 | Aesthetic and Minimalist Design | 3 | Restrained; architecture panel on legacy CSS |
| 9 | Error Recovery | 2 | Staleness notice names no remedy |
| 10 | Help and Documentation | 1 | Nothing explains what Approve binds |
| **Total** | | **21/40** | **Acceptable** |

## Design Specificity Verdict
Frame is the product's (ux-plan Phase 4 frame goals already met); content model is the category's. current_approval/approval_history loaded for every item and never shown. Fixed since 2026-09-20: off-ladder tokens, StalenessNotice, viewing marker, empty-state copy, breadcrumb name, mono timestamp, accent sites 9 to 5, Story pager. Detector: CLI clean (11 targets); runtime false positives only (sanctioned NEXT edge, overlay glow, exempt disabled button). Browser-only findings: Story route overflow at 390 (StoryCard.tsx:117 shrink-0), disabled Previous link 3.35:1 and keyboard-reachable, current rail step off-screen at 390.

## Priority Issues
- [P1] Approval invisible as a human act: show Approved by + date, lapsed-on-edit wording, recap before approving, Story explains approval lives on Review & approve.
- [P1] "What needs me?" unanswerable from Epic/rail: verdict per row, counts line, target-named link, rail glyph + title. Stale Story roll-up needs data fetching: raise.
- [P1] Focus lost on inline Edit/Cancel; native disabled defeats blockedReason on Approve, Regenerate all, merge.
- [P1] Story route accent on leaving; overflow at 390.
- [P2] Staleness three names, no remedy; wrong quality copy when never assessed.
- [P2] Architecture hidden; ArchitectureImpactPanel legacy CSS, 11px uppercase labels, toLocaleString, jargon; Map architecture outside the card.

## Persona Red Flags
PO: muted Edited; Approve above evidence on Feature 2; no signature; pushed to /review mid-work. Sam: focus loss; gated controls leave tab order; merge checkbox 2.5.3; no Story list heading; breadcrumb ends "Story". Business owner: jargon list. Architect: systems hidden behind two disclosures.

## Minor Observations
Eyebrow in StoryProposalPanel and breakdown-locked; breadcrumb links 15px; NEXT copy redundant on Backlog; rail current step off-screen at 390; dead focused=false branches; buttons 39px vs 36px.

## Questions to Consider
Why is the signature never shown? Should the single accent go to the next item needing approval across Features? Is Edited provenance or verdict?
