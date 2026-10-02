# Enhancement — Landscape domains, placements and descriptions from documents

Requested 2026-10-01 by the product owner. This is slice 2b of the structured-architecture-document
plan, stacked on 2a, and is recorded in the ADR-0094 amendment. Slice 2a gave systems a description
and a landscape domain, edited by hand. Reading `SMB_Product_Architecture_Explorer_v4.md` still
dropped:
- its Domains table;
- the domain heading above each systems table;
- its Sub-domain column;
- each Function.

**Scope.** The product owner confirmed the file list on 2026-10-01 and asked for the model to
propose domains as well, not only the table reader. **This slice includes frontend feature work
beyond the presentation-only rule in `CLAUDE.md`:** new suggestion kinds and editor fields. The
presentation follows `docs/design-system.md`.

## Objective

A reading suggests the landscape a document describes: its domains and sub-domains, where each
system sits, and what each system is for. "Accept all" can build it.

## User outcome

**For the reported file:**
- 11 landscape domain suggestions: the 8 domains, plus Un-assisted, Assisted and Data & Case under
  Customer;
- 39 placements;
- 39 system descriptions taken from the Function column.

All of these come from the table reader, and "Accept all" adds them in order: domains, then
systems, then placements.

**In review:**
- A domain reads "A sub-domain of Customer".
- A placement reads "Place BCRM in Customer › Assisted".
- A system shows its description beside its other names.
- A placement that would move a system already placed elsewhere waits for a one-by-one decision.
- "Edit and accept" corrects a domain's name, parent or description, a placement's domain, or a
  system's description.

**Other documents.** In prose, Word and PDF documents, the model suggests the same kinds when the
document names landscape areas.

## In scope

- `landscape_domain` and `placement` suggestion kinds, and a system description, with how each is
  classified and applied.
- The accept order.
- Saving landscape domains on accept.
- The table reader's Domains table, placement by heading, Domain cell or Sub-domain cell, and
  Function as the description.
- Prompt `catalogue-extraction-v8`.
- Review wording and the editor.

## Out of scope

- Capability domains, which are still never proposed.
- Using landscape domains in impact mapping.
- Products and journeys (phase 3).

## Domain

- `CandidateKind.LANDSCAPE_DOMAIN` and `.PLACEMENT`.
- `CandidateMatch.NEEDS_DOMAIN`.
- `CandidateContent.landscape_domain_id` and `.parent_domain_id`; a system's `description` is now
  allowed.
- `find_landscape_domain`.
- `classify`, `apply_candidate` and `needs_one_by_one` (moving a placed system).

## Application

`ProposeCatalogueChanges` and `DecideCatalogueCandidate`:
- a domain is never matched as a system name, nor re-resolved as one;
- the accept order runs domains before sub-domains;
- accepting saves `landscape_domains`.

## Ports

No change.

## Adapters

- `catalogue_tables.py` (`catalogue-tables-v2`): Domains tables, placements, sub-domains and
  descriptions. Domain rows are consumed.
- `catalogue_extraction.py`:
  - `ChangeOutput` gains the kinds `landscape_domain` and `placement`, and the fields `domain` and
    `parent_domain`;
  - `domain_key` keys a sub-domain under its parent;
  - a system's `text` is its description.
- `catalogue_extraction_prompt.py`: `catalogue-extraction-v8`.

## API

- `CandidateContentSchema.landscape_domain_id` and `.parent_domain_id`.
- The new kinds and match values.
- Regenerated OpenAPI types.

## UI

- `labels.ts`: kind and match labels.
- `SuggestionList.tsx`:
  - wording for the new kinds;
  - the kind order follows the accept order;
  - landscape domains group on their own.
- `SuggestionEditor.tsx`: domain, placement and system-description fields.

## Tests

- `test_landscape_suggestions.py`:
  - domain matching, parents and filling;
  - placement needs, bare names, moves decided one by one;
  - descriptions that fill and never replace;
  - field rules;
  - the reader's domains, sub-domains, placements and descriptions on the synthetic landscape;
  - a Domain column without a Domains table;
  - the model's domains and placements from prose;
  - end to end: read, then Accept all, places and describes every system.
- `test_catalogue_tables.py` and `test_catalogue_table_reading.py`: updated counts and prompt
  version.
- `ArchitectureCataloguePage.test.tsx`: wording, and moving a placement before accepting it.
