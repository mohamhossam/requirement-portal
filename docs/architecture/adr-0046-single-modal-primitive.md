# ADR-0046 — Single modal primitive

Status: Accepted
Date: 2026-09-18

## Context

Five dialogs had each grown their own behaviour. Two were native `<dialog>`
elements with near-identical hand-written logic (`WorkspaceDrawer`, and the
sources panel in `AnalysisSources`). Three were `div`/`form` elements carrying
`role="dialog"`, each missing something: the manual Story change dialog had no
focus trap, the governance dialog in `ApprovalWorkflowPanel` had neither a trap
nor any way out by keyboard, and `ConfirmDialog` implemented two different
behaviours selected by a `focused` prop — with a trap and focus restoration when
set, and neither when not.

That prop was not an unfinished thought. It meant "I am nested inside the
drawer", and its `stopPropagation` calls kept Tab inside the confirmation and
stopped Escape closing the drawer underneath. ADR-0045 records that the focused
Breakdown workspace uses native drawers whose focus restoration and tab trapping
are tested; the same guarantees were absent from most of the other dialogs.

## Decision

One primitive, `components/Modal.tsx`, owns modal behaviour: a native
`<dialog>`, `showModal()` on mount, `close()` and focus restoration on unmount,
Escape through the native `cancel` event, outside-click via the bounding-rect
check, and a focus trap. The five dialogs keep their own content, CSS class and
public props, and delegate behaviour to it.

Nesting is the top layer's job rather than ours: a second `showModal()` stacks
above the first, traps its own Tab and takes Escape first. `ConfirmDialog`'s
`focused` prop is therefore removed.

Two consequences were not obvious and are recorded so they are not re-litigated:

- **A portal is not about stacking.** The top layer paints above everything
  regardless of DOM ancestry or z-index, so nothing needs a portal to be seen.
  What a portal changes is which descendant selectors match. The drawer renders
  inside `.breakdown-shell`, whose `.breakdown-shell .button` rule restyles every
  button beneath it, so the drawer has always escaped to `document.body` to keep
  the global button style. `Modal` therefore takes a `portal` flag and each
  caller keeps the placement it had. A confirmation raised from inside the
  drawer stays a descendant of it, which its smoke test asserts.

- **Initial focus cannot use React's `autoFocus`.** React focuses the element
  imperatively instead of setting the attribute `showModal()` looks for, so
  `showModal()` then moves focus to the first control anyway. Dialogs whose
  opening focus is not their first control pass an `initialFocus` ref.

## Consequences

The manual Story change dialog and the governance dialog gain a focus trap, and
the governance dialog gains Escape. `ConfirmDialog`'s hardcoded `confirm-title`
and `confirm-message` ids become `useId`, ending duplicate ids whenever two
confirmations are mounted at once. `.dialog-backdrop` is deleted in favour of
the native `::backdrop`.

jsdom implements `<dialog>` but not `showModal`, so the shim that previously sat
in one test file moves to `src/test/setup.ts`. The focus trap skips controls with
no layout box and jsdom reports none, so the trap is inert under unit tests by
design; `tests/analysis-sources.spec.ts` and `tests/focused-breakdown.spec.ts`
assert it in a real browser.

No domain, application, infrastructure, API, persistence or provider contract
changes. ADR-0045 stands; this generalises its modal guarantees to every dialog.
