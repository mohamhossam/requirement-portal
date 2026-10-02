# Enhancement — Third Review Remediation

## Objective
Resolve the findings of the third whole-workspace review (2026-09-25,
`fix/review-remediation` @ `37d7bbb`, after the six phases of
`enhancement-review-remediation-2.md`). Work in phases, each of which leaves
the repository green. The only behaviour change a user can see is that search
now covers the whole workspace (finding 5, the user's decision).

## User Outcome
- Operators get a cost guard with no unmetered path, bounded input on every
  request field, and tested operational code.
- Users find every Requirement they can read through search.
- Contributors can install the frontend without the corporate registry.
- Maintainers get smaller composition and collaboration modules.

## Decisions taken with the user (2026-09-25)
- **Finding 2, cost guard.** Rate-limit the routes that trigger automatic
  provider work with the existing per-actor limit (`limit_provider_calls`).
  Automatic jobs are not charged separately when they run.
- **Finding 5, search scope.** Search covers the whole workspace, matching
  workspace-wide read (ADR-0075). Drafts stay private. The ADR-0075 exception
  is removed.
- **Finding 6, `.npmrc`.** Remove `frontend/.npmrc` from the repository.
  Document the one-line registry setup for the corporate network.

## Findings and where they go
| # | Finding | Severity | Phase |
|---|---|---|---|
| 1 | No CI run or human review of the branch yet. | High | Process. The PR is open and CI runs on each push. The first failure (smoke) is fixed in `c295734`. A human review stays with the user. |
| 2 | Automatic jobs bypass the cost guard. | Medium | 1 |
| 3 | 89 free-text request fields rely only on the body cap. | Medium | 2 |
| 4 | Operational code has weak coverage. | Medium | 3 |
| 5 | Search is narrower than read. | Medium | 4 |
| 6 | `frontend/.npmrc` pins the corporate registry. | Low | 4 |
| 7 | Frontend items waiting on the redesign. | Low | 6, in part (see Out of Scope) |
| 8 | Next split candidates. | Low | 5 |
| 9 | Supply-chain leftovers. | Low | 4 |
| 10 | The rate limit counts per API process. | Low | Already in AGENTS.md §19. No change. |

## In Scope

### Phase 1 — Cost guard on automatic-job triggers (#2)
- 1.1 Apply `limit_provider_calls` to every route whose use case schedules
  automatic provider work:
  - an automatic knowledge screen: `POST /requirements`, draft promotion,
    `PUT /requirements/{id}`, knowledge-screen ensure, knowledge-finding
    decisions, and intent-proposal decisions;
  - automatic answer suggestions: asking a clarification question, and
    resolving questions (which records an analysis round).

  Refunds for requests refused before any provider call (401, 403, 404, 422)
  already apply.
- 1.2 Guard tests (**revised** during delivery):
  - The trigger routes are listed in `test_provider_rate_limit.py` as their
    own set.
  - A reachability check walks each route's dependency graph. It replaces the
    planned list of scheduler consumers. Any route that can reach a provider
    port or a scheduler port must be limited, or listed with the reason it
    calls none on that path.
  - A behaviour test shows an exhausted budget refuses Requirement creation
    with 429 and creates nothing.
- 1.3 Check whether uploads start provider work. Limit them if they do, and
  record the result.
- 1.5 (**added**) Limit the model calls the reachability check found without
  the limit:
  - clarification resolution, including resolution from the breakdown review,
    which re-analyses synchronously;
  - the two Story quality GETs, which run the evaluator.
- 1.4 Amend ADR-0074 (cost guard) and update `docs/operations/deployment.md`.

### Phase 2 — Bounds on every free-text request field (#3)
- 2.1 Shared bounded string types in the request schemas (short text, long
  text, identifier, YAML document), sized from the domain limits in
  `domain/requirement/intake_limits.py` where they exist.
- 2.2 Apply them to every free-text request field and list. **Revised:** the
  bound sits on the request schema only, not also in the domain. Every
  provider-bound value, including AI job commands, enters through these
  schemas, so the schema bound is already a 422 before any provider call. The
  one exception is `ReviewedPassage`: it is a domain value used directly as a
  request item, and a request-only copy would rename the OpenAPI component
  the browser client is typed against. So its bound is in the domain.
- 2.3 A guard test walks the OpenAPI request bodies. It fails on any string
  without `maxLength`, array without `maxItems`, or open object.
- 2.4 Regenerate the OpenAPI contract (`npm run api:check`).

### Phase 3 — Coverage of operational code (#4)
- 3.1 `interfaces/maintenance.py`: tests for the rebuild-and-mark path, for a
  refused run, and for the exit codes.
- 3.2 `ai_job_execution.py`: tests for the failure, cancellation and
  lease-loss paths, and for the notifications they send.
- 3.3 `postgres_architecture_jobs.py`, and the embedding and classifier
  adapters: tests for the uncovered branches (PostgreSQL tests run against
  the test container).
- 3.4 Raise the backend coverage floor to the new measured baseline.

### Phase 4 — Search scope, `.npmrc` and supply-chain leftovers (#5, #6, #9)
- 4.1 `UnifiedKnowledgeSearch` returns every readable submitted Requirement,
  using the same read rule as direct reads. Drafts stay excluded. Update
  ADR-0075 and add a test.
- 4.2 Remove `frontend/.npmrc`, document the registry setup in `WORKSPACE.md`,
  and drop any CI step that only existed to override it.
- 4.3 Pin GitHub Actions by commit SHA, with the tag in a comment. Dependabot
  already updates Actions.
- 4.4 Audit the optional `document-ocr` extra in the `supply-chain` job.
- 4.5 The web image's build-time `apk upgrade` stays. It is deliberate and
  documented (ADR-0077). Only the rationale is restated.

### Phase 5 — Structure (#8)
- 5.1 Split `container.py` along its composition seams: the field assembly
  moves into the existing `composition/` modules.
- 5.2 Split `activity_projection.py` and `analysis_collaboration.py` along
  their existing responsibilities, with no behaviour change.

### Phase 6 — Frontend, within the presentation-only rule (#7)
- 6.1 Raise the frontend coverage floors with component tests for the
  least-covered presentational components. Tests are not UI logic.
- 6.2 Split `AnalysisPanel.tsx` into presentational subcomponents, where no
  hook, state or data flow changes. If a seam needs a logic change, stop and
  raise it (CLAUDE.md).

## Out of Scope
- **`client.ts` and `rules.ts` (#7).** They are services and state logic, which
  CLAUDE.md forbids changing during the redesign. They stay deferred in
  AGENTS.md §19.
- **A global cross-replica spend ceiling (#10).** The per-process limit stays.
- **A human code review (#1).** That stays with the user.
- Rewriting git history.

## Domain
Phase 2.2: bounds on prompt-bound fields.

## Application Use Cases
Phase 4.1: the search visibility rule. No new use cases.

## Ports
None.

## Adapters
Phase 3 (tests only), and Phase 5 (moves only).

## API
- Phase 1: new 429s on the trigger routes.
- Phase 2: new 422s for over-long input.
- Phase 4.1: search returns more results.

## UI
None, beyond Phase 6's presentation-only split. The existing error display
already shows 422 and 429 messages.

## Business Rules
- Search visibility equals read visibility.
- Every provider-spending path is rate-limited.

## Tests
Each phase adds the cheapest tests that prove its change. See the Validation
Evidence section.

## Acceptance
- [x] Phase 1 — delivered; local gates green.
- [x] Phase 2 — delivered; local gates green.
- [x] Phase 3 — delivered; local gates green.
- [x] Phase 4 — delivered; local gates green.
- [x] Phase 5 — delivered; local gates green.
- [x] Phase 6 — delivered; local gates green.

## Validation Evidence

### Phase 1 — 2026-09-25, branch `fix/review-remediation`
Delivered 1.1–1.5.

- **Automatic triggers limited (1.1).** `limit_provider_calls` is now on
  every route that queues automatic provider work:
  - Requirement create, promote and edit;
  - knowledge-screen ensure;
  - knowledge-finding and intent-proposal decisions;
  - asking a clarification question.
- **Direct model calls found and limited (1.5).** The reachability check
  found routes that called a model directly, beyond what the review reported:
  - clarification resolution, single and batch, which re-analyses
    synchronously;
  - open-question resolution from the breakdown review, which re-analyses
    through the same path;
  - `GET .../stories/quality` and `GET .../stories/{id}/quality`, which run
    the Story quality evaluator on every read. The browser does not call them;
    it reads the stored assessment.
- **Uploads (1.3).** No upload route reaches a provider or scheduler port.
  Attachment and library ingestion are local. Library embedding happens only
  in builds, which were already limited. Uploads stay unlimited.
- **Residual.** The requirement index worker re-embeds changed text after any
  corpus edit, including edits through unlimited routes. It is recorded in
  ADR-0074 (amended) and AGENTS.md §19.
- **Guard (1.2).** `test_provider_rate_limit.py` resolves each route's
  dependencies, including annotations imported only for type checking. It
  fails if a route can reach one of 14 provider ports or 2 scheduler ports
  without the limit, unless the route is listed in `NOT_PROVIDER_CALLING`
  with a reason (16 routes, each checked at method level).
- **Behaviour.** `test_provider_call_rate.py` shows a second Requirement
  creation over budget is a 429 and creates nothing.
- **Docs (1.4).** ADR-0074 is amended, and the deployment guide lists the
  trigger actions and advises sizing the limit for bulk authors.

### Phase 2 — 2026-09-25, branch `fix/review-remediation`
Delivered 2.1–2.4 (2.2 and 2.3 revised; see In Scope).

- **Shared types.** `interfaces/api/schemas/bounds.py` defines `Identifier`
  (200), `Name` (300), `Sentence` (1,000), `Text` (10,000) and `YamlDocument`
  (1,000,000), plus list sizes of 50 per request and 5,000 per architecture
  catalogue. They reuse the intake limits where one exists.
- **Coverage.** Every request string and list now has a maximum, 136
  route-field pairs before this change:
  - the AI job start union;
  - analysis and clarification;
  - governance and review;
  - Epic, Feature and Story edits;
  - knowledge decisions, ownership, saved views and worksheets;
  - the architecture catalogue, YAML import and preview query;
  - the library approval revision.
- **Architecture schemas.** These also serialise responses, so their bounds
  are generous enough that no stored catalogue fails to read back.
- **`ReviewedPassage`.** It is bounded in the domain: block identity 1,000,
  text 200,000, exclusion reason 10,000. That keeps its shared OpenAPI
  component, which `client.ts` is typed against, unchanged.
- **Guard.** `tests/architecture/test_request_bounds.py` walks the OpenAPI
  request bodies, through `$ref`, unions and nested models. It fails on a
  string without `maxLength`, an array without `maxItems`, or an open object.
- **Behaviour.** `tests/unit/test_request_field_bounds.py`:
  - over-long values get 422 before the use case: a draft answer, a review
    comment, an AI job identifier, a 51-answer batch;
  - a value exactly at the maximum still reaches the use case;
  - the domain passage bound holds.
- **Contract.** `frontend/openapi.json` is regenerated: it only adds
  `maxLength` and `maxItems`. `src/api/schema.d.ts` is unchanged.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container),
covering Phases 1 and 2 together:
- `pytest` — PASS, 1612 passed
- `ruff check .`, `ruff format --check .`, `mypy src tests` (509 files),
  `lint-imports` — PASS
- `npm run build`, `npm run lint`, `npm run api:check` — PASS
- `CI=1 npx playwright test` (both projects) — PASS: 89 passed, 5 skipped,
  0 flaky. The server log has no 422 or 429 responses, so no browser flow
  sends a value over a new bound.

### Phase 3 — 2026-09-25, branch `fix/review-remediation`
Delivered 3.1–3.4. Tests only, plus the coverage floor; no production code
changed.

| Module | Before | After | New tests |
|---|---|---|---|
| `interfaces/maintenance.py` | 0% | 93% | `test_maintenance_entry_point.py` |
| `application/use_cases/ai_job_execution.py` | 70% | 95% | `test_ai_job_execution.py` |
| `infrastructure/persistence/postgres_architecture_jobs.py` | 65% | 99% | `test_postgres_architecture_jobs_errors.py`, `integration/test_postgres_architecture_jobs.py` |
| `infrastructure/llm/requirement_knowledge_adapters.py` | 70% | 99% | `test_knowledge_embedding_adapters.py` |

- **Maintenance (3.1).**
  - The command refuses memory persistence and unknown arguments (exit 2)
    without building a rebuild.
  - With PostgreSQL it rebuilds once and prints the count.
  - Found while testing: PostgreSQL without `DATABASE_URL` is refused
    earlier, by the settings, with a clear `ConfigurationError`. The test
    pins that behaviour.
- **Job executor (3.2).**
  - Every job operation except the breakdown-review open-question resolution
    is started over HTTP, claimed through the index-gated queue and run
    through `ExecuteAiJob`, with its result resource and success notification.
  - Also covered: a failure, recorded with a public error and a notification;
    an index wait on a job that needs no index, which fails; an automatic
    failure, which notifies the Requirement owner; a contradiction, which
    notifies both owners.
  - Cancellation is covered before the attempt and between the provider call
    and the commit.
  - Unclaimed and superseded attempts are refused and leave the job running.
  - Malformed stored commands fail as `ai_job_conflict`.
  - The test container runs no background workers, so the test is the only
    claimant. An in-process worker would otherwise race the test's claims
    and make it flaky.
- **Architecture jobs (3.3).**
  - Against PostgreSQL: three lapsed attempts end as `attempts_exhausted`;
    manual retry and cancellation work, and a transition from the wrong
    state is a conflict; re-enqueueing a cancelled job queues it again; a
    finished attempt cannot heartbeat.
  - Without a database: every driver error becomes `PersistenceError` with
    its cause, and invalid stored rows fail loudly.
- **Knowledge adapters (3.3).**
  - Local and OpenAI embeddings reorder vectors by index and make no request
    for empty input.
  - They reject HTTP errors, non-JSON, malformed payloads, non-numeric,
    missing or extra vectors, and wrong-width or non-finite vectors.
  - The structured classifier rejects provider errors, blank, repeated and
    self-duplicating citations.
  - The suggester rejects a suggestion that cites one passage twice.
- **Dead code noted.** `requirement_knowledge_adapters.py` lines 342-343 catch
  an `IndexError` that the range check just above makes impossible. Left in
  place: this phase adds tests only.
- **Floor (3.4).** `fail_under` rises from 90 to 92 (measured 92.44%). CI
  measures with PostgreSQL, as here.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest --cov` — PASS, 1670 passed, 92.44% coverage
- `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports` —
  PASS

### Phase 4 — 2026-09-25, branch `fix/review-remediation`
Delivered 4.1–4.5.

- **Search scope (4.1).** `UnifiedKnowledgeSearch.execute(query)` no longer
  takes an actor, and no longer filters by membership.
  - A hit is dropped only when its Requirement no longer exists, or its
    evidence or source lineage is stale.
  - Drafts are never indexed. The index is built from submitted Requirements
    only, and drafts live in their own repository.
  - The route still requires a signed-in actor through its router.
  - `test_unified_search_balances_sources_across_the_workspace` (renamed from
    `..._filters_membership`) shows: a colleague's Requirement is found, and a
    draft with the same words is not.
  - ADR-0075 now says search follows read, and ADR-0064 notes the amendment.
- **`.npmrc` (4.2).**
  - `frontend/.npmrc`, which pointed at the corporate registry, is removed
    and git-ignored.
  - `package-lock.json` already resolved all 390 packages from
    `registry.npmjs.org`, and the web image's `npm ci` never copied `.npmrc`.
    So only the CI override existed because of it, and that is removed too.
  - `WORKSPACE.md` §6.1 documents the one-line `npm config set registry`
    for internal networks. The developer's user-level npm config already
    carries it.
- **Actions by SHA (4.3).** All 17 `uses:` lines are pinned by full commit SHA
  with a `# vX.Y.Z` comment:
  - checkout v4.4.0, setup-node v4.4.0, upload-artifact v4.6.2 and
    setup-uv v6.8.0, resolved with `git ls-remote`;
  - the annotated setup-uv tag is dereferenced to its commit.

  `tests/architecture/test_action_pins.py` enforces it and fails on the
  previous workflow.
- **OCR extra audit (4.4).** The `supply-chain` job audits the export that
  includes `document-ocr` (145 packages). It was clean locally with
  pip-audit 2.10.1.
- **`apk upgrade` (4.5).** It stays; ADR-0077 restates why. ADR-0077 also
  records the Action pins, the OCR audit and the 92% floor.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest --cov` — PASS, 1672 passed, 92.43% coverage
- `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports` —
  PASS
- `uv export --extra document-ocr` + `pip-audit --strict` — no known
  vulnerabilities
- `npm run build`, `npm run lint`, `npm run api:check` — PASS
- `CI=1 npx playwright test` (both projects) — PASS, 89 passed, 5 skipped,
  0 flaky

### Phase 5 — 2026-09-25, branch `fix/review-remediation`
Delivered 5.1 and 5.2. They move code only; behaviour and every public API are
unchanged.

| Module | Before | After | Moved to |
|---|---|---|---|
| `interfaces/api/container.py` | 1,137 | 745 | `composition/requirements.py`, `analysis_workflow.py`, `review.py`, `breakdown.py`, `jobs.py` |
| `application/use_cases/analysis_collaboration.py` | 930 | 745 | `application/use_cases/analysis_reconciliation.py` (231) |
| `infrastructure/persistence/activity_projection.py` | 953 | 699 | `infrastructure/persistence/postgres_activity_reader.py` (295) |

- **Composition (5.1).** Each new builder returns a frozen `...Wiring`
  dataclass, like the existing ones.
  - `Container` keeps every field, assembled explicitly from the bundles, so
    no `container.x` access changed and mypy still checks each field.
  - Review is built before the breakdown, because Epic, Feature and Story
    approval use its recorder.
  - ADR-0071 is amended.
- **Reconciliation (5.2).** The check that a re-analysis accounted for every
  active AI question is now the pure function `reconcile_round`. It returns
  the round, new questions and superseded questions, and
  `AnalysisCollaboration` stores them.
- **Reconciliation tests.** `tests/unit/test_analysis_reconciliation.py` now
  tests each rule directly (9 tests), from a real fake-analyzer second round:
  - a missing review, and omitted reconciliation details, are refused;
  - each action must carry the right content;
  - a duplicate new uncertainty is refused;
  - retiring a question the analysis still states is refused;
  - the model may not restate a person's question.

  Combined coverage of the module is 95%. The rest is defensive branches
  that the earlier checks make unreachable.
- **Activity (5.2).** The PostgreSQL read adapter, its lookups and its deltas
  moved to `postgres_activity_reader.py`. The shared, backend-neutral
  projection stays. Five importers were retargeted.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest --cov` — PASS, 1672 passed, 92.49% coverage (before the 9
  reconciliation tests; those pass on their own)
- `ruff check .`, `ruff format --check .`, `mypy src tests` (523 files),
  `lint-imports` (7 contracts) — PASS
- `CI=1 npx playwright test` (both projects) — PASS: 88 passed, 5 skipped,
  1 flaky. The flaky test is the desktop journey (`review-flow.spec.ts`,
  responsive), and it passed on retry.
  - The failure snapshot shows the "Analysis finished" notice while the
    Analysis panel still says "No analysis yet": a frontend refetch race
    after a job completes.
  - It flaked the same way before this remediation, and Phase 5 changed only
    backend wiring.
  - Fixing it needs a frontend state-logic change, which CLAUDE.md reserves
    for the user's approval. It is raised as a separate task, not fixed here.

### Phase 6 — 2026-09-25, branch `fix/review-remediation`
Delivered 6.1 and 6.2 within CLAUDE.md's presentation-only rule. No hook,
service, state, query or API call changed. The 6.2 file list was confirmed
with the user before editing, including one added file, `analysisFormat.ts`.

- **Client contract (6.1).** `src/api/contract.test.ts` calls every function
  of `api` and `knowledgeApi` (150 functions) with a stand-in argument and
  records each request.
  - It asserts every method and path matches an operation in `openapi.json`,
    so the hand-written client cannot drift from the API contract.
  - A deliberately broken path (`/knowledge-index/retry-now`) fails it.
  - `controlLibrary` is called with each of its literal path segments.
- **Architecture knowledge page (6.1).** `ArchitectureKnowledgePage.test.tsx`
  (11 tests) covers:
  - the maintainer gate;
  - saving a system with trimmed aliases, constraints and matching phrases;
  - retiring a system also drops its relationships;
  - retiring a squad unassigns its systems;
  - publishing needs a current index, a rationale and confirmation;
  - cancelling and retrying a build;
  - YAML export and import;
  - test retrieval's candidates and uncertainty;
  - reactivation needs a rationale.
- **Floors (6.1).** Measured before → after: statements 67.83 → 76.25,
  branches 66.21 → 70.15, functions 52.95 → 65.80, lines 71.40 → 80.22.
  `vitest.config.ts` floors rise to 75 / 69 / 64 / 79.
- **`AnalysisPanel.tsx` split (6.2).** 1,790 → 615 lines. The hook-free
  pieces moved verbatim into `StatusStrip.tsx`, `SettledColumn.tsx`,
  `IntentProposalCard.tsx`, `QuestionCard.tsx`, `LegacyClarificationForm.tsx`,
  `RoundHistory.tsx` and `analysisFormat.ts`.
  - `AnalysisPanel.tsx` keeps the design notes, `useIntentDrafts`,
    `AnalysisPanelContent` (all state) and the public `AnalysisPanel`.
  - A line-multiset comparison shows the same 1,699 non-import lines before
    and after. The only textual additions are `export` keywords and imports.
  - `AnalysisPanel.test.tsx` is unchanged, and its tests pass.
- **Findings recorded, not fixed.** Both need frontend logic changes, so they
  are in AGENTS.md §19:
  - identity-dependent queries run before identity loads (`enabled:
    undefined`);
  - the Clarify panel can briefly show "No analysis yet" after the analysis
    job finishes. This is the flaky smoke test, raised as a separate task.
- **Still deferred.** `client.ts` generation and the `rules.ts` switch-over
  wait for the redesign (AGENTS.md §19).

Commands (local):
- `npm run test:coverage` — PASS, 450 tests, floors met
- `npm run lint`, `npx tsc -b`, `npm run build` — PASS
- `CI=1 npx playwright test` (both projects) — PASS on the second run: 89
  passed, 5 skipped, 0 flaky.
  - The first run lost both local servers partway through:
    `ERR_CONNECTION_REFUSED` on the UI port and `ECONNREFUSED` on the API
    port. Tests that ran while the servers were up passed.
  - The rerun, on different ports with the same code, had no connection
    errors.
