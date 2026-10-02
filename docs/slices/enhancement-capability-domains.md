# Enhancement — Capability domains

Scheduled 2026-09-30 by the product owner. This is slice C of three from the ontology, taxonomy
and GraphRAG review (ADR-0089), after connected systems (ADR-0087) and typed relationships
(ADR-0088). It is feature work outside the UI redesign's presentation-only rule.

## Objective

Group what systems do into a small, maintained tree of business areas. Use it to suggest where to
look when mapping finds no system, to read impact by business area, and to browse the catalogue.

## User outcome

- **Maintainers:**
  - add, rename, nest (up to three levels) and remove domains in a draft;
  - place each capability in one from the system dialog;
  - a domain that still holds something says what, and which systems, before it can be removed;
  - files carry domains, and older files still import.
- **Everyone** can switch the catalogue workbench to "Domains". Each business area shows its
  capabilities and the systems behind them, and capabilities not placed yet are called out. A
  draft marks the domains it adds or changes.
- **Mapped Features and Stories:**
  - each matched capability shows its domain;
  - a "Matched business areas" line appears.
- **When nothing is mapped,** the impact shows "Closest business areas" as a suggestion. It gives
  the words the item shares with the catalogue and the systems working there.
- **Exports** carry each capability's domain path.

## In scope

Domains on the release, the seed tree, files, diff, evidence words, impact fields, the fallback,
export `1.3`, and the workbench, editor and impact UI.

## Out of scope

- Extraction proposing domains.
- Tag fields on backlog items.
- Filtering or reporting by domain beyond the impact panel and export.
- Changing which capabilities a mapped system carries (see ADR-0089, Consequences).

## Domain

- `CapabilityDomain`, `ArchitectureKnowledge.capability_domains` and tree invariants, with
  `domain_path()` and `updated(capability_domains=…)`.
- `KnowledgeCapability.domain_id`.
- `SystemCapability.domain_id` and `domain_path`.
- `DomainSuggestion` and `ArchitectureImpact.suggested_domains`, refused alongside a catalogued
  system.
- The diff has `ChangedItem.DOMAIN` and a capability `domain` field.
- `apply_candidate` keeps a capability's domain.

## Application

- `capability_domain_fallback.suggest_domains`: Unicode-aware whole-phrase matching over
  catalogue words, at most two suggestions, one per branch.
- `ResolveArchitectureKnowledge` places capabilities from the pinned release and suggests domains
  only when nothing catalogued was mapped.
- Evidence chunks add domain paths.
- `ManageArchitectureKnowledge.update` and file import carry domains.

## Ports

- `ArchitectureKnowledgeMatch.suggested_domains`.
- `CatalogueContent.capability_domains`.

## Adapters

- Seed YAML: eight domains, and all 31 capabilities placed.
- Catalogue files: YAML/JSON keys, and an Excel Domains sheet and column.
- Impact payloads: optional keys.
- Generation guidance strips domain fields.
- Export `1.3`.

## API

- `CapabilityDomainSchema`.
- `KnowledgeReleaseResponse.capability_domains`.
- `DraftUpdateRequest.capability_domains`, where omitting it keeps the draft's domains.
- `KnowledgeCapabilitySchema.domain_id`.
- `SystemCapabilityResponse.domain_id` and `domain_path`.
- `DomainSuggestionResponse`.

## UI

- `DomainTree` (the workbench "Domains" view).
- `DomainsEditor` (in Add content, under Edit manually).
- A capability domain picker in `SystemsEditor`.
- The domain line in the dossier.
- `ArchitectureImpactPanel` domain chips, "Matched business areas", and `SuggestedDomains`.
- Also: slice B's add-dependency form uses five columns only from `lg`.

## Business rules

- Domains group what systems do; they never select a system.
- Suggestions are advice and never enter fingerprints or prompts.

## Tests

- `tests/unit/test_capability_domains.py`:
  - tree invariants and placement;
  - the seed;
  - the diff;
  - every file format and old workbooks;
  - fallback ranking, branches, Arabic, no-hit and determinism;
  - the resolver's placement and suggestions;
  - payloads, fingerprints and prompts;
  - suggestions that keep domains;
  - export.
- `test_architecture_p1.py` covers domain words in evidence text.
- Frontend:
  - `ArchitectureCataloguePage.test.tsx`: add a domain, the blocked remove with its reason,
    placing a capability, and the Domains view;
  - `ArchitectureImpactPanel.test.tsx`: domain chips, areas and the suggestion card.

**Evidence.**
- `pytest tests/unit`: 1,787 passed.
- `ruff check`, `ruff format --check`, `mypy src tests` and `lint-imports` (7 contracts) are clean.
- Frontend: `api:check`, `lint`, `typecheck`, `test` (592 passed) and `build` are green.
- Browser, against the fake API:
  - the Domains view (two columns at 1440px, no overflow);
  - the domains editor;
  - a Feature on DCRM + CWOM showing "Order capture: Back-office order capture";
  - a Feature with no system mapped ("Faster SMB billing") suggesting Billing, with BSCS.
- Impeccable critique (dual-agent), baseline 22/40, with three P1s:
  - the Remove reason was hidden;
  - "Business areas" overstated;
  - the suggestion card looked like a mapping.

  There were also two P2s: the tree structure, and the select order and depth. All five are
  fixed and rechecked live. Snapshot:
  `.impeccable/critique/2026-09-30T16-31-50Z__frontend-src-features-catalogue-domaintree-tsx.md`.
- Not run:
  - the PostgreSQL integration suite (only its export-version assertion changed);
  - a live-model check.
