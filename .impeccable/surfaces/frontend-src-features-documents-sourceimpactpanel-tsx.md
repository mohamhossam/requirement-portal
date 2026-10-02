# Source lineage and change impact

Mode: Operate. A narrow extension of the existing Requirement clarification and document
governance surfaces. No new visual world, navigation tier or design-system decision.

## Direction contract

Make exact source lineage and affected content inspectable before the Requirement owner records
an impact decision. Direct citations remain distinct from indirect dependencies. Retaining
historical evidence requires a rationale; choosing revision remains unresolved until content is
revised or regenerated. Earlier decisions and approvals remain in history.

Inherit the current Public Sans UI typography, indigo action system, flat surfaces, shared Button,
native form fields and disclosures. The panel begins with an explicit review control; dependencies
load on request and support search, active-content filtering and bounded pages. Rows separate with
hairlines. Exact source identifiers and excerpts live in disclosures; review history retains actor,
time and rationale. At narrow widths, controls wrap and long source content breaks within its row.

## Documentation checkpoint — 2026-09-23

Source inspection covered:

- `frontend/src/features/documents/SourceImpactPanel.tsx` and `source-impact.css`.
- Integrations in `frontend/src/app/requirement/AnalysisView.tsx` and
  `frontend/src/app/LibraryGovernance.tsx`.
- `frontend/src/components/ui/Button.tsx`, `frontend/src/styles/tokens.css`, and the
  Public Sans declarations in `frontend/src/styles/index.css`.
- `PRODUCT.md`, `DESIGN.md`, `.impeccable/design.json`, and the existing
  `.impeccable/surfaces/frontend-src-app-librarypage-tsx.md` context.

Opened all three supplied final captures: `.impeccable/review/lineage-chromium.png`
(1440px), `lineage-responsive-chromium.png` (740px), and `lineage-mobile.png` (390px).
They show the expected clarification surface, populated direct/indirect dependency rows,
attributed review history and impact-decision controls. The mobile capture shows wrapped search
and pagination actions with content contained in the column. Exact-source disclosures are closed
in these captures; their content and semantics were checked in code.

The implementation uses semantic line tokens, existing controls and inherited typography; it
introduces no palette, font, responsive tier, shadow treatment or shipping raster asset. Decision
forms are conditional on the permission passed by the Requirement integration; document governance
uses the read-only view with a link to the Requirement review. Backend authorization, persistence
and approval preservation are outside this documentation inspection's evidence scope.

The handoff reports detector output `[]` and an independent finish-review disposition of `ship`
with no material UI findings at screenshots/code scope. This checkpoint did not rerun the detector,
browser or functional tests and does not broaden that verdict.

## Preserved system and existing drift

`DESIGN.md` and `.impeccable/design.json` are preserved. They describe the older Archivo Narrow,
oxblood, cool-paper system and older shell geometry; current tokens and this extension use
Public Sans, indigo and paper neutrals. The library surface brief already records this drift.
This ordinary extension neither approves a system change nor repairs that pre-existing mismatch.

## Related regression checkpoint — 2026-09-23

Inspected the shared drawer recipe in `frontend/src/components/Modal.tsx`: `max-w-full`
removes the user-agent dialog width cap while retaining its existing bounded desktop width.
Opened `.impeccable/review/source-drawer-desktop.png` (1440px) and
`source-drawer-mobile.png` (390px); the source drawer fits each viewport, with its existing
close control, source links and answer attribution visible.

Inspected `frontend/src/styles/06-source-documents.css`: catalogue cards constrain their
content track with `minmax(0, 1fr)`, wrap MIME metadata, and fold from three to two to one
column at the existing md/sm tiers. Opened `catalogue-desktop.png` (1440px) and
`catalogue-mobile.png` (375px) in the same review directory, including the replacement full-page
mobile capture. These show contained metadata and the expected desktop/mobile column layout
through the last mobile row. The records differ between desktop and mobile captures, so these
images do not establish content parity.

The handoff reports passing route-fit checks at eleven widths and passing navigation, focus
and header browser tests. It reports `ship` for the drawer and a final independent `ship` for
the catalogue with no material screenshot findings. The catalogue verdict covers screenshot
containment through the last row, not content parity, contrast or accessibility certification.
No browser or detector was rerun by the documenter.
These geometry corrections reuse the incumbent system. DESIGN.md, its sidecar and their
previously recorded drift remain unchanged.
