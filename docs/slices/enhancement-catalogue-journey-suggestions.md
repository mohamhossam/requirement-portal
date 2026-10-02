# Enhancement — Journeys from documents

Requested 2026-10-01 by the product owner. This is slice 3d of the structured-architecture-document
plan, stacked on 3c, and is recorded in the ADR-0096 amendment. Slice 3c gave journeys a place in
the catalogue. Reading `SMB_Product_Architecture_Explorer_v4.md` still dropped the New Activation
journey. Its integration rows became dependencies between systems and its activity rows
capabilities; the journey itself was not kept:
- 18 activities;
- 7 flow rules;
- 18 integrations;
- the details under each activity: description, related components, input → output, eTOM and
  evidence.

**Scope.** The product owner confirmed the file list on 2026-10-01 and asked for the model to read
journeys from prose too. **This slice includes frontend feature work beyond the presentation-only
rule in `CLAUDE.md`:** a new suggestion kind, with the journey drawer reused to correct it.

## Objective

A reading suggests each journey a document describes, whole, tied to its offering's order type and
ready to review and accept after its systems and offering.

## User outcome

- **For the reported file**, one suggestion: "Journey: New Activation — For Business Pro Plus ›
  New Activation · 18 activities · 7 flow rules · 18 integrations". It carries:
  - every activity, in order, with its phase, track, performing and supporting systems, system
    function, mode, whether the customer sees it, and evidence;
  - from each activity's details: its description, its components (as the offering's), input and
    output, eTOM and source;
  - every flow rule and integration.

  Its derived flow is the document's 21 arrows.
- **Accept all** adds it after the systems and offering it names. Until they are in the draft, it
  waits as *Needs its system first* or *Needs its product offering first*.
- **Edit and accept** opens the journey drawer, to correct anything before accepting. A system or
  offering the version does not have yet stays chosen, marked "not in this version".
- **Replacing.** A journey that would replace one already in the draft is always decided one by
  one, and keeps the existing id.
- **Other documents.** In prose, Word and PDF documents, the model suggests journeys: activities,
  their systems, and the rules that leave the main order. A model whose context is too small to
  also do this reads without journeys, and says so. Journey tables are still read.
- **Documents can be read again.** A document already read can be read again, because the reading
  profile changed (`catalogue-extraction-v10+catalogue-tables-v4`).

## In scope

- `CandidateKind.JOURNEY` and `CandidateMatch.NEEDS_OFFERING`.
- Classify, apply, and one-by-one on replace.
- The journey merge.
- The accept order, and saving journeys.
- The table reader's journey sections.
- Prompt v10, a lean journey answer shape, and the lean fallback for small contexts.
- Review wording and the drawer reuse.

## Out of scope

- Journey and product context on impacts (slice 3e).
- Reading the flow from a mermaid diagram: the flow is always derived.

## Domain

- **`products.py`:**
  - `find_offering`, `find_order_type` and `find_offering_component`, which match by id, code or
    name, ignoring case and punctuation;
  - `first_known`, now shared.
- **`journeys.py`:** `merge_journeys` and `same_journey`.
- **`candidates.py`:**
  - `CandidateKind.JOURNEY`, `CandidateContent.journey` and `CandidateMatch.NEEDS_OFFERING`;
  - systems, offering, order type and components are resolved at classify and accept;
  - a replace keeps the id, and is decided one by one.

## Application

`ProposeCatalogueChanges`:
- `_canonical_journey` names a journey's systems, offering, order type and components by the ids
  they will have. Offerings suggested in the same reading count.
- `_one_journey_each` merges readings of one journey.
- Journeys are accepted after offerings, and accepting saves `journeys`.

## Ports

No change.

## Adapters

- **`catalogue_tables.py`** (`catalogue-tables-v4`) reads `Journey: X` sections:
  - the activities, flow rules and integration details tables;
  - `#### N. Title` detail blocks (a description, and `**Key:** value` bullets);
  - the offering is the product section the journey follows or sits in, and the order type is the
    one of the journey's name.

  Flow-rule rows, detail bullets and the mermaid diagram are not sent to the model. Activity rows
  and descriptions are sent marked read.
- **`catalogue_extraction.py`:**
  - the `journey` kind, with `JourneyOutput`, `StepOutput` and `RuleOutput`;
  - `_journey` makes the model's reading valid;
  - `LeanChangeOutput` and `LeanExtractionOutput` are used when the context is too small.
- **`catalogue_extraction_prompt.py`:** `catalogue-extraction-v10`, `JOURNEY_RULE` and
  `LEAN_SYSTEM_PROMPT`.

## API

- `CandidateContentSchema.journey`, with derived edges.
- `CandidateMatch` gains `needs_offering`.
- Regenerated OpenAPI types.

## UI

- `labels.ts`: the kind label and the needs-offering match.
- `SuggestionList.tsx`: journey wording and counts, a journeys group, and the offerings passed to
  the editor.
- `SuggestionEditor.tsx`: opens `JourneyDrawer` for a journey.
- `JourneyDrawer.tsx`: `title` and `saveLabel`. Systems and offerings the version lacks stay
  chosen.

## Tests

- **`test_journey_suggestions.py`:**
  - waits for systems, the offering, the order type and components, then names them by id;
  - replace is one by one and keeps the id;
  - merge and matching rules, and lookups by code or name;
  - a full journey section, with details and the derived flow;
  - offering and order type found from the section;
  - a broken journey left to the model;
  - the model's journey made valid;
  - the lean fallback, with its warning;
  - no repeat from read rows;
  - parts read apart become one suggestion naming the suggested offering;
  - end to end, Accept all adds the journey after its offering.
- **Fixture:** gains activity details and flow rules.
- **Existing tests:** updated counts, prompt version and helpers.
- **`ArchitectureCataloguePage.test.tsx`:** journey wording, needs-offering, and correcting in the
  drawer with an absent system kept.
