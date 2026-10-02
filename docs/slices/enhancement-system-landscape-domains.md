# Enhancement — Landscape domains and system descriptions

Requested 2026-10-01 by the product owner. This is slice 2a of the structured-architecture-document
plan, stacked on 1d, and is recorded in ADR-0094. A landscape document's Domains table, its
Sub-domain column and each system's Function had nowhere to go in the catalogue.

**This slice includes frontend feature work beyond the presentation-only rule in `CLAUDE.md`.** It
adds new fields and new calls on the existing save. The product owner confirmed the scope and the
file list on 2026-10-01. The presentation follows `docs/design-system.md`:
- labelled inputs;
- errors beside the field;
- sentence case;
- tokens only;
- 24px targets.

## Objective

A maintainer can say what each system is for and where it sits in the landscape, and browse the
landscape by domain and sub-domain. This is kept apart from the business areas that group
capabilities.

## User outcome

- **"Edit manually":**
  - lists **Landscape domains** above **Capability domains**;
  - adds a landscape domain or a sub-domain;
  - shows what each domain holds, and that a domain still holding systems cannot be removed.
- **The system drawer** has a **Description** and a **Landscape domain** picker in Identity.
- **The Domains view** shows each landscape domain with its systems and what they are for, and
  then the systems not placed yet, before the capability domains.
- **A system's dossier** shows its description and "Landscape: Customer › Assisted".
- **Files:**
  - catalogue files (Excel, YAML, JSON) carry both new fields and the tree, and older files still
    import;
  - the review of changes names added, changed and removed landscape domains and system
    placement changes.

## In scope

- The domain tree and system fields, files, diff, evidence text, API and UI listed above.

## Out of scope

- Suggesting landscape domains, placements or descriptions from documents (slice 2b).
- Using landscape domains in impact mapping.
- Seeding a default landscape.
- Owners.

## Domain

- `LandscapeDomain`.
- `ArchitectureKnowledge.landscape_domains` and `landscape_path()`.
- `SystemDefinition.description` and `landscape_domain_id`.
- One shared tree check for both trees.
- `ChangedItem.LANDSCAPE_DOMAIN`, and the system fields `description` and `landscape_domain` in
  the diff.

## Application

- `ManageArchitectureKnowledge.update` takes `landscape_domains`. File import carries them.
- Evidence text gains a description line and a landscape line, only when present.

## Ports

- `CatalogueContent.landscape_domains`.

## Adapters

- `catalogue_files.py`:
  - YAML/JSON `landscape_domains`, plus per-system `description` and `landscape_domain`;
  - the Excel `LandscapeDomains` sheet;
  - Systems `description` and `landscape_domain_id` columns;
  - template instructions.
- `knowledge_yaml.py` loads the tree.

## API

- `SystemDefinitionSchema.description` and `.landscape_domain_id`.
- `LandscapeDomainSchema`.
- `KnowledgeReleaseResponse.landscape_domains`.
- An optional `DraftUpdateRequest.landscape_domains`.
- Regenerated `frontend/openapi.json` and `src/api/schema.d.ts`.

## UI

- `api/knowledge.ts`: types, and `save` sends `landscape_domains` when known.
- `SystemDrawer.tsx`: Description and Landscape domain, and the summary leads with the place.
- `SystemsEditor.tsx`: passes the tree.
- `DomainsEditor.tsx`: one editor configured by `kind` (`capability` or `landscape`). The landscape
  one counts and names held systems, and a sub-domain's id carries its parent's.
- `DraftJourney.tsx`: both editors under "Edit manually".
- `DomainTree.tsx`: a landscape tree, then the capability tree.
- `CatalogueBrowser.tsx`: description and landscape path in the dossier.
- `DiffList.tsx` and `labels.ts`: landscape-domain item and field labels.

## Tests

- **`test_landscape_domains.py`:**
  - placement must name a listed domain;
  - tree rules worded for landscape domains;
  - the two trees stay separate;
  - every file format round-trips;
  - unlisted placements are refused, and older files still read;
  - the diff;
  - evidence text appears only when known;
  - the API saves the tree, keeps it when left out, and refuses removing a domain in use.
- **`test_catalogue_files.py`:** the template lists `LandscapeDomains`.
- **`ArchitectureCataloguePage.test.tsx`:**
  - adding a sub-domain and placing and describing a system;
  - the Domains view and dossier;
  - the new-system payload.

**Evidence.**
- Backend: `pytest` full suite, `ruff`, `mypy` and `lint-imports`.
- Frontend: `vitest` (603), `eslint`, `npm run build` and `npm run api:check`.
- **Not run:** a browser check. Another session's dev servers held ports 8000 and 5173, and
  changing the shared launch configuration was out of scope.
