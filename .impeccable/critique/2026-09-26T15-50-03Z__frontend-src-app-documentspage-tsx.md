---
target: Phase 7 Documents catalogue and detail
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:/home/user/smb-ai-requirement-agent/frontend/src/app/DocumentsPage.tsx"
target_fingerprint: "sha256:78d33a5f045e12815ed5b3a31167d67769206994d45d77c003acf873fd120335"
target_path: /home/user/smb-ai-requirement-agent/frontend/src/app/DocumentsPage.tsx
timestamp: 2026-09-26T15-50-03Z
slug: frontend-src-app-documentspage-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence)

Targets: frontend/src/app/DocumentsPage.tsx, frontend/src/app/DocumentDetailPage.tsx (redesign Phase 7), live seeded app at 1440 / 390, Paper and Slate.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | "Does the AI see this?" is wrong or missing in three places: unticked hidden-sheet rows listed under "what analysis reads"; PDFs never show extracted passages; draft files never state current inclusion |
| 2 | Match System / Real World | 2 | Enum labels translated, but parser vocabulary leaks: "R/C labels and bracketed markers", "neutral paragraph locations", "DOCX extraction produced no usable text", `Worksheet 1!1:1`, a hex id on every passage |
| 3 | User Control and Freedom | 3 | Reversible checkbox, back link, clearable filters; no return from a "Show in the file" jump |
| 4 | Consistency and Standards | 3 | "Needs a decision" filter returns a row that never says so; checkbox "Worksheet 2" vs content "Margin model" |
| 5 | Error Prevention | 2 | Upload new version states no formats/limits and not that it replaces what analysis reads; accept list omits .pptx/.csv/.tsv the reader supports |
| 6 | Recognition Rather Than Recall | 3 | Outline, owner titles and anchors help; sheet position-to-name mapping left to memory |
| 7 | Flexibility and Efficiency | 2 | Search matches filenames only; no filter/group by requirement; no bulk include; date without time |
| 8 | Aesthetic and Minimalist Design | 3 | Clean and flat; hex ids, checksum twice, "845 B (845 bytes)", blocked state said five times |
| 9 | Error Recovery | 2 | Blocked file names no likely cause and has no fix in the card; the upload is a secondary button far away |
| 10 | Help and Documentation | 2 | Consistent Help position and a hint on the decision; nothing says whether "warnings" matter |
| **Total** | | **24/40** | **Acceptable** |

## Design Specificity Verdict

LLM assessment: the detail page is authored for this product (evidence-then-decision card with the provider disclosure under the checkbox; serif for file content vs sans for the instrument; warnings anchored to passages with indigo target / amber flag edges). The catalogue is category-interchangeable — a generic file-manager table that ignores that files belong to requirements. The passage viewer reads like parser output (R1C1 strings, A1= rows, raw Markdown), not the file.

Deterministic scan: CLI `impeccable detect` clean on both files and features/documents (exit 0, 0 findings). Browser overlay under the app's real CSP: injection refused (script-src 'self'), no user-visible overlay. With CSP bypassed in a scratch browser: 10 findings on 4 pages — 8 line-length (80ch interface measure is ~88–98 real characters; the draft line at DocumentDetailPage:380 has no max-width, ~103), 1 side-tab (danger-tone Card: 3px left edge + 10px radius — the design system's own "One Edge Rule", shared by Card/ErrorNotice/Toaster; a deliberate system choice), 1 nested-cards (false positive: a table thead on sunken ground inside the framed section).

## Overall Impression

A clear improvement on the card grid and a detail page with the right spine, but the page still does not tell the truth about its own question: what the AI will receive. And amber is spent on boilerplate format notes, so six of eight files look like they need attention when one does.

## What's Working

1. The decision card's order and consequence: readiness → what to check → hidden sheets → Include in analysis, with "sent to the configured AI provider" directly under it (Principle 2).
2. Two channels for every status and the Register Rule held: glyph + words on every badge; serif passages at document measure; dark theme holds.
3. Catalogue construction: enums in business words, owner titles resolved, whole-row link with a separate owner target and a row focus ring, live "N of M files", recoverable no-match state.

