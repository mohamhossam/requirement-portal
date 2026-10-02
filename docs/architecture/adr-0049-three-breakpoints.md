# ADR-0049 — Three breakpoints, named once

Status: Accepted
Date: 2026-09-19

## Context

The frontend folded at seven widths — 640, 700, 760, 850, 899, 900, 1050 —
spread across eight stylesheets, with no recorded reason for any of them. 899
and 900 were a single pixel apart in different files, so at exactly 900px the
focused Breakdown showed its desktop backlog while the sidebar had already gone.

Measuring before editing changed what this decision is about. Two findings:

**Forty-four of the 262 declarations inside those queries did nothing.** A media
query adds no specificity, and these files are ordered by import, so a plain
rule in a later file beats a media rule in an earlier one at every width.
`08-stitch-foundation.css` sets `.app-header { height: 64px; flex-wrap: nowrap }`
as a base rule, which killed the phone header height in `01`, the wrapping
header in `07`, and the header's entire 760px reflow. The app header has never
changed shape at any width. Twenty-four of the 760px block's thirty-one
declarations were dead: that tier was a fossil, not a tier.

**Four routes scrolled sideways, all of it invisible to the test suite.** The
`chromium` project runs at 1440 and `responsive-chromium` at 740, so nothing had
ever rendered the band between. The reports page carried a 254px left margin for
a sidebar hidden below 900, so every phone scrolled 230px sideways. The analysis
workspace was 1353px wide from 950 to 1350. The dashboard needed 946px from 900
to 945. The intake page hid its guidance panel off-screen from 1050 to 1260.

## Decision

Three tiers, and no others:

| Tier | Width | What folds |
|---|---|---|
| `lg` | 1050px | The widest multi-pane layouts: source rail, intake support column |
| `md` | 900px | The sidebar goes; two-column content becomes one |
| `sm` | 640px | Phone: headings stack, nav collapses, cards go full width |

They are declared once, in `src/styles/index.css`'s `@theme` block, as
Tailwind's own `--breakpoint-md` and `--breakpoint-lg` (`sm` is already 40rem).
Every stylesheet reads them through `theme(--breakpoint-…)`, which Tailwind
resolves at build time — a custom property cannot be used in a media query, but
this can. So a stylesheet and a `max-md:` in a component cannot drift apart, and
`Toaster.tsx`'s `max-[640px]:` became `max-sm:`.

Queries are written `width < tier` rather than `max-width: tier`, matching
Tailwind's `max-*` variants exactly, so the tiers partition cleanly with no
one-pixel overlap. Consequence: at exactly 640px and exactly 900px the app now
renders in the wider tier. Both were measured; both fit.

Two tiers were removed rather than reassigned, by making the layout that owned
them size itself: `.ask-question` is a wrapping flex row instead of four fixed
tracks with an 850px query, and `.approval-stepper` wraps instead of having a
700px query to itself. A layout that adapts needs no width of its own. The same
move fixed three of the four overflows; `.worklist-toolbar` and
`.worklist-table` got the fourth.

Dead declarations were deleted, not revived. Reviving forty-four rules would
change how the app looks in forty-four places at once, which is a different
decision. The one exception is `.review-layout`'s 1050px fold, re-declared where
it can win because its absence was what made the analysis workspace overflow.

`src/styles/breakpoints.test.ts` asserts that every width query names one of the
three tiers and that no raw pixel width appears in one. A fourth tier is
allowed, but as a decision recorded here rather than a rule dropped into
whichever stylesheet was open. The comment asking for restraint at the top of
`index.css` did not hold for four slices; this does.

`tests/responsive-layout.spec.ts` renders seven routes at seven widths across
the band no project covered, asserting that pages fit, navigation stays
reachable, the rail folds on the right side of `lg`, and the stepper stays one
row. It runs in one project, because it sets its own viewports.

## Consequences

Verified by layout fingerprint: x, width, display, grid-template-columns,
flex-direction, flex-wrap, position and overflow-x for every classed element,
seven routes at twenty-two widths from 360 to 1440. Screenshots were useless
here — the fixture's ids and relative timestamps differ between runs — while the
fingerprint is stable run to run (two captures of HEAD, 6955 measurements, zero
variance).

Deleting the dead declarations changed nothing at all: 6955 of 6955 identical.
No route overflows at any of the twenty-two widths. At 1440px the only
differences are `.ask-question`'s first column growing 6px, and the worklist
table and toolbar gaining a scroll container and a wrap they do not need there.
The 760–900 band changes the most, which is the point: it now folds like the
tier it was already half inside.

The smoke suite goes from 2.8 to 3.8 minutes for the new coverage.

Known and not addressed here: between 640 and 900 the header's nav collides
with the actor menu. `07`'s `.global-nav { order: 3; width: 100% }` was written
to put the nav on its own row in a flat header, which generation three nested
inside `.header-leading`; it can no longer do that, and all it did was squeeze
the brand onto two lines, so it is deleted. Giving the nav its own row again
needs a change to the header component and a look at what belongs in it, which
is not a breakpoint decision.

No domain, application, infrastructure, API, persistence or provider contract
changes.
