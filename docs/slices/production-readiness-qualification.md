# Production readiness — release qualification

## Current delivery status — verified 2026-09-25

The qualification tools are in `main`, through
[PR #39](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/39). It rebuilt the
original [PR #15](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/15) commit
`480a31e` on current `main` (see "Rebased onto `main`" below); #15 was then closed. PR #39's
final hosted run passed every job, including the new `recovery` job on the pinned PostgreSQL 17
image. See the delivery ledger in `ROADMAP.md`.

This closes hosted validation of the tools, not production qualification. The
target-environment, representative-corpus and human-evaluation gates below remain open.

## Objective

Close the outstanding validation work with reproducible evidence. This follows the implemented
production-readiness remediation and document-knowledge enhancement; it introduces no new feature
slice. **Release qualification remains open until the environment-specific gates below pass.**

## User Outcome

Maintainers can repeat a nonempty database recovery check in CI and measure HTTP search under
concurrency, with actual failures and limitations recorded instead of inferred readiness.

## In Scope

- Revalidate backend, frontend, real PostgreSQL/pgvector and browser journeys.
- Add a synthetic nonempty backup/restore rehearsal to hosted CI, on the pinned PostgreSQL 17 image.
- Supply a bounded HTTP search measurement command and record the local result.
- ~~Fix a browser-test race discovered by the full verification run.~~ Superseded: the same
  reviewer-journey race was fixed on `main` in `c295734` (a retried `openTriage`).

## Out of Scope

External publication and deployment are not performed by these qualification tools. No release
requirement is dropped: target-environment access and human evaluation remain prerequisites.

## Domain

No changes. Preserve source eligibility, owner access, immutable approval/history and source lineage.

## Application Use Cases

No changes. The recovery fixture exercises the existing upload, extraction review, approval,
indexing, analysis, owner decision, dependency inspection and original-download use cases.

## Ports

No new ports or contracts.

## Adapters

No production adapter changes. Recovery uses the existing composition root and PostgreSQL adapters
with explicit fake generation and test-only scanner substitution, as in the existing browser fixture.
The CLI requires a `codex_qualification_test_*` database and refuses to seed any nonempty database.

## API

No contract changes. The load command calls `/health`, `/ready` and the read-only
`POST /knowledge/search`. It exports counts, response failures and latency, never tokens,
source bodies or query text. A supplied bearer token requires HTTPS outside loopback.

## UI

No product UI changes or omissions. The collaboration browser test now waits until the reviewer
workspace is visible before opening its question; identity reconciliation deliberately remounts
the old workspace. Assertions about reviewer permissions and saved drafts remain intact.

## Business Rules

Synthetic data and fake providers cannot qualify actual model quality, OCR, malware protection,
customer-corpus representativeness or deployment capacity. Successful-response latency is reported
separately from failures. The measurement report always leaves capacity approval false.

## Tests

- Database-name safety guards and rejection of verifying a restore against its original database.
- All-table counts/digests before any restored application startup; original SHA-256 and owner-only
  download, exclusion-safe search, exact publication/history and source dependency readback.
- Migration re-entry and two nonempty projection rebuilds, with authoritative history unchanged.
- Load percentile/error accounting, complete outages, empty measurements and credential transport.
- Existing full unit/integration/browser suites and repeated desktop/mobile identity-switch case.

## Acceptance Criteria

- [x] Nonempty local PostgreSQL backup/restore evidence, including private source content and history.
- [x] Executable search concurrency measurements with explicit error and qualification limits.
- [x] Hosted quality, browser and recovery jobs passed: first for PR #15 (`480a31e`, PostgreSQL
  16/17), then for the rebased PR #39 (PostgreSQL 17, the version every environment runs).
- [ ] Target-environment maintenance, restore/recovery and operational release checks completed.
- [ ] Representative retrieval/grounding and one-million-chunk performance evidence completed.

## Validation Evidence

Baseline `9fa926f209d691cb55f2386b733f44596530d973` has successful hosted
[CI run 35804166832](https://github.com/mohamhossam/smb-ai-requirement-agent/actions/runs/35804166832).
This baseline result does not certify the new qualification changes.

Local Windows 11, Python 3.14.5, Node 24.20.0 and Docker PostgreSQL 17/pgvector, 2026-09-23:

```text
TEST_DATABASE_URL=<new dedicated loopback test database> .venv/Scripts/python.exe -m pytest -o faulthandler_timeout=120
1398 passed, 1 warning in 134.82s (before adding the qualification tests)

npm --prefix frontend run api:check
PASS — OpenAPI TypeScript contract matches
npm --prefix frontend run lint
PASS
npm --prefix frontend run typecheck
PASS
npm --prefix frontend test
41 files; 277 tests passed
npm --prefix frontend run build
2004 modules transformed; build completed

python -m tests.release_recovery seed --database-url <new test source> --manifest <manifest.json>
status: seeded; tables: 53
pg_dump -Fc; pg_restore --exit-on-error --no-owner into a different new test database
backup: 0.237s; restore: 0.383s (tiny synthetic fixture; not a production RTO)
python -m tests.release_recovery verify --database-url <restored test database> --manifest <manifest.json>
status: passed; tables_verified: 53; rows_verified: 95; requirements_rebuilt_twice: 1
Original checksum, publication/history digests, access/exclusion guards and source dependency/search passed.

python -m tests.release_load --base-url http://127.0.0.1:5395 --queries <synthetic queries.json> --users 25 --requests 100 --output <result.json>
100 successful requests; 0 errors; 0 empty results; 25 concurrent clients
p50: 222.95ms; p95: 403.12ms; max: 419.67ms; 37.44 requests/second
One published chunk, two synthetic query texts, fake embedding, local HTTP; capacity_qualified: false.
```

Initial `localhost` database connections stalled before reaching PostgreSQL. Only those test
processes were stopped; explicit `127.0.0.1` and a connection timeout resolved the problem.
The initial frontend run accidentally used bundled Node 22 and failed the MSW Blob download test;
the CI-aligned Node 24 rerun passed all tests. An initial recovery manifest was captured before
readback refreshed actor profiles; the fixture now captures its final manifest after readback.
The corrected rehearsal used new databases and matched every table without exceptions.

The full local browser run reported `80 passed, 1 failed, 5 skipped (10.2m)`. The failure inspected
the old actor's open question during identity reconciliation, then waited on the remounted closed
question. The five skips are duplicate viewport suites whose desktop cases already cover eleven
widths. The test now waits for the new visible actor/permissions. Its initial new text locator matched
both the actor heading and select option; the corrected locator targets the displayed actor heading.
Final repeated-case and hosted results are recorded below when complete.

### Final local verification

```text
TEST_DATABASE_URL=<dedicated PostgreSQL/pgvector test database> .venv/Scripts/python.exe -m pytest
1408 passed, 1 warning in 134.34s (0:02:14)
.venv/Scripts/python.exe -m ruff check .
All checks passed!
.venv/Scripts/python.exe -m ruff format --check .
864 files already formatted
.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 421 source files
.venv/Scripts/lint-imports.exe
Analyzed 359 files, 2612 dependencies. Contracts: 6 kept, 0 broken.

npm --prefix frontend run test:smoke -- review-flow.spec.ts --grep "owner assigns a reviewer" --repeat-each 3
6 passed (49.8s), desktop and responsive
npm --prefix frontend run lint
exit 0
npm --prefix frontend run typecheck
exit 0

python -m tests.release_recovery verify --database-url <third fresh restore> --manifest <manifest.json>
status: passed; tables_verified: 53; rows_verified: 95; requirements_rebuilt_twice: 1
authoritative_history_unchanged_after_maintenance: true
```

The complete browser suite and the PostgreSQL restore job run in hosted CI for this change.
Use that final revision's checks, rather than the earlier baseline's result, before merging.

## Deferred / Open

No target staging/deployment environment or actual human-labelled dataset has been supplied.
The parent release gates remain: 200 human-labelled queries including 50 cross-language cases;
actual-model/context comparison and semantic support/conflict review; one million chunks with
25 users, database p95 <1s and end-to-end p95 <3s with separate embedding timing and ingestion
fairness; quotas/metrics/alerts; actual scanner/OCR/Office bundle checks; deployment-specific
nonempty legacy migration, backup restore and outage/crash recovery. A synthetic restored current
schema does not certify upgrade of a production legacy database. See the operating runbook.

## Rebased onto `main` — 2026-09-25 (supersedes PR #15)

PR #15 (`480a31e`) predated three rounds of remediation and no longer applied. It was cherry-picked
onto `main` with these changes:

- **Imports.** `build_projection_rebuild` now comes from `interfaces/api/composition/operations.py`,
  and `LLMProvider`/`PersistenceProvider` from `infrastructure/config/options.py`.
- **CI job, to satisfy the guards `main` added since:**
  - one job on the pinned `pgvector/pgvector:pg17@sha256:…` image, not a `pg16`/`pg17` matrix
    of unpinned tags. `test_image_pins.py` requires digest pins and one PostgreSQL image
    everywhere, and production runs 17, so a 16 rehearsal would qualify a version nobody deploys;
  - Actions pinned by commit SHA (`test_action_pins.py`);
  - the locked install `uv sync --locked`, not `pip install -e`.
- **Browser test.** The `review-flow.spec.ts` wait was dropped; `main` already fixes that race.

Local evidence (pgvector PostgreSQL 17 test container; seed, `pg_dump -Fc`, `pg_restore` into a new
database, verify):

```text
python -m tests.release_recovery seed ...     -> {"status": "seeded", "tables": 59}
python -m tests.release_recovery verify ...   -> status: passed; tables_verified: 59;
  rows_verified: 98; requirements_rebuilt_twice: 1; original_checksum_verified: true;
  publication_and_history_digests_verified: true;
  private_original_and_excluded_passage_guards_verified: true;
  source_dependency_and_search_reads_verified: true;
  authoritative_history_unchanged_after_maintenance: true
pytest tests/unit/test_release_load.py tests/unit/test_release_recovery.py -> 10 passed
ruff, ruff format, mypy (the four files) -> clean
```

