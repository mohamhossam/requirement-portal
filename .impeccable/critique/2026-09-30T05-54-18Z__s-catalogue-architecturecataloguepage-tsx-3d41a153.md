---
target: architecture catalogue journey
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\catalogue\\ArchitectureCataloguePage.tsx"
target_fingerprint: "sha256:e0651874f10cff1011a02f885a31794d346d6e3a8e3c49a068a7e316deea9106"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\catalogue\\ArchitectureCataloguePage.tsx"
timestamp: 2026-09-30T05-54-18Z
slug: s-catalogue-architecturecataloguepage-tsx-3d41a153
---
Method: dual-agent (A: design review · B: detector + browser evidence)

# Critique: Architecture catalogue journey

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Desk names live version and next step; opening a step gives no focus move or scroll (step heading off-screen at 390px, y≈1137). |
| 2 | Match System / Real World | 2 | "evidence index", "revision 2", "packaged-seed", "Matched by:", truncated IDs, removed system as raw "cwom". |
| 3 | User Control and Freedom | 2 | Opening Step 3 starts an index build; Accept all and single removals have no confirm or undo. |
| 4 | Consistency and Standards | 2 | "Changed" badge uses the indigo accent; History keeps "In progress" pressed; remove version in two places; mixed view heading sizes. |
| 5 | Error Prevention | 3 | Publish well guarded; bulk accept and removals unguarded. |
| 6 | Recognition Rather Than Recall | 3 | Rail + NEXT help; the change itself is scattered across list tail, matrix and Step 2. |
| 7 | Flexibility and Efficiency | 2 | No deep links, Back leaves page; 30 tab stops in the list; no "changed only" filter. |
| 8 | Aesthetic and Minimalist Design | 2 | ~385px chrome before content at 1440x900; version name 3x in first viewport; explanatory text everywhere. |
| 9 | Error Recovery | 3 | Clear errors with retry; build error announced twice. |
| 10 | Help and Documentation | 2 | One line of matrix help; "evidence index" never explained in business terms. |
| **Total** | | **24/40** | **Acceptable** |

## Design Specificity Verdict
Parts authored (matrix, stage-rail desk + NEXT, evidence-first suggestions); first viewport generic and lands on ADFS, a zero-dependency record chosen alphabetically. CLI detector 0 findings / 19 files. Browser detector (headless, 6 views): side-tab + nested-cards on NEXT block (DraftJourney.tsx:385, one element; nested card real), skipped heading h2→h4 (DiffList.tsx:18), line length ~115 (DraftJourney.tsx:256), column overflow on list/detail grids (expected). False positives: nested-cards on table thead and DiffList lists, cramped-padding on shared Table wrapper, line-length on shared PageHeader. Measurements: 0px horizontal overflow at 1440/1000/390; only target under 24px is the matrix checkbox (20x20) inside a 299x26 label; no duplicate button names on landing.

## What's Working
1. Dependency matrix: crosshair, marks with words, fixed readout, sentence labels for screen readers.
2. Change desk: live version always named, amber outdated-mapping warning, NEXT in the person's verbs, folds to one line below 1050px.
3. Publish/remove safeguards and evidence-first suggestions.

## Priority Issues
- [P1] Change story scattered and out of scale: "8 removed" flat list, six indigo "Changed" badges, CWOM at list tail, raw ID "cwom", matrix count ignores removed links. Fix: change strip with jump links, pin changed systems or "Changed (n)" filter, group follow-on diffs, resolve removed names from version in use, neutral "Changed" badge. Command: /impeccable clarify then /impeccable layout.
- [P1] Focus order and feedback: desk before workbench in DOM (tab stops 14–20 before switches 21–25); opening a step or selecting a system at 390 moves no focus and no scroll; matrix focus rings clipped by sticky row headers (2.4.11). Fix: workbench first in DOM with grid areas, focus + scroll step heading, scroll to dossier below md, scroll-margin for marks. Command: /impeccable harden.
- [P1] Opening Step 3 auto-starts an index build (hook at DraftJourney.tsx:167-171), even before review. Logic change: raise to the user. Fix: explicit Build trigger only; Publish keeps build-then-publish. Command: /impeccable harden (needs approval).
- [P2] First viewport spent on chrome: content at y≈385, matrix grid at y≈620; description repeats the desk; switches always stack; 390 pill wraps. Fix: one-line description, switches on one row, drop duplicate names, fold legend, open on first changed or most-connected system. Command: /impeccable distill then /impeccable layout.
- [P2] Bulk AI acceptance and unguarded removals: primary "Accept all" with no confirm or undo; instant document/dependency removal; five same-named Remove buttons. Fix: secondary with count confirm, undo toast, specific aria-labels. Command: /impeccable harden.

## Persona Red Flags
Alex: no deep links; 30 tab stops in list; no matrix arrow keys; download format far from Download; Edit manually 2976px wall. Sam: desk before workbench; silent step opening; clipped matrix focus ring; duplicate Remove names; double error announcement. Jordan: empty ADFS landing; matrix literacy assumed; unexplained terms; Step 1 checked though nothing added (logic, raised).

## Minor Observations
History actions unaligned, Published wraps 3 lines, row actions off-canvas at 390; step rail wraps at 1000 with stranded numbers; Review step lacks a forward action and NEXT repeats the open step; eVEDA diff badge wraps; "From documents" vs "Build from documents"; two-line vision-model explanation in the drop area; CNS shows "Dependencies (0)" under a removed dependency; publish success is a one-line notice.

## Questions to Consider
- When a version is in progress, should landing be what it changes?
- Is the matrix the hero, or the per-system neighbour diagram?
- Should the evidence index be a status line on Publish instead of a step?
