---
target: Knowledge step (/knowledge), Phase 5 verification
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\requirement\\KnowledgeView.tsx"
target_fingerprint: "sha256:d1e7772ef2b1c496d603da9e706cd8317671630dce744f7e0d87d92ee453eb7f"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\requirement\\KnowledgeView.tsx"
timestamp: 2026-09-26T10-57-24Z
slug: frontend-src-app-requirement-knowledgeview-tsx
---
Method: dual-agent verification (A: design review · B: detector + browser evidence), after the Phase 5 build. Same seed as the baseline; also as a non-owner reviewer.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Verdict heading and counts; shell NEXT still says Analyse |
| 2 | Match System / Real World | 2 | Related side names the other requirement by short ID (no title in the payload); API rationale is system language |
| 3 | User Control and Freedom | 3 | Choice + confirm dialog naming both, Cancel focused |
| 4 | Consistency and Standards | 3 | Badges, serif quotes, mapped fields |
| 5 | Error Prevention | 3 | Explicit choice, gated buttons with reasons |
| 6 | Recognition Rather Than Recall | 2 | Evidence often one side only (fixed after this run: own business need shown for comparison) |
| 7 | Flexibility and Efficiency | 2 | Links leave the screen; no jump between findings |
| 8 | Aesthetic and Minimalist Design | 3 | One status per card; provenance at the foot |
| 9 | Error Recovery | 2 | Non-member saw a 403 from the index notice (fixed after this run) |
| 10 | Help and Documentation | 3 | Says who must accept and what closing does |
| **Total** | | **26/40** | **Acceptable** (baseline 14) |

## Verification
Detector CLI clean on all 7 files. Overlay: nested card (resolution box in finding card) and a long format line — both fixed after the run; side-tab on the warning card is the sanctioned One Edge. Measured: no overflow, no text <12px in the workspace, no raw enums, no heading skips, every aria-disabled control has a tab stop and a description, one filled accent per page.

## Fixed after this run
Radio choice no longer moves focus (WCAG 3.2.2); non-member reviewer no longer sees the index 403; "Waiting for an owner's decision" neutral for people who cannot act; own business need set beside a one-sided match; nested card removed.

## Remaining
Linked title and both sides of a contradiction need the API; shell NEXT on Knowledge (journey.ts, ux-plan §6).