## Priority Issues

- **[P1] "What was read" is not what the AI reads.** Unticked hidden-sheet rows sit under "Each passage below is what analysis reads"; PDFs show only the original although the hint says "the text passages … below are sent"; draft files never state their inclusion. Why: this is the page's question, about data leaving for an AI provider. Fix: mark passages from unticked hidden sheets "Not sent — hidden sheet" (sunken, muted, words) and group by sheet; for PDFs add "What analysis reads" beside the original from evidence_blocks already loaded; on draft files state "In analysis on the draft" / "Left out on the draft". Command: /impeccable clarify
- **[P1] Amber is spent on boilerplate.** Document-level reader notes make 6/8 files "Ready, with warnings"; the one unreadable file is barely louder. Why: breaks "the only loud thing is the unresolved thing"; people learn to ignore amber. Fix: on detail, separate passage-anchored warnings from format notes and put format notes in a quiet "How this file type is read" disclosure; in the catalogue reserve badges for blocked / needs-a-decision and show "Ready · notes" as quiet text. Raise a severity change with the backend if needed. Command: /impeccable quieter
- **[P1] The unreadable file is a dead end and contradicts itself.** Jargon cause, no fix in the card, same fact five times, "Left out" in the catalogue vs "leave it out before analysing". Fix: put "Upload a readable version" in the card as the page's one accent (plus the draft link), one plain-language cause line ("often a scan with no text layer"), drop the empty "What was read" section, and say "Not usable" in the catalogue's Analysis column with the decision words on the row. Command: /impeccable harden
- **[P2] Passages don't look like the file.** Table/worksheet rows as encoded strings, raw Markdown, a hex id on every passage (read aloud by screen readers). Fix: render runs of table_row / worksheet_range as a real table per table or sheet with the sheet name; move the id behind "Copy link to passage"; hide the outline with fewer than two headings. Command: /impeccable layout
- **[P2] The catalogue ignores the requirement.** Filename-only search, no grouping/filter by Attached to, date-only Added so same-day sorts look inert, no bulk include. Fix: search owner titles too, add a requirement filter or grouping, show time or relative time. Command: /impeccable shape

## Persona Red Flags

**Alex (Power User)**: searching a requirement name returns "0 of 8 files"; one-by-one include with no bulk; table region is a tab stop that scrolls nothing at 1440; no `/` to focus search; same-day files indistinguishable by time.

**Sam (Accessibility)**: a 24-char hex id announced on every passage; the list named three times (sr-only h2 "Files", caption "Documents", region "Documents"); "Show in the file" has no way back; "Worksheet 2" never says "Margin model"; the blocked badge's red wash disappears on the red card.

**Business owner (non-agile)**: her ordinary Word brief is flagged amber with "R/C labels and bracketed markers…"; "A1=Plan | B1=Monthly" is unreadable; told to "leave this file out on the draft" when it already says Left out; never told whether the AI will see her draft file; a SHA-256 is her most prominent trust signal.

## Minor Observations

- Search control 54px against the 36px spec (shared with the worklist); "N files" count floats far from the pills.
- Below md, the File header sort and the "Newest first" select are two sort controls.
- "Open PDF" uses a Download glyph but opens a tab.
- A single-version file shows a Versions list repeating the checksum.
- At 390 the File record precedes "What was read" — about a screen of metadata first.
- Line length: helper paragraphs run ~88–98 characters at the 80ch measure; DocumentDetailPage:380 has no cap.

## Questions to Consider

- If every Word file carries the same warning, is it a warning or a footnote about how files are read?
- Should the catalogue list files at all, or requirements with their evidence underneath?
- What if "What was read" were the literal payload the AI would receive with the current ticks, updating as hidden sheets are toggled?
- Is a 64-character hash the trust signal a business owner can use, or is "Unchanged since you attached it on 26 Sep" the real one?
