# Slice 5D — Source Documents

## Objective

Let authors attach safe, versioned supporting evidence, choose the exact
versions included in analysis, and review extraction/provenance without
coupling the domain to blob storage or document libraries.

## User Outcome

An author can upload PDF, DOCX, or TXT evidence from intake/capture, see an
explicit extraction result, include or exclude usable versions, inspect safe
previews and metadata, upload a new immutable version, remove current context,
and trace the checksum used by analysis.

## Domain

- `SourceDocument` belongs to exactly one draft or Requirement and retains an
  ordered immutable version history.
- `SourceDocumentVersion` records ID, filename, MIME type, size, SHA-256,
  extraction status/error/text, and creation time.
- Only active, successfully extracted current versions can be included.
- Uploading a new version clears prior inclusion; removal is logical and keeps
  metadata/history available to persisted revisions.
- `RequirementAnalysis.document_references` records the exact selected IDs and
  checksums.

## Application

- Upload/list/get/version/include/remove use cases validate scope and assemble
  provider-neutral analysis context.
- Inclusion changes, removal, and replacement of an included version use the
  existing transactional invalidation boundary.
- Draft promotion atomically moves attachment metadata to the Requirement.
- Selected extracted text exceeding the configured context budget fails
  explicitly; it is never truncated.

## Ports

- `DocumentRepositoryPort` for metadata.
- `DocumentStoragePort` for immutable bytes.
- `DocumentExtractorPort` for untrusted file conversion to plain text.
- The existing analyzer port accepts typed document context independently of
  provider payloads.

## Adapters

- In-memory metadata/blob adapters keep offline mode account-free.
- PostgreSQL metadata migration `004_source_documents.sql` plus filesystem blob
  storage provide durable mode.
- `SafeDocumentTextExtractor` supports PDF, DOCX, and UTF-8 TXT, verifies
  signature/extension/MIME agreement, rejects traversal archive entries and
  macros, limits expanded DOCX size, and emits plain text only.

## API

- Upload/list/version endpoints under Requirement and draft attachments.
- Project catalogue, detail, extracted content, and safe PDF endpoints under
  `/documents`.
- Requirement inclusion and logical removal endpoints.
- Unsupported/unsafe/extraction/context errors are centrally mapped to 4xx;
  storage failure is a mapped 500 and provider failures remain 502.
- OpenAPI and TypeScript types include document metadata and analysis evidence
  references.

## UI

- Intake and Capture expose accessible upload, extraction failure, metadata,
  review, include/exclude, and remove controls.
- `/documents` is enabled only now that its backend capability exists.
- `/documents/:documentId` provides metadata, checksum, version history,
  escaped extracted text, safe browser PDF preview, and new-version upload.
- The reusable header exposes only Worklist and Documents; later Library,
  Archive, Reports, assignments, and profile navigation remain absent.
- Layout reflows at the existing responsive breakpoint and uses local Archivo
  and Lucide assets only.

## Tests

- Domain: immutable versioning, inclusion guard, snapshot round-trip.
- Adapter: signature/MIME mismatch, traversal, macros, corrupt/blank content,
  storage root/path failures, and PostgreSQL restart durability.
- Application/API: size/context limits, draft promotion, exact analysis
  provenance, inclusion/replacement/removal invalidation, and error mapping.
- UI: multipart boundary, upload failure preservation, safe plain-text render,
  include/remove controls, catalogue/detail, immutable version journey, and
  desktop/responsive Playwright coverage.

## Acceptance Criteria

- [x] PDF, DOCX, and TXT uploads are limited to 10 MB by default.
- [x] Declared MIME type, extension, and file signature/content agree.
- [x] Extracted content is plain text and unsafe DOCX content is rejected.
- [x] In-memory and durable metadata/blob adapters are composition-root wired.
- [x] Selection is explicit and over-budget context is never truncated.
- [x] Every analysis records exact document version/checksum references.
- [x] Replacing/removing selected evidence invalidates current generated work.
- [x] Historical revision snapshots retain prior evidence references.
- [x] Catalogue and safe detail/preview routes are keyboard accessible and
  responsive.

## Validation Evidence

- `.venv\Scripts\python.exe -m pytest -q` — PASS, 390 passed / 5 live
  PostgreSQL tests skipped because `TEST_DATABASE_URL` is absent.
- `.venv\Scripts\python.exe -m ruff check .` — PASS, all checks passed.
- `.venv\Scripts\python.exe -m ruff format --check .` — PASS, 226 files
  formatted.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS, no issues in 186
  source files.
- `.venv\Scripts\lint-imports.exe` — PASS, 2 contracts kept / 0 broken.
- `npm.cmd run api:check` — PASS; committed TypeScript matches OpenAPI.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS, 14 files / 58 tests.
- `npm.cmd run build` — PASS, Vite emitted local Archivo assets.
- `npm.cmd run test:smoke` — PASS, 4 journeys across Chromium 1440×1000
  and responsive Chromium 740×1000.
- Catalogue screenshots from both viewports were visually inspected in
  `frontend/test-results/`.
- CI — not independently verifiable from this workspace because the GitHub
  repository is private and no authenticated GitHub CLI/session is available.

## Agreed Omission

The user-approved phased implementation plan scoped Slice 5D to Source
Documents and did not include the roadmap's maintained template/example
library. That library is not represented by mock choices or nonfunctional
controls. It is carried as a separately schedulable `5D.1 Maintained
Template/Example Library` enhancement and recorded in the debt register.
