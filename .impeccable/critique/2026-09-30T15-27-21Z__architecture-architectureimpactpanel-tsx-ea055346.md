---
target: Connected systems group in ArchitectureImpactPanel
total_score: 21
max_score: 36
na_heuristics: 9
p0_count: 0
p1_count: 2
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\architecture\\ArchitectureImpactPanel.tsx"
target_fingerprint: "sha256:0ce4e9445a134e99132cd58af92f976a21db2a8df93db6d99e8c6273687ae186"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\architecture\\ArchitectureImpactPanel.tsx"
timestamp: 2026-09-30T15-27-21Z
slug: architecture-architectureimpactpanel-tsx-ea055346
---
Method: dual-agent (A: design review sub-agent · B: detector + browser sub-agent). Live seeded page: DCRM + CWOM mapped, 7 connected systems.

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | "to check" implies a checklist with no done state |
| 2 | Match System / Real World | 3 | "one relationship away" is graph jargon; "→" hides direction |
| 3 | User Control and Freedom | 3 | Group cannot be collapsed on its own |
| 4 | Consistency and Standards | 2 | 2px neutral edge off-system; connected names bolder than mapped |
| 5 | Error Prevention | 2 | Compact line has no "not mapped" cue; comma+slash names misread |
| 6 | Recognition Rather Than Recall | 2 | Capabilities in payload but not shown |
| 7 | Flexibility and Efficiency | 2 | No grouping by mapped system; no route to the catalogue |
| 8 | Aesthetic and Minimalist Design | 2 | Names repeated per row; "Squads not assigned" x7 |
| 9 | Error Recovery | n/a | Read-only display |
| 10 | Help and Documentation | 3 | Intro explains on Features, absent on Stories |
| **Total** | | **21/36** | Acceptable |

Detector: CLI clean (0). Browser overlay: 3 line-length flags in the group (2 single-line false positives, 1 real 107-char wrap; no measure cap). Contrast passes AA in both themes.

Priority issues:
- [P1] Hierarchy inversion: connected names computed 700, mapped 400.
- [P1] Capabilities hidden; "Squads not assigned" repeated 7 times.
- [P2] No grouping by mapped system; arrow does not state direction.
- [P2] Compact Story line ambiguous and lacks "not mapped".
- [P2] Off-system 2px left edge reads as a citation.

Fixed in the same pass: mapped names semibold, connected regular; rows grouped "Linked to <mapped> (n systems)" with "Used by / Uses <mapped>: description"; capability shown; squads shown only when any exist, otherwise one group-level note; compact "Not mapped: A; B"; edge removed; aria-labelledby via useId; role="list"; 80ch measure cap; omitted count links to the architecture catalogue. Verified live in dark 1440 and light 900 (no horizontal overflow).
