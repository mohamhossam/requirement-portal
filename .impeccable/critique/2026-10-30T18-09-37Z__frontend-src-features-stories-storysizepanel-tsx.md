---
target: all story-point UI changes in this session
total_score: 25
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\ai\\projects\\requirement-portal\\frontend\\src\\features\\stories\\StorySizePanel.tsx"
target_fingerprint: "sha256:cc09bdb94e979a7ad81914120c7d5f475e64c3c44200c66c18f800d3c1bb6454"
target_path: "C:\\ai\\projects\\requirement-portal\\frontend\\src\\features\\stories\\StorySizePanel.tsx"
timestamp: 2026-10-30T18-09-37Z
slug: frontend-src-features-stories-storysizepanel-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence)

Target: the story-point estimates UI added in this session (ADR-0121): StorySizePanel.tsx, SizeBadge.tsx, storyPoints.ts, StoryCard.tsx, StoryList.tsx, ApprovalWorkflowPanel.tsx, PublicationPanel.tsx. Mode: Operate.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Accept's spinner shows on Save size; no success announcement |
| 2 | Match System / Real World | 2 | "Story points" never explained; four names for one concept |
| 3 | User Control and Freedom | 3 | Clearing hidden behind "Not sized" → "Clear size"; no undo |
| 4 | Consistency and Standards | 2 | Out-of-date sizes: muted line, no action (Quality uses a Card + button); plain-disabled Suggest sizes |
| 5 | Error Prevention | 2 | One click reopens an approved Story's approval, unwarned |
| 6 | Recognition Rather Than Recall | 3 | No way to request a suggestion from a single Story page |
| 7 | Flexibility and Efficiency | 2 | One Story at a time; no accept-all; focus lost on each save |
| 8 | Aesthetic and Minimalist Design | 3 | Size shown twice on a sized card; form stays after decision |
| 9 | Error Recovery | 3 | Version conflict refetches silently |
| 10 | Help and Documentation | 2 | Nothing says what a point means; Select hint unused |
| **Total** | | **25/40** | **Acceptable** |

## Design Specificity Verdict

Mostly authored for this product; the decision moment is generic. Honest partial totals, AI-judgement labelling, neutral badge and save-on-button are specific to Requirement AI's principles. The Size section is a stock select + Save bolted onto the card, not a sibling of the Quality panel's business-language question. Detector: 0 findings in all six changed files; browser overlay flagged only pre-existing code (side-tab on NextAction and tone Cards = the system's deliberate 3px edge, false positive; nested-cards on StoryQualityPanel inside StoryCard, pre-existing judgement call).

## What's Working

1. Honest totals: "2 points · 1 of 2 sized" / "Not sized yet" never present a partial sum as the whole.
2. One Accent Rule kept: neutral SizeBadge with a ruler, Accept is secondary.
3. Provenance kept: who decided and how, "How this size was suggested", "The AI could not size this Story" as a third state, save on button not on select change.

## Priority Issues

1. [P1] Sizing silently reopens approval and relabels the Story "Edited". Fix: confirm via ConfirmDialog when the Story is approved; consider a "Sized" provenance wording. Command: /impeccable harden
2. [P1] "Story points" is unexplained jargon for the business owner. Fix: question heading ("How big is this Story, compared with the others?"), Select hint ("Relative effort against the other Stories in this Feature — not hours or days. 13 means split it."), one noun ("size") throughout. Command: /impeccable clarify
3. [P2] Two equal paths at one decision; focus lost on save; loading on the wrong button. Fix: pre-select the suggestion, Accept as the one action with "Choose another size" disclosed; per-action loading; focus the Size heading and announce the result; collapse to badge + "Change size" once confirmed. Command: /impeccable distill
4. [P2] Out-of-date / no-suggestion states inconsistent with Quality and dead-ended. Fix: warning Card with inline "Suggest sizes again"; a "No suggestion yet" line with an action on the Story page; blockedReason not disabled. Command: /impeccable harden
5. [P3] Review row shows size without basis and nothing for unsized; total sits among approval gates. Fix: "Not sized" muted text; basis in sr-only text; move total to a separate "Backlog size" line. Command: /impeccable clarify

## Persona Red Flags

- Alex: 20 Stories = 20 page visits; no accept-all; focus dropped on each save.
- Sam: focus lost on save, no live confirmation; Accept not described by the rationale; dangling aria-describedby to story-…-gated on non-focused cards.
- Business owner: "13 points" read as days; "1 of 2 sized" beside approval gates implies it is required; "Edited" after Accept looks like a requirement change.

## Minor Observations

- Diagonal 12px ruler shares a silhouette with the Edited pen.
- Suggestion block's 1px left line matches the acceptance-criteria list; no spark glyph for AI provenance.
- Suggestion headline <strong> renders at weight 400 (text-body overrides).
- "Not sized yet" vs "Not sized" wording drift; "·" vs "," separators.
- decided_at not shown.
- Size sits above Quality (which judges Estimable/Small); consider the reverse order or a link.

## Questions to Consider

- Is one-click Accept a decision or a rubber stamp, given points are relative?
- Should the business owner see Small / Medium / Large rather than numbers?
- Would one Feature-level sizing table fit a relative decision better than per-Story forms?
