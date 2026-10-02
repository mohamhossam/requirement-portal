# Enhancement — Squad catalogue and building the architecture catalogue from documents

Scheduled 2026-09-29 by the product owner. This pulls Knowledge Center sub-slice F forward (ADR-0081)
and replaces Slice 14's per-release squads with an organisation catalogue (ADR-0080).
It is **feature work outside the UI redesign's presentation-only rule**: it adds API calls,
queries and mutations, as agreed with the user.

## Objective

Maintainers should be able to:

- **Curate who owns what** as a static squad catalogue: value streams with a lead and products,
  and squads with a scrum master and one resource per system.
- **Build the architecture catalogue** from Word, PDF and image documents, or from a catalogue
  file.
- **Publish a new version** after reviewing what it changes.

## User outcome

**Squad catalogue** (`/architecture-knowledge/squads`)
- A maintainer adds people (name, team, email) and value streams with a lead.
- Inside a value stream, the maintainer adds:
  - products, each linked to the architecture systems it is made of;
  - squads, each naming a scrum master and one resource from each system it works on.
- A system can appear in several squads.
- Readers view it, without email addresses.

**Architecture catalogue** (`/architecture-knowledge`)
- The page shows the version in use.
- A maintainer starts a new version and fills it in one of three ways:
  - adding documents, which the AI reads into cited suggestions to accept, edit or reject;
  - uploading an Excel (from the template), YAML or JSON catalogue, after seeing what it would
    change;
  - editing by hand.
- The maintainer then reviews the changes against the version in use, builds the evidence index,
  and publishes with a rationale.
- Any version can be downloaded in the three formats, or made active again.

**Mapping.** Mapped Features and Stories show each system's squads, value streams and products.

## In scope

- An organisation domain, repository, use case and `/organisation` API.
- Ownership removed from architecture releases, and mapping-time ownership lookup.
- A catalogue file codec (XLSX, YAML, JSON), a downloadable template, preview and apply import,
  export, and the release diff.
- Architecture uploads widened to PNG and JPEG.
- An `EXTRACTION` job, the extractor port, structured and fake adapters, a versioned prompt,
  candidate storage, decisions, and a `catalogue` LLM task.
- The redesigned architecture catalogue page and the new squad catalogue page. Both stay under
  Documents, reached by a shared catalogue sub-navigation, with no new top-level destination.

## Out of scope

- Second-person approval before publishing. The user chose self-review with a changes view.
- People on impacts. Impacts record squads, value streams and products only.
- Reading scanned PDF pages or Word-embedded diagrams with the vision model.
- Squad-aware review staleness. Ownership edits never make reviews stale, because impacts are
  snapshots.
- A data migration. Development databases are reset.

## Domain

- `domain/organisation/catalogue.py`: `Person`, `ValueStream`, `Product`, `Squad`,
  `SquadSystemResource`, and the `OrganisationCatalogue` aggregate. Its operations are
  `put_*`/`remove_*` with per-record revisions, and `ownership(system_id)`.
- `domain/architecture/knowledge.py`: ownership is removed.
- `domain/architecture/entities.py`: `SystemReference.squads`, `value_streams` and `products`
  are tuples of `OrganisationReference`.
- `domain/architecture/diff.py`: `diff_releases`.
- `domain/architecture/candidates.py`: `CandidateContent`, `CatalogueCandidate` (with `decide`),
  and `classify`, `apply_candidate` and `find_system`.

## Application

- `ManageOrganisationCatalogue`: every write needs the maintainer role; readers get
  `view`/`ownership` without emails.
- `ManageArchitectureKnowledge`: `preview_file_import`, `apply_file_import`, `export_file`,
  `file_template` and `changes`.
- `ProposeCatalogueChanges` and `DecideCatalogueCandidate`.
- `ArchitectureJobs.start_extraction`.
- `ResolveArchitectureKnowledge` adds organisation ownership, including on the legacy seed path.

## Ports

