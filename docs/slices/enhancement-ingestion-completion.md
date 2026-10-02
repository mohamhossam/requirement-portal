# Enhancement — Document ingestion completion

## Objective

Finish the user's document-ingestion scope within the reviewed document-knowledge enhancement:
safe source previews, content-scoped warning exclusions, asynchronous Requirement attachments,
remaining format/heading safeguards and regression fixtures. Implemented locally; CI and optional
runtime deployment qualification remain open. ADR-0065 records the structural decisions.

## User Outcome

Upload, follow processing across page reloads, retry/cancel, compare supported original source
regions with extraction, correct or exclude passages, review and explicitly publish in the browser.
Unsupported regions, unavailable renderers and failed extraction remain visible.

## In Scope

- Private original raster comparison for PDF pages, images/embedded regions and configured PPTX slides.
- Exact-block warning resolution, reversible through re-inclusion, with original warning history.
- Async Requirement/draft uploads and replacements with durable status, retry/cancel and inclusion.
- OCR heading isolation, missing-image/graphic placeholders, unextracted Word region notices and PNG CRC errors.
- Existing approval/indexing/publication and legacy synchronous upload contracts.

## Out of Scope

The broader parent enhancement's retrieval/load/semantic qualification, generalized lineage and
production scanner/OCR deployment remain tracked in that ledger. These are not new omissions.

## Domain

LibraryVersion retains assets and typed warning scope. Its unresolved-blocker calculation uses only
the latest saved review. AttachmentTarget distinguishes queued Requirement uploads from publishable
library documents. Legacy metadata remains immutable and conservative.

## Application Use Cases

DocumentLibrary returns owner-authorized, exact-version previews and preserves warning provenance.
AttachmentIngestion authorizes submission/status/control and transactionally finalizes scanned
results through UploadDocument. Membership and replacement guards are rechecked before attachment.

## Ports

Extend DocumentLibraryPort with attachment status/pending-finalization reads. Reuse extraction,
storage and transaction ports; no provider/framework dependency enters domain or application.

## Adapters

Memory and PostgreSQL JSON metadata implement the same queue reads. The bounded child handles
safe raster extraction and optional LibreOffice conversion. Office inputs with external references,
active/embedded objects or invalid bounds cannot be rendered. Default image/PDF extraction works
without OCR configuration; configured unavailable OCR fails explicitly.

## API

- `POST/GET /{requirements|requirement-drafts}/{source_id}/document-ingestions`.
- `POST /{scope}/{source_id}/document-ingestions/{id}/{retry|cancellation}` with expected version.
- Owner-only `GET /library/documents/{id}/versions/{version}/blocks/{block}/original-preview`.
- Existing review/publication response shows current unresolved blockers and original typed warnings.
- Existing error/status mappings reused; OpenAPI snapshot and generated browser types updated.

## UI

Existing DocumentPanel submits async uploads, restores processing status after reload, exposes
retry/cancel and refreshes completed evidence. Library review lazily opens source comparison next
to the affected passage, explains image transcription and scoped blockers, and keeps save-before-
approval guards. Incumbent responsive layout and visual identity retained.

## Business Rules

Only exact affected-block exclusions resolve scoped blockers. Unscoped and legacy blockers cannot
be bypassed. Originals remain owner-only even after selected passages are published. Attachment
completion does not publish shared knowledge. Review/approval and immutable history remain separate.

## Tests

Warning-scope/re-inclusion/legacy JSON fixtures; exclusion-to-publication trust checks; owner-only
source access and exact block identity; async idempotency/cancel/retry/quarantine/atomic completion;
OCR heading isolation, unsupported graphics and corrupt PNG; optional slide conversion/failure;
component upload/cancel/retry and full browser reload/source-comparison/publication flows.

## Acceptance Criteria

- [x] Browser uploads and status survive navigation/reload; retry/cancel remain explicit.
- [x] Supported source raster previews do not expose private originals to readers.
- [x] Exclusions resolve only their affected blockers and never unknown document-wide failures.
- [x] Format failures and unavailable preview/OCR runtimes remain explicit.
- [x] Local validation and browser evidence recorded below.
- [ ] CI green and real deployment scanner/OCR/Office-renderer qualification recorded.

## Validation Evidence

Executed on Windows, 2026-09-22, using `.venv/Scripts/python.exe` and `npm.cmd`.
The existing interpreter and generated-file tools required sandbox escalation; execution was
approved. No live provider calls were made by the deterministic gates.

