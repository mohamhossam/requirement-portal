# Enhancement — Fourth Review Remediation

## Objective
Resolve the findings of the fourth whole-workspace review (2026-09-25,
`fix/review-remediation` @ `e2d1bd4`, after the six phases of
`enhancement-review-remediation-3.md`; CI green on PR #18). Work in phases,
each leaving the repository green. The one change a user can see is a Clarify
panel that no longer shows stale state (Phase 5, once approved).

## User Outcome
- Operators get polled lists that stay bounded as a workspace ages, and read
  notifications that are cleaned up.
- The production job queue, the migration runner and deployment preflight are
  tested.
- Stored records never fail to load because of a limit meant for new input.

## Decisions taken with the user (2026-09-25)
- **Findings #4 and #6 (frontend logic).**
  - #6 is fixed here: the Architecture knowledge page's identity-dependent
    queries wait for a loaded identity.
  - #4, the stale Clarify panel, comes from the separate investigation task.
    The user approves its fix there, and it is brought into Phase 5.
- **Finding #3 (retention).** A separate one-shot command,
  `python -m smb_requirement_agent.interfaces.retention`. It deletes read
  notifications older than `NOTIFICATION_RETENTION_DAYS` (default 90) and is
  safe to run with the API live. The offline maintenance command stays
  offline-only.
- **Branch.** Continue on `fix/review-remediation` (PR #18).

## Findings and where they go
| # | Finding | Severity | Phase |
|---|---|---|---|
| 1 | No human review yet (CI is now green). | High | Process; the user's. |
| 2 | `GET /requirements/{id}/ai-jobs` and `GET /notifications` have no limit and are polled. | Medium | 1 |
| 3 | Nothing prunes operational rows. | Medium | 2 |
| 4 | The Clarify panel can show "No analysis yet" after the job finishes. | Medium | 5 (from its task) |
| 5 | Thin tests on `postgres_ai_jobs.py`, `migration_runner.py` and `deployment_preflight.py`. | Medium | 3 |
| 6 | The Architecture knowledge page requests data before identity loads. | Low | 5 |
| 7 | Some input limits also apply when stored records are read back. | Low | 4 |
| 8 | The 429 message on saving a Requirement says only "Too many AI requests". | Low | 4 |
| 9 | Unreachable `IndexError` handler in `requirement_knowledge_adapters.py`. | Low | 4 |
| 10 | Deferred on purpose: `client.ts`, `rules.ts`, the per-process limit, index re-embedding. | Low | Already in AGENTS.md §19. No change. |

## In Scope

### Phase 1 — Bounded, polled lists (#2)
- 1.1 `GET /requirements/{id}/ai-jobs` takes `limit` (default 100, maximum 500).
  It returns every active job, then the newest finished jobs up to the limit.
  An active job can never be cut off, and the browser's job observation
  already ignores jobs that leave the list.
- 1.2 `GET /notifications` takes `limit` (default 100, maximum 500), newest
  first.
- 1.3 The limit lives in the repository query (`LIMIT`) as an optional
  argument. The activity projection, which reads every job as the audit
  record, keeps reading them all.
- 1.4 The browser keeps calling without `limit` and gets the defaults, so no
  frontend change is needed. Regenerate `openapi.json`.

### Phase 2 — Notification retention (#3)
- 2.1 `NotificationRepositoryPort.delete_read_before(cutoff)` for memory and
  PostgreSQL, and a `PruneReadNotifications` use case.
- 2.2 `interfaces/retention.py` command, with a `retention` compose profile and
  `NOTIFICATION_RETENTION_DAYS` validated in settings.
- 2.3 ADR-0079 records what is retained and why:
  - AI jobs are kept, because they are the activity feed's audit record and
    the automatic-screen reservation's memory;
  - read notifications are pruned;
  - unread notifications are kept, and are bounded on read by Phase 1.
- 2.4 Update the deployment guide.

### Phase 3 — Tests for critical storage code (#5)
- 3.1 `postgres_ai_jobs.py`: claiming, lease expiry and reclaim, fenced
  writes, deferral, idempotency, and the notification queries.
- 3.2 `migration_runner.py`: applying in order, being idempotent, refusing
  unknown or edited migrations (whatever the runner guarantees).
- 3.3 `deployment_preflight.py`: each check it runs, and its exit codes.

### Phase 4 — Correctness details (#7, #8, #9)
- 4.1 `ReviewedPassage`'s size limit moves from `__post_init__` (which also
  runs on load) to where a review is submitted. The OpenAPI guard's
  exemption points there instead.
- 4.2 The architecture catalogue schemas serialise responses without
  re-validating, so a stored release always reads back. The limits keep
  applying to requests.
- 4.3 The 429 message explains that creating or changing a Requirement counts,
  because it starts knowledge screening.
- 4.4 Remove the unreachable `IndexError` handler.

### Phase 5 — Frontend (#6, #4)
- 5.1 `ArchitectureKnowledgePage`: queries depending on the maintainer role
  are enabled only once identity has loaded, with a test that no releases
  request is made for a non-maintainer.
- 5.2 Integrate the stale-panel fix from the investigation task after the
  user approves it there. If it has not reported, this item stays open.

## Out of Scope
- A human code review (#1).
- Deferred items (#10), already in AGENTS.md §19.
- Rewriting git history.

## Domain
None.

## Application Use Cases
Phase 2: `PruneReadNotifications`. Phase 4.1: the review input limit.

## Ports
Phase 1: optional limits on two repository methods. Phase 2: one delete
method.

## Adapters
Phases 1–3.

## API
Phase 1: optional `limit` on two list routes, with defaults that keep today's
results for any realistic workspace. Phase 4.3: a clearer message.

## UI
Phase 5 only.

## Business Rules
Unchanged.

## Tests
Each phase adds the cheapest tests that prove it. See Validation Evidence.

## Acceptance
- [x] Phase 1 — delivered
- [x] Phase 2 — delivered
- [x] Phase 3 — delivered
- [x] Phase 4 — delivered
- [ ] Phase 5 — 5.1 delivered; 5.2 waits on the investigation task

## Validation Evidence

### 2026-09-25, branch `fix/review-remediation`
- **Phase 1, bounded lists.**
  - `GET /requirements/{id}/ai-jobs` and `GET /notifications` take `limit`
    (1–500, default 100).
  - The job list returns every active job, then the newest finished ones, so
    a watched job cannot drop out.
  - The repository methods take an optional bound SQL `LIMIT`. None means
    `LIMIT NULL`, so the activity projection still reads every job.
  - `openapi.json` and `schema.d.ts` are regenerated (+2 lines of types). No
    frontend code changed.
  - Tests (`tests/unit/test_bounded_lists.py`,
    `tests/integration/test_postgres_bounded_lists.py`) cover:
    - an old running job is kept alongside the newest finished ones;
    - active jobs survive a limit smaller than their count;
    - the activity reader still sees every job;
    - the route refuses 0 and 501;
    - notifications come back newest first;
    - the same results in PostgreSQL.
- **Phase 2, retention.**
  - `PruneReadNotifications` deletes notifications read before a cutoff and
    keeps unread ones.
  - It runs through `interfaces/retention.py`, with the `retention` compose
    profile and `NOTIFICATION_RETENTION_DAYS` (default 90, validated;
    documented in `.env.example` and `production.env.example`).
  - ADR-0079 records why AI jobs are kept: they are the activity feed's
    record and the automatic-screen reservation's memory. AGENTS.md §19
    records their growth, with archiving as the future option.
  - The deployment guide has a Retention section.
  - Tests cover the rule, the settings, both command outcomes and the
    PostgreSQL delete.
  - While there, the `.env.example` rate-limit comment was corrected to name
    Requirement create and change as limited actions.
- **Phase 3, storage tests.**
  - `integration/test_postgres_ai_job_queue.py`:
    - idempotency binding: a repeat is allowed, a different command is a
      conflict;
    - the current attempt can report progress and heartbeat; a stale token
      cannot;
    - after `fence_attempt` the old attempt cannot finish;
    - another worker reclaims, finishes and releases;
    - notification round-trip and preferences defaulting to off.

    The module deletes its own `fence-` jobs before and after each test, so
    claims on the shared database stay deterministic across runs.
  - `integration/test_migration_runner.py` runs against a throwaway schema
    and a stand-in folder:
    - migrations apply once, in name order;
    - a renamed legacy migration is recorded, not rerun;
    - a failing migration raises `PersistenceError` and applies nothing,
      because the whole run is one transaction;
    - an empty package has no latest migration.
  - `unit/test_deployment_preflight.py`: fake identity is refused with exit 2
    and the reason; OIDC exits 0.
- **Phase 4, correctness details.**
  - `ReviewedPassage` is limited at submission
    (`require_submittable_passages`, called by `DocumentLibrary.review`), no
    longer in `__post_init__`, so stored reviews always load.
  - The architecture catalogue schemas build responses with
    `model_construct`, so a stored release over a request limit reads back;
    requests stay limited. Both are tested.
  - The 429 message now says that creating or changing a Requirement counts.
  - The unreachable `IndexError` handler is removed.
- **Phase 5.1.** `ArchitectureKnowledgePage`'s identity-dependent queries use
  `enabled: ... === true`, so nothing is requested before identity loads. The
  restored assertion (no releases or documents requested for a
  non-maintainer) fails without the change. AGENTS.md §19 retires the item.
- **Phase 5.2.** Open. The investigation task has not reported yet.

Environment note: the local PostgreSQL test container stopped partway
through, and a test hung connecting to it. That matches the earlier smoke
run's dropped connections. The container was restarted and the tests were
rerun.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest --cov` — PASS, 1703 passed, 92.80% coverage. `postgres_ai_jobs.py`
  goes 72% → 95%, `deployment_preflight.py` 50% → 94%, and
  `migration_runner.py` and the retention modules reach 100%.
- `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports` —
  PASS
- `npm run test:coverage` (450 tests, floors met), `npm run lint`,
  `npx tsc -b`, `npm run build`, `npm run api:check` — PASS
- `CI=1 npx playwright test` (both projects) — PASS, 89 passed, 5 skipped,
  0 flaky

### Follow-up — Dependabot configuration
PR #18 merged at `e2d1bd4`, which put `.github/dependabot.yml` on `main`, and
Dependabot opened 15 PRs (#20–#34) within four minutes. Most were majors:
Actions 4→7, TypeScript 7, vitest 5, jsdom 30, pytest 9, mypy 2, a Python 3.14
base image and a non-LTS Node 25 image. The configuration now:
- groups every Actions update into one PR;
- caps each ecosystem at three open PRs;
- ignores the Python base image beyond 3.12, Node majors and PostgreSQL
  majors.

The existing Dependabot PRs are the user's to close or merge. This commit and
`ae6133e` go to `main` through a new PR from `fix/fourth-review-remediation`,
because PR #18 was merged before `ae6133e` was pushed.

