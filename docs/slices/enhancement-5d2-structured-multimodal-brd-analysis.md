# Enhancement 5D.2 — Structured Multimodal BRD Analysis

> Status: **complete locally; CI pending push**.

## Objective

Analyze large DOCX and XLSX business requirements as structured, source-cited evidence without
exceeding the configured model context or silently discarding tables and meaningful images.

## Roadmap Scope Check

| Roadmap field | Delivery |
|---|---|
| Domain | Immutable evidence blocks/assets, extraction warnings/readiness, exact analysis references, hidden-sheet selection, and stage provenance. |
| Application | Evidence assembly, bounded packet planning, focused analysis, citation validation, cached hierarchical consolidation, failure atomicity, and durable progress. |
| Ports | Structured document extraction, focused multimodal analyzer, fragment cache, and progress ports. |
| Adapters | Safe DOCX/XLSX extraction, raster normalization, fake/OpenAI/local packet analysis, memory cache, PostgreSQL cache/progress migration. |
| API | XLSX uploads, readiness/summary/warnings/blocks, authenticated thumbnails, hidden-sheet selection, citations, stage provenance, and progress. |
| UI | Structured preview, warnings, images, sheet opt-in, provider disclosure, live progress, and citation navigation. |
| Tests | Synthetic structure/security fixtures, budgets/cache/citations, provider payloads, persistence/API/UI/OpenAPI/browser coverage and all gates. |

Nothing in the Enhancement 5D.2 roadmap entry is dropped.

## Behavior

- DOCX source order, heading paths, numbered/list content, table row context, and meaningful body
  images become immutable evidence blocks. Generated contents, unsafe package paths, macros,
  active content, external relationships, malformed packages, and excessive expansion are
  rejected or explicitly warned about at extraction boundaries.
- XLSX retains visible worksheet coordinates, formulas and cached values without executing them,
  identifies charts/images/external links, reports hidden sheets, and includes hidden evidence
  only after an explicit user choice.
- The application reserves prompt/schema/output capacity before packing evidence. Oversized text
  blocks are split without changing their stable source citation; images per packet are bounded.
- Every generated fact, rule, constraint, uncertainty, dependency, or proposal must cite a known
  block inside its packet. Blank, unknown, mixed, duplicate, missing, and stale references fail
  generation before persistence.
- Successful first-stage fragments and consolidation fragments are cached using source checksum,
  packet fingerprint, model, prompt, and extraction version. Consolidation is itself bounded and
  model-assisted so statements from separate sections can be compared. Cache hits rebind block
  citations to the current immutable document/version identity before validation, allowing safe
  checksum reuse across separately uploaded copies.
- Analysis remains one manually reviewed candidate for one Requirement. Packet failure preserves
  prior analysis, human answers, and question history.
- Local schema-valid responses with unusable citations receive the single strict focused recovery
  defined by ADR-0032; the recovery never rewrites or silently drops generated content.

## Sample Acceptance

The confidential sample was inspected locally but is not committed. Its structure is accepted
without the old single-prompt context failure, including duplicate source BUC labels and image
evidence. A workbook visible only inside a screenshot is not fetched; visual analysis may report
the missing reference and the user must upload the workbook separately. Conflicts and placeholders
remain cited ambiguities/questions rather than invented rules.

## Validation Evidence

- `$env:TEST_DATABASE_URL='postgresql://smb:smb_dev@127.0.0.1:5432/smb_requirements'; .venv\\Scripts\\python.exe -m pytest` — PASS; 634 tests, including PostgreSQL integration coverage, the API lifecycle regression, and user-priority queue dispatch (one upstream Starlette deprecation warning).
- `.venv\\Scripts\\python.exe -m ruff check .` — PASS; all checks passed.
- `.venv\\Scripts\\python.exe -m ruff format --check .` — PASS; 373 files already formatted.
- `.venv\\Scripts\\python.exe -m mypy src tests` — PASS; no issues in 302 source files.
- `.venv\\Scripts\\lint-imports.exe` — PASS; 2 architecture contracts kept, 0 broken.
- `npm.cmd test -- --run` — PASS; 23 files and 114 tests.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run build` — PASS; production build generated (Vite emitted its advisory for the 531.07 kB main chunk).
- `npm.cmd run api:check` — PASS; committed OpenAPI TypeScript types match regeneration.
- `$env:SMOKE_API_PORT='8016'; $env:SMOKE_UI_PORT='4189'; npm.cmd run test:smoke` — PASS; 14 Playwright journeys across desktop and responsive Chromium.
- Direct port-8000 startup probe — PASS; FastAPI completed its lifespan and `GET /health` returned HTTP 200 within the 30-second launcher window after startup reconciliation was grouped into one transaction.
- Local extraction of the supplied sample — PASS; 164 ordered blocks (19 headings, 13 paragraphs, 13 list items, 114 table rows, and 5 image occurrences), duplicate BUC9 headings preserved, and 12 bounded analysis packets plus one consolidation stage with the deterministic fake provider. The confidential file and temporary render artifacts were not committed.
- CI — pending push; local success is not CI authority.

## Architecture Impact

ADR-0029 records structured immutable evidence and hierarchical analysis. Dependency direction
remains Interfaces/Infrastructure → Application → Domain, and concrete providers remain selected
only in the composition root.

## Deferred / Open

- PDF and TXT retain their compatible plain-text path; structured PDF layout extraction is not in
  this enhancement.
- OCR for text inside screenshots depends on the configured vision-capable analyzer; no separate
  OCR engine or automatic external-file retrieval is introduced.
- CI remains pending until the branch is pushed.
