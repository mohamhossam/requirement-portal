# ADR 0014 — Immutable source-document versions

## Status

Accepted

## Context

Requirement analysis can use uploaded PDF, DOCX, and TXT evidence. Reviewers
must know exactly which bytes influenced an analysis, unsafe document content
must not enter core logic, and durable deployments must not force blob data
into relational aggregate snapshots.

## Decision

Represent a source document as metadata with an ordered tuple of immutable
`SourceDocumentVersion` values. Each version records its filename, declared
MIME type, byte size, SHA-256 checksum, extraction result, and creation time.
Analysis inclusion selects one successfully extracted version explicitly; a
new version clears that selection and invalidates current generated content.

The application owns separate `DocumentRepositoryPort`, `DocumentStoragePort`,
and `DocumentExtractorPort` boundaries. Offline mode uses in-memory metadata
and blobs. Durable mode stores metadata in PostgreSQL and immutable bytes in a
configured filesystem root. Extraction adapters return plain text only and
reject mismatched signatures, unsafe DOCX packages, macros, corrupt content,
blank extraction, and over-budget analysis context.

Every `RequirementAnalysis` stores document ID, version ID, filename, and
checksum references. Revision snapshots therefore retain the exact evidence
reference after a document is replaced or removed; physical blob garbage
collection is outside this slice.

## Consequences

Review and audit can distinguish a logical document from each set of uploaded
bytes, and analysis never silently changes to a newer version. Relational
metadata and filesystem blobs require operational backup coordination. A blob
can remain orphaned if metadata persistence fails after its immutable write;
deferred garbage collection may reclaim such blobs later.

## Alternatives Considered

- Store mutable files in place: rejected because prior analyses would lose
  reproducible evidence identity.
- Store blobs inside Requirement snapshots: rejected because it inflates every
  revision and couples domain persistence to file transport.
- Render DOCX HTML: rejected because plain text is sufficient for analysis and
  has a substantially smaller active-content and injection surface.
- Silently truncate selected documents: rejected because it hides missing
  evidence from the reviewer and makes provenance misleading.
