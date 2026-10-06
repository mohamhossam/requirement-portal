# Enhancement — Knowledge Center B2: the corpus browser, portfolio findings and nudges (requirement-portal half)

> **Status:** delivered on `feat/knowledge-corpus-browser` (2026-10-06).
> **Parent:** the Knowledge Center re-plan, sub-slice B2
> ([enhancement-knowledge-center.md](enhancement-knowledge-center.md)). knowledge-portal shows
> the two tables and the nudge action under its fourth table, Requirement knowledge, in its own
> slice.

## Objective

A′ counts the Requirement corpus on knowledge-portal's front page. B2 lets a knowledge admin see
*which* Requirements and findings those counts are, and ask the owners of a finding that has
stood too long to decide it. The rules and the data stay here (ADR-0099 Amendment 1);
knowledge-portal reads them over three service-token routes and keeps nothing.

## API

All three are added to `contracts/requirement-internal.openapi.json` and need the service token.

**`GET /internal/knowledge/corpus`** answers a `CorpusPage` (`items`, `next_offset`), ordered by
title, then id.

| Query | Meaning |
|---|---|
| `index_state` | `current`, `waiting`, `failed` or `rebuild_required` |
| `owner_id` | The owner's actor id |
| `q` | Matched against titles, ignoring case; wildcards are literal |
| `open_findings_only` | Only Requirements named by a finding in force |
| `not_screened_for_days` | Never screened, or last screened before this many days ago |
| `offset`, `limit` | `limit` is 1–100, 50 by default |

Each `CorpusRow` carries `requirement_id`, `title`, `duplicate`, `owner` (`{id, display_name}` or
null), `index_state`, `last_screened_at` and `open_findings`.

**`GET /internal/knowledge/findings`** answers a `FindingsPage` of findings in force, the
longest-standing first, filtered by `kind`, `age` (`under_7_days`, `from_7_to_30_days`,
`over_30_days`) and `owner_id` (either Requirement's). Each `FindingRow` carries `finding_id`,
`kind`, `rationale`, `raised_at`, `age`, `subject` and `related` (each `{requirement_id, title,
owner}`), `last_nudge` (`{at, by}` or null) and `next_nudge_at` (null when it may be nudged now).

**`POST /internal/knowledge/findings/{finding_id}/nudge`** takes `{actor_id, actor_name}`, the
knowledge admin who asks, and answers a `NudgeResult` (`finding_id`, `nudged_at`, `recipients` by
display name, `next_nudge_at`). It answers 404 for an unknown finding, and 409 with the reason
for a finding no longer in force, one nudged in the last 7 days, or one whose Requirements have
no owner.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | **Identity and state, plus the judge's rationale.** Never a description, passage, evidence excerpt or email. | Agreed in session (2026-10-06). The rationale says why a finding matters without moving Requirement content across the boundary. |
| 2 | **"In force" is A′'s rule:** actionable, and both Requirements still at the versions the finding judged. Age is measured from the screen that raised it, in A′'s buckets. | The tables then agree with the front page's counts and with what owners see. |
| 3 | **The index state is decided in the use case**, from `IndexBacklogReader.pending()`: a pending source is `failed` once it stopped retrying on the same change, otherwise `waiting`; anything else is `current`; a model change makes every row `rebuild_required`. The adapter only takes an `only` or `excluding` set of ids. | One rule, shared with the summary, and no provider within reach of the internal routes. |
| 4 | **A nudge notifies both owners, each once, at most once every 7 days per finding.** Each notification links to that owner's Requirement's Knowledge step. | Agreed in session (2026-10-06). Either owner can decide the finding; a week matches the age buckets. |
| 5 | **A nudge is recorded here** in `knowledge_finding_nudges`: the admin's id and name, when, and the actor ids notified. | The audit trail stays with the data it is about; knowledge-portal stores nothing. |
| 6 | **Notifications no longer need an AI job.** `actor_notifications.job_id` is nullable, and `NotificationResponse.job_id` is `string \| null`. The browser alert's title is chosen by kind, so a nudge no longer reads "AI work failed". | ADR-0099 Amendment 1. |

## Changes

- **Domain:** `NotificationKind.KNOWLEDGE_FINDINGS_NUDGE`; `ActorNotification.job_id` optional.
- **Migration** `202610061100_knowledge_finding_nudges.sql`: `job_id` drops `NOT NULL` (the
  foreign key stays), and the nudge table with its latest-first index.
- **Ports:** `knowledge_portfolio.KnowledgePortfolioPort` and `FindingNudgesPort`.
- **Adapters:** `PostgresKnowledgePortfolio` (two queries) and `PostgresFindingNudges`;
  `RepositoryKnowledgePortfolio` and `InMemoryFindingNudges` for memory mode, the latter enrolled
  in memory transactions.
- **Application:** `IndexBacklogReader.pending()`; `KnowledgePortfolio.corpus()` and
  `.findings()`; `NudgeFindingOwners`, one transaction that locks both Requirements.
- **Interface:** the three routes, the contract and its path test; the notification schema and
  the browser client's types; the notification centre's alert title by kind.

## Tests

**Unit:** `tests/unit/test_knowledge_portfolio.py`
- a corpus row is identity and state, with each owner's display name;
- the corpus filters by owner, title (wildcards literal), open findings, index state and
  screening age, and pages;
- a finding row names both sides and carries the rationale;
- findings filter by kind, age and either owner, and age through the buckets;
- a finding left behind by an edit is not listed;
- a nudge notifies both owners with no AI job, linking to each Knowledge step, and the row shows
  the last nudge;
- a second nudge within 7 days is refused, and one on day 7 goes through;
- one owner of both Requirements is notified once;
- a decided or unknown finding cannot be nudged;
- the routes need the token, refuse a limit over 100, pass the cooldown's 409 through, and never
  carry an email or a description.

**PostgreSQL:** `tests/integration/test_knowledge_portfolio_postgres.py`
- both queries, their filters and paging, a nudge's notifications with a null `job_id`, the
  nudge record, the cooldown, and the last nudge on an aged finding, against the real schema.

## Validation evidence

Recorded on 2026-10-06, locally, with PostgreSQL 16:

- `ruff format --check src tests` and `ruff check src tests`: clean.
- `mypy src tests`: clean.
- `lint-imports`: contracts kept.
- Full `pytest` with `TEST_DATABASE_URL`: green.
- Frontend `lint`, `typecheck`, `api:check`, `test` and `build`: green.
