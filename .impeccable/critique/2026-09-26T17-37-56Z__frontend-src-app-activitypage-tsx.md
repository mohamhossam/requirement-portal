---
target: Phase 8 Activity and Reports
total_score: 15
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:/home/user/smb-ai-requirement-agent/frontend/src/app/ActivityPage.tsx"
target_fingerprint: "sha256:cbeb722551e7b44c45290daf4802b42ba048e604b1f0b2eccea60d0cf6355d4b"
target_path: /home/user/smb-ai-requirement-agent/frontend/src/app/ActivityPage.tsx
timestamp: 2026-09-26T17-37-56Z
slug: frontend-src-app-activitypage-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence)

Targets: frontend/src/app/ActivityPage.tsx, frontend/src/app/ReportsPage.tsx (redesign Phase 8), live seeded app at 1440 / 390, Paper and Slate.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | 100-event cap is silent (API total/has_more ignored); no announced result count; after a /reports deep link the date range is only prose and the date inputs stay empty |
| 2 | Match System / Real World | 2 | Action labels are business words; raw `ai_job: <uuid>`, "Traceable audit projection", "Clarification cohort", "Artifact approvals", "Actor unavailable" for system work |
| 3 | User Control and Freedom | 2 | Each keystroke in an ID field pushes history and fetches; Action only removable via Clear all; deep-link occurred_from overrides the From/Before inputs |
| 4 | Consistency and Standards | 1 | No Table/Input/Select/Badge/Pill primitives; uppercase eyebrows and badges; 40px controls; off-ladder radii; ExternalLink glyph on internal links |
| 5 | Error Prevention | 1 | Free-text UUIDs; malformed ID reads as "No matching activity"; From can be after Before |
| 6 | Recognition Rather Than Recall | 1 | Requirement and actor recalled as UUIDs; Action has no control |
| 7 | Flexibility and Efficiency | 1 | URL filters good; no pagination, no multi-select, 3 events per 1440x900 screen, 130 tab stops in the 26-week table |
| 8 | Aesthetic and Minimalist Design | 1 | 176px card per one-line event; 100 identical "Open affected requirement"; 127 of the table's links are "0" |
| 9 | Error Recovery | 2 | Error+retry and filtered-empty exist; no bad-ID diagnosis; two Clear all at once |
| 10 | Help and Documentation | 2 | Global Help present; nothing explains cohort, blocker or categories |
| **Total** | | **15/40** | **Poor** |

## Design Specificity Verdict

LLM assessment: category-generic. /activity is a stock SaaS timeline of cards; /reports is stock KPI + table + list. The one product-specific idea is each weekly count deep-linking to its audit evidence (Principle 5); it survives. Beside the redesigned Documents and Worklist the two screens read as a different product.

Deterministic scan: CLI `impeccable detect` clean (0, exit 0). Browser detector (dev server, no CSP): 112 × undersized-ui-text (.workflow-badge 10.88px, 01-foundation.css:107), 3 × kicker-above-heading (ReportsPage.tsx:47,48,51), 1 × side-tab on .filter-context (false positive: One Edge Rule, config-exempt), 1 × line-length ~85 (heuristic artefact, capped at 80ch). All flagged links 23.2px tall. Contrast ≥4.5:1 everywhere; no horizontal overflow at 390. Under the built app's script-src 'self' the overlay is refused — no user-visible overlay on the real build.

## Overall Impression

Two pre-redesign screens holding one very good idea. Activity must become an audit ledger, not a news feed; Reports must answer the PO's two questions — what is stuck, is it moving — in that order.

## What's Working

1. Metric-to-evidence deep links (ReportsPage.tsx:14).
2. Business-language label maps for 30 actions and 6 categories (ActivityPage.tsx:18–58).
3. Sound state basics: loading / error+retry / empty / filtered-empty; real fieldset with aria-pressed; tokens only; dark mode holds.

## Priority Issues

- **[P1] Filters ask for UUIDs, and one filter is missing (§3.8).** Fix: requirement picker by title (listRequirements q), person picker (searchActors), Action select grouped by category, active filters as removable chips, deep-link dates reflected in the controls, debounced replace-history typing. Command: /impeccable harden
- **[P1] Activity is a card feed where an audit needs a ledger.** 176px/event, 100 h2s, 100 identical links, accent spent on every dot, category by colour alone. Fix: Table primitive (When · Who · What happened · Requirement title as link · Evidence in words), grouped under a heading per day, "Showing 100 of N". Command: /impeccable distill
- **[P1] Reports answers neither PO question in order.** Blockers last with no age; trend is a mostly-zero 12-row grid; "60% resolved" outranks the h1. Fix: blockers first by age in days with Blocking Red edge + words; weekly chart beside the table (categorical ramp, no status hues, no accent); zero cells plain text; resolution rate as resolved-of-opened at headline size. Command: /impeccable distill, /impeccable colorize
- **[P2] WCAG 2.2 gaps.** Link purpose ("Open affected requirement" ×100, "0"), 23.2px targets, no live result count, h1→h3 in empty/error states, no table caption. Command: /impeccable harden
- **[P2] Type and chrome break the system.** Uppercase .eyebrow / .workflow-badge below the 12px floor; active range button text is --surface not --on-accent; summary panel filled Margin Grey without status meaning. Command: /impeccable polish

## Persona Red Flags

**Alex (Power User)**: silent 100 cap; no multi-category despite API support; typing floods history; 130 tab stops; 3 events per screen.

**Sam (Accessibility)**: 100 h2s with no day structure; links list is "Open affected requirement" ×100 and "0" ×127; no announcement after filtering; 10.9 / 11.5px text; deep-linked Action filter exists only as prose.

**Product Owner (is the portfolio moving?)**: no trend line; "Median resolution 0h" looks broken; blockers have no age/owner/stage and sit at the bottom; "Artifact approvals" is method vocabulary.

## Minor Observations

- toLocaleDateString() on a UTC Monday renders Sunday west of UTC; From/Before read as UTC midnight.
- Deep-link context shows an exclusive bound with seconds; "Window ends … 5:32:41 PM" over-precise.
- Floating Filter icon carries nothing.
- At 390 the filter panel fills the first viewport; the table hides 3 of 5 metrics behind an uncued scroll.
- "Requirement knowledge" vs "Knowledge" category naming drift.

## Questions to Consider

- Ledger or feed? If a ledger, should Activity look like the worklist?
- Why does Reports open on throughput when "what is stuck" is the only thing a PO can act on today?
- The honest reference for "60%" is the previous window — PRODUCT.md forbids inventing a target.
