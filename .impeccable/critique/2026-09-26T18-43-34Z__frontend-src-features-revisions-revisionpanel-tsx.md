---
target: Phase 9 History (re-critique)
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:/home/user/smb-ai-requirement-agent/frontend/src/features/revisions/RevisionPanel.tsx"
target_fingerprint: "sha256:7ff36c6def769372c3cfbb2f8d986054ee5637ef95652cd5371a840899f6c547"
target_path: /home/user/smb-ai-requirement-agent/frontend/src/features/revisions/RevisionPanel.tsx
timestamp: 2026-09-26T18-43-34Z
slug: frontend-src-features-revisions-revisionpanel-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence). Re-critique after the Phase 9 build (96c7ed8), blind to the first run.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Download states and out-of-date flag work; comparison result lands below the fold |
| 2 | Match System / Real World | 2 | API sentences verbatim; IDs not names; "Analysis" as a status |
| 3 | User Control and Freedom | 3 | Swap and fold work; no way back to the row after a row compare |
| 4 | Consistency and Standards | 3 | Primitives throughout; aria-pressed pills where Knowledge uses radios; empty states off EmptyState |
| 5 | Error Prevention | 2 | Download of a pre-edit approval with only a bullet; review CTA with no backlog |
| 6 | Recognition Rather Than Recall | 2 | Identical rows; no need-version diff; approval's basis need version not shown |
| 7 | Flexibility and Efficiency | 2 | Duplicate quick pairs; row compare hidden below lg |
| 8 | Aesthetic and Minimalist Design | 3 | Calm; repeated Backlog column; accent noise |
| 9 | Error Recovery | 2 | Terse compare/export errors |
| 10 | Help and Documentation | 2 | Format hints don't name the destination |
| **Total** | | **24/40** | **Acceptable** |

## Design Specificity Verdict

Specific at the top (approved export with drift stated and "exactly as it was approved"), generic below (versions table of identical rows, undiffed need versions, API sentences). CLI 0 findings on all three files. Browser: side-tab on the success Card edge (One Edge Rule), nested-cards/cramped-padding on table frames (false positives), line-length on the approval sentence (~114) and change list (~111), em-dash overuse partly from shell. Real: compare result h3 focused with outline none; whole result inside aria-live plus focus → double announcement; success badge invisible on the success card. Contrast ≥5.08 everywhere; no overflow at 1440/1000/390; focus never lost to body.

## Priority Issues

- [P1] Approval validity buried in a success card; basis need version not shown. /impeccable clarify
- [P1] "What changed" ignores what the client has: no need-version diff; Backlog column repeats; IDs not names (names need API). /impeccable clarify
- [P2] Result lands off-screen; row compare gone below lg; duplicate quick pairs. /impeccable adapt
- [P2] One Accent broken: filled JSON pill above the primary; up to 18 indigo row links. /impeccable quieter
- [P2] Empty/edge states: review CTA without backlog, empty-list hairline, pending review unnamed, no fold gap marker. /impeccable harden

## Persona Red Flags

Alex: no shareable pair; N clicks to find the edit; row compare gone at 1000. Sam: double announcement; invisible focus on result; pills not radios; duplicate names. PO: no ADO guidance; UUID filename (API client); drift doesn't interrupt download; no Activity link.

## Minor Observations

Rail shows Clarify on History; restriction line names no one; middot in prose; 12px h4; blocked Compare misaligned; reversed comparisons unflagged; fold count 6; history refetch error routed to compare slot; terse errors.

## Questions to Consider

- Should a drifted approval still be the green hero?
- Timeline of events rather than a table of versions?
- Should the export choice name the destination rather than the format?
