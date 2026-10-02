# Enhancement — Reviewed document ingestion and Requirement knowledge

## Objective

Implement the user's approved five-slice ingestion/retrieval plan. **In progress, not complete or
production-qualified.** This checkpoint delivers a usable standalone library path; it does not
claim delivery of all five slices. No outstanding scope has been agreed for omission.

Owner-reviewed reference applicability and bounded same-section retrieval context are the two
follow-up checkpoints; see `enhancement-reference-applicability.md`,
`enhancement-reference-parent-context.md`, ADR-0052 and ADR-0053.
The next checkpoint adds rendered table-field children and explicit, owner-scoped corpus builds;
see `enhancement-table-corpus-builds.md` and ADR-0054.
PowerPoint row-level extraction and exclusion now have a dedicated quality checkpoint;
see `enhancement-presentation-tables.md` and ADR-0055. This does not close general format quality.
Word table rows now have their own checkpoint for exclusion-safe headers/merges, grid positions
and independently reviewed nested tables; see `enhancement-word-tables.md` and ADR-0056.
The CSV/TSV checkpoint makes the first record independently reviewable without copied headers;
see `enhancement-delimited-rows.md` and ADR-0057.
The XLSX checkpoint exposes merged anchors and continuations without copied wording;
see `enhancement-spreadsheet-merges.md` and ADR-0058.
The TXT/Markdown checkpoint makes heading exclusion/correction safe in descendant metadata;
see `enhancement-text-sections.md` and ADR-0059.
The Word prose checkpoint removes copied labels/heading paths while retaining table/image rules;
see `enhancement-word-prose.md` and ADR-0060.
Worksheet names now have an independent heading/positional-metadata checkpoint;
see `enhancement-worksheet-names.md` and ADR-0061.

The chunking/indexing checkpoint adds dedicated Requirement indexing and actual-model fixture
qualification; see `enhancement-chunking-indexing.md` and ADR-0062. Overall production qualification
remains open.

The ownership/dependency checkpoint adds known-user handover with immutable transfer history and
member-filtered current/historical Requirement reference dependencies; see
`enhancement-library-governance.md` and ADR-0063. The user explicitly excluded delegated reviewers
from this checkpoint. ADR-0066 completes recorded copied-content lineage and indexed impact review; see `enhancement-source-lineage.md`.

The Search and AI grounding checkpoint completes unified search, reference-backed answers and
reference-conflict screening, with a separate semantic evaluation rubric/calculator. See
`enhancement-search-ai-grounding.md` and ADR-0064; actual human/model qualification remains open.

## User Outcome

From Documents → Shared knowledge library, an owner can upload a reference, observe processing,
correct/exclude extracted passages, preview saved chunks, approve exact content, search published
passages, upload an immutable replacement, and withdraw evidence. A citation opens its exact
published file/extraction revision, even while a newer upload is private or the cited block is
beyond the first review page. Original downloads remain owner-only to avoid leaking exclusions.

## In Scope / Delivery Ledger

