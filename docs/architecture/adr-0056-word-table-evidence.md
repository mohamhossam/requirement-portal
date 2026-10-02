# ADR-0056: Word table evidence preserves row exclusions

## Status

Accepted within the approved document extraction-quality enhancement.

## Context

The Word extractor reused the first row as column labels and propagated vertical-merge anchor
text. It also flattened nested tables into the enclosing row and reused cell wording in image
labels. Excluding a source row therefore did not necessarily remove its wording from publication.

## Decision

New DOCX extractions use `structured-docx-tables-v1`, including Requirement attachments that share
the extractor. Each table row retains only its own paragraph text, rendered with R/C grid positions.
Paragraph/explicit line breaks remain distinct; run fragments concatenate. Annotate spans, empty
cells, omitted leading/trailing grid positions and declared horizontal/vertical merge state.
Do not infer headers or propagate an anchor's wording.

Nested tables have their own TABLE_ROW blocks, location and context parent. The containing cell
retains a structural marker at that position. Table parents and image labels use neutral positions,
so excluding a heading, row or nested table cannot leave its wording in another table's metadata.
Table images keep their separately reviewed image evidence and existing readiness rules.

Malformed numbers, nonpositive spans and unknown merge states fail explicitly at the adapter.
Limit each row to 1,000 grid columns, nesting to eight levels and the whole document to the
configured visited-cell budget, counting span/omission positions without allocating copies.
Declared grid differences produce a visible warning: Word permits a span to extend a grid. Merge
annotations describe source metadata and require comparison with the original; they do not certify
a reconstructed visual layout.

Existing extractor/metadata/index/API contracts and UI controls suffice. No migration or external
dependency is added. Stored revisions and citations remain immutable. Existing documents must be
uploaded as a new version, reviewed and explicitly published to adopt this extraction behavior;
rebuilding old extracted text alone cannot remove prior copied content.

## Consequences

Owners can exclude Word table rows and nested tables independently. Positional labels replace
inferred field/value relationships, including for new Requirement attachments. Approved nearby rows
can still provide same-table context under ADR-0053. Existing publication/activation protections
remain in force, and older affected publications require owner review rather than a silent rewrite.

The implementation follows the documented distinction between grid positions and actual cells.
See [Word grid spans](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.gridspan?view=openxml-3.0.1),
[vertical merge metadata](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.verticalmerge?view=openxml-3.0.1)
and [python-docx table structure](https://python-docx.readthedocs.io/en/latest/user/tables.html).
Synthetic contracts do not replace representative document/RTL layout qualification.
