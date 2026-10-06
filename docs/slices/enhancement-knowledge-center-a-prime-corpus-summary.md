# Enhancement — Knowledge Center A′: the Requirement corpus summary (requirement-portal half)

> **Status:** delivered on `feat/knowledge-corpus-summary` (2026-10-06).
> **Parent:** the Knowledge Center re-plan, sub-slice A′
> ([enhancement-knowledge-center.md](enhancement-knowledge-center.md)). knowledge-portal
> shows the summary as the fourth numbered table on its front page, in its own slice.

## Objective

Knowledge admins work in knowledge-portal, but the Requirement corpus lives here (ADR-0099,
Amendment 1). A′ shows the corpus's health on knowledge-portal's front page. Requirement work
answers one read over its service-token internal API, as counts only, so no Requirement data
leaves this service.

## API

`GET /internal/knowledge/corpus/summary` (service token; added to
`contracts/requirement-internal.openapi.json`) answers `CorpusSummary`:

| Field | Meaning |
|---|---|
| `requirements` | Every Requirement, including those closed as duplicates |
| `duplicates` | Closed as duplicates; indexed with no passages, so never a candidate |
| `current` | Indexed at their latest change: `requirements − waiting − failed` |
| `waiting` | Changed and not yet indexed again |
| `failed` | Stopped retrying after three failed batches on the change still pending, until someone retries |
| `rebuild_required` | The embedding model changed and the new index must be built first. The counts are then 0 |
| `open_findings` | Findings still in force by age: `under_7_days`, `from_7_to_30_days`, `over_30_days` |
| `as_of` | When the summary was read |

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | **Counts only.** No ids, titles or owners. | Only counts are needed. Like the mapping stats, the summary needs no membership check. |
| 2 | **A finding is in force on the Knowledge step's own rule:** it is actionable (open or resolution pending), and both Requirements are still at the versions it judged. It is aged from the screen that raised it. | The front page then agrees with what owners see. A finding left behind by an edit does not count. |
| 3 | **The age buckets are under 7 days, 7–30 days and over 30 days.** | Agreed in session (2026-10-06). A finding should be decided within a week, and one over a month is overdue. |
| 4 | **A backlog reader** (`IndexBacklogReader`) is built from the index, the progress store and the identity, never the embedding provider. It pages through the pending sources and counts as failed those whose progress stopped on the same change. | The same rule decides retrying (`eligible`), and it works for both the legacy index and the generation index. `FAILED_AFTER = 3` now lives in the progress port, so the status, the claim and the summary share one number. Holding no provider keeps the internal routes outside the provider rate limit's reach (`tests/architecture/test_provider_rate_limit.py`). |

## Changes

- **Ports:**
  - `corpus_summary.CorpusCountsPort`;
  - `RequirementIndexProgressPort.failed(identity)`.
- **Adapters:**
  - `PostgresCorpusCounts`, two queries;
  - `RepositoryCorpusCounts`, for memory mode, which reads `InMemoryRequirementKnowledgeStore.raised_findings()`;
  - `failed()` on the memory and Postgres progress stores.
- **Application:**
  - `IndexBacklogReader.backlog()`;
  - `InternalReads.corpus_summary()`.
- **Interface:** the route, the contract and the contract test's path set.

## Tests

**Unit:** `tests/unit/test_corpus_summary.py`
- an empty portfolio reads as all zeros;
- new Requirements wait, then are current once indexed;
- findings move through the buckets at 0, 6, 7, 30 and 31 days;
- a decided finding leaves the count, and the duplicate is counted;
- a finding whose Requirement moved on is not counted;
- a source that stopped retrying is failed until it changes;
- the backlog counts every page (1,203 sources);
- a model change reports a rebuild;
- the route admits only the service token and answers counts without ids.

**PostgreSQL:** `tests/integration/test_corpus_summary_postgres.py`
- counts, a finding in force, and a failed progress row read against the real schema.

**Contract:** `test_requirement_internal_contract.py`, with the new path.

## Validation evidence

Recorded on 2026-10-06, locally, with PostgreSQL 16:

- `ruff format --check src tests` and `ruff check src tests`: clean.
- `mypy src tests`: clean.
- `lint-imports`: 9 contracts kept.
- Full `pytest` with `TEST_DATABASE_URL`: green.
