# ADR-0065: Scoped ingestion warnings, private source previews and asynchronous attachments

Status: Accepted for the requested document-ingestion completion scope. Deployment qualification
and CI remain separate release evidence.

## Decision

Preserve typed extraction warnings and their exact block IDs in immutable library versions.
Publication evaluates unresolved blockers against the current saved review. Only excluding the
specific affected block with a rationale resolves a scoped blocker. Corrections and unrelated
exclusions do not resolve it; re-inclusion restores it. Document-wide and legacy unscoped blockers
remain blocking. Public projections remove all warning/asset metadata, including excluded content.

Missing/unsupported Word and workbook images, and unsupported presentation graphics, have neutral,
independently excludable placeholder regions. These placeholders do not claim extracted content.
Word's additional unextracted regions are called out; OCR heading metadata uses positional labels.
Malformed PNG checksums become explicit adapter errors. Empty OCR configuration leaves the existing
safe image/PDF extractor enabled; an explicitly configured unavailable OCR runtime fails visibly.

Original source previews are owner-only, file-version/block-bound, non-cacheable raster responses.
Use the existing bounded extractor/asset port for images and PDF pages. Optional local LibreOffice
conversion provides PPTX slide rasters inside that child boundary, with a fresh private profile,
disabled macros, no shell invocation, a deadline and bounded output. External relationships and
active/embedded objects prevent conversion. Unsupported or unconfigured previews stay explicit;
there is no fabricated slide reconstruction or remote document upload. Full Word/spreadsheet layout
remains an original download; their supported image regions have raster previews.

Requirement and draft browser uploads use a separate AttachmentIngestion application facade and
202/status/retry/cancel routes. Reuse the existing durable ingestion metadata/blob/lease repository
with an explicit AttachmentTarget, rather than creating a synthetic Requirement or an AI job.
Such records are excluded from library lists, library review routes, handover and publication.
After scanned extraction, finalization and the completed-document marker share the Requirement
transaction. UploadDocument accepts the prepared extraction and applies the existing membership,
replacement-version, inclusion and downstream-invalidation rules. Recheck access at finalization.
Cancelled/stale leased work cannot commit. Existing synchronous upload APIs stay compatible.

## Consequences

The object graph remains in the composition root, with existing ports extended for attachment
status/finalization reads. JSON payload defaults retain legacy compatibility; no relational
migration is needed. The document worker also finalizes prepared attachments. Browsers poll only
outstanding processing and refresh evidence on completion, without requiring the upload page to stay open.

Legacy warning scopes and asset metadata are not inferred or rewritten. Old OCR publications may
still contain copied heading wording; owners must withdraw/re-upload/review affected originals.
Production OCR/scanner/Office-renderer qualification and large-portfolio queue performance remain
deployment evidence; deterministic fixtures are not a substitute for those checks.

Explicit failed-upload exclusion preserves the processing/quarantine status and blocks no longer
needed prompt input. It does not permit a quarantined retry or attach failed content.

Renderer invocation follows the official [LibreOffice startup parameters](https://help.libreoffice.org/latest/en-GB/text/shared/guide/start_parameters.html)
and [macro security levels](https://help.libreoffice.org/latest/en-US/text/shared/optionen/macrosecurity_sl.html).
