---
target: Capability domain UI (Domains view, domains editor, impact domains and suggestion card)
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\catalogue\\DomainTree.tsx"
target_fingerprint: "sha256:5c0e584f7906efb84f6f403de10f1f27025092ff2ebb52ba5b5b8cfeb8351947"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\catalogue\\DomainTree.tsx"
timestamp: 2026-09-30T16-31-50Z
slug: frontend-src-features-catalogue-domaintree-tsx
---
Method: dual-agent (A: design review sub-agent · B: detector + browser sub-agent). Live seeded pages: Domains view, domains editor in a draft, a Feature mapped to DCRM + CWOM, and a Feature with no system mapped ("Faster SMB billing").

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Domains view ignored the draft diff |
| 2 | Match System / Real World | 3 | "Inside" vague; diff says "parent domain" |
| 3 | User Control and Freedom | 2 | Opening a system loses tree position |
| 4 | Consistency and Standards | 2 | h3 view title (others h2); selects in insertion order |
| 5 | Error Prevention | 2 | Parent select offered level-3 parents |
| 6 | Recognition Rather Than Recall | 2 | Blocked removal did not say which systems hold the capabilities |
| 7 | Flexibility and Efficiency | 1 | No search or collapse over 8 domains / 31 rows |
| 8 | Aesthetic and Minimalist Design | 3 | 31 indigo links competing with NEXT |
| 9 | Error Recovery | 2 | Remove reason only in aria-label |
| 10 | Help and Documentation | 3 | Empty state names a path but gives no link |
| **Total** | | **22/40** | Acceptable |

Detector: CLI clean on all four files. Browser overlay: skipped heading (h1→h3) on the Domains view; disabled Remove at 4.4:1 (inactive, exempt, but accurate); 80ch caps yield ~90–98 chars/line.

Priority issues:
- [P1] Disabled Remove: reason invisible and aria-label-only; "Remove" missing from the accessible name.
- [P1] "Business areas" undercounts: only matched capabilities carry domains on the seed path; "Capabilities of X" overstated.
- [P1] Suggestion card styled like a mapped system card.
- [P2] Domains view not a real tree: flat list, skipped heading level, no counts, no draft marks.
- [P2] Domain selects in insertion order; parent select ignored the depth limit.

Fixed in the same pass: Remove uses blockedBy with a visible reason naming the systems ("Holds 1 capability from BSCS. Move them to remove this domain."), stays focusable, accessible name "Remove X"; header reads "Matched business areas" and the list label is restored to "Matched capabilities for X"; suggestion card is plain text ("No system mapped." / "Closest business areas" / "Its systems, not mapped" / "Words in common") with a link to the domains view; Domains view has an h2, nested lists with h3–h5 by depth, per-domain counts, a two-column layout at lg, draft change badges and an amber-edged "Not placed in a domain yet" group; selects follow tree order and the parent select only offers levels 1–2 ("Parent domain"); measures capped at 68ch. Also relaxed slice B's add-dependency form to five columns only from lg. Verified live: heading outline, two columns at 1440 with no overflow, card copy, Remove aria-disabled with its description.