- `OrganisationRepositoryPort`
- `CatalogueFilePort`
- `CatalogueCandidateRepositoryPort`
- `CatalogueExtractorPort`
- `ArchitectureYamlPort` is removed.

## Adapters

- Postgres and in-memory organisation and candidate repositories. The migrations are
  `202609290900_organisation_catalogue.sql` and `202609291000_catalogue_candidates.sql`.
- `infrastructure/architecture/catalogue_files.py`
- `infrastructure/llm/catalogue_extraction.py` and `prompts/catalogue_extraction_prompt.py`
- `LocatedDocumentExtractor` skips images.

## API

**`/organisation`**
- `GET` returns the whole catalogue; `GET /audit`; `GET /systems/{id}/ownership`.
- `POST`/`PUT` for `/people`, `/value-streams`, `/products` and `/squads`, and `DELETE` for
  value streams, products and squads.
- Updates carry `expected_revision`.

**`/architecture-knowledge`**
- `GET /catalogue-template.xlsx`
- `GET /releases/{id}/catalogue-file?format=`, `POST /releases/{id}/catalogue-file/preview`,
  `POST /releases/{id}/catalogue-file`
- `GET /releases/{id}/changes`
- `POST /releases/{id}/documents/{version_id}/extractions` (rate-limited, 202)
- `GET /releases/{id}/suggestions`, `POST /releases/{id}/suggestions/{id}/decision`,
  `POST /releases/{id}/suggestions/acceptance`
- `GET`/`POST /releases/{id}/yaml` are removed.

**New errors**
| Error | Status |
|---|---|
| `organisation_not_found` | 404 |
| `organisation_conflict` | 409 |
| `invalid_organisation` | 422 |
| `catalogue_suggestion_not_found` | 404 |
| `catalogue_suggestion_conflict` | 409 |
| `catalogue_suggestion_dependency` | 409 |
| `catalogue_extraction` | 502 |
| `catalogue_extraction_unusable` | 502 |
| `catalogue_extraction_uncited` | 502 |
| `catalogue_extraction_unsupported` | 422 |

## UI

**`features/catalogue`**
- `ArchitectureCataloguePage` and `CatalogueNav`.
- `DraftJourney`: a four-step stepper (add content, review changes, build, publish), where every
  step stays reachable.
- `DocumentSources`: button plus drop zone, with extraction starting automatically after upload.
- `SuggestionList` and `SuggestionEditor`: evidence is shown before the decision.
- `CatalogueFileImport`: template download and preview.
- `SystemsEditor`, `DiffList`, `JobStatus` and `ReleaseHistory`.

**`features/organisation`**
- `SquadCataloguePage`: value stream cards with products and squad tables, a people tab, and
  editors.

**Other changes**
- `ArchitectureImpactPanel` shows squads, value stream and products.
- The evidence page uses the shared primitives.
- The old `ArchitectureKnowledgePage` and its stylesheet are removed.

**Accessibility**
- Drag-and-drop always has a button alternative.
- Stepper buttons carry explicit accessible names and `aria-current="step"`.
- Every enum goes through a label map.
- Job progress uses `role="status"`.
- There is no horizontal scroll at 390px.

## Business rules

- Ownership comes only from the curated organisation catalogue. AI never writes to it.
- AI suggestions never change a draft on their own. Only a maintainer's accept applies one, under
  the draft's revision.
- A capability, constraint or dependency needs its system in the draft first.
- Products and squads can only add systems in the active release. Links that lapse later are
  flagged, never enforced.
- A file import replaces the draft's systems and dependencies only after a preview; documents are
  kept.
- Images need a vision-capable profile, otherwise extraction is refused with a clear error.

## Tests

