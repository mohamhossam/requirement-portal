---
target: Phase 9 History
total_score: 13
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:/home/user/smb-ai-requirement-agent/frontend/src/features/revisions/RevisionPanel.tsx"
target_fingerprint: "sha256:b53b1ed02208a91b2b5c082dccdc52a82ffc317bd3d4929dc66791d9fd543104"
target_path: /home/user/smb-ai-requirement-agent/frontend/src/features/revisions/RevisionPanel.tsx
timestamp: 2026-09-26T18-28-15Z
slug: frontend-src-features-revisions-revisionpanel-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence)

Target: frontend/src/app/requirement/RevisionsView.tsx, frontend/src/features/revisions/RevisionPanel.tsx (redesign Phase 9, History), seeded requirement with 19 backlog revisions (v18 approved), 1440 / 390 / 720, Paper and Slate.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Silent download; stale comparison after selects change; rail says Clarify on History |
| 2 | Match System / Real World | 1 | UUIDs in the diff; "0/1 intent decisions", "Durable traceability", "immutable" |
| 3 | User Control and Freedom | 2 | No swap, no compare-with-previous, pair not shareable |
| 4 | Consistency and Standards | 1 | Legacy Section, uppercase labels, off-ladder radii, raw selects |
| 5 | Error Prevention | 2 | Observer gets an operable format select; nothing says approval predates the source |
| 6 | Recognition Rather Than Recall | 1 | From/To are bare v1…v19 |
| 7 | Flexibility and Efficiency | 1 | No approved → current shortcut, no row actions |
| 8 | Aesthetic and Minimalist Design | 1 | 11-fact run-on string ×19; "Not exportable" ×18 |
| 9 | Error Recovery | 1 | Load error without retry; export error away from Download |
| 10 | Help and Documentation | 1 | Nothing explains revisions or export formats |
| **Total** | | **13/40** | **Poor** |

## Design Specificity Verdict

LLM: generic and pre-redesign — last consumer of the legacy Section ("03", tracked-uppercase eyebrow), two bordered boxes of run-on counts, no primitives. Deterministic: CLI 0 findings (both files, 01-foundation.css). Browser: all-caps labels (Export format / From / To at 11.2px/800), kicker above heading, em-dash ×18, first-viewport column imbalance; sub-12px meta (11.84px ×43). At 390 `.revision-layout` crushes to 92px/161px columns and clips (WCAG 1.4.10). Download disables its focused button → focus to body; success silent; errors reported twice (inline + toast). v18 sits off-screen inside a 320px scroller. Contrast all ≥4.5.

## Priority Issues

- [P1] No answer-first approved export; v18 buried and unmarked; post-approval source edit invisible. /impeccable layout + clarify
- [P1] Comparison unreadable and unannounced: backend strings with UUIDs, no live region, stale after selects change, bare version options. (Names for IDs need an API change.) /impeccable clarify + harden
- [P1] Revision list is prose in a scroll box, oldest first, ignoring review_status/epic/approval fields. /impeccable distill + layout
- [P2] Legacy frame: Section chrome as a third accent, uppercase sub-12px type, off-ladder radii, no reflow at 390, rail marks Clarify current, History has no aria-current. /impeccable polish + adapt
- [P2] Thin states: load error without retry, errors away from their control, silent success, bare empty/one-revision states, observer sees export controls. /impeccable harden

## Persona Red Flags

Alex: no shareable pair, 19-option selects, no shortcuts, 2,352px inner scroll. Sam: run-on rows, approval not a status, comparison unannounced and read as UUIDs, rail announces Clarify. PO: format detached from Download, UUID filename, silent download, approved v18 built from requirement v1 while the source is v2 — unmentioned.

## Minor Observations

Seconds-precision locale timestamps; description omits export; "Human requirement history"; Download at 33px; no swap; dark theme clean.

## Questions to Consider

- Should History be a panel as §4 says, with export on Review & approve?
- Does anyone want 19 revisions, or the 4–5 milestones?
- Is the loudest thing the approved export, or that the approval no longer matches the source?
