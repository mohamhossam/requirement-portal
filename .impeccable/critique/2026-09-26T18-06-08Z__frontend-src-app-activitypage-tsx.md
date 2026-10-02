---
target: Phase 8 Activity and Reports (re-critique)
total_score: 25
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:/home/user/smb-ai-requirement-agent/frontend/src/app/ActivityPage.tsx"
target_fingerprint: "sha256:8622f2764ebb414a3e5126642b8275916bd5686d1614060d62c64182db0f4513"
target_path: /home/user/smb-ai-requirement-agent/frontend/src/app/ActivityPage.tsx
timestamp: 2026-09-26T18-06-08Z
slug: frontend-src-app-activitypage-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence). Re-critique after the Phase 8 build (50b2c6c), blind to the first run.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Day heading counts loaded rows, not the day; changing the report window blanks blockers |
| 2 | Match System / Real World | 2 | Server summaries lead rows ("Screen requirement knowledge succeeded"); "Any ai generation activity"; Question vs Clarification |
| 3 | User Control and Freedom | 3 | Enter on a freshly focused picker applies a filter; typed text lost on Tab |
| 4 | Consistency and Standards | 2 | Combobox departs from WAI-ARIA; "Questions resolved" names two measures; "darker column" false in Slate |
| 5 | Error Prevention | 2 | First option armed on focus; reversed range still queries with an unrelated empty state |
| 6 | Recognition Rather Than Recall | 3 | Name pickers fix §3.8; What happened is one 37-option native list |
| 7 | Flexibility and Efficiency | 2 | No date presets, no hide-automated toggle, single category |
| 8 | Aesthetic and Minimalist Design | 3 | Calm, on-token; "Not recorded" column; zero-filled table under the chart |
| 9 | Error Recovery | 3 | Linked date error; empty state says "Widen the dates" when none are set |
| 10 | Help and Documentation | 2 | Exclusive Before, metric definitions and per-chart scales unexplained |
| **Total** | | **25/40** | **Acceptable** |

## Design Specificity Verdict

LLM: thinking is product-specific (count → evidence deep links with exact UTC weeks, Evidence column, name pickers, blockers first, ink bars under Reserved Vocabulary); visual form is generic admin (filter card, table, sparklines); chart under-designed. Deterministic: CLI 0 findings on all six files. Browser: side-tab on Blockers edge (One Edge Rule, by design; not in config whitelist for ReportsPage.tsx), nested-cards ×3 on sunken thead and cramped-padding ×2 on table regions (false positives), line-length ~90 in shared PageHeader. Contrast 0 failures in 16 runs except during refetch: opacity-60 drops muted text to 2.58:1 / 3.24:1. Native date picker button focus has no visible ring. Overlay not available under the built CSP.

## Priority Issues

- [P1] Combobox keyboard model: overflowing listbox is a Tab stop then focus falls to body; option 0 armed on focus so Enter applies a filter; typing over a choice appends; aria-selected marks commitment not highlight; empty message is an option. /impeccable harden
- [P1] Chart misleads: independent unlabelled y-scales (5 and 17 same height), no x labels, current week by lightness only, "darker column" false in Slate. /impeccable clarify
- [P2] Machine strings lead rows; lowercased "ai"; system actor reads as a person; AI rounds "Not recorded". /impeccable clarify
- [P2] Day counts are loaded rows; Load more drops focus; local times vs UTC filters unlabelled; reversed-range empty copy; refetch dimming fails contrast; error shifts row alignment. /impeccable harden
- [P3] Reports: two "Questions resolved"; blocker kind missing; all-"Not recorded" column; zero table repeats chart; window change blanks blockers. /impeccable distill

## Persona Red Flags

Alex: no presets, 37-option select, no hide-automated, re-pick needs clear, Enter-on-focus. Sam: focus to body after picker Tab and Load more; lists announce expanded on every pass; no-match as disabled option; section name repeats h1. PO: answer at the bottom with no deltas; equal bars for 5 and 17; two different "12 questions resolved"; 26 zero rows.

## Minor Observations

Empty state glyph is a "create" icon; Evidence reference wraps inconsistently; category line repeats when filtered; date inputs mm/dd/yyyy vs "Sep 21"; window pills push history; "All activity" floats detached.

## Questions to Consider

- Audit of human decisions, or system log — should automated events collapse by default?
- Should Reports open with one sentence that answers the PO?
- If every count opens its evidence, should the bars be the links?
