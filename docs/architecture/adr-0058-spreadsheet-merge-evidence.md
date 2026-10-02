# ADR-0058: Spreadsheet merged ranges remain row-local evidence

## Status

Accepted within the approved document extraction-quality enhancement after ADR-0057.

## Context

The read-only XLSX path retained cell coordinates and formulas but omitted merged-range metadata.
Reviewers could not distinguish an ordinary blank cell from a merged continuation or see a merged
range extending past the last populated row. Copying anchor wording to fill those positions would
bypass independent row exclusions, the trust problem already addressed in Word and delimited data.

## Decision

New XLSX extractions use `structured-xlsx-merges-v1` in both library and Requirement attachments.
Read merge metadata from the already parsed worksheet XML. Annotate anchors and continuation cells
with canonical range/anchor coordinates, never copied anchor wording. Empty merged anchors receive
an explicit empty marker; continuation-only rows remain reviewable WORKSHEET_RANGE blocks.
Keep existing worksheet parents, row locations, formulas/cached-value annotations, chart/image
handling and hidden-sheet selection behavior.

Validate merge references, positive ordered coordinates, multi-cell ranges and non-overlap before
returning evidence. Reject duplicate/overlapping ranges and values in non-anchor continuation cells
as explicit extraction failures requiring source correction. Reject ranges beyond the existing
100,000-row/1,000-column bounds and apply the configured visited-cell budget across merged areas
of all worksheets before materializing row intervals. Rendering traverses at most the bounded
worksheet rectangle including merge extents; omitted empty tail rows from the read-only parser
cannot erase continuation annotations. Missing/external worksheet relationships fail explicitly.

The owner sees a merge-review warning through existing API/UI schemas. A marker describes source
structure, not a business statement or inferred header. Existing row exclusion, preview/build,
activation, exact citation and approved-only surrounding-context rules apply unchanged. Attachment
review reflows its outline, warnings and metadata at the existing responsive tiers; evidence
identifiers and long text wrap within the available width.

## Consequences

No new port, provider, domain entity, schema migration or UI component is needed. Merge structures
are adapter-internal metadata; no framework dependency crosses inward. Existing extraction and
publication history stays immutable. A new upload/review/publication is required to adopt the fix;
rebuilding stored extraction text does not add merge information.

Synthetic contracts do not qualify arbitrary workbook layout, charts, hidden rows/columns, OCR,
formula correctness, rendering or retrieval quality. Token counting/embedding configuration remains
unchanged, and the parent delivery ledger remains open.

References: Microsoft's [MergeCell reference metadata](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.spreadsheet.mergecell?view=openxml-3.0.1)
and [openpyxl merged-cell representation](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.worksheet.merge.html).
The installed read-only parser was also inspected to verify its empty-tail behavior.
