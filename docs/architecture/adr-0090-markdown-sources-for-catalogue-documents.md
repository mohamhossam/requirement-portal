# ADR 0090 — Markdown as a catalogue source document

## Status

Accepted. Amends the list of accepted files in ADR 0081, as already amended by ADR 0086.

## Context

Architects often keep their landscape notes, system inventories and decision records as Markdown,
in a wiki or a repository. Requirement documents already accept `.md` (ADR 0042), and
`SafeDocumentTextExtractor` already reads `text/markdown` as UTF-8 text (ADR 0059).

"From documents" refused Markdown in two places:

- `ARCHITECTURE_EXTENSIONS` did not list it.
- `LocatedDocumentExtractor` matched `text/plain` exactly and opened every other text type as a
  DOCX archive, which is the same failure ADR 0086 records for spreadsheets.

## Decision

**"From documents" accepts `.md` and `.markdown` as `text/markdown`.**

- The type is added to `ARCHITECTURE_EXTENSIONS`. Uploads pass through the same validation and
  extractor checks as other files: UTF-8 only, no NUL bytes, not blank.
- **The filename decides an untyped upload.** Browsers often send Markdown with an empty type, as
  `application/octet-stream`, `text/plain` or `text/x-markdown`. When the filename ends in `.md`
  or `.markdown`, such an upload is stored as `text/markdown`. This is the same rule requirement
  documents already use. A `.md` file declared as any other type is still refused.

**Markdown is read like plain text.** `LocatedDocumentExtractor` gives it the same 40-line
`lines A-B` passages as TXT. The index's line-span packing, the suggestion batches and the passage
dialog therefore need no change.

- Markdown is not rendered, and its syntax stays in the quoted text, as ADR 0059 decided for
  requirement documents.
- No dependency is added.

## Consequences

- An architect's Markdown notes can be read for suggestions and indexed without first being
  converted to Word or PDF.
- Passages do not follow Markdown headings. A heading can open one 40-line window while its body
  falls in the next. Heading-aware passages remain possible later through
  `LocatedText.heading_path`, if citations need them.

## Amendment — Passages follow headings and tables (2026-10-01)

The 40-line windows split tables from their header rows. They also never told the model which
section a row belonged to, so a Markdown landscape lost most of its structure before it was read
(`docs/slices/enhancement-markdown-structured-passages.md`).

**Markdown gets its own passages.** `infrastructure/architecture/markdown_passages.py` reads the
Markdown architects write without rendering it and without a new dependency:
- **Headings:** ATX and setext headings.
- **Text blocks:** paragraphs, lists, block quotes and fenced blocks, up to 40 lines each.
- **Tables:** GitHub pipe tables.
- **Front matter.**

Plain text keeps its 40-line windows.

- **A heading** is its own passage and sets `LocatedText.heading_path` for what follows, as Word
  headings already do.
- **A table row** is one passage, `line N`, written as `Column: value | …`.
  - Every row carries its header wherever it is read.
  - Cells saying nothing (`—`, `-`, empty) are left out.
  - An escaped `\|` stays inside its cell.
- **Other blocks** are located as `line N` or `lines A-B`.

**The model is told each passage's section.**
- `ExtractionSegment.section` carries the heading path. The prompt sends it as
  `"section": "Landscape › Customer"`, and the prompt moves to `catalogue-extraction-v5`. This
  also applies to Word documents, whose passages already had headings.
- Because the reading profile changes, a document already read can be read again.
- A call that is past half full ends where a new section starts. A full or cut-off part
  (ADR-0091) is split where its sections meet, nearest its middle, so a table stays in one call
  where it fits.

**Earlier citations still open.** A suggestion read under the old windows cites `lines 1-40`. The
passage dialog opens the first passage on those lines, with its neighbours.

**The index packs rows under their heading.** Consecutive passages under one heading are packed
into chunks as Word paragraphs are. A chunk mixing `line 7` and `lines 3-5` is located as
`lines 3-7`. Markdown chunk text and hashes change once, when a release is next built.
