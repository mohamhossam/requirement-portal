---
target: Intake (/requirements/new), Phase 6 verification
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\NewRequirementPage.tsx"
target_fingerprint: "sha256:b5dc6e08a83388d665f2b0534c3a584aca82ea6226a5bc73818a9e093606411f"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\app\\NewRequirementPage.tsx"
timestamp: 2026-09-26T11-36-44Z
slug: frontend-src-app-newrequirementpage-tsx
---
Method: dual-agent verification (A: design review · B: detector + browser evidence), after the Phase 6 build. Same seed as the baseline; 1440×900, 768×600, 390×844, Paper and Slate; real Tab walks.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Readiness beside the button; a blocked click gives no visible response |
| 2 | Match System / Real World | 3 | Plain labels; the API's extraction message remains |
| 3 | User Control and Freedom | 3 | Help link dropped the draft (fixed after this run) |
| 4 | Consistency and Standards | 3 | Primitives throughout; tab title differed from h1 (fixed) |
| 5 | Error Prevention | 3 | Pressable primary, accent only when ready |
| 6 | Recognition Rather Than Recall | 3 | Example beside the form; below lg folded without a frame (fixed) |
| 7 | Flexibility and Efficiency | 3 | Type or attach; optional detail folded, opens when filled |
| 8 | Aesthetic and Minimalist Design | 3 | Calm, on-token; save status said three ways |
| 9 | Error Recovery | 3 | Summary takes focus, links to fields |
| 10 | Help and Documentation | 3 | Complete example with what happens next |
| **Total** | | **30/40** | **Good** (baseline 18) |

## Verification
Detector CLI clean on all three files; overlay: four line-length flags on hints at the 80ch interface measure. No overflow, no text <12px, no uppercase, no numbering; no focused element under the bar or header on any walk; empty submit moves focus to the summary with inline field errors.

## Fixed after this run
Help link keeps the open draft; #example opens the inline example below lg; inline example framed; described-by deduplicated in Button; only save failures announced; sticky example scrolls within itself on short screens; tab title "New requirement".

## Remaining
URL does not follow the draft (page logic); Enter in a field submits "Save draft and exit" (first submit button); drawer edit form's actions not pinned.
