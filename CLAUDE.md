# CLAUDE.md

Engineering rules for this repository live in `AGENTS.md` and apply here in full. This file adds Claude-specific guidance on top of them.

## UI Rules

The full UI/UX redesign shipped (Phases 0–10; `docs/slices/redesign-phase-*.md`, ADR-0117). The frontend is now maintained within that shipped design, not redesigned again. These rules apply to every change under `frontend/`.

- **The shipped design governs.** `docs/ux-plan.md` (§4 onward: scope decisions, screens, routes, IA) and `docs/design-system.md` record the design the code implements; `DESIGN.md` records the visual system as built. Read the relevant sections before editing UI. Where a document contradicts the shipped code, do not silently diverge either way: fix the document when the code is the deliberate state, and raise it when it is not.
- **Extend, don't fork.** Build new UI from the existing primitives (`frontend/src/components/ui/`), tokens (`tokens.css`), the single `Modal`, and the named CSS layers. No new hex values, breakpoints, shells, or one-off styles — the style tests (`frontend/src/styles/*.test.ts`) enforce this; keep them green.
- **Presentation changes stay presentation.** A styling or layout change must not casually rewrite hooks, services, state logic, data fetching, or API calls. When a UI task genuinely needs a logic change, it is ordinary engineering work under `AGENTS.md` (tests, gates, scope agreed first) — not something to smuggle into a restyle, and not something to ban outright.
- **Stack.** React + Vite (TypeScript). Follow the conventions already in `frontend/src/`.
- **Accessibility.** Meet WCAG 2.2 AA: contrast ratios, keyboard reachability and visible focus, focus never obscured, 24px minimum target size, semantic landmarks and headings, labelled controls, consistent help, and respect for `prefers-reduced-motion`.
- **List files before big edits.** Before a multi-file or cross-cutting change, enumerate the files you intend to touch and confirm the scope.
- **Build after each change.** Run the frontend build and keep it green:

  ```bash
  cd frontend && npm run build
  ```
