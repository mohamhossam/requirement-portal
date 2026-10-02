---
target: Phase 7 Documents catalogue and detail (after critique fixes)
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:/home/user/smb-ai-requirement-agent/frontend/src/app/DocumentsPage.tsx"
target_fingerprint: "sha256:2ce0e60849989e643d4ba47f0cb81f94072c320b80c757fc40b73110a83d61a5"
target_path: /home/user/smb-ai-requirement-agent/frontend/src/app/DocumentsPage.tsx
timestamp: 2026-09-26T16-22-01Z
slug: frontend-src-app-documentspage-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence). Re-run after the critique fixes (commit 7afcc36); neither assessment saw the earlier result.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Readiness, In analysis ✓, live count, Saving… all work; toggling inclusion never says whether the requirement's analysis now needs re-running |
| 2 | Match System / Real World | 3 | Plain labels; lapses: a heading labelled "Paragraph 1", Word tables headed "Column 1/2/3", raw reader strings, a UUID on the not-found page |
| 3 | User Control and Freedom | 2 | Filter/search/sort reset on returning from a file; no Clear filters control |
| 4 | Consistency and Standards | 3 | The unreadable file is "Not usable", counted under "Left out", and flagged "Needs a decision" — three names for one state |
| 5 | Error Prevention | 3 | Good consequence text on Include; header "Upload new version" shows no accepted formats |
| 6 | Recognition Rather Than Recall | 3 | Owner titles help; the Attached-to select lists same-named requirements twice, indistinguishably |
| 7 | Flexibility and Efficiency | 2 | No passage-text search, no bulk include, filters not in the URL, a tab stop per passage label |
| 8 | Aesthetic and Minimalist Design | 3 | Restrained in both themes; File column collapses 900–1250px; PDF page image repeats the original |
| 9 | Error Recovery | 3 | Unreadable-file card is strong (cause, fix, formats, reader report); not-found page weak |
| 10 | Help and Documentation | 3 | Global help, reading-notes disclosure, hints; nothing defines "Needs a decision" |
| **Total** | | **28/40** | **Good** |

## Design Specificity Verdict

LLM assessment: the detail page is authored for this product — serif document register for passages, "Not sent · hidden sheet" on the margin ground, the amber warning ↔ passage round trip, tables rebuilt from reader output, and the fix inside the unreadable-file card all follow from Principles 1 and 2. The catalogue is a competent, generic table: no grouping by requirement, attention rows not pinned, no sense of evidence per requirement.

Deterministic scan: CLI clean (exit 0, 0 findings) on both pages and features/documents. Under the app's real CSP the overlay is refused; with CSP bypassed, 16 findings on 5 pages: line-length (the 80ch interface token allows ~98 characters; the accepted-formats line at DocumentDetailPage:258 is uncapped at ~111), nested-cards and cramped-padding on the passage tables (a real double frame: a framed Table inside a bordered passage row; thead hits are false positives), and side-tab on the danger card (the One Edge Rule, intended). Additional fact: the app's own CSP (`frame-src 'none'`, contentSecurityPolicy.ts:64, since 258c5a3) blocks the blob iframe, so the PDF "Original" preview does not render in the built app — pre-existing, not introduced by Phase 7.

## Priority Issues

- **[P1] The catalogue's File column collapses at laptop widths.** Measured 0px at 920, 50px at 1100, 150px at 1200, 230px at 1280: fixed column widths plus the 240px sidebar leave File as the only flexible track. Fix: below lg fold Analysis and Added into the File cell (as below md), give File a floor (~16rem) and let Attached to absorb the squeeze. Command: /impeccable adapt
- **[P1] "Needs a decision" leads to a page with no decision.** The unreadable draft file is "Could not be read" + "Needs a decision" + "Not usable" and counted under "Left out"; its page offers only Upload. Fix: one state name everywhere; the blocked card opens with the pending decision and both exits; keep unreadable files out of "Left out" or say "Left out · can't be read". Command: /impeccable clarify
- **[P2] Trust is answered only by readability.** included_version_id is never shown, so on a two-version file you can't tell which version analysis read; versions are inert; the checksum has no context. Fix: mark "Current" and "Used by analysis" separately in the record; one line explaining the checksum. Command: /impeccable harden
- **[P2] A left-out file's passages look sent; PDF compare is a scroll-compare.** Unticked files show full-strength passages under "What analysis reads" beside muted hidden-sheet rows; the PDF page image repeats the original. Fix: "What analysis would read" + not-sent ground when excluded; original and passages side by side at lg; collapse the page image. Command: /impeccable layout
- **[P2] The power-user path is thin.** Filters reset on return, no passage search, no bulk actions, attention rows not pinned. Fix: pin needs-a-decision rows (or a one-line strip); raising URL-persisted filters as a state change. Command: /impeccable harden

## Persona Red Flags

**Alex (Power User)**: filters lost on every return from a file; no evidence-text search; no multi-select; 15 tab stops for 9 passages (every location label a link, every grid a focusable region); catalogue unreadable in a half-width window.

**Sam (Accessibility)**: the readiness cell is announced "Could not be readNeeds a decision" with no space; same-named owners in the select sound identical; focus stays on body after "Show in the file"; light-theme checkbox focus ring is black while others are indigo.

**Business owner (non-agile)**: "Needs a decision" with no decision on arrival; "Paragraph 1" on a heading and "Column 1/2/3" over a real header row; "configured AI provider" is abstract; a 64-character checksum is noise.

## Minor Observations

- Excel grid cells break mid-word at 390 ("Monthl/y") — `overflow-wrap:anywhere` on cells; use break-word.
- Amber "Needs a decision" text directly under a red badge: two status hues in one cell.
- The not-found page shows a raw UUID and an unhelpful "Try again".
- "Shared library" / "Architecture knowledge" header buttons are unexplained destinations outside the four-item IA.

## Questions to Consider

- Should the catalogue group by requirement ("3 in analysis, 1 needs a decision") instead of a flat file list?
- When a file is left out of an analysed requirement, should the page say what happens to findings that cite it (Principle 4)?
- Is there a legitimate state where analysis reads an older version than the current one — and if so, why is it invisible?
- Would original ↔ what analysis reads side by side, for every type, be this screen's signature?
