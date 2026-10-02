# ADR-0050 — The header's navigation gets its own row

Status: Accepted
Date: 2026-09-19

Amends ADR-0049 on the one thing it left open. Everything else in 0049 stands.

## Context

ADR-0049 recorded, and did not fix, that the header's global nav collided with
the notification bell and the actor menu between 640px and 900px. Measuring the
header on its own at twelve widths found the collision was wider than that:

| Width | What overlapped |
|---|---|
| 360 | the brand sat under the bell and the actor menu |
| 640–800 | the nav sat under the bell and the actor menu |
| 900–980 | the nav sat under the bell |

Three bands, one cause: `.app-header` is a `flex-wrap: nowrap` row whose
children all have hard minimum widths, so when the total exceeds the viewport
the items overlap rather than reflow.

Below 640 there was also no primary navigation at all. The sidebar is hidden
below 900 and `.global-nav` was hidden below 640, which left the brand link to
`/` as the only way out of a page on a phone.

The rule meant to solve this — `.global-nav { order: 3; width: 100% }` at 760px
— was deleted in 0049 for being unable to work: the nav was a child of
`.header-leading`, so it could take a row of its own only within that inner flex
row, which is not a row of the header.

## Decision

`.global-nav` becomes a sibling of `.header-leading` rather than a child, and
below the `md` tier the header wraps and gives it the row under the brand.

The header is `position: sticky` below `md` and `fixed` above it, so growing a
row is safe below and not above — which settles where each part may give way:

- **Below `md`** the header wraps. The nav takes its own row, centred, with a
  top border. `.header-slot` wraps onto a row of its own too when the brand and
  the slot cannot share one, which is what fixes 360.
- **Above `md`** the header must stay one row, so the actor's name and email now
  appear at `lg` rather than at `md`. They need about 100px the header has not
  got until then, and their arrival at 900 was the whole of that band's
  collision. Below `lg` the persona select still names the actor.
- The nav is no longer hidden below `sm`. It has a row of its own now, so there
  is no reason to take it away, and phones get primary navigation back.

`.app-header` changes from `justify-content: space-between` to `flex-start` with
a 32px gap, because the nav is a third child and `space-between` would spread
all three. `.header-slot`'s existing `margin-left: auto` keeps it to the right,
which is what actually held the layout before.

## Consequences

The desktop header is unchanged, measured rather than assumed: at 1440px the
only difference in the layout fingerprint is `.header-leading` shrinking from
407px to 142px, because the nav left it. The nav, brand, bell, actor menu and
action button are at the same coordinates as before.

Nothing overlaps at any of sixteen widths from 360 to 1440, and no page
overflows. The header is 64px tall above `md` as before, 99px from 640 to 880
(two rows), and up to 157px at 360 (three rows) — which is a lot of chrome on a
phone, and still the first time that viewport has had working navigation.

`tests/responsive-layout.spec.ts` gains a fourth test asserting that no two
header items share a row and overlap, and that navigation is reachable, at every
tier width plus 360 and 480. It was checked against the defect: removing the
wrap fails it at 360.

No domain, application, infrastructure, API, persistence or provider contract
changes.
