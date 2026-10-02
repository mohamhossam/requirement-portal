---
target: architecture catalogue AI suggestions list
total_score: 23
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\catalogue\\SuggestionList.tsx"
target_fingerprint: "sha256:401fe6b43e970f0f868f35ed7d217e4bccf9693c7b35ddc987e99f583ae9e796"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\catalogue\\SuggestionList.tsx"
timestamp: 2026-09-30T08-37-30Z
slug: frontend-src-features-catalogue-suggestionlist-tsx
---
Method: dual-agent (A: design review · B: detector + browser)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | "May already exist" replaces "Needs its system first" on a dependency that is still blocked; the bulk count is unexplained until the dialog opens |
| 2 | Match System / Real World | 3 | Plain copy; "Use BCRM" does not say which end or which name it replaces |
| 3 | User Control and Freedom | 2 | A link can't be undone from the row (pre-existing for Accept) |
| 4 | Consistency and Standards | 2 | System rows demote Accept to ghost, dependency rows don't; "Add to" and "Use" are the same act worded differently |
| 5 | Error Prevention | 2 | "Use BCRM" and "Accept" are identical buttons with opposite meanings, stacked at 390px |
| 6 | Recognition Rather Than Recall | 2 | The existing system is shown as a bare name; "Similar name to BCRM." is tautological |
| 7 | Flexibility and Efficiency | 2 | Bulk covers 1 of 4; no filter for "needs a decision"; one name question asked on every row |
| 8 | Aesthetic and Minimalist Design | 3 | Calm, but a matched row stacks five layers |
| 9 | Error Recovery | 2 | ErrorNotice sits at the section top, far from the row (pre-existing) |
| 10 | Help and Documentation | 3 | Inline explanations work; "Inferred" as a category is never explained |
| **Total** | | **23/40** | **Acceptable, needs work** |

## Design Specificity Verdict

LLM: specific in voice and evidence order (serif quote, then source, then a warning-edge block, then actions); generic in the decision mechanics (a stock callout-plus-button). "Inferred" is the quietest mark in the row even though it is the product's key uncertainty signal.

Deterministic scan: the CLI detector found 0 issues in SuggestionList.tsx and labels.ts. The runtime overlay found 8: side-tab and nested-cards on the two possible-match groups (new), line-length on the rationale paragraph (new), and line-length/nested-cards in DocumentSources.tsx and ArchitectureCataloguePage.tsx (pre-existing, other files). The side-tab is a deliberate §4.5 warning edge; nested-cards is borderline (a sunken inset only 1.19:1 from the card).

Measurements: all text passes AA in both themes (block text 8.84 light / 11.46 dark; Inferred badge 5.08 / 7.48; warning edge 3.42 / 6.60 non-text). Targets are at least 32.8px. No horizontal overflow at 390px.

## Priority Issues

- **[P1] "May already exist" hides "Needs its system first."** The possible-match label replaces the match label, so a dependency that is still blocked by a missing source looks resolvable by "Use BCRM". Fix: show both badges when the match is not "new".
- **[P1] One exclusive choice is split across two places with unequal weight.** "Add to BCRM" is in the block; "Keep as a new system" is in the action bar. On dependency rows, "Use BCRM" and "Accept" are identical. Fix: put the keep option in the block's list, and label the dependency alternative "Accept as written" in a lighter style.
- **[P1] WCAG 2.5.3 Label in Name fails on the new buttons.** Accessible names don't start with the visible text. Fix: start each aria-label with the visible label.
- **[P2] No evidence for the match.** Nothing shows what BCRM is. Fix: show the existing system's other names and capabilities from draft.systems.
- **[P2] "Inferred" looks like "New," and the bulk count is unexplained.** Fix: a distinct glyph; the rationale gated on basis; a note saying how many need a one-by-one decision; fix the dialog title plural.

## Persona Red Flags

- **Power-user maintainer:** "Accept all" clears 1 of 4; the same name question is asked per row; no filter for items needing a decision.
- **First-time architect:** doesn't know what BCRM is; "Inferred" and "New" look alike; "Use BCRM" is ambiguous; the blocked state is hidden.
- **Keyboard or screen-reader user:** 3 Label in Name failures; the group name "Existing systems “Dynamics CRM” may be" reads as a broken sentence.

## Minor Observations

- Linking shows the generic "Added to this version."
- The block mixes a sunken ground (neutral register) with an amber edge (status).
- The success notice doesn't name the link that was made.
- ConfirmDialog uses the danger variant for a non-destructive accept (pre-existing).
- Accent is used above "one accent, once" on this screen (pre-existing).

## Questions to Consider

- Should name resolution be one decision that settles every row naming it?
- Should inferred dependencies live in their own group?
- What is bulk accept for when it covers 1 of 4?