- **Backend**
  - `tests/unit/test_organisation_catalogue.py`: domain invariants, revisions, maintainer and
    reader access, email redaction, mapping with two squads, API round trip.
  - `tests/unit/test_catalogue_files.py`: round trip in all three formats, Excel lists and blank
    rows, sheet and row errors, template, diff, endpoints.
  - `tests/unit/test_catalogue_suggestions.py`: classify and apply, adapter citation checks and
    image readings, API from extraction to accepted draft, images.
  - Integration tests (`TEST_DATABASE_URL`): `test_postgres_organisation.py` and
    `test_postgres_catalogue_candidates.py`.
  - Updates to the error-status, rate-limit, jobs, backlog export and architecture knowledge
    tests.
- **Frontend**
  - `ArchitectureCataloguePage.test.tsx`: 9 tests.
  - `SquadCataloguePage.test.tsx`: 6 tests.
  - `ArchitectureImpactPanel.test.tsx`: updated.

## Follow-up fix: reading with small local models (2026-09-29)

With `KNOWLEDGE_PROVIDER=local` and the default 8,192-token window, reading a Word document failed
("the AI model's answer could not be used"). Asking again then left it "Waiting to start".

**Causes.**
- The first version sent 24,000-character batches, which the local client refuses as over budget.
- Asking again re-queued the job without resetting its attempts, so it could never be claimed.

**Fix.**
- **Reading fits the model.** The adapter reads within the configured input budget and cuts long
  passages into located parts. One unreadable part is a warning, not a failure.
- **Paraphrased quotes.** A paraphrased quote is backed by the matching sentence from the document.
- **Stale work stops.** Reading stops between calls once the document leaves the draft.
- **Jobs restart cleanly.**
  - Re-queued jobs start with fresh attempts.
  - Retry runs straight away when jobs run inside the request.
  - A new `GET /releases/{id}/extractions` gives each document's reading status. The page shows it
    after a reload and explains a wait.
- **Evidence.** `tests/unit/test_catalogue_reading.py` includes a reproduction through the real
  local client with the default window.

## Follow-up: configurable models and journey P1 (2026-09-30)

A review of the architecture journey found three P1 problems and the user chose to stop the
local-only model rule (ADR-0082).

- **Configurable models.** Architecture embeddings and mapping reasoning follow `LLM_PROVIDER` or
  the model profiles, like every other AI task. The `KNOWLEDGE_*` model settings and the tokenizer
  mount are gone; `KNOWLEDGE_EVALUATION_APPROVED` still gates production.
- **Named systems are always found.** A system named in the text is backed by its own record even
  when document passages outrank it in search.
- **Word sections.** Passages are packed under their headings (up to about 400 tokens), prefixed
  with the heading path; a table row is one chunk; system records list their dependencies.
- **Build of record.** `GET /releases/{id}/build` shows the latest build after a reload. Opening
  the build step on a stale index starts a build; "Build and publish" publishes once it succeeds,
  and the confirmation names the changes.
- **Upgrade.** Migration `202609301000` drops 1,024-dimension indexes; build and publish once.

**Evidence.** `tests/unit/test_architecture_p1.py`, the Postgres `system_chunk` check in
`tests/integration/test_postgres_architecture.py`, and three new page tests in
`ArchitectureCataloguePage.test.tsx`.
Gates on 2026-09-30: ruff, format, mypy and lint-imports pass; `pytest --cov` with
`TEST_DATABASE_URL` passes at 93.07% coverage; Vitest under Node 24 passes 546 tests at
80.53 / 73.72 / 71.35 / 83.59; `npm run build` and `npm run api:check` pass. The unused
`tokenizers` dependency stays until the lockfile is regenerated with the CI `uv` version.

## Follow-up: journey P2 (2026-10-01)

ADR-0083.

- **Browse the catalogue.** Knowledge readers now see the systems in use, read-only: what each
  does, constraints, "Depends on" and "Used by", and owning squads, value streams and products.
  Maintainers open the same view next to the version in use.
- **Shared sample requirements.** Maintainers keep one list, of up to 20 items, on the server.
  `GET` and `PUT /architecture-knowledge/sample-requirements` replace it under a revision check.
- **Compare before publishing.** Once the index is built, the build step maps each sample with the
  version in use and with this version, one request per sample, and labels each row. One ad hoc
  requirement can be compared too, and a run can be stopped.
  `POST /releases/{id}/compare-impact` serves one requirement.
