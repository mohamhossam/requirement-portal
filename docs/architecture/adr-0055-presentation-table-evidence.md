# ADR-0055: Row-local presentation table evidence

## Status

Accepted within the approved document extraction-quality checkpoint.

## Context

Flattening every DrawingML text node on a slide into one paragraph erases table boundaries,
splits formatting runs into separate lines, and prevents row-level review/exclusion. Copying the
first extracted text into every block's heading can also retain excluded content in retrieval.

## Decision

New PPTX extractions use `structured-pptx-tables-v1`. Traverse source XML order, emit ordinary
paragraphs separately, and render each table row as TABLE_ROW with physical R/C positions. Empty
cells retain a marker. Declared row/column spans and merge continuation flags are annotated and
accompanied by a review warning. Do not infer semantic headers or propagate merged anchor text.
Source run fragments concatenate; paragraph and explicit line breaks remain distinct.

Slide text, each table, and speaker notes have separate neutral structural parents. Table text
is never duplicated in a flattened slide block. Excluding a row therefore excludes its wording
from indexed children, labels and surrounding context, including when it is a merged anchor.

Validate row width, span/flag values and aggregate cell bounds at the extraction adapter boundary.
The existing warning/review UI exposes uncertainty; this is not a visual layout reconstruction or
an OCR claim. Existing immutable extractions and published citations are not migrated or rebuilt.
Other document formats retain their existing extraction version. Existing ports, JSON persistence,
owner approvals and versioned chunk/build/activation contracts are unchanged.

## Consequences

PowerPoint table rows can use the approved table-child policy without a new API or UI workflow.
Coordinates and bracketed annotations are extraction aids, not new business statements. Reviewers
must compare merged/RTL tables against the original file. Synthetic format fixtures prove the
contract, not representative production extraction quality; broader fixtures remain in the ledger.

DrawingML represents each table row as table cells in grid order; cell metadata declares merging.
See Microsoft's [TableRow](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.tablerow?view=openxml-3.0.1)
and [TableCell](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.tablecell?view=openxml-3.0.1)
references. No third-party parser or new runtime dependency is introduced.
