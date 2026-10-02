# ADR 0086 — Spreadsheets as catalogue source documents

## Status

Accepted. Amends ADR 0081's list of accepted files.

## Context

Architects often keep system inventories and integration lists in spreadsheets. ADR 0081 let a
maintainer upload DOCX, PDF, TXT, PNG and JPEG to "From documents". A workbook could only come in
through "Upload catalogue file", and only in the template's fixed sheets and headers.

Requirement documents already accept XLSX, CSV and TSV. `SafeDocumentTextExtractor` checks their
signatures, archive limits and cell limits, and emits one evidence block per row (ADR 0058,
ADR 0061). `LocatedDocumentExtractor` treated every file other than PDF or TXT as DOCX, so a
workbook could not be read for suggestions or indexed.

## Decision

**"From documents" accepts XLSX, CSV and TSV.** They are added to `ARCHITECTURE_EXTENSIONS` and
pass through the same upload validation as other formats. No dependency is added. Legacy `.xls`
stays unsupported, because openpyxl cannot read it.

**A row is a passage.** `LocatedDocumentExtractor` maps the extractor's evidence blocks instead of
parsing the file a second time.

- **XLSX.**
  - Each visible sheet opens with a heading passage located `sheet N`, whose text is the sheet
    name.
  - Each non-empty row becomes `sheet N, row R`. Its text is the extractor's `A3=… | B3=…` form,
    so a quoted cell value matches its row.
  - Rows carry the sheet name as their heading path. The index packs consecutive rows of one
    sheet, located as `sheet N, rows R–S`.
  - Chart summaries keep their `chart N` location.
- **Hidden sheets are left out.** The requirement-document warning already says hidden sheets are
  excluded from AI analysis, and nobody reviewing the workbook sees them.
- **CSV and TSV.** Each non-empty record becomes `row R`, with the `R1C1: …` text. Headers are not
  inferred.

## Consequences

- An architect's own workbook can be read for suggestions without matching the template. The
  template import stays the way to load a complete catalogue in one step.
- The model sees the header row in the same batch as the rows below it, but row text does not
  repeat the headers. A workbook without a header row reads as bare cell values.
- `ProposeCatalogueChanges` still reads at most 600 passages per document. A larger sheet is read
  in part, and the run warns how many passages were left out.
- The passage dialog shows neighbouring rows, because a cited location is looked up the same way
  as a paragraph.