| Approved slice | Delivered at this checkpoint | Still required; not dropped |
|---|---|---|
| Library and governance | Independent owned documents; immutable uploads; extraction review history; fingerprint-bound approvals; withdrawal; owner/public projections; audited ownership transfer; member-filtered current/historical Requirement reference dependencies and publication currency; API/browser | Recorded lineage and indexed reconciliation completed by ADR-0066; unrecorded legacy origins stay unknown |
| Ingestion | Durable leased attempts; idempotency; cancel/retry; separate bounded child extraction; ClamAV protocol; PPTX and CSV/TSV adapters; reviewable PowerPoint and Word table rows with positions/merge annotations and exclusion-safe parents; independent nested Word tables; exclusion-safe first-record CSV/TSV review with positional fields; bounded row-local XLSX merge annotations; TXT/Markdown locations and exclusion-safe positional heading paths; correction-safe Word prose labels and paths; independently reviewed worksheet names with neutral row/image/chart paths; local OCR adapter boundary | Real Docling/Tesseract/Office renderer deployment qualification and production-format representativeness. ADR-0065 adds private raster previews, scoped warning exclusions, async attachments, OCR heading isolation and format regression fixtures |
| Chunking and indexing | Isolated child blocks/heading metadata; sentence-preferred bounded splitting; exact-child citations; bounded approved same-section context; explicit conservative budget counter; rendered table/wide-row field packing and long-field labels; hashes/cache; durable 16-chunk batches; versioned owner-scoped corpus build manifests, explicit activation/discard and rebuild; old version retained until activation; dedicated bounded/resumable Requirement index worker and API/browser recovery; reviewed structured-table fixture matrix; actual gemini-embedding-001 token measurements and acceptance for 64 synthetic samples; two-owner real-model rollout/rollback and PostgreSQL contract | Production/customer-table representativeness and deployed maintenance qualification remain release work; existing clean Requirement indexes adopt new children by source change or explicit rebuild |
| Retrieval and grounding | Document-only POST /knowledge/search plus member-filtered unified search; reference-backed clarification suggestions with immutable citations and stale-selection guards; reference-conflict screening; explicit semantic-judgment evaluation; bounded hybrid search; Arabic normalization; exact live citation checks; labelled analysis reference proposals/conflicts; owner rationale/decisions; immutable citation lineage; lazy confirmation/generation/final-approval staleness checks | Recorded index lineage and broader dependency tracking completed by ADR-0066; actual human-labelled semantic quality qualification remains |
| Production qualification | Functional/failure tests; real PostgreSQL/pgvector contract; deterministic evaluation calculator; setup/recovery checklist | Actual human-labelled 200-query/50-cross-language evaluation, latency/load harness and measurements, quotas/metrics/alerts, nonempty restore rehearsal, real scanner/OCR deployment checks, green CI |

## Out of Scope

New object storage, multi-tenant portfolios, automatic policy applicability, automatic approval of
legacy attachments, and external backlog publication.

## Domain

`domain/document/library.py`: LibraryDocument, LibraryVersion, ExtractionRevision, ReviewedPassage,
Publication and explicit ingestion states. Publication binds file/revision/content selection and
chunking policy. Upload metadata remains immutable. Approval is not applicability confirmation.

## Application Use Cases

`DocumentLibrary` owns submission, visibility, review, approval, withdrawal and processing control.
`ReferenceKnowledge` owns chunk previews, recoverable embedding batches, current-source search and
bounded same-section context reconstructed from the approved revision.
`retrieval_evaluation.py` calculates distinct-source recall, hit rate, nDCG and trust-boundary gates.
Existing full-primary-document analysis and bilateral Requirement conflict workflows are unchanged.

## Ports

DocumentLibraryPort, DocumentScannerPort, ReferenceIndexPort and TokenCounterPort. Reuse existing
blob storage, extraction, configured embedding, clock and transaction ports. No adapter is selected
outside the composition root.

## Adapters

Memory and PostgreSQL metadata/index implementations; additive migration 022; existing PostgreSQL
blobs; ClamAV INSTREAM; explicit fake-only offline scanner; isolated safe format extraction and
optional Docling/Tesseract eng+ara processing. OCR assets and Tesseract are not installed or qualified
by this checkpoint. Missing models/scanner fail visibly rather than yielding empty success.

The current counter charges one UTF-8 byte per budget unit; 512/768 are conservative units, **not
measured model tokens**. ADR-0062 now records separate actual-model measurements for 64 synthetic
fixtures (18–528 gemini-embedding-001 tokens). These qualify fixture safety, not optimal packing or
cross-language retrieval quality; production evaluation remains open.

## API

- POST /library/ingestions: multipart, bounded upload, key and optional replacement identity.
- GET /library/documents and /library/documents/{id}: authenticated visibility/status/history.
- Version original/review/approval/retry/cancellation routes; document withdrawal/index-retry.
- GET /library/documents/{id}/chunks/preview: owner-only saved-review preview.
- POST /knowledge/search: approved document passages only.
- POST /knowledge/search/unified: published passages and member-visible Requirement evidence (ADR-0064).

## UI

Lazy route /documents/library and exact version-bound citation view. Separate current upload and
published version states; side-by-side extracted/reviewed text, selections, exclusion reasons,
20-passage review pages, saved chunk preview with separate exact/context views, approval,
withdrawal, retry and replacements.
Unsaved passage edits block approval and clear stale previews. Mutation refresh clears old search
results. English/Arabic passage text uses automatic direction. This is not an original-page renderer.