| Command | Recorded output |
|---|---|
| `.venv/Scripts/python.exe -m pytest` | `1355 passed, 36 skipped, 1 warning in 817.60s (0:13:37)` |
| `.venv/Scripts/python.exe -m pytest tests/unit/test_ingestion_completion.py tests/unit/test_ingestion_format_safeguards.py tests/unit/test_document_library.py` | Final recovery/scope regression rerun: `49 passed, 1 warning in 3.00s` |
| `.venv/Scripts/python.exe -m ruff check .` | `All checks passed!` |
| `.venv/Scripts/python.exe -m ruff format --check .` | `846 files already formatted` |
| `.venv/Scripts/python.exe -m mypy src tests` | `Success: no issues found in 408 source files` |
| `.venv/Scripts/lint-imports.exe` | `Analyzed 353 files, 2537 dependencies. Contracts: 6 kept, 0 broken.` |
| `npm.cmd run api:check` | OpenAPI TypeScript regenerated in a temporary directory; no drift, exit 0. |
| `npm.cmd run typecheck` | `tsc -b --pretty false`, exit 0. |
| `npm.cmd run lint` | `eslint .`, exit 0. |
| `npm.cmd run test` | `Test Files 40 passed (40); Tests 275 passed (275)` |
| `npm.cmd run build` | `2002 modules transformed`, production build succeeded. |

One component run encountered simultaneous long timing stalls across unrelated tests; an isolated
full rerun passed all 275 tests. The original browser PNG fixture exposed a malformed CRC escaping
as SyntaxError. That is now an explicit adapter failure with a regression fixture; a validated
source image then passed browser source comparison/publication. These failed attempts are not
counted as successful validation.

Final browser command, with isolated `SMOKE_API_PORT=8119` and `SMOKE_UI_PORT=4199`:
`npm.cmd run test:smoke -- ingestion-completion.spec.ts library-flow.spec.ts` — `8 passed (1.2m)`.
It includes reload, failed-upload retry/exclusion, source raster decoding, review/publication,
withdrawal and exact historical citations at both viewport widths.
Final component checks after the initial-status guard: `16 passed (16)` across DocumentPanel and
NewRequirementPage, followed by a successful production build. Desktop (1440px) and narrow (740px)
source-comparison and attachment screenshots were inspected: controls and source content remain
within their columns, with narrow stacking. A white synthetic image tests raster decoding, not
OCR accuracy or Office rendering fidelity.

## Changed Files

- Domain/ports: `domain/document/library.py`, `application/ports/document_library.py`.
- Application: `application/use_cases/attachment_ingestion.py`, `document_library.py`, `documents.py`.
- Adapters: `infrastructure/persistence/document_library.py`, `infrastructure/config/settings.py`,
  `infrastructure/documents/{bounded_extractor,library_worker,local_ocr,office_preview,process_resources,text_extractor}.py`.
- API wiring/routes: `interfaces/api/{container,dependencies}.py`, `interfaces/api/routes/{documents,library}.py`.
  Python paths above are relative to `src/smb_requirement_agent/`.
- Browser: `frontend/src/features/documents/{DocumentPanel,OriginalPreview}.tsx`,
  `frontend/src/app/{LibraryPage.tsx,library.css}`, API client and generated OpenAPI/types.
- Regressions: `tests/unit/test_ingestion_completion.py`, `test_ingestion_format_safeguards.py`,
  extraction-version expectations in existing Word/XLSX/library/API/PostgreSQL fixtures;
  `frontend/src/features/documents/DocumentPanel.test.tsx`, `frontend/src/app/{NewRequirementPage,LibraryPage}.test.tsx`,
  `frontend/tests/ingestion-completion.spec.ts`, existing review-flow/spreadsheet upload expectations.
- Documentation: this spec, ADR-0065, architecture index, parent enhancement ledger, ROADMAP,
  WORKSPACE, AGENTS legacy-OCR debt, document-knowledge runbook and `.env.example`.


## Deferred

LibreOffice is not installed on this host. Its conversion/failure contract is tested with a
deterministic adapter fixture; actual slide-rendering fidelity requires deployment qualification.
Without it, the browser gives a clear unavailable state and offers the original/PDF export path.
Real Docling/Tesseract and ClamAV deployment checks remain in the parent release ledger. PostgreSQL
tests require TEST_DATABASE_URL; skipped tests are not claimed as passing. CI has not run for this
uncommitted checkout.

The final focused rerun also covers draft completion, denied source access, quarantine-preserving
exclusion, external/embedded Office rejection and renderer process-tree cleanup. All 49 cases
passed; subsequent mypy, Ruff and all six import contracts passed.
