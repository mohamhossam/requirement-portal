# ADR-0057: Delimited first records remain independently reviewable

## Status

Accepted within the approved document extraction-quality enhancement.

## Context

CSV/TSV extraction treated the first record as a header, omitted it from review, and copied its
wording into every later row. A reviewer could not exclude that record while keeping data rows.
A file without headers also lost its first data record. This is the same publication-boundary
problem addressed for Word tables in ADR-0056.

## Decision

New CSV/TSV extractions use `structured-delimited-rows-v1`. Emit every nonblank logical record,
including the first, as TABLE_ROW. R/C labels are record/field positions; no header semantics are
inferred. Empty fields have explicit markers. Quoted delimiters, escaped quotes and embedded line
breaks remain field text. Formula-like strings are inert text, never evaluated.

Keep neutral table parents. The first nonempty-width record establishes the rectangular width;
inconsistent widths fail visibly. Empty physical records are skipped but retain their positions.
Empty field-only records count toward limits and width but supply no business evidence. Limits
cover the first record, cumulative visited cells, 100,000 records, 1,000 fields per record, parser
field size and rendered character budget. Malformed input produces existing adapter errors.

Existing domain, port, JSON storage, review/build/activation/search API and UI contracts suffice.
No dependency, schema migration or composition change is introduced. The review warning explains
record numbering and extraction markers. Row labels identify logical records, not physical lines.

## Consequences

Owners can exclude first-record wording independently through existing review controls. Selected
adjacent records still provide approved context under ADR-0053. Previous extractions/publications
remain immutable; adopting the fix requires new upload, review and publication. Rebuilding old
extracted text alone retains copied wording. Owners must inspect affected legacy publications.

The UTF-8 budget adapter and embedding configuration are unchanged. Synthetic CSV/TSV fixtures
are contract evidence, not general format/OCR/retrieval quality qualification.