Impeccable preserved the incumbent interface and required independent finish review/documentation.
The reviewer found and verified fixes for unsaved approval, replacement-state clarity, and exact
citation navigation. Final `ship` disposition covers the last scored citation fix only. The independent
documenter confirmed no new visual system; pre-existing DESIGN.md/token drift was not repaired.
Vercel React guidance informed lazy loading and actor-scoped query caching.

## Business Rules

- Private uploads and excluded passages never enter a public document projection.
- Original binaries can contain exclusions and are not shared merely because some text is published.
- Only the owner mutates/approves; optimistic versions fence concurrent updates.
- Ingestion leases and index leases prevent stale workers committing results.
- Index retries back off and stop after three attempts; owner retry remains explicit.
- Partial embedding batches remain unsearchable. Approval activates only after complete indexing.
- Withdrawn evidence is filtered both before candidate retrieval and before returning citations.
- Historical edits/approvals remain auditable. Active analysis reference staleness now guards
  confirmation/generation/final approval; broader portfolio dependency integration remains open.

## Tests

Unit/API coverage includes owner access, private/public projections, exclusion leakage, immutable
replacement, idempotency, CAS conflicts, cancellation/quarantine, expired attempts, index backoff,
lease fencing, withdrawal during embedding, partial-batch resume, malformed scanner verdicts,
Arabic chunk budgets, original line numbers, CSV inert values and evaluation arithmetic.

PostgreSQL integration verifies migration, durable publication after restart, replacement continuity
and withdrawal. Browser tests exercise publish/search/withdraw and exact passage 21 from published
v1 while v2 is private, at desktop and narrow widths.

## Acceptance Criteria

- [x] Standalone reference upload → review → owner approval → search → withdrawal is usable.
- [x] Exact selected publication is enforced in application, persistence and browser paths.
- [x] Library partial indexing and stale processing cannot publish incomplete results.
- [x] Existing primary-document analysis remains intact.
- [x] Exact child citations retain bounded owner-approved same-section context without re-embedding.
- [ ] All remaining approved ledger scope is implemented.
- [ ] Bilingual OCR/retrieval and one-million-chunk performance targets are demonstrated.
- [ ] All repository gates and CI are green; restore rehearsal is recorded.

## Validation Evidence

Executed locally on Windows, 2026-09-21. PostgreSQL tests used only the dedicated disposable database
`codex_document_knowledge_test_20260921`, not the application's normal database.

The bounded surrounding-context checkpoint supersedes the counts below with 1,206 backend tests,
265 frontend tests and four passing desktop/narrow library browser cases. Full evidence, including
the unchanged repository-wide Ruff and legacy source-dialog failures, is recorded in
`enhancement-reference-parent-context.md`.
The later table/build checkpoint records 1,216 backend tests, 267 frontend tests, eight passing
library/reference browser cases and a final two-case build rerun after an edit-preservation fix.
See `enhancement-table-corpus-builds.md`; the inherited Ruff and source-dialog failures were
reproduced, and CI remains unverified.
The PowerPoint table checkpoint adds row-local extraction/exclusion coverage: 1,229 backend tests,
267 frontend tests and two desktop/390px presentation browser cases pass. Full evidence is in
`enhancement-presentation-tables.md`; the same repository-wide Ruff/format failures and pending CI
remain open. No tokenizer or representative production extraction qualification is implied.
The subsequent Word checkpoint records 1,247 backend tests, 267 frontend tests, four passing
Word/PowerPoint library browser cases and two passing attachment regression cases after updating
the extraction expectation/source selectors. See `enhancement-word-tables.md`; legacy DOCX
publication cleanup, inherited Ruff/format failures and CI remain open.

The CSV/TSV checkpoint records 1,269 backend tests including PostgreSQL, 267 frontend tests and
eight passing CSV/TSV/Word/PowerPoint browser cases. See `enhancement-delimited-rows.md` for actual
commands, the local Docker/IPv4 recovery, inherited repository failures and unverified CI. This
is format-contract coverage, not completion or production qualification of the enhancement.

