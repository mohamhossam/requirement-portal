# Enhancement — Heading- and table-aware Markdown passages

Requested 2026-10-01 by the product owner. This is slice 1b of the structured-architecture-document
plan; slice 1a, output-aware reading, was merged as #83. `SMB_Product_Architecture_Explorer_v4.md` is
a Markdown landscape of systems, a product and a journey. It was cut into blind 40-line windows: a
table could start in one window while its header sat in the previous one, and no passage said which
section it came from. The decision is recorded as an amendment to ADR-0090. There is no UI change.

## Objective

A Markdown document is read the way it is written: by heading, with every table row carrying its
own header and section.

## User outcome

- **Table rows read whole.** A table row is suggested from the row itself, such as
  `System: BCRM | ID: SYS-BCRM | Integrations: CBCM, GIS`, whichever call it is read in.
- **Sections are known.** The model knows each passage's section, such as
  `Landscape › Customer (TAM · Customer)`, so a short row or paragraph is read in context.
- **Citations point to the row.** A citation names the exact row (`line 54`) or block
  (`lines 9-11`), and "Show in document" opens it.
- **Old citations still open.** Suggestions already read under the old windows still open their
  passage.
- **Documents can be read again.** A document already read can be read again for suggestions,
  because the reading profile changed.

## In scope

- A Markdown passage reader for:
  - ATX and setext headings;
  - paragraphs, lists, block quotes and fenced blocks, each up to 40 lines;
  - pipe tables;
  - front matter.
- The section of each passage is given to the model, and the prompt moves to
  `catalogue-extraction-v5`.
- Batches end at a section change once past half full. A full part is split where its sections
  meet.
- The passage dialog falls back to an overlapping passage for old `lines A-B` citations.
- Index spans that mix `line N` and `lines A-B`.

## Out of scope

- Prompt rules for reading tables and name canonicalisation (slice 1c).
- Reading tables without the model (slice 1d).
- Rendering Markdown, inline formatting, HTML blocks, and nested or indented code blocks.
- Plain text, which keeps its 40-line windows.

## Domain

No change.

## Application

- `ExtractionSegment.section`: the heading path, filled from `LocatedText.heading_path` in
  `ProposeCatalogueChanges`.
- `ReadKnowledgeDocument.passage`: when the cited location is a line window that no longer exists,
  it returns the first passage overlapping it.
- `BuildArchitectureIndex` `_span`: mixed `line N` and `lines A-B` locations read as `lines A-B`.

## Ports

- `ExtractionSegment` gains `section` (defaulted).

## Adapters

- `infrastructure/architecture/markdown_passages.py`: the reader.
- `LocatedDocumentExtractor`: uses the reader for `text/markdown`.
- `catalogue_extraction_prompt.py`:
  - `catalogue-extraction-v5`;
  - a `section` per segment;
  - the rule "use the section to tell what a row is about, quote only the segment's text".
- `StructuredCatalogueExtractor`:
  - parts and splits keep their section;
  - `_batches` ends a call at a section change past half full;
  - `_halves` cuts at the section boundary nearest the middle.

## API

No change.

## UI

No change.

## Tests

- **`test_markdown_passages.py`, against a synthetic fixture (`tests/fixtures/catalogue/synthetic_landscape.md`):**
  - heading paths;
  - setext and closed headings;
  - table rows with repeated headers, escaped pipes and empty cells;
  - pipes without a table;
  - lists, quotes and fences;
  - bounded blocks;
  - front matter and CRLF.
- **`test_architecture_p1.py`:**
  - Markdown follows headings while plain text keeps its windows;
  - index chunks pack rows under their heading.
- **`test_architecture_p3.py`:** an old `lines 1-40` citation opens the first passage on those lines.
- **`test_catalogue_reading.py`:**
  - the section reaches the prompt only when present;
  - calls end at a new section past half full;
  - a full part splits where its sections meet.
