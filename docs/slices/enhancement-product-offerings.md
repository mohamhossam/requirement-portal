# Enhancement — Product offerings

Requested 2026-10-01 by the product owner. This is slice 3a of the structured-architecture-document
plan, stacked on 2b and recorded in ADR-0095. `SMB_Product_Architecture_Explorer_v4.md` describes
Business Pro Plus: its order types, nine components and twenty-two component → system
responsibilities. None of it had a place in the catalogue.

**The product owner chose:**
- the full scope: model, files, changes, evidence, API, a browse view and a hand editor;
- the name "Product offerings";
- the file list, confirmed on 2026-10-01.

**This slice includes frontend feature work beyond the presentation-only rule in `CLAUDE.md`.** The
presentation follows `docs/design-system.md`:
- labelled fields with errors beside them;
- sentence case;
- tokens only;
- table headers;
- status as words;
- 24px targets.

## Objective

A version of the catalogue holds the commercial offerings it supports: how each is ordered, what it
is made of, and which systems deliver each component in which role.

## User outcome

- **Browsing.** A **Product offerings** view lists each offering with:
  - its facts and confidence;
  - its rules;
  - its order types, with "Not offered yet";
  - a components table;
  - a component × system table of roles;
  - what each system does and for which orders;
  - its customer value and who it is for.

  A system opens its dossier.
- **Editing.** In **Edit manually**, a maintainer adds, edits or removes offerings. Removing asks
  first.
  - The drawer covers the offering, its order types, components, the systems that deliver each
    component, customer value and audiences.
  - Missing names, systems and roles are reported beside their fields.
- **Files.** Catalogue files carry offerings: YAML/JSON `products`, and five Excel sheets. Older
  files still import.
- **Review of changes.** It names an added, changed or removed offering, and which of its parts
  changed.
- **Protection.** A system that an offering names cannot be removed. The message says which
  offering and component name it.
- **Mapping.** Requirement mapping can retrieve an offering's systems through its evidence.

## In scope

The domain model and its checks, files, diff, evidence chunk, API, browse view and editor listed
above.

## Out of scope

- Suggesting offerings from documents (slice 3b).
- Journeys and activities (slices 3c–3d).
- Product context on impacts (slice 3e).
- Linking an offering to the organisation catalogue's products.

## Domain

- `domain/architecture/products.py`:
  - `SourceConfidence`, `OfferingPoint`, `OrderType`, `ComponentResponsibility`,
    `OfferingComponent` and `ProductOffering`;
  - `role_code`;
  - `check_offerings`.
- `domain/architecture/invariants.py`: `InvalidKnowledgeError`, `required` and `optional`, shared
  without import cycles.
- `ArchitectureKnowledge.products`; responsibilities must name catalogued systems.
- `ChangedItem.PRODUCT`, and changed offering fields.

## Application

- `ManageArchitectureKnowledge.update` takes `products`. File import carries them.
- `BuildArchitectureIndex` writes one `product <id>` chunk per offering.

## Ports

- `CatalogueContent.products`.

## Adapters

- `catalogue_files.py`:
  - YAML/JSON `products`;
  - the Excel `Products`, `OrderTypes`, `OfferingComponents`, `Responsibilities` and
    `ProductPoints` sheets, gathered into the YAML shape with row-level errors;
  - template instructions.
- `knowledge_yaml.py` loads offerings.

## API

- `ProductOfferingSchema` and its parts.
- `KnowledgeReleaseResponse.products`.
- An optional `DraftUpdateRequest.products`.
- Regenerated OpenAPI types.

## UI

- `api/knowledge.ts`: types, and `save` sends `products` when known.
- `ProductsView.tsx`: the browse view.
- `ProductsEditor.tsx` and `ProductDrawer.tsx`: the editor.
- `ArchitectureCataloguePage.tsx`: the Product offerings view.
- `DraftJourney.tsx`: the editor under Edit manually.
- `labels.ts`: confidence labels and role words.
- `DiffList.tsx`: the product item in changes.

## Tests

- `test_product_offerings.py`:
  - role codes;
  - confidence parsing;
  - offerings refusing contradictions;
  - systems that cannot be removed while named;
  - every format round-trips an offering;
  - workbook errors name sheet and row;
  - older files;
  - the diff separates components from responsibilities;
  - the evidence chunk text;
  - the API saves, keeps and protects.
- `test_catalogue_files.py`: the template lists the five sheets.
- `ArchitectureCataloguePage.test.tsx`:
  - the browse view and matrix;
  - adding an offering with errors beside fields;
  - removing after confirming.
