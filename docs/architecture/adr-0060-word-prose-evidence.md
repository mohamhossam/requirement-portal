# ADR-0060: Word prose corrections do not retain original metadata wording

## Status

Accepted within the approved extraction-quality ledger after ADR-0059.

## Context

ADR-0056 isolated Word table rows, but body headings still supplied descendant section paths.
Body paragraph/list labels also copied original wording. Excluding a heading or correcting a
paragraph could therefore leave original wording in public metadata, index labels and citations.
Repeated heading text also grouped distinct sections together.

## Decision

New DOCX uploads use `structured-docx-sections-v2`. Body headings, paragraphs and list items use
`Paragraph N` locations. Number direct body paragraphs including blanks and skipped table-of-
contents entries; table paragraphs keep their independent table/row locations from ADR-0056.
Heading paths use `Heading at paragraph N`, retaining declared level ancestry and distinct source
positions. The original wording remains in the block text for independent review and correction.

Image and external-reference blocks use neutral section paths. Preserve the existing unsupported-
image readiness rule using an adapter-local boolean derived from the original root heading:
documents without a heading and the existing introductory/document-control contexts keep their
existing treatment. Tables retain separate neutral parents and their existing image rules.
This metadata change does not reclassify images or qualify that legacy heuristic.

A review warning explains positions and the scope of paragraph numbering. Reuse existing
evidence/review/approval models, extraction ports, API projections, UI controls and persistence.
No new dependency, migration, tokenizer, embedding setting or chunk-policy identity is introduced.

## Consequences

Reviewed prose can be corrected without original text surviving as a label. Excluded headings
leave no wording in descendants' paths. Included corrected headings can still supply approved
same-section context. New positional paths keep repeated source sections distinct.

Stored revisions/publications remain immutable. Owners must inspect affected legacy Word
publications and upload/review/publish a new version; rebuilding stored extraction alone preserves
old metadata. Full Word layout/headers/footers/text boxes, broader OCR/format quality and remaining
shared-knowledge qualification are separate ledger work. No completeness or production claim.
