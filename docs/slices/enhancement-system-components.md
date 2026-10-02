# Enhancement — System components

Requested 2026-10-01 by the product owner: "in the architecture catalogue each system can have
multiple components under it, and each component can have different capabilities". It is feature
work outside the UI redesign's presentation-only rule. The plan was approved with that exception
named, as for capability domains. Decisions taken with the product owner:
- components are a reference from each capability, not strict nesting;
- components have an id, a name, an Arabic name, a description, aliases and a technology;
- they are show-only in mapping;
- document reading proposes them in this slice.

## Objective

Let a system be described as the parts it is built from, with each capability placed in the part
that delivers it. Carry that structure through editing, files, document reading, review, the
dossier, impacts and export, without changing what gets mapped.

## User Outcome

- **Maintainers:**
  - add, edit and remove a system's components in the system dialog;
  - place each capability in one;
  - a component that still delivers capabilities says which, and cannot be removed until they
    move;
  - files carry components, and older files still import.
- **Document reading** suggests components, and capabilities that name their component.
  - A capability waiting for a component it names is marked "Needs its component first".
  - Accept-all adds components before their capabilities.
- **Everyone** reads a system's "What it does" grouped by component, with each component's
  technology, other names and description, and "Not in a component" last.
- **Mapped Features and Stories** show each matched capability's component.
- **Exports** carry each capability's component.

## In Scope

Components on systems; capability placement; invariants; files; the diff; suggestions and
extraction; impact fields; export `1.4`; and the editor, dossier, suggestion and impact UI.

## Out of Scope

- Component names as matching or retrieval evidence (ADR-0092, Consequences).
- Components shared across systems, and dependencies between components.
- A separate Components workbench view.
- Components in the packaged seed. No source records them, and inventing them would be an
  invented business rule.

## Domain

- `SystemComponent` and `SystemDefinition.components`.
  - Ids are unique and labels are unique per system.
  - `SystemDefinition.component()`.
- `KnowledgeCapability.component_id`, which must name a component of its own system.
- `SystemCapability.component_id` and `component_name`, present together.
- The diff:
  - `ChangedItem.COMPONENT`, keyed `system/component`;
  - a capability `component` field.
- Candidates:
  - `CandidateKind.COMPONENT`;
  - `CandidateContent.component_id`, `description` and `technology`, each limited to the kinds it
    applies to;
  - `CandidateMatch.NEEDS_COMPONENT` and `find_component()`.
  - `apply_candidate` adds a component or fills in an existing one. It places a capability that
    has no component and never moves one.

## Application Use Cases

- `ResolveArchitectureKnowledge` places each capability's component from the pinned release.
- `ProposeCatalogueChanges` passes component names in `KnownSystem.components`.
- `DecideCatalogueCandidate.accept_all` orders system → component → capability.
- `ExportBreakdown` sets `ExportCapability.component`.

## Ports

- `KnownSystem.components`.
- `ExportCapability.component`, with `EXPORT_SCHEMA_VERSION = "1.4"`.

## Adapters

- **Catalogue files:**
  - YAML and JSON: `components` and a capability's `component` key;
  - Excel: a Components sheet and a Capabilities `component_id` column;
  - all optional.
- **Extraction:**
  - `catalogue-extraction-v4`. `main`'s structured-documents plan names a "prompt v4" for its
    slice 1c; that slice moves to v5;
  - `ChangeOutput` gains `component` and `technology`, and kind `component`;
  - `FakeCatalogueExtractor` reads `Component: Name [technology]` and
    `Capability: Name (phrases) @ Component`.
- **Impact payloads:** optional `component_id` and `component_name`.
- **Generation guidance** strips both, so the prompts are unchanged.
- **The backlog Excel export** has a `capability_components` column.

## API

- `SystemComponentSchema`.
- `SystemDefinitionSchema.components`. Omitting it reads as no components.
- `KnowledgeCapabilitySchema.component_id`.
- `CandidateContentSchema`: `component_id`, `description` and `technology`.
- The enums: `CandidateKind.component`, `CandidateMatch.needs_component` and
  `ChangedItem.component`.
- `SystemCapabilityResponse`: `component_id` and `component_name`.
- No new routes.

## UI

