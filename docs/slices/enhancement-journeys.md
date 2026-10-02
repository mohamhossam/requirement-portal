# Enhancement — Journeys

Requested 2026-10-01 by the product owner. This is slice 3c of the structured-architecture-document
plan, stacked on 3b, and is recorded in ADR-0096. `SMB_Product_Architecture_Explorer_v4.md`
describes Business Pro Plus › New Activation:
- 18 activities;
- 7 flow rules;
- 18 integrations;
- a mermaid diagram.

None of it had a place in the catalogue.

**Scope.** The product owner chose the full scope (model, files, changes, evidence, API, a browse
view with a drawn flow, and a hand editor) and confirmed the file list on 2026-10-01. **This slice
includes frontend feature work beyond the presentation-only rule in `CLAUDE.md`.** The presentation
follows `docs/design-system.md`:
- labelled fields with errors beside them;
- table headers;
- the drawing as an image with a summary and a text table beside it;
- dashed and labelled marks, not colour alone;
- reduced motion respected;
- tokens only.

## Objective

A version of the catalogue holds the journeys that fulfil its offerings' orders: the activities in
order, the systems that perform them, the exceptions and side tracks, and how each activity hands
over. The flow is drawn from them.

## User outcome

- **A Journeys view.** For each journey:
  - its offering and order type;
  - an ordered activities table;
  - the drawn flow;
  - its decisions, loops and parallel tracks in words;
  - an integrations table.

  A system opens its dossier.
- **Edit manually.** A maintainer adds, edits and removes journeys.
  - Activities fold to one line each.
  - Rules and integrations choose from the journey's activities.
  - The order type follows the chosen offering.
  - Errors appear beside their fields.
- **The flow is never drawn by hand.** It is derived from the activities and rules. For the
  reported journey it is the document's 21 arrows.
- **Protection.** A system, offering, order type or component that a journey names cannot be
  removed. The message says which journey and activity name it.
- **Files.** Catalogue files carry journeys: YAML/JSON `journeys`, and four Excel sheets. Errors
  name the row.
- **Review of changes.** It names which parts of a journey changed.
- **Mapping.** Requirement mapping can retrieve a journey's systems through its evidence.

## In scope

The domain model and derived flow, checks, files, diff, evidence chunk, API, browse view, flow
drawing and editor listed above.

## Out of scope

- Reading journeys from documents (slice 3d).
- Journey context on impacts (slice 3e).
- A general graph layout.

## Domain

- `domain/architecture/journeys.py`:
  - `Activity`, `FlowRule`/`FlowRuleKind`, `ActivityIntegration` and `Journey`;
  - `activity_order`;
  - `journey_edges` and `JourneyEdge`;
  - `check_journeys`.
- `ArchitectureKnowledge.journeys`.
- `ChangedItem.JOURNEY`.
- `products.check_source` is now public, so journeys share it.

## Application

- `ManageArchitectureKnowledge.update` takes `journeys`. File import carries them.
- `BuildArchitectureIndex` writes one `journey <id>` chunk per journey.

## Ports

- `CatalogueContent.journeys`.

## Adapters

- `catalogue_files.py`:
  - YAML/JSON `journeys`;
  - the Excel `Journeys`, `Activities`, `FlowRules` and `ActivityIntegrations` sheets;
  - each part names its own row when refused.
- `knowledge_yaml.py` loads journeys.

## API

- `JourneySchema` and its parts, with derived `edges` on the way out, ignored on the way in.
- `KnowledgeReleaseResponse.journeys`.
- An optional `DraftUpdateRequest.journeys`.
- Regenerated OpenAPI types.

## UI

- `api/knowledge.ts`: types, and `save` sends `journeys` when known.
- `JourneysView.tsx` and `JourneyFlow.tsx`: browse and flow.
- `JourneysEditor.tsx` and `JourneyDrawer.tsx`: the editor.
- `ArchitectureCataloguePage.tsx`: the Journeys view.
- `DraftJourney.tsx`: the editor under Edit manually.
- `labels.ts`: rule labels and number order.
- `DiffList.tsx`: the journey item.

## Tests

- **`test_journeys.py`:**
  - the reported journey's shape gives exactly the document's 21 arrows, with activities ordered
    as numbers;
  - journeys refusing contradictions;
  - systems, offerings, order types and components that cannot be removed while named;
  - every format round-trips a journey and its flow;
  - workbook errors name the rule's row;
  - the diff;
  - the evidence text;
  - the API sends derived edges and ignores sent ones, and protects offerings.
- **`test_catalogue_files.py`:** the template lists the four sheets.
- **`ArchitectureCataloguePage.test.tsx`:**
  - the Journeys view: ordered activities, track words, the flow region and image, rules in words,
    integrations, and opening a system;
  - adding a journey with an offering, activities and a decision, with the duplicate number error.
