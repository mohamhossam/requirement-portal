---
target: System components dossier and system dialog
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\.claude\\worktrees\\system-components\\frontend\\src\\features\\catalogue\\CatalogueBrowser.tsx"
target_fingerprint: "sha256:637e184d4818e90c21432d42ff3705ae04365fcb8b4449a67a537e4c881458dd"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\.claude\\worktrees\\system-components\\frontend\\src\\features\\catalogue\\CatalogueBrowser.tsx"
timestamp: 2026-10-01T07-54-53Z
slug: c-features-catalogue-cataloguebrowser-tsx-48cbaf9e
---
Method: dual-agent (A: design review · B: detector + browser evidence)

## Critique — System components (dossier + system dialog)

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | No focus move/announcement after Add component |
| 2 | Match System / Real World | 3 | "Component 1 ID" slug with no example |
| 3 | User Control and Freedom | 2 | Cancel discards a long form without asking |
| 4 | Consistency and Standards | 2 | Off-ladder 2px rule; Remove label naming; editable component ID vs locked System ID |
| 5 | Error Prevention | 3 | No ID uniqueness hint |
| 6 | Recognition Rather Than Recall | 2 | Component row doesn't show what it delivers; assignment ~1300px away |
| 7 | Flexibility and Efficiency | 1 | No collapse, bulk assign, or move-to |
| 8 | Aesthetic and Minimalist Design | 2 | 222px column beside an empty one; repeated hints |
| 9 | Error Recovery | 3 | Blocked reason joins comma-containing names |
| 10 | Help and Documentation | 3 | Fieldset description clear and linked |
| **Total** | | **24/40** | Acceptable |

Detector: CLI 0 findings. Browser overlay: 1 in-scope (nested-cards on Components fieldset, partly false positive — top-layer dialog), 7 pre-existing. No 375px overflow.

### Priority issues
- [P1] "What it does" crammed in a 222px half column (CatalogueBrowser SystemDossier) — full-width row, two-column component layout, one meta line.
- [P1] Drawer length and split component↔capability relationship (SystemsEditor SystemDialog) — name/ID first, details disclosure, "Delivers:" line, section-head legends.
- [P2] Component vs capability hierarchy too flat — title type, technology badge, ink-soft capabilities, sunken inset instead of 2px rule, "3 capabilities in 3 components".
- [P2] Blocked Remove looks enabled; reason unparseable — mute blocked style; count-based copy naming "Not in a component".
- [P2] Remove label grows with name; dossier components are landmarks — "Remove component" + aria-label; div not section.

### Persona red flags
- Power-user maintainer: ~10k px drawers, scattered selects, silent Cancel loss.
- First-time architect: unexplained required ID first; "(3 · 3 components)".
- Screen-reader user: no announcement on add; landmark noise; bidi meta line.

### Minor
- Capability diff "(component)" lacks from/to; "Not in a component" last; repeated hints.
