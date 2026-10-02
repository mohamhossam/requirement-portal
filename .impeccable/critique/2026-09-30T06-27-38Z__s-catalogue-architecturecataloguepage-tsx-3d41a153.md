---
target: architecture catalogue journey
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\catalogue\\ArchitectureCataloguePage.tsx"
target_fingerprint: "sha256:992c2c6fe38811f185ca07d9527a58c3c9100806051b40a5da9d75c2e69a485e"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\catalogue\\ArchitectureCataloguePage.tsx"
timestamp: 2026-09-30T06-27-38Z
slug: s-catalogue-architecturecataloguepage-tsx-3d41a153
---
Method: dual-agent (A: design review · B: detector + browser evidence)

# Critique #2: Architecture catalogue journey (after the fix pass)

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Desk always shows in use / in progress / NEXT; "reviewed" state lost on reload (component state). |
| 2 | Match System / Real World | 3 | Mostly business language; "revision 2", "fake-owner", "packaged-seed", "evidence index", matrix hint remain. |
| 3 | User Control and Freedom | 3 | Deep links and Back verified; "Back to systems" drops focus to body. |
| 4 | Consistency and Standards | 2 | draft vs version in progress; Relationship vs Dependency; "8 removed" vs the strip's story line. |
| 5 | Error Prevention | 2 | Build and publish possible with Review undone, no warning. |
| 6 | Recognition Rather Than Recall | 3 | Dossier and readout good; vertical matrix names truncate; Publish shows counts only. |
| 7 | Flexibility and Efficiency | 3 | Roving list, URL state, Back verified; no matrix arrow keys or add-dependency. |
| 8 | Aesthetic and Minimalist Design | 2 | 245px chrome; Edit manually 2,922px; red "Removed" badge repeated 8 times. |
| 9 | Error Recovery | 3 | Job errors explained with retry. |
| 10 | Help and Documentation | 2 | Inline hints only; "evidence index" unexplained. |
| **Total** | | **26/40** | **Acceptable** |

## Design Specificity Verdict
Specific inside (change strip, ± matrix, stage-rail desk + NEXT, dossier opening on a changed system), generic around it (245px frame). CLI detector: [] on 19 files (also with --no-config). Browser detector (7 views, headless): line length ~115 on Publish/Build meta (DraftJourney.tsx:173,256,271); column overflow 204–218% on list/detail grids. False positives: side-tab/nested-cards on sanctioned 3px edges, table thead, DiffList lists, Table frame padding, repeated system names, shared PageHeader. Measurements: 0px overflow everywhere; only sub-24px target is a checkbox inside a 299x26 label; duplicate "Add documents" name from the pre-existing sr-only file input. Both agents confirm step-open focus does not land in the step.

## Priority Issues
- [P0] Focus lost on step open/close: rAF focus runs before the step renders; the pressed button unmounts; focus falls to body. Fix: focus in an effect after render; on close focus the view heading. /impeccable harden
- [P1] Edit manually is a 2,922px scroll. Fix: workbench grammar (index + editable dossier with dependency add rows). /impeccable layout
- [P1] NEXT is weak and contradicts Publish; reviewed state not persisted (logic: raise). Fix: NEXT at desk top as the one filled button, drop the strip duplicate, warn inside out-of-order steps. /impeccable clarify
- [P2] Frame costs the first viewport; matrix buried under a readout box. Fix: h1 on the tabs row, shorter description, sticky readout beside the matrix. /impeccable layout, /impeccable distill
- [P2] Vocabulary drift (draft, Relationship, "8 removed", revision N). Fix: one label map, change story in Review and Publish, "last changed <time>". /impeccable clarify

## Persona Red Flags
Alex: 22 matrix tab stops for 11 dependencies, no grid keys, no matrix editing, NEXT nags after reload. Sam: P0 focus loss; stepper Enter doesn't move focus; tab order jumps from y264 to y201; removed CWOM row not focusable. Jordan: matrix jargon; "evidence index" and "revision" unexplained; removed system can't be opened.

## Minor Observations
History leaves both version toggles unpressed; desk h2s equal weight; "Dependencies (0, 1 removed)" awkward; "New" suggestion badge uses the accent; "Add documents" primary vs NEXT; matrix below the fold at 390px.

## Questions to Consider
- Should landing be the matrix, with the dossier as its readout?
- Does Review earn a step when its completion isn't saved?
- Why does the version in use get equal desk space on every view?
