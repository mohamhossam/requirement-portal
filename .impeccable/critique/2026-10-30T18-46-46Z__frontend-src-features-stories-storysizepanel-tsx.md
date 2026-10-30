---
target: story-point UI after list-level sizing round
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:C:\\ai\\projects\\requirement-portal\\frontend\\src\\features\\stories\\StorySizePanel.tsx"
target_fingerprint: "sha256:b279731562ff4cdb8009d7ade8101f63d579e14a227ec6a6b604be2f56c23b30"
target_path: "C:\\ai\\projects\\requirement-portal\\frontend\\src\\features\\stories\\StorySizePanel.tsx"
timestamp: 2026-10-30T18-46-46Z
slug: frontend-src-features-stories-storysizepanel-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence)

Target: story-point estimates UI after the second fix round (list-level sizing via StorySizeCell, siblings in the size panel, focus, provenance, quieter out-of-date notice). Mode: Operate.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Accepting on a list row is never announced; a failure there shows nothing |
| 2 | Match System / Real World | 2 | "Points" and the scale gaps unexplained on the list and Review; "Edited" after sizing |
| 3 | User Control and Freedom | 3 | Re-sizing an approved Story costs a fresh approval each time |
| 4 | Consistency and Standards | 3 | Who decided worded three ways (named on card, "Set by a person" on Review, nothing on the row) |
| 5 | Error Prevention | 3 | Nothing says to size before approving |
| 6 | Recognition Rather Than Recall | 2 | Rationale disappears when choosing another size; dropdown hides the scale |
| 7 | Flexibility and Efficiency | 2 | No accept-all; a non-AI size still needs the Story page |
| 8 | Aesthetic and Minimalist Design | 3 | Row "Why?" outweighs Accept and pushes it to a new line when open |
| 9 | Error Recovery | 2 | A failed row accept surfaces only in the hidden Story card |
| 10 | Help and Documentation | 3 | Explanation lives only on the Story page, not where most sizing now happens |
| **Total** | | **26/40** | **Acceptable** |

## Design Specificity Verdict

Mostly specific: business-question heading, provenance register for AI, neutral badge, honest totals. Defaults remain in the stock 7-option select and the unsorted comparison list. Detector: 0 CLI findings across 8 files; overlay flagged only pre-existing code (documented 3px edges, nested quality card, collapsed content) plus the repeated timestamp (seed artefact; the size row adds one occurrence).

## What's Working

1. Provenance and truth: unsized is never zero, a suggestion is never a size, overridden suggestion is a footnote, Review shows the basis.
2. Story-page accessibility: focus into the picker and back, status announcement, gated controls keep their tab stop, row accept label names the Story.
3. Confirm tone fits: primary, not danger, focus still on Cancel.

## Priority Issues

1. [P1] Accepting on a list row loses focus, is not announced, and fails silently (error only reaches the hidden card). Fix: error prop + inline ErrorNotice on the cell; sr-only status "Size set to N points for <gist>"; focus the new badge or row link. Command: /impeccable harden.
2. [P2] The rationale disappears when you disagree with it. Fix: keep a one-line "AI suggested 5 points: <rationale>" above the picker; replace the select with a six-button radio group marking the AI's size. Command: /impeccable clarify.
3. [P2] "Edited" now means two things (sizing vs changed words). Kept by owner decision; at minimum say it at the moment of acceptance. Command: /impeccable clarify.
4. [P2] Nothing tells reviewers to size before approving; no batch accept. Fix: "size it before approving" wording on unsized unapproved rows; optional "Accept all N suggestions" with one confirmation; return link from the size section to Review. Command: /impeccable onboard then /impeccable distill.
5. [P3] Row hierarchy and glyph: bordered 36px "Why?" outweighs 32px Accept and wraps it; the 12px Weight glyph reads as a padlock. Fix: text-variant summary, rationale full-width below, try another glyph or none. Command: /impeccable polish.

## Persona Red Flags

- Alex: no bulk accept; 10 dialogs for 10 approved Stories; non-AI sizes need the Story page.
- Sam: focus lost after a row accept, no announcement, invisible failures; repetitive "Not sized yet — size it" link text on Review.
- Business owner: points unexplained on list and Review; "Edited" after sizing.

## Minor Observations

- Who-decided wording inconsistent across card, Review, row.
- Provenance disclosure names differ.
- Confirm dialog says "Change size" even when setting a first size or clearing.
- Size section sits below the fold; an unsized Story has no header signal.
- Comparison list unsorted, current Story not placed on it.
- 375px: no overflow; Slate: sunken block reads correctly.

## Questions to Consider

- Should the Feature list be a ladder where Stories are placed against each other, with the AI's placement as a ghost?
- Should sizing have its own provenance word, so "Edited" keeps meaning changed words?
- Does a business owner need to see points at all on rows they haven't sized?
