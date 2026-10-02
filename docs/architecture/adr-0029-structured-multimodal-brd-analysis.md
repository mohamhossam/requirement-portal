# ADR 0029 — Structured Multimodal BRD Analysis

## Status

Accepted.

## Context

Flattening a DOCX into one string loses headings, table relationships, and images. It also
causes otherwise valid BRDs to exceed a local model's context window. Raising that window is
not a reliable or scalable document-analysis strategy, and referenced workbooks must never be
fetched or interpreted implicitly.

## Decision

Immutable source-document versions may carry ordered evidence blocks, safe raster assets,
extraction warnings, and an extraction-format version while retaining `extracted_text` for
compatibility. Analysis items cite exact block IDs together with document version and checksum.

Application services plan bounded section-aware packets, validate all provider citations, cache
successful fragments by source/prompt/model/extraction fingerprints, and hierarchically
consolidate validated packet findings. A failed packet or consolidation does not commit a partial
analysis. Concrete DOCX/XLSX, model, cache, and persistence implementations remain adapters
selected by the composition root.

XLSX formulas are never executed, hidden sheets are opt-in, external relationships and OLE
objects are never followed, and meaningful image evidence blocks analysis when the configured
provider cannot accept images. HTTP asset access is authenticated and checksum-bound to an
immutable source version.

## Consequences

Large structured documents can be analyzed within provider budgets with exact source links and
retryable cached work. Cross-section contradictions receive a focused consolidation pass instead
of a string concatenation merge. Storage and provider traffic increase, extraction is more
complex, and legacy uploads require a new immutable version to gain structured evidence.

## Alternatives Considered

- Increase the local context window: useful as a temporary workaround but still loses document
  structure and does not scale to larger inputs.
- One Requirement per BUC: rejected because source sections are traceability boundaries inside
  one initiative, not independent business requirements.
- Automatically fetch linked workbooks: rejected for security, provenance, and authorization
  reasons.
