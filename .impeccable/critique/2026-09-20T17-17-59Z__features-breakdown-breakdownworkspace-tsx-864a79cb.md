---
target: breakdown screens
total_score: 20
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 3
target_identity: "file:C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\breakdown\\BreakdownWorkspace.tsx"
target_fingerprint: "sha256:65f64f4ffb5605a6d49bdb2885a9d9af5aa52e51f6b42c02267e806bf7c4c17d"
target_path: "C:\\ai\\projects\\smb-ai-requirement-agent\\frontend\\src\\features\\breakdown\\BreakdownWorkspace.tsx"
timestamp: 2026-09-20T17-17-59Z
slug: features-breakdown-breakdownworkspace-tsx-864a79cb
closed: true
---
Method: dual-agent (A: design review, run blind to the detector · B: detector + live browser evidence). No degradation.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2/4 | Quality state exists only on the Story route. `BacklogTree`'s `RowStatus` and `compact-story-list` both render provenance only, so two Stories read identically when one has 2 failed checks. |
| 2 | Match System / Real World | 2/4 | "INVEST quality", "SPIDR recommendations", "Epic", "MVP / Later drop", "Portfolio outcome" all render unexplained. `design-system.md` §14 names this exact anti-pattern. |
| 3 | User Control and Freedom | 2/4 | Regeneration confirms and names the loss; Approve has no confirmation and no undo. The irreversible act is casual, the reversible one ceremonial. |
| 4 | Consistency and Standards | 2/4 | "Continue reviewing" means two different things. Approve exists on Epic + Feature, silently absent on Story. Measured: 39px / 39px / 22px controls in one action row. |
| 5 | Error Prevention | 3/4 | `blockedReason`, `EditorConflictNotice`, `ConfirmDialog` on every regeneration path. Undercut by the empty state. |
| 6 | Recognition Rather Than Recall | 2/4 | Rail clamps Story voices to 2 lines; every voice opens "As a SMB customer, I want...", so the discriminator sits inside the ellipsis. |
| 7 | Flexibility and Efficiency | 1/4 | One accelerator, unexplained. No next-story, no bulk approve, no "only what needs me". 12 Features x 6 Stories = 72 clicks through a 240px column. |
| 8 | Aesthetic and Minimalist Design | 3/4 | Genuine restraint - flat in flow, zero hex in any scoped component, disciplined type. Costs: rail duplicates the right column, 9 accent sites on one screen. |
| 9 | Error Recovery | 2/4 | `StalenessNotice` - the most important state here - is illegible in dark and painted in the wrong status colour. |
| 10 | Help and Documentation | 1/4 | Nothing explains what an Epic is, what INVEST measures, or what Approve binds. |
| **Total** | | **20/40** | **Needs work** |

## Design Specificity Verdict

Split, and the split is the finding: the details are this product's, the composition is anyone's.

Unliftable: `ProvenanceDetails` as a standing disclosure on every card; `StatusBadge` mapping provenance rather than severity; the regeneration dialog that names what survives; the Source Serif register that makes drafted prose feel drafted.

Category-default: the tree, the breadcrumb, the card with title + badge + Edit + Approve. More damning - the two things PRODUCT.md says a competitor could not copy are the two weakest things on screen. Uncertainty is not first-class: the rail says "Answer 4 blocking questions" while the backlog beneath reads Approved, Approved, Approved, with nothing reconciling them. Approval is not visibly separate from generation: `onApprove` fires from a header button with no summary of what it binds.

The one unmistakably product-specific composition decision is folding the tree into the journey rail. That thinking stopped at navigation and never reached the cards.

**Deterministic scan: clean.** Detector returned `[]` across all 13 components, exit 0, re-verified with `--no-config` to rule out suppression. `npm run build` and `npm run lint` both pass. Zero hex or rgba in any scoped `.tsx`.

**Visual overlays:** injected successfully on the app shell with a live contrast sweep in both colour schemes. Could not reach the breakdown routes live - those exist only under Playwright request interception against `src/test/fixtures.ts`. Breakdown numbers are pixel measurement plus token computation. Five findings excluded as false positives (subpixel antialiasing, fixed-chrome capture artifacts, one row captured mid-animation).

## Overall Impression

The foundation work landed: dark mode genuinely works, the token layer is respected, the register split does real perceptual work, the single-spine rail is executed well. What is missing is that the redesign fixed the frame and left the content model alone. A Product Owner still cannot answer "what needs me?" without opening every Story one at a time - which is the entire job. Biggest opportunity: surface the quality signal upward, not another visual pass.

## What's Working

1. **The single-spine rail.** `RailSlot`'s portal moves where the tree renders while leaving where it is fetched untouched - presentation-only fix to an IA problem. `BacklogTree` answers in `StageRail`'s vocabulary.
2. **The two-face register.** Public Sans for chrome, Source Serif 4 for everything the model drafted, applied to voice and criteria.
3. **`Button`'s `blockedReason`.** Gated primary keeps tab position, announces `aria-disabled`, renders its reason through `aria-describedby`.

## Priority Issues

