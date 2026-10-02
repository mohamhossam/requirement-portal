# Shared document library

Mode: Operate. This extends Documents inside the existing visual system; no new navigation tier
or visual identity is introduced. The approved implementation brief defines upload, side-by-side
review, selections, publication states and citations. No design alternatives are needed.

## Direction contract

THESIS: Make the difference between private uploaded evidence and owner-approved shared passages
visible at every step. Ingestion and publication are separate decisions.

OWN-WORLD: Inherit the application's current Public Sans type, indigo action accent, flat surfaces, controls and
three breakpoints. No new font, raster asset, hero or dashboard metrics.

STORY: Upload, compare extracted content with the original, correct/exclude, save review, approve,
then search exact published passages. Withdrawal is explicit and asks for a rationale.

FIRST VIEWPORT: Existing application shell; library title and attachments return link; a narrow
upload/search/list column beside a wide review region. Narrow screens stack those columns.

FORM: Precisely specified Documents extension; no concept seed. Existing reusable controls,
actor-scoped query cache, bounded passage pages, source links and mixed-direction text.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict,
DESIGN.md, and every shipping raster carrying its provenance.

## Bounded reference context checkpoint — 2026-09-21

The saved-chunk preview and shared-search results now keep the exact citable passage in the primary
reading flow and place same-section approved context in a compact disclosure. The disclosure names
its interpretive role, retains automatic text direction and uses the existing flat inset surface.
No navigation, visual identity or responsive breakpoint changed.

Functional desktop/narrow browser cases passed and the detector returned no findings. The browser
run produced both width screenshots, but manual image inspection could not be completed because the
session's Windows sandbox helper failed in both the local viewer and computer-use fallback. This is
recorded as unavailable validation, not a visual certification.

## Table corpus build checkpoint

Extend the incumbent Operate surface with preview → approve/build → explicit activation.
Keep the previous publication and pending build states visible together. Activation explains
that previous citations require reconciliation. Pending builds can be discarded independently.
Unsaved passage changes block source-dependent actions. Existing controls, responsive layout,
typography, colors and actor-scoped query cache remain authoritative; no new visual world.

Validation: 267 frontend unit tests passed; lint, typecheck and production build passed. The
library/reference browser group passed eight cases; the final build flow passed again at 1440px
and 390px with unsaved replacement protection. The detector returned `[]`. The main agent opened
the desktop/mobile full-page, controls and dirty-replacement captures under `.impeccable/review/`.
Independent finish review requested one fix: disable replacement upload while passage edits are
dirty and explain saving first. The verdict pass scored that specific fix resolved and returned
`ship` at the fix-list scope; this is not whole-surface certification. Existing source-dialog
geometry failures and DESIGN.md drift remain outside this extension.

Documenter verification: CorpusBuild and the replacement guard reuse incumbent buttons, native
disclosures/checkboxes, line-separated passages and the existing 900px column collapse. No new
font, palette, responsive tier, component styling or shipping raster asset was introduced;
DESIGN.md and `.impeccable/design.json` remain unchanged. Source inspection and desktop/mobile
control captures confirm distinct build/activation actions and a visible explanation for the
dirty replacement gate. Pre-existing documentation drift remains: root DESIGN.md and its sidecar
describe Archivo Narrow/oxblood and older geometry, while current tokens and this surface use
Public Sans/indigo. This extension neither approves nor repairs that drift.

## Ownership and dependencies checkpoint

Extend the incumbent Operate workspace with explicit owner handover and a lazy dependency list.
Reuse the existing typography, flat sections, native forms and responsive layout. The owner can
inspect current/historical Requirement references before changing evidence, then transfer with a
known-user selection, rationale and acknowledgement of losing private access. Unsaved review
changes block handover. No new visual identity, raster assets or navigation tier.

Checkpoint verification: the user selected ownership transfer and dependency visibility, excluding
delegated document reviewers. Member-filtered references explicitly warn they are an incomplete
workspace impact view. Known-user transfer requires rationale and access-loss acknowledgement;
unsaved passage edits block handover. Changing actor search clears recipient and acknowledgement,
and submission checks current successful results. Immutable history preserves uploader/approver
attribution. The fresh finish reviewer found the actor-search edge case; its verdict marked that
single fix resolved and returned ship at the fix-list scope. Desktop/mobile browser flows passed
and all four final captures were opened. Independent documenter verified existing tokens, controls,
responsive layout and all captures: no new design-system decision or shipping raster asset.
DESIGN.md and its sidecar remain unchanged; their pre-existing drift is not repaired here.

## Search/grounding checkpoint — 2026-09-22

Unified search extends the incumbent Operate workspace with a native scope selector and
line-separated results explicitly labelled Requirement evidence or Published document. Document
links retain publication, version, extraction revision and passage identity; visible copy keeps
publication separate from the Requirement owner's applicability decision. Existing Public Sans,
indigo controls, passage styling and narrow-screen column stacking are reused.

Independent documentation verification inspected LibraryPage.tsx, library.css, current tokens
and both final `grounding-search-chromium.png` and `grounding-search-responsive-chromium.png`
captures under `.impeccable/review/`. The handoff records two passing grounding browser tests,
detector output `[]`, and a ship verdict limited to the reviewer's single responsive fix.
No new visual system or shipping raster asset was introduced. DESIGN.md and its sidecar remain
unchanged; their pre-existing Archivo Narrow/oxblood and geometry drift is outside this extension.

## Ingestion source-comparison checkpoint — 2026-09-22

Preserved the incumbent Operate surface. Each private review passage now has a lazy source-raster
comparison control; unsupported preview regions remain explicit. Scoped warning explanations sit
with their affected content. Original/extracted text and editable reviewed text retain the existing
two-column layout and narrow stacking. Source images are bounded within the column. Desktop and
740px browser checks and screenshots were inspected; no new visual system or tokens introduced.
