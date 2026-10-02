# ADR-0061: Worksheet names remain independently reviewed evidence

## Status

Accepted within the approved extraction-quality ledger after ADR-0060.

## Context

XLSX row labels, section paths, chart/image parents and warnings copied worksheet names.
Excluding or correcting the heading did not remove its original wording from shared metadata.

## Decision

New XLSX uploads use `structured-xlsx-sections-v2`. Each worksheet name occurs as its own
reviewable HEADING text. Labels and section paths use `Worksheet N`, where N is the workbook
XML tab position, counting empty, hidden and chart tabs. Row labels use `Worksheet N!R:R`.
Hidden paths retain the existing `Hidden worksheet: ` prefix with the neutral identifier.
Images and charts use the same position mapping as rows; warnings do not copy worksheet names.

Reuse the existing hidden-sheet selection contract: new uploads expose/select `Worksheet N`;
legacy revisions retain their original name identifiers. No stored selection or revision is
rewritten. The original name remains visible in the owner's extracted heading. Preserve merge,
formula/cache, image readiness and chart extraction behavior. Formula references and chart text
may explicitly contain a worksheet name as source text; those are separately reviewed passages,
not metadata copies to sanitize or reinterpret.

Use existing extraction/review/publication ports, API projections, UI controls and persistence.
No new domain model, provider, dependency, migration, configuration or chunk policy is required.

## Consequences

Owners can correct/exclude names without metadata copies appearing in approved rows or citations.
Selected corrected headings can still supply approved same-sheet context. Existing publications
remain immutable; adoption requires a new upload, review and publication. Rebuilding old extracted
text retains its old metadata. This does not qualify workbook layout, OCR, retrieval, tokenization
or the overall enhancement. Remaining delivery and release work stays in the parent ledger.
