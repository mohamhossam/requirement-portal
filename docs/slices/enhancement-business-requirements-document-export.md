# Enhancement — Business Requirements Document export

Requested by the owner on 2026-10-30: "the BRD business requirement document to be exported in the
standard way". Decision record: ADR-0119. Formats Word and Markdown; available once the analysis
is confirmed; offered on the Confirm view and the History screen; conventional BRD sections.

**Scope.** Declared frontend feature work beyond the presentation-only rule in `CLAUDE.md`: a new
download capability on two screens, built from the existing primitives (`Card`, `Badge`, `Button`,
the lucide `Download` icon) and the download pattern the approved export already uses.

---

## Objective

Let the requirement team take the confirmed analysis away as a conventional Business Requirements
Document, rendered deterministically from the immutable revision, so stakeholders who never open the
portal can read, circulate and sign it.

## User Outcome

- A Requirement Owner, business analyst or reviewer downloads the document as Word or Markdown from
  the Confirm view as soon as the analysis is confirmed, and from History at any later time.
- Once the backlog has formal final approval, the same document carries the approved Epic, Features,
  Stories and acceptance criteria as functional requirements, so one file holds the whole case.
- Uncertainty is never hidden: assumptions, dependencies, open questions and ambiguities appear
  with their status and the answer a person gave.

## In Scope

- `RequirementSpecification` contract (schema 1.0), `SpecificationExportPort`, the
  `ExportRequirementSpecification` use case and two errors.
- Word (`python-docx`) and Markdown renderers over one shared outline.
- `GET /requirements/{id}/revisions/{n}/specification?format=docx|md` and three additive fields on
  `BreakdownRevisionResponse`.
- History card and Confirm status-strip controls, with tests and the browser journey.
- Slice spec, ADR-0119, roadmap, changelog, product brief, UX plan, glossary.

## Out of Scope

- PDF output.
- Any model call. The document is copied from stored, confirmed data.
- Changes to the neutral backlog export (ADR-0023), its 1.x schema or the knowledge handoff.
- A new permission flag; the export's `can_export_approved_revisions` (owner or reviewer) applies.

## Domain

- No change. The document is read from `BreakdownRevision` (confirmed analysis, epic, features,
  stories, review) and the `RequirementRevision` the analysis was made from.

## Application Use Cases

- `ExportRequirementSpecification.execute(requirement_id, revision_number, format, actor)`:
  requirement exists → member authorisation → revision exists → analysis confirmed → select the
  requirement revision → build the document → render. Public helpers `is_specification_available`,
  `select_requirement_revision`, `build_requirement_specification`.
- Errors: `RequirementSpecificationNotAvailableError` → `requirement_specification_not_available`
  (409); `SpecificationExportFormatError` → `specification_export_format` (422).

## Ports

- `governance/application/ports/specification_export.py` — `SpecificationExportPort`: `format`,
  `extension`, `media_type`, `render(document) -> bytes`.

## Adapters

- `governance/infrastructure/exports/specification_outline.py` — the document as ordered blocks
  (headings, paragraphs, bullets, tables), numbered 1–16 after the cover and document control.
- `docx_specification_exporter.py` — python-docx; deterministic core properties; archive rewritten
  with sorted entries and fixed timestamps; illegal-XML guard.
- `markdown_specification_exporter.py` — GitHub-flavoured Markdown, UTF-8, LF, escaped table cells.
- `xml_text.py` — the control-character guard, now shared with the XLSX exporter.

## API

- `GET /requirements/{requirement_id}/revisions/{revision_number}/specification?format=docx|md`,
  `Content-Disposition: attachment; filename="requirement-<id>-business-requirements-v<n>.<ext>"`,
  `Cache-Control: private, no-store`. 403 observer, 404 unknown requirement or revision, 409
  unconfirmed, 422 unknown format.
- `BreakdownRevisionResponse.specification_available`, `.analysis_confirmed_by`,
  `.analysis_confirmed_at`. `frontend/openapi.json` and `schema.d.ts` regenerated.

## UI

- History (`RevisionPanel`): a "Business Requirements Document" card under the approved export (or
  the "nothing approved" card), for the approved version or else the newest confirmed one, with a
  Word/Markdown format choice, one download button, a polite status line and an alert on failure.
  The same restricted-copy sentence as the export when the person is not on the team.
- Confirm (`StatusStrip`): once the analysis is confirmed, a row "Business Requirements Document,
  version N" with "Download Word document" and "Download Markdown", busy state, status and alert.
  The revision number comes from the History query, enabled only once confirmed and refreshed after
  confirmation.

## Business Rules

- The document exists for a revision whose analysis the owner confirmed; nothing earlier.
- Functional requirements appear only when the same revision holds a formal final approval and a
  complete tree; otherwise the section states the backlog is not approved.
- Every statement keeps its origin (captured with the need, found by the analysis, accepted
  proposal) and evidence; repeated wording is listed once.
- Assumptions are labelled as not confirmed; every uncertainty shows Open or Resolved with the
  answer, who answered and when; answered items the analysis no longer lists stay in the record.
- People appear by display name only.
- Rendering is deterministic: the same revision gives the same bytes in both formats.

## Tests

- `tests/unit/governance/test_requirement_specification.py`: builder from a confirmed-only revision
  and from an approved one, requirement-version matching after an edit, unconfirmed refusal; Word
  headings in order, document-control table, byte stability, control-character refusal; Markdown
  outline and escaping; no email in either rendering; transport headers and 403/404/409/422; the
  revision list's new fields.
- `tests/unit/test_error_handlers.py`: the two new rows. `tests/unit/test_openapi_snapshot.py`.
- Frontend: `RevisionPanel.test.tsx` (card absent, before approval, approved copy, busy, restricted,
  failure), `StatusStrip.test.tsx`, `client.test.ts`; `tests/review-flow.spec.ts` downloads Word and
  Markdown from History and finds the controls on Confirm.

## Acceptance Criteria

- [x] A confirmed analysis downloads as `.docx` and `.md` from Confirm and History.
- [x] An unconfirmed revision answers 409; an observer 403; `format=pdf` 422.
- [x] The approved revision's document contains the Epic → Features → Stories as FR-nn / FR-nn.m.
- [x] A confirmed but unapproved revision's document says functional requirements are not included.
- [x] Two renders of the same revision are byte-identical in both formats.
- [x] No email address appears in either file.
- [x] The neutral export, its schema and the knowledge handoff are unchanged.

## Validation Evidence

Recorded 2026-10-30 on `feat/business-requirements-document-export`:

- `pytest` — full suite passed, exit code 0 (2026-10-30, after the frontend and docs changes).
- `ruff check .` — All checks passed!
- `ruff format --check .` — 1351 files already formatted
- `mypy src tests` — Success: no issues found in 762 source files
- `lint-imports` — Contracts: 43 kept, 0 broken.
- Frontend: `npm run api:check`, `npm run lint`, `npm run typecheck` clean; `vitest run` — 68 files,
  598 tests passed; `npm run build` — built; `playwright test tests/review-flow.spec.ts --project=chromium`
  — 9 passed, including the extended journey that downloads Word and Markdown from History and finds
  the controls on Confirm. Checked by hand in the browser pane against the fake API: both downloads
  return 200 and the status strip reports the finished download.

## Deferred

- PDF output.
- Clarification questions asked by hand (`ClarificationQuestion`), which are not in the analysis
  snapshot; the recorded clarifications are.
- A glossary drawn from the domain's ubiquitous language rather than the document's own labels.
