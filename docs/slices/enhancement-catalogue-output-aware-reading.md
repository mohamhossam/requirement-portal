# Enhancement — Output-aware catalogue reading

Requested 2026-10-01 by the product owner. `SMB_Product_Architecture_Explorer_v4.md` was uploaded
to the architecture catalogue, and most of it was not suggested. It is a Markdown landscape of
domains, systems, one product and one journey.

This is slice 1a of the structured-architecture-document plan. The plan's later slices are:
- **1b:** heading- and table-aware Markdown passages;
- **1c:** prompt v4 and name canonicalisation;
- **1d:** a deterministic table reader;
- **2a–2b:** system descriptions and landscape domains;
- **3a–3e:** products, journeys and their use in impact mapping.

ADR-0091 records the decision. There is no UI change.

## Objective

No part of a document is lost because one model answer could not hold everything it states.

## User outcome

- A dense document is read in parts small enough for each answer to cover its part.
- A part whose answer is cut off, or fills up, is split and read again in halves, instead of
  failing or being silently under-read.
- Where a part still cannot be read completely, the reading's notes say so and name the part.
- Under configured model profiles:
  - one bad answer is asked for again, rather than failing the reading;
  - a matching failure no longer discards a reading that already succeeded.
- "System depends on itself" suggestions are no longer offered. They used to fail when accepted,
  and the reading's notes now count them.

## In scope

- Call sizing from the model's output limit, and splitting on a cut-off or full answer, in
  `StructuredCatalogueExtractor`.
- A truncation marker on every structured transport.
- Retrying `ModelTransportError` in the extractor, and turning it into `SystemMatchingError` in
  the matcher.
- The structured answer cap raised from 80 to 200, and `MAX_SEGMENTS` from 600 to 1,200.
- Leaving out self-dependencies when proposing.

## Out of scope

All of the following belong to later slices:
- how Markdown is cut into passages (1b);
- the extraction prompt and name resolution across parts (1c);
- reading tables without the model (1d);
- new catalogue fields or entities (2a–3e).

## Domain

No change. Self-dependencies are not refused in `CandidateContent`, so stored suggestions still
load (ADR-0091).

## Application

- `ProposeCatalogueChanges` leaves out a dependency whose source and target are the same system.
  It adds the note "N dependency suggestion(s) were left out because they linked a system to
  itself."
- `MAX_SEGMENTS` is 1,200.

## Ports

No new ports.

## Adapters

**`infrastructure/llm/structured_output.py`**
- `OutputTruncatedError`, and `truncated(error)`, which follows the cause chain.

**Transports**
- The OpenRouter, local and OpenAI clients raise their usual error from `OutputTruncatedError`
  when an answer stops at the token limit.
- The configured transport raises `ModelTransportError("invalid_output")` from it.

**`infrastructure/llm/catalogue_extraction.py`**

| Constant | Value |
|---|---|
| `_TOKENS_PER_CHANGE` | 150 |
| `_CHARACTERS_PER_OUTPUT_TOKEN` | 1.0 |
| `_DEFAULT_OUTPUT_TOKENS` | 16,384 |
| `_MIN_CAPACITY` | 10 |
| `_MAX_SPLIT_DEPTH` | 4 |
| `_MIN_SPLIT_CHARACTERS` | 400 |

- A call's text is the smallest of 48,000 characters, the input room, and
  `max(1,600, output tokens × 1.0)` characters.
- The parts waiting to be read form a queue in document order.
- A cut-off answer, or one with at least `capacity` suggestions, splits its part with `_halves`,
  within the call budget (`3 × parts + 4`).
- A truncated answer is not retried whole.
- The retry catches `ModelTransportError`. `_permanent` still blocks authentication,
  configuration and payment failures.
- `ExtractionOutput.changes` accepts up to 200 items.

**`infrastructure/llm/catalogue_matching.py`**
- A `ModelTransportError` becomes `SystemMatchingError`.

**`interfaces/api/composition/llm.py`**
- Passes `max_output_tokens` for the profiles, local and OpenRouter providers.

## API

No change.

## UI

No change. The new notes appear in the existing "Notes from reading the documents" list.

## Tests

- `test_catalogue_reading.py`:
  - a profiles transport failure is retried, and an authentication failure is not;
  - a cut-off answer splits into halves that are each asked for;
  - a full answer is set aside for its halves;
  - splitting stops and notes an incomplete part;
  - a passage too dense for any answer fails with that reason;
  - call size follows the output limit.
- `test_catalogue_matching.py`: a transport failure becomes `SystemMatchingError`.
- `test_catalogue_suggestions.py`: a self-dependency is left out, with its note.
- `test_openrouter_adapters.py`, `test_local_llm_adapters.py` and `test_llm_profiles.py`: only a
  cut-off answer is marked as truncated.