### [P0] Two undefined space tokens put every disclosure under the target floor
`--space-9` and `--space-11` do not exist; the ladder is 1,2,3,4,5,6,8,10,12,16. Found independently by both assessments and verified live.
- `frontend/src/styles/02-breakdown-workspace.css:25` `min-height: var(--space-11)` -> invalid -> 20px
- `frontend/src/styles/02-breakdown-workspace.css:36` `min-height: var(--space-9)` -> invalid -> 22px

Every piece of evidence on this surface sits behind one of these. PRODUCT.md records 24px as settled and binding. Visible artifact: "Continue reviewing" (39px), "Edit" (39px), "More actions" (22px) in one row. Both still pass normative 2.5.8 via the spacing exception; they fail the project's own floor.

Fix: `var(--space-6)` on the disclosure summary, `var(--space-8)` + `padding: var(--space-2) var(--space-4)` on the inline one. Grep for other off-ladder values. Command: /impeccable audit

### [P0] StalenessNotice is illegible in dark and wearing the wrong status colour
`frontend/src/styles/01-foundation.css:236-237` hardcodes `#efc0b7` / `#84332d` on `--danger-soft`. In dark: ~2.0:1. It is red for staleness while `Card tone="warning"` paints the same card amber - two status vocabularies for one fact.

Fires at the exact moment Principle 4 exists to protect. A dark-theme PO sees effectively nothing; a light-theme PO sees red, which everywhere else means blocking/rejected. Appears in none of the seven captures, which is how it survived.

Fix: delete those rules and the `border-radius: 0` override in `04-modernist.css:82`; rebuild on `Card tone="warning"`. Command: /impeccable harden

### [P1] Quality findings are invisible above the Story route, so triage is impossible
`StoryQuality` is fetched per Feature but surfaced only inside one Story card. `RowStatus` and `FeatureRow` show provenance only. Two Stories look identical when one has 2 failed checks. Principle 1 says never bury an unresolved thing to look finished.

Fix: presentation-only, data already resolved. Failure count as `Badge tone="warning"` on `compact-story-list` rows, rolled up to `FeatureRow`, optional count into `RowStatus`. Command: /impeccable layout

### [P1] The rail's "viewing" marker recedes in dark and can hit the forbidden contrast pair
Viewed step marked `bg-surface-sunken`. In dark that is `#0C0E11`, darker than the `#111316` canvas - the inversion design-system.md §4.3 rule 3 forbids. `--ink-faint` on `--surface-sunken` measures 4.43:1, the one pair tokens.css documents as forbidden, now reachable because a blocked step can also be the viewed step.

Fix: mark viewing with a border or weight change rather than a sunken ground, or lift blocked+viewing to `--ink-muted`. Command: /impeccable polish

### [P1] The empty state offers a confident primary the rail says you cannot take
Full-accent Generate Epic while step 4 renders blocked and NEXT says four questions are outstanding. Three elements, three answers to "may I proceed?", and the loudest says yes.

Fix: pass the outstanding count into the empty state; if `generation.ok` is genuinely true, say why and drop the button to secondary. Command: /impeccable clarify

## Persona Red Flags

**Product Owner (primary).** Must decide unaided whether approvals mean anything while the rail reports 4 blocking questions. No Approve on the Story card and no explanation - it lives on /review. Approving the Epic binds content the button never shows. 7 Stories = 7 rail clicks against 2-line labels all starting with the same six words, no position, no next.

**Business owner, non-agile.** Meets "INVEST quality", "SPIDR recommendations", "Spike", "Paths", "Epic", "MVP / Later drop" with no definition and no help affordance. The team already proved it knows the fix - `StoryQualityPanel` translates `deterministic` -> "Rule-based check" citing Principle 2 - then prints "SPIDR" as a heading.

**Solution architect.** Architecture behind two differently-named disclosures at two levels ("System impact" inside the card, "Architecture mapping" floating outside it), all collapsed. "Which systems does this requirement touch?" means opening every Feature and Story.

## Minor Observations

- 8px misalignment: `lg:px-2` puts the rail column at x=288 against the page header at x=280. Six distinct left edges within 55px.
- Mobile rail shows 3 of 6 steps and the 4px themed scrollbar cue does not render in the capture.
- Breadcrumb's last crumb is the literal word "Story"; `aria-label="Selected backlog item"` where convention is "Breadcrumb".
- `ProvenanceDetails` renders a formatted timestamp in `--font-mono`; §5 reserves mono for IDs and checksums.
- Dead CSS still shipping: `.status-generated/.status-edited/.status-approved` with four hardcoded hexes. `.quality-panel` declared in two files. `--target-min: 24px` declared, referenced zero times.
- Adjacent live failures outside this surface: notification bell glyph 1.03:1 in dark (`06-source-documents.css:18`), `.text-button.danger-text` "Delete" 2.07:1 in dark.

## Questions to Consider

1. If the rail says step 2 is current with four blocking questions, why is the Backlog generable at all - and if that state is legitimate, why does no screen say so?
2. Should Approve exist on this surface at all, or should Epic and Feature approval move to /review where the evidence is?
3. The one genuinely product-specific decision was folding the tree into the rail. What would an "AI drafted this, a human must decide" card look like if designed from Principle 2 rather than inherited from the category?
4. Is INVEST a label or a filter? Would "2 things to check before this is ready to build" lose anything a PO needs?
