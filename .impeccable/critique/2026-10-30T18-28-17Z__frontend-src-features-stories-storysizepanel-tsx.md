---
target: story-point UI after harden/clarify/distill/polish
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\ai\\projects\\requirement-portal\\frontend\\src\\features\\stories\\StorySizePanel.tsx"
target_fingerprint: "sha256:ebaac44dcbe974e6791e837678e02d9b9404fed0f8c828e3f2bebc3ec1bfe720"
target_path: "C:\\ai\\projects\\requirement-portal\\frontend\\src\\features\\stories\\StorySizePanel.tsx"
timestamp: 2026-10-30T18-28-17Z
slug: frontend-src-features-stories-storysizepanel-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence)

Target: story-point estimates UI after the harden/clarify/distill/polish pass (StorySizePanel, SizeBadge, StoryCard, StoryList, ApprovalWorkflowPanel, PublicationPanel). Mode: Operate.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Pending AI suggestions invisible in the compact Story list |
| 2 | Match System / Real World | 3 | The 1/2/3/5/8/13 scale is never explained or anchored |
| 3 | User Control and Freedom | 3 | Choose/Change/Cancel drop focus to body; overridden AI keeps offering itself |
| 4 | Consistency and Standards | 3 | In-card controls use disabled, toolbar uses blockedBy; "Edited" after a size |
| 5 | Error Prevention | 3 | Approve-unsized-then-size trap; AI value saved as "Set by a person" |
| 6 | Recognition Rather Than Recall | 2 | "Compared with the others" with no others shown; rationale hidden while choosing |
| 7 | Flexibility and Efficiency | 2 | No sizing from the list, no batch accept |
| 8 | Aesthetic and Minimalist Design | 3 | Duplicate "Suggest sizes again"; two rows when a suggestion was overridden |
| 9 | Error Recovery | 3 | "Could not size — too large" offers no split |
| 10 | Help and Documentation | 3 | No anchors on the scale |
| **Total** | | **28/40** | **Good** |

## Design Specificity Verdict

Specific and inside the house idiom: question heading mirroring Quality, provenance register for AI (spark, sunken ground, serif rationale), neutral badge, accent untouched. The remaining gap is the interaction model: relative sizing asked one Story at a time with no siblings in view. Detector: 0 CLI findings; browser overlay found one new issue in changed code (line-length ~98ch on the size explanation, StorySizePanel.tsx:123), the rest pre-existing (NextAction / tone-card 3px edge = documented device; nested quality card; repeated timestamps partly seed artefact, one new copy in the size row).

## What's Working

1. Provenance and decision kept apart; unsized said in words; "1 of 2 sized".
2. Business-language copy: question heading, "not hours or days", "anything bigger should be split", confirm dialog explains the consequence.
3. Accept described by rationale, live "Size set to…", focus back on heading after save, 24px targets.

## Priority Issues

1. [P1] Relative sizing designed as an isolated per-Story decision — no siblings, no list-level sizing, no batch accept. Fix: size from the Feature's Story list (suggestion + Accept per row, rationale on demand), sibling reference in the panel. Command: /impeccable shape then /impeccable distill.
2. [P1] Opening "Choose/Change size" and Cancel drop focus to body (verified live). Fix: focus the Select on open, return focus on Cancel. Command: /impeccable harden.
3. [P2] An overridden AI suggestion keeps asking to be accepted. Fix: when a confirmed size differs, collapse the suggestion to a quiet "AI suggested 5 points" line with rationale disclosed, no Accept. Command: /impeccable clarify.
4. [P2] Provenance blurred: Edited badge after sizing; choosing the AI's pre-filled value records "Set by a person"; basis sr-only on Review. Fix: record accepted_suggestion when the chosen value equals the suggestion (or start the select at current/blank); show basis visibly on Review; decide "Edited" vs a size-only label (logic change). Command: /impeccable clarify.
5. [P2] Approve-then-size trap; amber out-of-date card even when every Story is sized; duplicate button. Fix: "Not sized yet" on Review links to the Story with a hint; warning card only when something is unsized, else a neutral line, and drop the toolbar duplicate while it shows. Command: /impeccable clarify then /impeccable quieter.

## Persona Red Flags

- Alex: no list sizing or batch accept; page round-trip per size; pending values hidden in the list.
- Sam: focus lost on Choose/Change/Cancel; in-card gated controls disabled (tab stop gone, description unreachable); in-card Suggest sizes disabled with no reason.
- Business owner: "points" unexplained outside the card; Fibonacci gaps unexplained; no comparison in view; "could not size" doesn't lead to a split.

## Minor Observations

- Number (14px sans) weaker than its rationale (16px serif).
- "a suggestion until someone accepts it" false in the could-not-size state.
- awaitingSave not reset on error.
- Confirm dialog uses the danger button for a non-destructive act.
- "Not sized yet" under "2 Stories" lacks a subject ("None sized yet").
- Size explanation line ~98ch (detector).

## Questions to Consider

- Should a Feature-level sizing table make the per-Story panel a read-only summary?
- Does a size need its own attestation lane rather than reopening content approval?
- When the AI says "too large", should the panel lead with "Split this Story"?