- **`SystemDrawer`** (the drawer redesigned in #82; this slice was merged onto it):
  - a Components section between Identity and Capabilities. Each component is a card that folds
    to its name, ID, technology and "Delivers n capabilities", and expands to name, ID (filled in
    from the name), Arabic name, technology, other names, what it does, and the capabilities it
    delivers;
  - each row's form key keeps capabilities linked while its ID is edited;
  - Remove stays blocked while the component delivers capabilities, and says so;
  - each capability card shows its component and has a Component select, disabled with a reason
    when the system has none;
  - the unsaved-changes check covers components.
- **`SystemsEditor`:** a Components column in the systems table.
- **`CatalogueBrowser` dossier:** "What it does" is grouped by component, with "Delivers (n)"
  under each and "Not in a component" last.
- **`SuggestionList` / `SuggestionEditor`:**
  - a Components group, with "Delivered by …" on capabilities;
  - "Needs its component first";
  - editing a component suggestion, and a component picker on capability suggestions.
- **`DiffList` and labels:**
  - component changes come after systems and nest under an added or removed system;
  - list keys include the item type, because component and capability keys share their shape.
- **`ArchitectureImpactPanel`:** each capability chip shows its component.
- **`CatalogueFileImport`:** the copy names components and capabilities.

## Business Rules

- A capability belongs to at most one component, and only one of its own system.
- Components organise; they never select a system.
- Suggestions never move a placed capability.

## Tests

- **`tests/unit/test_system_components.py`:**
  - invariants and blocked removal;
  - the diff;
  - every file format, plus older files and errors that say where they are;
  - mapping placement;
  - payloads, fingerprints and prompts;
  - classifying and applying suggestions;
  - kind-limited candidate fields;
  - extraction through the structured and offline readers;
  - the API from suggestion to accept-all;
  - schema round-trips;
  - export.
- **Updated:**
  - `test_catalogue_files.py` (the template sheets);
  - `test_backlog_export.py` and the PostgreSQL export assertion (`1.4`);
  - four extraction test builders, for the new output fields;
  - `frontend/openapi.json` and `schema.d.ts`.
- **Frontend:**
  - `ArchitectureCataloguePage.test.tsx`: the component editor (blocked remove, adding, placing,
    renaming the ID), the grouped dossier, and component suggestions;
  - `ArchitectureImpactPanel.test.tsx`: the component on a chip.

## Acceptance Criteria

- [x] A maintainer adds components to a system and places capabilities in them. A component in
      use cannot be removed and says why.
- [x] Files round-trip components in YAML, JSON and Excel; older files import.
- [x] Document reading suggests components. A capability naming a missing component waits for
      it, and accept-all applies both in order.
- [x] The dossier groups capabilities by component.
- [x] A mapped capability carries its component; fingerprints and prompts are unchanged.
- [x] Exports carry the component (`1.4`).

## Validation Evidence

- **Backend:**
  - `pytest tests/unit`: 1,826 passed;
  - `ruff check .`, `ruff format --check .` and `mypy src tests` (585 files) are clean;
  - `lint-imports`: 7 contracts kept.
- **Frontend:** `api:check`, `lint`, `typecheck`, `test` (598 passed) and `build` are green.
- **Browser, fake API and in-memory store** (draft "Components trial"):
  - added Quote engine (Microservice, CPQ) and Agent desk to BCRM, and placed "Assisted sales,
    quoting, and order capture" in Quote engine;
  - the saved release holds both components and the placement;
  - Remove on Quote engine is blocked, with "Delivers Assisted sales, quoting, and order
    capture…";
  - the dossier groups by component, and the change line reads "2 component changes · 1
    capability change";
  - an uploaded text document suggested "Pricing service" (new), "Discount approval"
    (`needs_component`) and "Quote follow-up" (placed in the existing Quote engine);
  - accept-all added the component first and placed both capabilities;
  - at 375px nothing scrolls sideways.
- **Impeccable critique** (dual-agent): baseline 24/40, with two P1s and three P2s.
  - **Detector:** the CLI scan found nothing. In the browser overlay, one in-scope flag (nested
    cards on the Components fieldset) is a partial false positive inside a top-layer drawer; the
    other seven are pre-existing.
  - **P1, dossier:** "What it does" was squeezed into a 222px half column. It is now a full-width
    row with one row per component (two columns from a 36rem container), and domain and phrases
    on one line.
  - **P1, drawer length:** each component leads with name and ID and a "Delivers …" line, and
    the rest sits behind "More about …". Legends are section headings. BCRM's drawer went from
    3,355px to 2,737px.
  - **P2, hierarchy:**
    - component names use the title style;
    - the off-ladder 2px rule became hairline dividers;
    - the count reads "3 capabilities in 3 components".
  - **P2, blocked Remove:**
    - the shared `Button` now gives `aria-disabled` the disabled look with hover pinned. This
      also corrects the domains editor's blocked Remove, which the primitive's comment already
      claimed looked disabled.
    - The reason gives a count and names "Not in a component".
  - **P2, labels and landmarks:**
    - the visible label is "Remove component", and `aria-label` carries the name;
    - dossier components are headings in a list, not landmarks;
    - a new component's name takes focus.
  - Rechecked live at 1440 and 375px, with no overflow. Snapshot:
    `.impeccable/critique/2026-10-01T07-54-53Z__c-features-catalogue-cataloguebrowser-tsx-48cbaf9e.md`.
- **`npm run test:smoke`** (ports 8020/4183): 73 passed, 5 skipped, and about 25 specs failed.
  - The failures are spread over the library, review flow, ingestion, focused breakdown and
    catalogue specs.
  - The ones checked wait for copy the redesign has already changed on `main`, such as "New
    draft from active release" and "Maintainer access is required.". Neither string appears
    anywhere in `frontend/src`.
  - No failing spec exercises components. The smoke suite needs its own refresh; it is raised
    as a separate task.
- **Not run:**
  - the PostgreSQL integration suite (only its export-version assertion changed);
  - a live-model extraction check;
  - a browser check of a mapped Feature's chip, which the unit and component tests cover.

## Deferred

- **Moving capabilities from a component's side**, with "Move to…" and bulk assignment. The
  product owner chose a follow-up slice on 2026-10-01: it is editor behaviour, not presentation.
  This slice adds the read-only "Delivers …" line instead.
- **An unsaved-changes guard on the system dialog's Cancel**, which today drops edits without
  asking (pre-existing, raised by the critique). It is a state-logic change for the same
  follow-up.
- **Making each component's ID from its name.**
- **Component names as mapping evidence** (ADR-0092, Consequences).