- **Faster rebuilds.** An embedding cache per model and passage text means a rebuild embeds only
  what changed. The cache is not pruned yet (ADR-0083).

**Evidence.**
- `tests/unit/test_architecture_p2.py`.
- The Postgres sample-list and cache checks in `tests/integration/test_postgres_architecture.py`.
- Five new page tests in `ArchitectureCataloguePage.test.tsx`.
- Gates on 2026-10-01:
  - ruff, format, mypy and lint-imports pass.
  - `pytest --cov` with `TEST_DATABASE_URL`: 93.11% coverage.
  - Vitest under Node 24: 554 tests, 80.85 / 74.05 / 72.06 / 83.89.
  - Build and `api:check` pass.
- In Chromium with the fake provider:
  - A reader browses the systems and opens one.
  - A maintainer compares two saved samples: one "Changed + Order Hub", one "Same systems".
  - No horizontal overflow at 1,440 or 390 px.

## Follow-up: journey P3 (2026-10-02)

ADR-0084.

- **Named versions.** Starting a version asks for a name. Only one version can be in progress; a
  second start gets 409, naming the draft and who started it.
- **Rename and discard.** Drafts can be renamed and discarded. Discarding deletes the draft's
  index and suggestions.
- **Dependency diagram.** Each system in the browser shows its neighbours as a small diagram,
  with the text lists kept.
- **What publishing affects.** The publish confirmation gives how many requirements, features
  and stories are mapped, and that remapping resets approvals. The in-use card shows how many
  requirements still use an older version.
- **Team-owned remap.** A breakdown mapped with an older version shows a banner that remaps after
  confirmation. There is no bulk remap.
- **Suggestions.** They group by kind or system, a group can be rejected together, and
  "Show in document" opens the cited passage with its neighbours and the quote marked.
- **Images.** Upload wording says images feed suggestions only.

**Evidence.**
- `tests/unit/test_architecture_p3.py`.
- The Postgres discard and count checks in `tests/integration/test_postgres_architecture.py`.
- Six new page tests in `ArchitectureCataloguePage.test.tsx` and three in
  `ArchitectureRemapBanner.test.tsx`.
- Gates on 2026-10-02:
  - ruff, format, mypy and lint-imports pass.
  - `pytest --cov` with `TEST_DATABASE_URL`: 93.19% coverage.
  - Vitest under Node 24: 568 tests, 81.16 / 74.12 / 72.55 / 84.14.
  - Build and `api:check` pass.
- In Chromium with the fake provider:
  - A version is named in the dialog.
  - Suggestions group by system, and one group is rejected together.
  - A cited passage opens with the quote marked.
  - The dependency diagram draws B2B BFF's neighbours.
  - The publish dialog states the effect on existing mappings.
  - No horizontal overflow at 1,440 or 390 px.
  - The remap banner is covered by component tests only, because a mapped requirement needs the
    full breakdown workflow.

## Follow-up: similar names and inferred dependencies (2026-09-30)

ADR-0085.

- **Similar names.** A name the catalogue does not know is checked against a shortlist of similar
  systems, and the catalogue model says which, if any, it is. The suggestion shows "May already
  exist" with each option's reason.
  - "Add to BCRM" makes the written name an alias.
  - "Use BCRM" re-points a dependency.
  - "Keep as a new system" accepts it as written.
  - Nothing links without the maintainer.
- **Word-level lookup.** `find_system` falls back to words alone when exactly one system fits. A
  dependency on `dynamics-crm` therefore resolves once "Dynamics CRM" is an alias of `bcrm`.
- **Inferred dependencies.** Extraction prompt `catalogue-extraction-v2` may propose a dependency
  the cited passages imply, with one sentence of reasoning. It shows as "Inferred" with that
  reasoning above the quote.
- **Accept all.** It skips inferred suggestions and open possible matches, and says how many were
  left.
