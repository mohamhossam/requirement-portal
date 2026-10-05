# Enhancement — Three-repository platform split

> Status: **done 2026-10-05: Stages 0–5 delivered, and the acceptance criteria checked below
> with their evidence.** Outstanding is one owner setting, branch protection on `main` (see
> Deferred). Decisions: ADR-0098, ADR-0099, ADR-0100. This is feature and architecture work. It is outside the `CLAUDE.md`
> presentation-only redesign rule, so the hook, service and API changes below are in scope.

## Objective

Move the shared reference library, the architecture catalogue and the squad (organisation)
catalogue out of the requirements application. They become a separate service with its own
database and UI, `knowledge-portal`. Shared mechanisms go into `platform-kernel`, and this
repository, `requirement-portal`, keeps requirement work. The original `smb-ai-requirement-agent`
is not changed and keeps running in parallel.

## User Outcome

- A knowledge administrator opens `/knowledge/` and curates the library and catalogues in a
  portal designed for curation.
- Other users never see the portal. Their citations and impact evidence still open, read-only,
  inside requirement-portal.
- A BA or product owner works exactly as before. Mapping, reference grounding and source impact
  behave the same, except that a withdrawn publication is seen within one event poll.

## In Scope

### Stage 0 — Repositories and decisions
- Create three repositories, each a fresh start from `smb-ai-requirement-agent@d5cfb57`.
- Write ADR-0098 to ADR-0100.
- Add `UPSTREAM.md` and the AGENTS.md §2.1 sibling note.
- Give each repository its own `AGENTS.md`, `CLAUDE.md` and `ROADMAP.md`.
- Set up branch protection and Dependabot.
- Give CI and Docker read access to `platform-kernel`.

### Stage 1 — `platform-kernel` v1.0.0
- Bring in the kernel modules per ADR-0100, with their tests.
- Make `run_migrations(url, migrations_package)` take the migrations package as a parameter.
- Add the new `InternalHttpClient` and the service-token middleware.
- Set up import-linter, CI and tagged releases.

### Stage 2 — Reshape this repository
1. Pin the kernel and replace the local copies with `smb_kernel` imports. Split
   `domain/identity/entities.py`, so assignments stay here. Add an import-linter context contract
   with a baseline of today's knowledge coupling.
2. Untangle in-process, with one process and one database, preserving behaviour:
   - add `ReferenceKnowledgePort`;
   - move attachments to `requirement_attachment_ingestions`;
   - split `DocumentIngestionWorker`;
   - add the `knowledge_events` outbox and the local projections, replacing the `FOR SHARE`
     checks;
   - move MAPPING jobs out of `architecture_jobs`;
   - move the source-impact routes to `/requirements/{id}/source-impact…`, keeping aliases;
   - give knowledge and attachment blobs separate storage namespaces.
3. Seams: for every port in ADR-0099, add an HTTP adapter and a deterministic fake, plus the
   `/internal/*` endpoints this service provides.

### Stage 3 — `knowledge-portal`
- **Backend:** the library, catalogue and organisation code, with its own migrations, its public
  and `/internal/*` routes, and `knowledge_admin` on every public route.
- **Worker:** ingestion, catalogue jobs and the outbox.
- **Import:** a `knowledge-portal import --source-database-url … --verify` command.
- **UI:** a new design system with its own `DESIGN.md`, tokens and primitives, meeting WCAG 2.2
  AA. Each screen gets an impeccable critique before its pull request.

### Stage 4 — Cutover here
- Wire the HTTP adapters, with settings and contract tests.
- Remove the knowledge code and routes.
- Extend `deploy/` with the knowledge services, nginx routes and the Keycloak role and group.
- Frontend: attachments-only Documents, a portal link for admins, read-only viewers, redirects and
  fixed links.

### Stage 5 — Data and cleanup
- Seed the platform from a backup of the original database: restore, migrate, run the import with
  `--verify`, then drop the moved tables.
- Remove the import-linter baseline.
- Update the run and deployment docs.