The XLSX merge checkpoint records 1,292 backend tests including PostgreSQL, 267 frontend tests,
eight passing library browser cases and two passing attachment cases after correcting a new test's
synchronous checkbox expectation. See `enhancement-spreadsheet-merges.md` for actual failures,
rerun evidence and preserved limits. Repository-wide Ruff and CI remain open.

The TXT/Markdown heading checkpoint records 1,313 backend tests including PostgreSQL, 267 frontend
tests and eight passing text/library browser cases. See `enhancement-text-sections.md` for the
initial stale-version test failure, corrected full rerun, transient Docker socket recovery and
unchanged inherited gates/CI limits. This remains bounded format-contract coverage.


The Word prose checkpoint records 1,327 backend tests including PostgreSQL, 267 frontend tests
and eight passing Word prose/table/attachment browser cases. See `enhancement-word-prose.md` for
actual commands and results. New Word metadata is correction/exclusion-safe; existing publications,
inherited repository failures, unqualified tokenizer and overall enhancement scope remain open.


The worksheet-name checkpoint records 1,335 backend tests including PostgreSQL with no skips,
267 frontend tests and eight passing desktop/mobile worksheet/merge/attachment browser cases.
See `enhancement-worksheet-names.md` for actual commands and the corrected fixture typing failure.
New XLSX metadata isolates name review while preserving legacy selections and publications.
Inherited repository failures, earlier source-panel positioning, unqualified tokenizer, CI and
all remaining ledger work remain open; this is local implementation evidence only.


```text
TEST_DATABASE_URL=<dedicated test database> .venv/Scripts/python.exe -m pytest
1196 passed, 1 warning in 123.97s

.venv/Scripts/python.exe -m ruff check src tests scripts/evaluate_document_knowledge.py
All checks passed!

.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 372 source files

.venv/Scripts/lint-imports.exe
Contracts: 6 kept, 0 broken

npm --prefix frontend run api:check
PASS — generated TypeScript contract matches snapshot
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test
Test Files 38 passed (38); Tests 263 passed (263)
npm --prefix frontend run build
PASS — 1999 modules transformed

SMOKE_API_PORT=5281 SMOKE_UI_PORT=5282 npm --prefix frontend run test:smoke -- library-flow.spec.ts
4 passed (26.4s)

SMOKE_API_PORT=5283 SMOKE_UI_PORT=5284 npm --prefix frontend run test:smoke -- attachment-flow.spec.ts analysis-sources.spec.ts
4 passed, 2 failed (34.3s)
Attachment cases passed. Existing analysis-sources cases expect "View sources for ...";
the current source-panel accessible label is "Where this came from: ...".

.agents/skills/impeccable/scripts/impeccable.cmd detect --json <LibraryPage.tsx> <library.css>
[]
```

Repository-wide gates were executed, not skipped:

```text
.venv/Scripts/python.exe -m ruff check . --output-format concise
FAIL — Found 72 errors, all in .claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py
.venv/Scripts/python.exe -m ruff format --check .
FAIL — 3 files would be reformatted, 777 files already formatted (same unrelated skill scripts)
```

Those unrelated scripts were preserved; no exclusion was added to hide them. Earlier local failures
(lifecycle fixture wiring, stale OpenAPI, database-test isolation, test selectors) were corrected and
superseded by the runs above. CI has not been run/pushed. No live OCR, live ClamAV, human retrieval
benchmark, scale benchmark or backup-restore success is claimed.

## Deferred / Open

The ledger's unfinished work remains in the approved enhancement, not an agreed scope reduction.
Operational instructions and required release evidence are in `docs/operations/document-knowledge.md`.

Document ingestion completion is recorded in `enhancement-ingestion-completion.md` and ADR-0065;
original-source comparison now uses safe raster previews where supported, with explicit unavailable
states and original downloads elsewhere. The parent release-qualification ledger remains open.

Source-lineage completion and current validation: `enhancement-source-lineage.md` (ADR-0066).
Its final repository/CI results supersede earlier checkpoint gate statements for the same tree.

Release validation follow-up: `production-readiness-qualification.md` records current CI inspection,
synthetic nonempty backup/restore and bounded HTTP concurrency measurements. Environment-specific
operations, representative human/model evaluation and full capacity qualification remain open.
