# Enhancement — Business need attachments as prompt input

## Objective
Implement the user-approved plan for Business need text, files, or both.

## User Outcome
Authors attach multiple DOCX, Markdown, PNG/JPEG, PDF, TXT and XLSX files directly
under Business need, save/resume their source and analyse it without mandatory text.
Figma designs use exported PNG, JPG or PDF files.

## In Scope
- Inline uploader/drop zone, processing rows, source selection, review, retry/removal.
- File-only source validation, atomic draft promotion and source-aware eligibility.
- Safe Markdown, raster image and visual PDF processing with evidence citations.

## Out of Scope
- Native .fig, live Figma links and legacy .doc.
- Provider-account changes, deployments and external backlog publication.

## Domain
Validated attachment-backed descriptions may be blank; ready versions require text
or image evidence. Intended failed uploads retain a source review blocker.

## Application Use Cases
Share current-source validation across promotion, updates and analysis. Extend upload
opt-in inclusion, draft inclusion/removal and metadata-only eligibility. Transfer
selected immutable versions during promotion and invalidate analysis after changes.

## Ports
Reuse document metadata/storage/extractor and provider-neutral analysis ports.
No new external integration boundary is introduced.

## Adapters
UTF-8 Markdown stays plain text. PNG/JPEG type/pixel validation and sanitation reuse
Pillow. PDF text plus bounded page renders use pypdfium2. Existing metadata JSON
persists requires_attention with a false fallback for legacy records.

## API
Uploads accept include_in_analysis=false by default. Add owned/version-checked
draft analysis-inclusion and deletion endpoints. Readiness responses consider files.
Regenerate OpenAPI and frontend types.

## UI
Embed source controls under Business need in new and edited Requirements. Ready
prompt uploads are selected by default. Show filenames, sizes, pending/ready/failed
status, preview, Include in analysis, retry, exclusion and removal. Disable analysis
until the title/source are ready and attachment mutations finish. Serialize draft
writes. Save-only remains provider-free and accepts partial input.

## Business Rules
Sources are untrusted business data. Preserve typed text independently of extraction;
surface source conflicts for review. Never silently drop image evidence. Keep the
10 MB per-file limit and existing resource/context budgets and ownership rules.

## Tests
Synthetic adapter/API cases cover attachment-only Markdown/DOCX/images/visual PDF,
combined input, source loss, failed-file review/retry, version conflicts, ownership,
legacy metadata, type/pixel checks and plain untrusted Markdown. UI cases cover
multi-file input, drop, transport failures, exclusion and resumed file-only analysis.
Browser journey covers upload, save, resume and background analysis at both viewports.

## Acceptance Criteria
- [x] File-only and combined sources reach reviewable source-linked analysis.
- [x] Draft sources and inclusion choices survive save/resume and promotion.
- [x] Intended failures and pending mutations prevent silent incomplete analysis.
- [x] Required backend/frontend gates and browser checks pass locally.

## Validation Evidence
Local verification on 2026-09-18. Browser providers use the fake model and an
isolated memory store; these checks do not evaluate a live model's interpretation.

Backend command results:
```text
python -m pytest
780 passed, 22 skipped, 1 warning in 118.40s (0:01:58)

python -m ruff check .
All checks passed!

python -m ruff format --check .
440 files already formatted

python -m mypy src tests
Success: no issues found in 345 source files

lint-imports
Contracts: 6 kept, 0 broken.
```

Frontend command results:
```text
npm run test
Test Files 24 passed (24)
Tests 141 passed (141)

npm run lint
exit code 0

npm run api:check
exit code 0; generated types match OpenAPI

npm run build
exit code 0; TypeScript and Vite production build passed

SMOKE_API_PORT=8067 SMOKE_UI_PORT=4187 npm run test:smoke
22 passed

git diff --check
exit code 0
```

The 22 skipped backend cases require TEST_DATABASE_URL; PostgreSQL integration
was not exercised. Existing Starlette deprecation and bundle-size warnings remain.
The document browser journey waits for resolved ownership permissions before file
selection. Desktop and responsive upload screenshots were visually inspected.

Validation covers file-only and combined sources, empty typed-description snapshot
round trips, saved selection/resume, citation assets, failed retries with legacy
default flags, explicit exclusion, last-source removal, source updates and analysis
invalidation, ownership/version conflicts, content/type/resource limits, and untrusted
Markdown. Existing text-only flows remain covered by the full regression suites.

CI has not run for these uncommitted changes. All required gates passed locally;
CI remains pending commit/push. The live API on port 8000 still exposes the old
upload schema and requires a backend restart plus a page refresh to load this code.

An earlier full browser run passed all attachment cases but failed one saved-view
check: POST saved-views returned 201, then GET returned an empty list while a
background suggestion job raised an in-memory transaction error. That intermittent
background-job/saved-view issue was observed outside the attachment feature and
remains an unresolved risk; the final browser result above is a separate full run.

## Deferred
CI verification requires a later commit/push. Live model semantic evaluation and
production deployment are outside this local implementation task.