**As delivered.**
- **No data moved, by decision.** The platform is still in development, so nothing is seeded from
  a backup ([#31](https://github.com/mohamhossam/requirement-portal/pull/31)). The path for an
  earlier system's data stays documented and tested: restore its backup, run `maintenance`, then
  `knowledge-import`, which copies and verifies every table (`docs/operations/deployment.md`,
  "Moving knowledge from an earlier system").
- **The moved tables are dropped by a guarded command**, `drop-knowledge-tables`
  ([#31](https://github.com/mohamhossam/requirement-portal/pull/31)). It drops all 18 or none, and
  only when that loses nothing. CI's deployment job drops them before the platform starts.
- **The import-linter baseline went earlier than planned**, with the knowledge code itself in
  Stage 4.2b ([#17](https://github.com/mohamhossam/requirement-portal/pull/17)). `.importlinter`
  has no `ignore_imports`.
- **The run and deployment docs** were updated in
  [#32](https://github.com/mohamhossam/requirement-portal/pull/32).
- **Closing checks** added here: requirement code names no knowledge table (an architecture
  test); a withdrawal reaches requirement work on the running platform; and the platform in a
  browser, with Playwright on the combined stack.

## Out of Scope
- Any change to `smb-ai-requirement-agent`.
- Knowledge Center sub-slices B–E. They come later, in knowledge-portal.
- Moving requirement attachments.
- A separate hostname.
- A shared UI package.
- Carrying git history.
- Automatic syncing of fixes from the original.

## Domain
- No business rule changes.
- `domain/identity/entities.py` splits: actor primitives move to the kernel; requirement
  assignments and access changes stay here.
- New projection records in this repository: reference publication state and active
  architecture release.

## Application Use Cases
- A new `ReferenceKnowledgePort` replaces the concrete `ReferenceKnowledge` dependency in
  `ReferenceGrounding` and `AnalysisCollaboration`.
- Attachment ingestion gets its own repository and worker.
- Currency checks (`require_current`, `stale_analysis`) read the local projection.
- MAPPING jobs become requirement jobs.

## Ports
- `ArchitectureKnowledgePort`: unchanged signature, with a new HTTP adapter.
- `ReferenceKnowledgePort`: new.
- `ReferenceSearchPort`: gains an HTTP adapter.
- A new port for consuming knowledge events.
- Provided to knowledge-portal: dependents, mapping statistics and actor directory endpoints.

## Adapters
- HTTP adapters built on the kernel's `InternalHttpClient`. They normalise or reject unusable
  responses at the boundary (AGENTS.md §4.3).
- A deterministic fake for every remote port, so memory mode runs offline (AGENTS.md §4.5).
- A PostgreSQL adapter for the projections and the attachment-ingestion table.

## API
- New `/internal/references/{document}/dependents`, `/internal/architecture-mapping/stats` and
  `/internal/actors`, requiring a service token.
- `/requirements/{id}/source-impact…`, with the old `/library/...` paths kept as aliases (AGENTS.md
  §16).
- After cutover, nginx forwards `/library/*` and `/architecture-knowledge/*` to `/knowledge-api/`.

## UI
- Requirements app:
  - Documents shows attachments only, plus an "Open knowledge portal" link for admins;
  - a portal link in the top bar for admins;
  - new read-only `ReferencePassagePage` and `ArchitectureEvidenceViewPage`;
  - redirects from `/documents/library*` and `/architecture-knowledge*`;
  - fixed hard-coded links in `QuestionCard`, `IntentProposalCard`, `AnalysisSources`,
    `ArchitectureImpactPanel` and `ArchitectureRemapBanner`.
- knowledge-portal: new screens in its own design system.

## Business Rules
- Historic, library and catalogue content stays reference knowledge, as before.
- Withdrawal is eventually consistent within one event poll (target ≤ 5 seconds), per ADR-0099.
- Only `knowledge_admin` enters knowledge-portal.

## Tests
- **Kernel:** unit tests and import-linter.
- **Here:**
  - the full gates after the kernel switch, which proves behaviour is unchanged;
  - rewritten cross-boundary tests: `test_reference_grounding`, `test_source_lineage`,
    `test_library_governance`, `test_architecture_p3`, `test_ingestion_completion`,
    `test_postgres_architecture`;
  - consumer contract tests for every adapter.
- **knowledge-portal:** unit and PostgreSQL tests, provider OpenAPI tests, and the import
  `--verify`.
- **End to end:** Playwright on the combined compose stack.

## Acceptance Criteria
- [x] `smb-ai-requirement-agent` has no commits from this work. Its `main` ends at `d5cfb57`
  (2026-10-01). The only later commits are the 14 Product Architecture Explorer commits on
  `smb-product-flow-architecture` (2026-10-03/04), which are separate work, not the split's.
- [x] `platform-kernel` v1.0.0 is tagged on green CI. The tag is `f0b30a6`; its CI run
  36992055593 and release run 36992330650 both succeeded. v1.0.1 and v1.0.2 were also released
  green.
- [x] This repository passes its full gates on the kernel, before any knowledge code is removed.
  **Locally, not in CI.** The gates passed on the kernel switch
  ([#2](https://github.com/mohamhossam/requirement-portal/pull/2): 1,923 tests and the kernel's 114),
  at the Stage 2 landing ([#13](https://github.com/mohamhossam/requirement-portal/pull/13): 1,997
  passed, 94.22% coverage) and before the removal
  ([#16](https://github.com/mohamhossam/requirement-portal/pull/16): 2,021 passed), as recorded in
  each pull request. CI could not run then: every run up to and including the removal
  ([#17](https://github.com/mohamhossam/requirement-portal/pull/17)) stopped at "Read access to
  platform-kernel", because the `KERNEL_READ_TOKEN` secret did not exist yet. The first green CI on
  `main` came after the removal (run 37133972998,
  [#27](https://github.com/mohamhossam/requirement-portal/pull/27)).
- [x] Attachments no longer use `library_documents`, and requirement transactions lock no
  knowledge rows. Attachments live in `requirement_attachment_ingestions` (migration
  `202610021000`). The only `FOR SHARE` reads the local projection `reference_publication_state`.
  `tests/architecture/test_knowledge_tables.py` now holds that no requirement code outside the
  guarded drop command names a knowledge table.
- [x] knowledge-portal runs alone offline and serves `/knowledge/` to `knowledge_admin` only. Its
  route-authentication architecture test requires the role on every public operation. The one
  exception is the explorer's read routes, which ADR-0101 Amendment 1 opened to anyone signed in.
  The offline fakes stand in for requirement work (`test_without_requirement_work_the_fakes_stand_in`).
- [x] Citations and impact evidence open read-only for non-admins. `test_knowledge_views.py` reads
  both as `fake-observer`, who holds no knowledge role. The platform's browser check opens a
  citation as that member, with no link into the portal.
- [x] A withdrawal in the portal marks dependent requirements stale within one poll. Citations are
  judged current against requirement work's copy, `reference_publication_state`, which follows
  the knowledge event feed (unit-tested in `test_reference_currency.py` and
  `test_reference_publication_state.py`). On the running platform, CI's deployment job
  (`tests/platform_withdrawal.py`) publishes and withdraws a library document and requires the
  copy to follow within 15 seconds. The rehearsal took 1.1 seconds.
- [x] `/knowledge-api/internal/*` is refused at the edge: **404, not 403** (amended 2026-10-05).
  The edge answers 404 for `/api/internal` and `/knowledge-api/internal`, so it doesn't reveal
  that the route exists. `test_platform_deployment.py`, the CI deployment job and
  `docs/operations/deployment.md` all hold to 404.
- [x] The import `--verify` matches row counts and blob checksums. `verify_knowledge` compares
  each table's row count and a checksum over its rows. The blob bytes and their sha256 are
  `knowledge_document_blobs` rows, so they are compared too. Covered by knowledge-portal's
  `test_knowledge_import.py` (`test_every_table_arrives_unchanged_and_verifies`,
  `test_verification_names_a_table_that_drifted`).

## Validation Evidence
- Stage 0: the repository was imported at `40c56d0` from `d5cfb57`.
- Stages 1–4: the pull requests named in the acceptance criteria above, and knowledge-portal
  v0.1.0.
- Stage 5 and the close-out (2026-10-05):
  - `pytest` with `TEST_DATABASE_URL` (local PostgreSQL 16 with pgvector) — PASS, 1690 passed;
  - `ruff check .` and `ruff format --check .` (1053 files) — PASS; `mypy src tests` — PASS, 511
    source files; `lint-imports` — PASS, 9 contracts kept;
  - frontend `eslint .`, `tsc -b` and `npm run build` — PASS;
  - `tests/platform_withdrawal.py` against both services run from source, requirement work on
    PostgreSQL — PASS, the copy followed the withdrawal in 1.1 seconds;
  - `npx playwright test -c playwright.platform.config.ts` behind a stand-in for the edge — PASS,
    3 tests. The compose stack itself runs in CI: this workspace's network refuses GitHub's
    image-blob storage, so it could not pull the knowledge images;
  - CI on the close-out pull request — recorded there.

## Deferred
- Retiring the original repository is a separate decision.
- Branch protection on `main` in each repository (Stage 0): an owner setting in GitHub, still
  listed as outstanding in knowledge-portal's roadmap.
