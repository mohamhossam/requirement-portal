# ADR-0047 — Persistent journey stepper

Status: Accepted
Date: 2026-09-18

Amends ADR-0045 on one point. Everything else in 0045 stands.

## Context

ADR-0045 composed a focused Breakdown workspace and removed the journey bar from
it, leaving a `<details>` menu whose summary read "Breakdown" — the name of the
place you were already in. The focus argument was sound for the content rail: a
backlog navigator plus route-selected detail is easier to work in than every
level at once. It was extended, without a separate decision, to the sense of
place.

Reading the stepper to generalise it turned up three defects in the version the
standard shell was still rendering:

- Six labels mapped onto five routes: *Analyse* and *Clarify* both linked to
  `/clarify`.
- `.journey-header ol` is `grid-template-columns: repeat(5, 1fr)`, so the sixth
  step wrapped onto a second row. Measured at HEAD: six steps, two rows, 114px
  tall. The CSS was written for five steps and a sixth label was added later.
- No step could show as blocked, so *Confirm* looked available while the
  knowledge screen was outstanding and *Breakdown* looked available before
  confirmation.

## Decision

One journey model, `src/app/requirement/journey.ts`, is the single source of the
five steps, their routes and their status, and it is rendered in both shells:
the full bar above the standard workspace, and a compact row in the focused
Breakdown header in place of the `<details>` menu.

Analyse and Clarify become one step, because they are one screen — the panel's
own eyebrow reads "Analyse / Clarify / Confirm". That gives five steps and one
route each, which is what the grid was always written for.

The stepper marks two things separately, because they come apart: the step the
journey is waiting on, and the step being viewed. On the Breakdown route before
confirmation those are *Analyse* and *Breakdown* respectively, and showing only
the first leaves a person unable to tell where they are. They carry
`aria-current="step"` and `aria-current="page"` accordingly.

Blocked steps stay navigable. Each destination already explains its own state —
`breakdown-locked` says so in words — which serves a person better than a
disabled control that cannot say why.

The model also derives what the current step is waiting on, shown in the
workspace header. That is a UI affordance derived from data the workspace has
already loaded, and deliberately not the backend's `NextAction`, which lives on
the worklist read model the workspace does not fetch. The module says so, so it
is not later mistaken for authoritative.

## Consequences

The focused Breakdown workspace regains a sense of place at the cost of one row
of chrome in its header. ADR-0045's content rail, mounted editors, drawers and
route-selected detail are unchanged, as are its tested focus restoration and tab
trapping.

The stepper is one row again rather than two. The active step's number was white
on a pale badge and therefore invisible; that is fixed in the same pass.

No domain, application, infrastructure, API, persistence or provider contract
changes.
