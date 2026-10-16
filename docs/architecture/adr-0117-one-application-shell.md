# ADR-0117 — One application shell for every route

Status: Accepted
Date: 2026-10-15

Supersedes ADR-0045, ADR-0047 and ADR-0050, whose decisions were made against the
pre-redesign chrome. Records what the UI redesign (Phases 0–10, PRs #46–#60;
`docs/slices/redesign-phase-*.md`) shipped in their place, so the ADR set matches
the code. ADR-0046 (single modal primitive), ADR-0048 (Tailwind utilities in a
named layer) and ADR-0049 (three breakpoints) stand unchanged; the redesign kept
and enforces all three.

## Context

The redesign's governing plan (`docs/ux-plan.md` §4) replaced the frontend's
chrome wholesale and noted that three accepted ADRs described chrome that no
longer exists. They were never formally superseded, so the record disagreed with
the code: `AGENTS.md` and `PRODUCT.md` cited ADRs 0045–0050 as binding while the
stylesheets and shell components carried comments saying 0045 and 0050 were gone.

- **ADR-0045** composed a Breakdown-specific shell with its own 280px navigator,
  while other stages kept the default shell — two applications in one.
- **ADR-0047** made a five-step horizontal journey stepper the shells rendered
  above the workspace.
- **ADR-0050** gave the old 64px header's global navigation its own wrapping row
  below `md`.

## Decision

- **One `AppShell` frames every route**
  (`frontend/src/components/shell/AppShell.tsx`): a fixed 56px top bar, a 240px
  collapsible sidebar that becomes a drawer below `md`, a skip link, and one
  `<main tabIndex={-1}>` that receives focus on route change. The seven
  page-level shells and the `breakdown-shell` are deleted. What survives of
  ADR-0045 inside the Backlog route's content is its substance, not its shell:
  route-selected detail, keyed editors kept mounted so drafts and version
  conflicts survive selection changes, and queries enabled only for the selected
  or expanded items.
- **The journey has six steps, rendered as a vertical stage rail.** One model,
  `frontend/src/app/requirement/journey.ts` — Source, Clarify, Knowledge,
  Confirm, Backlog, Review & approve — rendered by `StageRail` (a
  `<nav aria-label>` with `aria-current`), not a horizontal stepper. Review is a
  first-class step (`docs/ux-plan.md` §4 calls its promotion the highest-leverage
  IA change); History stays a panel, not a step. ADR-0047's principles carry
  over even as its five-step stepper goes: one model as the single source of
  steps, routes and status; blocked steps stay navigable; the step being viewed
  and the step the journey waits on are marked separately.
- **The top bar carries no navigation.** Brand, help, notifications, account and
  the one primary action (`frontend/src/components/shell/AppTopBar.tsx`); the
  sidebar is the only navigation. ADR-0050's wrapping header-navigation row is
  gone because there is no header navigation left to reflow.

## Consequences

- The record matches the code: `02-breakdown-workspace.css` and `AppTopBar.tsx`
  already said their ADRs were superseded, and now the ADRs say so too.
- Documents that cited "ADRs 0045–0050" as a block (`PRODUCT.md`) now cite
  0046, 0048 and 0049 plus this decision.
- The responsive and focus guarantees ADR-0050 introduced tests for are kept by
  the redesign's own suites (`frontend/tests/responsive-layout.spec.ts`,
  `frontend/src/styles/breakpoints.test.ts`).
- No domain, application, infrastructure, API, persistence or provider contract
  changes.

## Alternatives considered

- **Three separate superseding ADRs.** The three decisions fell to one change —
  the redesigned shell — and recording that change three times would say less,
  not more.
- **Leaving the ADRs "Accepted" and relying on code comments.** That is the
  state this ADR removes: two sources of truth that disagree.
