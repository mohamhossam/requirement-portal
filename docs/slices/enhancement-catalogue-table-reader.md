# Enhancement — Reading catalogue tables without a model

Requested 2026-10-01 by the product owner. This is slice 1d of the structured-architecture-document
plan, stacked on 1c and recorded in ADR-0093. Slices 1a–1c make the model read a landscape's
tables well. A model still varies from run to run, spends its answer copying cells, and cannot
join an integration row's activity numbers to systems named in another table.

## Objective

A landscape's systems and integrations are suggested completely, exactly and identically on every
reading. The model is left to read only what needs wording.

## User outcome

- **Every system row** gives its system, its plain name, its ID and aliases, and one dependency
  per Integrations entry. Each is cited by its own row.
- **Every integration between two activities** of different systems gives a dependency. API rows
  are typed "calls the API of".
- **Labelled.** These suggestions are labelled "Read from table" in the review list.
- **The same every time.** Reading the same document again gives the same table suggestions.
- **Kept if the model fails.** If the model fails on the rest of the document, the table
  suggestions are kept, with a note.
- **Documents can be read again.** A document already read can be read again, because the reading
  profile changed.

## In scope

- `CatalogueTableReader` and `TableFirstCatalogueExtractor`, for every provider.
- Cells on Markdown table rows.
- The `read` flag in the prompt (`catalogue-extraction-v7`).
- Per-suggestion reader provenance.
- The "Read from table" label.

## Out of scope

- Tables in Word, PDF or Excel. Their rows carry no cells yet.
- Domains, sub-domains and system descriptions (slices 2a–2b).
- Components, responsibilities, activities and journeys as catalogue records (phase 3).
- Merging an Integrations link with an integration-details link between the same systems.

## Domain

No change.

## Application

- `ProposeCatalogueChanges` stores a suggestion's model and prompt version from
  `ProposedChange.reader` when the reader proposed it.
- Cells are passed into segments.

## Ports

- `LocatedText.cells`.
- `ExtractionSegment.cells` and `ExtractionSegment.read`.
- `ProposedChange.reader`.

## Adapters

- **`infrastructure/architecture/catalogue_tables.py`**
  - **Recognised tables:** systems tables, activities tables and integration-details tables.
  - **Names:** resolved through the catalogue, then the document's own names, then a name without
    its trailing qualifier.
  - **Integrations entries:** "via" qualifiers kept; "A / B" split into two systems; phrases left
    out.
  - **Evidence markers:** GAP rows give nothing; INFERRED rows give inferred suggestions.
- **`markdown_passages.py`:** table rows carry every column as cells.
- **`catalogue_extraction_prompt.py`:** `catalogue-extraction-v7`, with `"read": true` and its
  rule.
- **Composition:** `architecture.py` wraps the configured extractor.

## API

No change. A suggestion's existing `model` is `catalogue-table-reader`.

## UI

- `SuggestionList.tsx` shows a "Read from table" badge, from the `TABLE_READER` constant in
  `labels.ts`. This is presentation only, from an existing field.

## Tests

- **`test_catalogue_tables.py`, against the synthetic landscape fixture:**
  - systems, aliases and IDs;
  - 12 links, including the split `A / B` entry and an API link between activities;
  - row citations and provenance;
  - consumed and read rows;
  - identical output over three readings;
  - same-system and GAP integration rows;
  - qualifiers, known slashed names, phrases, INFERRED and GAP system rows, and base-name
    resolution;
  - the model sent only what is left, with read rows marked and its duplicates dropped;
  - a model failure keeping the reader's suggestions;
  - the prompt's read flag;
  - the API listing reader suggestions with their note;
  - rows without cells left to the model.
- **`ArchitectureCataloguePage.test.tsx`:** the "Read from table" badge.
