# CLAUDE.md

Engineering rules for this repository live in `AGENTS.md` and apply here in full. This file adds Claude-specific guidance on top of them.

## UI Redesign Rules

The frontend is undergoing a full UI/UX redesign. These rules apply to every change under `frontend/`.

- **Full redesign, not a refresh.** Do not preserve the existing look. Treat the current visual design as disposable; propose and implement a new one rather than patching what is there.
- **Presentation only.** Change layout, markup, styling, and interaction. Never modify hooks, services, state logic, data fetching, or API calls. If a redesign appears to need a logic change, stop and raise it instead of making the change.
- **Source of truth.** `docs/ux-plan.md` and `docs/design-system.md` govern the redesign once they exist. Read them before editing UI. Where they conflict with an existing component, the documents win.
- **Stack.** React + Vite (TypeScript). Follow the conventions already in `frontend/src/`.
- **Accessibility.** Meet WCAG 2.2 AA: contrast ratios, keyboard reachability and visible focus, focus never obscured, 24px minimum target size, semantic landmarks and headings, labelled controls, consistent help, and respect for `prefers-reduced-motion`.
- **List files before big edits.** Before a multi-file or cross-cutting change, enumerate the files you intend to touch and confirm the scope.
- **Build after each change.** Run the frontend build and keep it green:

  ```bash
  cd frontend && npm run build
  ```
