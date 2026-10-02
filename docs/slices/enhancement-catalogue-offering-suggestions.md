# Enhancement — Product offerings from documents

Requested 2026-10-01 by the product owner. This is slice 3b of the structured-architecture-document
plan, stacked on 3a, and is recorded in the ADR-0095 amendment. Slice 3a gave product offerings a
place in the catalogue. Reading `SMB_Product_Architecture_Explorer_v4.md` still dropped Business
Pro Plus:
- its facts;
- 2 order types;
- 9 components;
- 22 component → system responsibilities;
- 5 customer values and 3 audiences.

**Scope.** The product owner confirmed the file list on 2026-10-01 and asked for the model to read
offerings from prose too. **This slice includes frontend feature work beyond the presentation-only
rule in `CLAUDE.md`:** a new suggestion kind, with the offering drawer reused to correct it.

## Objective

A reading suggests each product offering a document describes, whole, ready to review and accept
after its systems.

## User outcome

- **For the reported file**, one suggestion: "Product offering: Business Pro Plus — 2 order types ·
  9 components · 22 system responsibilities". It carries:
  - the facts, proposition and two rules;
  - the order types, one of them a known gap that is not offered;
  - every component, the Static IP gap included;
  - every responsibility, with its role and order types;
  - the values and audiences.
- **Accept all** adds it after the systems it names. Until they are in the draft, it waits as
  *Needs its system first*.
- **Edit and accept** opens the offering drawer, to correct anything before accepting.
- **Replacing.** An offering that would replace one already in the draft is always decided one by
  one, and keeps the existing id.
- **Other documents.** In prose, Word and PDF documents, the model suggests offerings. Parts read
  in different calls are merged into one suggestion.
- **Documents can be read again.** A document already read can be read again, because the reading
  profile changed (`catalogue-extraction-v9+catalogue-tables-v3`).

## In scope

- `CandidateKind.PRODUCT`, with classify, apply, and one-by-one on replace.
- The offering merge.
- The accept order, and saving offerings.
- The table reader's product sections.
- Prompt v9 and the nested model output, made valid before use.
- A compact answer schema.
- Review wording and the drawer reuse.

## Out of scope

- Journeys and activities (slices 3c–3d).
- Product context on impacts (slice 3e).

## Domain

- `products.py`: `merge_offerings`, `merge_components` and `same_offering`.
- `candidates.py`:
  - `CandidateKind.PRODUCT` and `CandidateContent.product`;
  - system names resolved at classify and accept;
  - replace keeps the id, and is one by one.

## Application

`ProposeCatalogueChanges`:
- `_one_offering_each` merges readings of one offering;
- system names inside an offering are re-resolved against the provisional draft;
- offerings are accepted last, and accepting saves `products`.

## Ports

No change.

## Adapters

- **`catalogue_tables.py`** (`catalogue-tables-v3`) reads product sections: facts, proposition,
  rules, order types, values, audiences, components (GAP kept) and responsibilities.
- **`catalogue_extraction.py`:**
  - `OfferingOutput` and its parts;
  - the `product_offering` kind;
  - `_offering` makes the model's reading valid;
  - the answer models send a compact schema.
- **`catalogue_extraction_prompt.py`:** `catalogue-extraction-v9`.
- **`markdown_passages.py`:** fixed sibling headings nesting when a document starts below `#`. A
  document opening at `##` nested each `###` inside the one before it.

## API

- `CandidateContentSchema.product`.
- Regenerated OpenAPI types.

## UI

- `labels.ts`: the kind label.
- `SuggestionList.tsx`: offering wording and counts, and an offerings group.
- `SuggestionEditor.tsx`: opens `ProductDrawer` for an offering. The drawer takes a `title` and a
  `saveLabel`.

## Tests

- **`test_offering_suggestions.py`:**
  - waits for its systems, then names them by id;
  - replace is one by one and keeps the id;
  - merge rules;
  - a full product section, with the GAP component kept and unknown order types left out;
  - the model's offering made valid;
  - parts read apart become one suggestion;
  - end to end, Accept all adds the offering after its systems.
- **`test_markdown_passages.py`:** sibling headings under a document that starts at `##`.
- **`test_catalogue_tables.py` and `test_catalogue_reading.py`:**
  - updated counts and prompt version;
  - the local 8k model still reads documents.
- **`ArchitectureCataloguePage.test.tsx`:** offering wording, needs-system, and correcting in the
  drawer before accepting.
