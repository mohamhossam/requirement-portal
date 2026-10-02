# ADR-0059: Text headings remain independently reviewed evidence

## Status

Accepted within the approved document extraction-quality enhancement after ADR-0058.

## Context

TXT/Markdown extraction copied hash-prefixed heading wording into descendant section paths.
Excluding or correcting a heading therefore left its original wording in public block metadata,
embedding labels, retrieval context headers and citation paths. Repeated headings after skipped
levels could also share or incorrectly nest context groups.

## Decision

New TXT and Markdown extractions use `structured-text-sections-v1`. Retain each heading's
original wording only in its own reviewable HEADING block. Section paths use neutral
`Heading at line N` coordinates. Track declared heading levels explicitly, dropping the current
level and deeper levels when a new heading starts. Repeated titles therefore remain distinct
sections, including when levels are skipped. Preserve physical line numbering, Unicode text and
the existing line-based hash-heading recognition in both formats.

A visible warning explains positional navigation and the limited Markdown interpretation.
This is not a Markdown renderer: links, HTML, images, fences, tables and setext headings are
retained as literal line evidence rather than semantically parsed or executed. No remote
resources are fetched. Reviewers still compare extracted lines against the original.

Reuse existing evidence/review/publication models, extraction port, API projections and browser
controls. A selected, corrected heading may contribute its reviewed wording to approved
same-section context; an excluded heading contributes no wording. No changes to child policies,
token counter, embedding configuration, composition, dependencies or persistence schema.

## Consequences

New uploads support independent heading exclusion/correction without residual metadata wording.
Stored extractions and publications remain immutable. Owners must inspect affected old text
publications and upload/review/publish a new version to adopt this fix; rebuilding old text alone
does not change section paths. This bounded fix does not resolve heading metadata in other formats
or qualify arbitrary Markdown layout, OCR, retrieval quality or model tokenization.