- **Error code.** `catalogue_matching` (502) is mapped, though a matching failure only adds a
  warning to the run.

**Evidence.**
- `tests/unit/test_catalogue_matching.py`.
- Two new page tests in `ArchitectureCataloguePage.test.tsx`.
- Gates on 2026-09-30:
  - ruff, format, mypy and lint-imports pass.
  - Backend suite: 1,769 passed and 65 skipped. One unrelated attachment test failed under full
    load and passed when re-run alone.
  - Vitest: 581 tests pass. Lint, typecheck, build and `api:check` pass.
- Impeccable critique (23/40, three P1 issues), fixed before the PR:
  - A possible match no longer hides "Needs its system first".
  - "Keep as a new system" now sits with the match options, and the existing system shows its other
    names and capabilities.
  - Button accessible names begin with their visible text (WCAG 2.5.3).
  - "Inferred" has its own glyph, and its reasoning follows the quote.
  - The list says how many suggestions need a one-by-one decision.
- In Chromium with the fake provider, a document read "System: Dynamics CRM", "System: Order Hub",
  "Order Hub depends on Dynamics CRM for quotes" and "Order Hub sends invoices to BCRM":
  - "Dynamics CRM" showed "May already exist: BCRM".
  - "Add to BCRM" made it an alias of `bcrm`.
  - The dependency then read "Order Hub → BCRM", and "Accept all 2 waiting" saved `order-hub → bcrm`.
  - The inferred "Sends invoices" dependency stayed waiting, with its reasoning shown.
  - No horizontal overflow at 390 px, and the match buttons are 32 px tall.

## Follow-up: spreadsheets as source documents (2026-09-30)

ADR-0086.

- **Accepted files.** "From documents" takes Excel (.xlsx), CSV and TSV alongside Word, PDF, plain
  text and images. The row icon shows which sources are spreadsheets.
- **Rows are passages.** A workbook is read as `sheet N, row R` under each visible sheet's name,
  and a CSV or TSV as `row R`. Hidden sheets are left out. The index packs rows of one sheet into
  `sheet N, rows R–S` chunks.
- **Citations.** A suggestion quotes cell values from its row. "View passage" shows the row with
  two rows either side.

**Evidence.**
- `tests/unit/test_architecture_p1.py`: workbook and delimited passages, and index chunks.
- `tests/unit/test_architecture_p3.py`: upload through the API, the extension check, and a row
  passage with its neighbours.
- One new page test in `ArchitectureCataloguePage.test.tsx`: a `.csv` that the browser types as
  `application/vnd.ms-excel` is sent as `text/csv`.

## Validation evidence (2026-09-29)

**Backend**
- `uv run ruff check src tests`: passed.
- `uv run ruff format --check src tests`: passed.
- `uv run mypy src tests`: passed.
- `uv run lint-imports`: 7 contracts kept, none broken.
- `uv run pytest --cov` with `TEST_DATABASE_URL` (PostgreSQL 16 with pgvector), as CI runs it:
  1,779 passed. Coverage is 93.02%, up from the 92.44% recorded on 2026-09-25, and the floor in
  `pyproject.toml` is raised from 92 to 92.5.

**Frontend**
- `npm run lint`, `npm run typecheck`, `npm run api:check` and `npm run build`: passed.
- `npx vitest run --coverage` under Node 24 (the CI version): 540 passed. Coverage is 80.56%
  statements, 73.7% branches, 71.24% functions and 83.56% lines, up from 76.25%, 70.15%, 65.8%
  and 80.22%. The floors in `vitest.config.ts` are raised to 80 / 73 / 70 / 83.
- Under the local Node 22, `client.test.ts › downloads an authenticated export` fails the same way
  on `main`. It passes under Node 24.

**In the browser**
- Environment: the fake providers with Playwright and Chromium.
- Journey: seed people, a value stream, a product and a squad; start a version; upload a text
  design; accept all suggestions; review changes; build; publish.
- Screenshots at 1440px and 390px show no horizontal overflow.
