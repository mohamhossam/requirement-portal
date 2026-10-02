# Enhancement — Second Review Remediation

## Objective
Resolve the findings of the second whole-workspace review (2026-09-24,
`fix/review-remediation` @ `8f32e1b`, after phases 1–7 of
`enhancement-review-remediation.md`). Work in phases, each of which leaves the
repository green. No new product capability is introduced.

## User Outcome
- Operators get input bounds, safe job execution, supply-chain checks and
  per-token cost visibility.
- Maintainers get one authorization pattern and smaller modules.

## Decisions taken with the user (2026-09-24)
- **Finding 1.** The branch is pushed to `origin/fix/review-remediation`. The
  PR is opened by the user; `gh` is unavailable here and the in-app browser is
  not signed in to GitHub. CI results feed Phase 3.
- **Finding 6.** Keep workspace-wide read: every signed-in user may read every
  submitted Requirement and its artifacts, and only drafts are private. Record
  this in an ADR and pin it with a test so it cannot change by accident.
- **Finding 7.** Untrack the committed skill binaries and review screenshots,
  and ignore them. They stay on disk, and history is not rewritten.

## In Scope

### Phase 1 — Bounds, hygiene and small corrections
| # | Finding | Change |
|---|---|---|
| 1.1 | Requirement free text and lists are unbounded (#2). | Domain intake limits for Requirement and draft fields, applied when content is submitted or edited, with the same bounds on the request schemas (422). Also a streamed request-body ceiling for every request, with multipart allowed one extra file, so the API is bounded without nginx. |
| 1.2 | 43 MB of duplicate binaries and 8 MB of screenshots are tracked; Docker build contexts upload them (#7). | Stop tracking and ignore them. `.dockerignore` excludes the agent and skill directories. |
| 1.3 | nginx serves the bundle uncompressed (#12). | Enable gzip for static text assets. API JSON is deliberately left uncompressed to avoid BREACH-style leaks. |
| 1.4 | Read visibility is undocumented (#6); a §19 debt row is stale (#13). | ADR recording workspace-wide read, plus a test that pins it. Retire the invalidation-transaction row. |
| 1.5 | The rate limit charges requests the caller got wrong (#11). | Refund the budget when a request is refused before any provider call (401, 403, 404 or 422). A 409 stays charged, because a conflict can surface at commit after a paid model call. |

### Phase 2 — Architecture job execution safety
- 2.1 Move lease renewal out of the application use case into
  `ArchitectureJobWorker` (infrastructure), matching the AI job worker (#3).
- 2.2 Fence the job's writes. Mapping and index results commit only while the
  attempt still holds its lease; a lost lease aborts the attempt without
  writing (#3).
- 2.3 Record failures through the public error catalogue, the same way AI jobs
  do, instead of the exception class name (#3). **Revised:** the public code
  only. The job record has no `retryable` column, and manual retry is always
  offered (ADR-0076).
- 2.4 Integrate the knowledge-screen claim-race fix from its separate session
  (task_1963073a), and verify it against the reference deployment (#4).

### Phase 3 — Supply chain and CI
- 3.1 Dependency audits in CI: `pip-audit` over the locked export and
  `npm audit --audit-level=high`. Dependabot covers pip, npm, Docker and
  Actions (#8).
- 3.2 Scan both images with Trivy in the `deployment` job, failing on fixable
  HIGH or CRITICAL issues (#8).
- 3.3 Pin base images by digest (#8).
- 3.4 Measure coverage (pytest-cov and vitest) with a floor set at the measured
  baseline (#8).
- 3.5 Fix whatever the first CI run of the pushed branch reveals (#1).

### Phase 4 — One authorization pattern
- 4.1 ADR choosing the pattern (#5). The requirement-scoped use case declares
  the permission it needs (member or owner), and the application enforces it in
  one place. Today it happens three ways: routes pass a permission to
  `RequirementCommands`, use cases receive `authorization=` a service, or use
  cases get the bare `access_repository` and check membership inline.
- 4.2 Migrate every requirement-scoped mutation to that pattern, with a guard
  test that fails if a use case checks membership any other way.

### Phase 5 — Structure
- 5.1 Split `snapshot_mapper.py`, `text_extractor.py` and `settings.py` along
  their existing seams (#9).
- 5.2 Hoist the composition package's function-level imports of installed
  dependencies. Extend the runtime-invariant guard to `interfaces` and
  `infrastructure`, with an allow-list for genuinely optional dependencies (#10).

### Phase 6 — Token accounting
- 6.1 Read provider-reported token usage from each structured-output and
  embedding response. Export `smb_provider_tokens_total{provider, model,
  kind}` so spend can be alerted on (#15).

## Out of Scope
- **Frontend logic items (#14).** These are the `rules.ts` switch-over,
  generated knowledge types and the `AnalysisPanel` split. They stay deferred
  to the UI redesign under CLAUDE.md's presentation-only rule (AGENTS.md §19).
- **A global cross-replica spend ceiling.** The per-process limit stays; §19
  records it.
- **Members-only read, or a confidential flag.** The user kept workspace-wide
  read.
- Rewriting git history.

## Domain
Phase 1.1: bounds on Requirement fields.

## Application Use Cases
Phase 2 (architecture job execution), Phase 4 (authorization). No new business
use cases.

## Ports
Phase 2.2 may add a lease-fence callback to the architecture job path.

## Adapters
Phases 2, 5 and 6.

## API
- Phase 1.1: new 422s for over-long input, plus a 413 for oversized bodies.
- Phase 1.5: no contract change.

## UI
None. The frontend is presentation-only during the redesign; its existing error
display already shows the new 422 and 413 messages.

## Business Rules
Unchanged, except the documented input bounds.

## Tests
Each phase adds the cheapest tests that prove its change. See the Validation
Evidence section.

## Acceptance
- [x] Phase 1 — delivered; local gates green (CI pending push).
- [x] Phase 2 — delivered (2.3 revised); local gates green (CI pending push).
- [x] Phase 3 — delivered; 3.5 awaits the first CI run on the PR. Local replays green.
- [x] Phase 4 — delivered; local gates green (CI pending push).
- [x] Phase 5 — delivered; local gates green (CI pending push).
- [x] Phase 6 — delivered; local gates green (CI pending push).

## Validation Evidence

### Phase 1 — 2026-09-24, branch `fix/review-remediation`
Delivered 1.1–1.5.

- **1.1 Intake bounds.** `domain/requirement/intake_limits.py` sets:
  - title: 300 characters;
  - description: 60,000;
  - desired outcome and customer context: 10,000 each;
  - lists: 50 items of 1,000 characters.

  The bounds are applied when content is submitted or edited: in
  `CreateRequirement`, `CreateRequirementDraft`, `Requirement.update` and
  `RequirementDraft.revise`. They are not applied on reconstitution, so older
  records still load. The request schemas carry the same bounds (422, and in
  the OpenAPI contract).

  `interfaces/api/body_limit.py` caps every body while it streams:
  `REQUEST_MAX_BODY_BYTES` (default 2 MiB), plus `DOCUMENT_MAX_FILE_BYTES` for
  multipart. Oversized bodies get 413 `request_body_too_large` with a
  correlation ID.
- **1.2 Repository hygiene.** Stopped tracking the three `impeccable.exe`
  copies and `.impeccable/review/` screenshots, and ignored them.
  `.dockerignore` is now an allow-list, so the build context fell from about
  50 MB to about 3 MB.
- **1.3 Compression.** nginx gzips static assets only; API responses stay
  uncompressed to avoid BREACH-style leaks. Verified with a rebuilt image:
  assets have `Content-Encoding: gzip`, and `/api/ready` has none.
- **1.4 Visibility and debt.** ADR-0075 records workspace-wide read, and
  `tests/unit/test_read_visibility.py` pins it. The invalidation-transaction
  row is retired: an AST check found every call site inside `transaction()`,
  directly or through `@atomic_story_change`.
- **1.5 Rate-limit refunds.** Requests refused as 401, 403, 404 or 422 are
  refunded; 409 stays charged. Two defects were found while testing the refund
  and fixed:
  - two calls counted at the same instant shared a ticket, so one refund
    removed both;
  - a refund that emptied an actor's queue crashed the next caller's cleanup.

Tests added:
- `tests/unit/test_intake_limits.py`: the limits, the first field over its
  limit is named, whitespace doesn't count, edits and draft revisions are
  bounded, legacy records still load, API 422, 413 for declared and streamed
  bodies, and multipart allowance.
- `tests/unit/test_read_visibility.py`.
- Refund tests in `tests/unit/test_provider_call_rate.py`.
- Settings tests for `REQUEST_MAX_BODY_BYTES`, and error-map coverage for
  `RequirementIntakeTooLargeError`.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1574 passed
- `ruff check .` — PASS
- `ruff format --check .` — PASS, 945 files
- `mypy src tests` — PASS, 491 source files
- `lint-imports` — PASS, 7 contracts kept
- `npm run lint`, `typecheck`, `build`, `api:check` — PASS (contract
  regenerated)
- `npm test` — PASS, 287 tests
- Reference deployment rebuilt and started with the CI steps: `/api/ready` 200,
  gzip verified.

### Phase 2 — 2026-09-24, branch `fix/review-remediation`
Delivered 2.1, 2.2 and 2.4. Delivered 2.3 as revised (ADR-0076).

- **2.1 Lease renewal.** Moved out of the application use case. The use case
  now exposes `claim_next`, `renew_lease` and `execute_claimed`, and
  `ArchitectureJobWorker` owns the renewal thread. Renewal errors are logged
  and retried instead of silently ending renewal. `ArchitectureJobNotFoundError`
  moved to `application/errors.py`, which breaks the import cycle with the
  public error catalogue.
- **2.2 Fenced commits.** `execute_claimed` passes a fence that renews the lease
  in three places: inside the mapping's commit transaction, before the index is
  stored, and before the release is marked built. A lost lease raises
  `ArchitectureJobLeaseLostError`; the attempt then stops without writing or
  recording an outcome. `BuildArchitectureIndex.execute` requires the fence.
  `MapBreakdownArchitecture.execute` defaults it to a no-op for the direct
  request route, which holds no lease.
- **2.3 Error codes.** Failures record `describe_public_error(exc).code`, for
  example `architecture_knowledge_conflict`, or `internal`.
- **2.4 Knowledge-screen race.** The fix from the separate session (branch
  `claude/eager-williams-70fc74`, 0f3830b) is cherry-picked as `f626ded`. It
  was based on `main`, so its `ExecuteAiJob` change was ported from
  `ai_jobs.py` to `ai_job_execution.py`, where Phase 5 moved it. Index-pending
  screening and suggestion jobs are requeued unconsumed, not failed.

Tests added:
- `tests/unit/test_architecture_jobs.py`:
  - a stale attempt reclaimed mid-run neither writes nor records an outcome,
    and the new attempt keeps the job;
  - an attempt holding its lease writes and succeeds;
  - failures record public codes (`architecture_knowledge_conflict`, and
    `internal` for an unexpected error, whose details are hidden);
  - the worker keeps a running job's lease renewed.
- From the cherry-pick: a deterministic race regression test, plus domain,
  store and PostgreSQL tests.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1583 passed (includes PostgreSQL integration)
- `ruff check .` — PASS
- `ruff format --check .` — PASS
- `mypy src tests` — PASS, 491 source files
- `lint-imports` — PASS, 7 contracts kept
- `npm run api:check` — PASS (no contract change)
- Reference deployment rebuilt, then 15 Requirements created in a burst through
  nginx: all 15 automatic screens succeeded, none failed.

### Phase 3 — 2026-09-24, branch `fix/review-remediation`
Delivered 3.1–3.4 (ADR-0077). 3.5 is open: CI results can't be read from this
environment (no `gh`, a private repository, and no browser session), so it
waits on the PR's first run.

What the first audit found and how each was fixed:
- **pip-audit.**
  - Pillow 11.3.0 (35 advisories) and pypdf 5.9.0 (77 advisories). Both parse
    untrusted uploads. Their bounds moved to `Pillow>=12.3,<13` and
    `pypdf>=6.16.1,<7`, and they are locked at 12.3.0 and 6.19.0.
  - `types-Pillow` was dropped, because Pillow ships its own types.
  - The full suite passes unchanged. The re-audit found no known
    vulnerabilities.
- **npm audit.** 2 high advisories in `js-yaml`, via the OpenAPI type
  generator. `npm audit fix` changed 7 lockfile lines; the result has 0
  vulnerabilities and still resolves only from npmjs.org.
- **Trivy.**
  - The API image had none.
  - The web image had 38 (nginx 1.27 on an old Alpine). It moved to
    `nginx-unprivileged:1.30-alpine`, which left one HIGH in libexpat, newer
    than the base. `apk upgrade` at build time cleared it: 0 findings, and the
    container still runs as uid 101.
- **Pinning.** Seven image references were pinned by digest, and
  `tests/architecture/test_image_pins.py` enforces it along with one PostgreSQL
  image.
- **Registry.** Checked `frontend/.npmrc`, which is committed with a corporate
  registry. CI already overrides it (`NPM_CONFIG_REGISTRY`, `c846b99`), and the
  web image runs `npm ci` before `.npmrc` is copied in, so neither path depends
  on it.

Found by the first coverage run: a real knowledge-review defect.
- **Symptom.** `test_knowledge_review_decision_and_worklist_states_are_public`
  failed once under coverage's slower timing. The background automatic screen
  and the test's synchronous screen had both screened the same input.
- **Cause.** Screening records at most one finding per current pair of
  Requirements, so a second screen of unchanged input records none. But
  `GetKnowledgeReview` counted only findings in each subject's latest screen.
  So any re-screen, from a retry, a requeued automatic job or a user action,
  silently dropped an undecided finding and reported the Requirement `ready`.
- **Fix.** The review now keeps any actionable finding while both
  Requirements are at the versions it judged, matching screening's own
  deduplication. A new version still supersedes it.
- **Test.** `test_re_screening_the_same_input_keeps_an_undecided_finding`
  (deterministic; no workers run) fails on the old code with `'ready' ==
  'action_required'` and passes with the fix. The knowledge and integration
  suites (79 tests) pass unchanged.

Coverage baselines, measured 2026-09-24:
- Backend: 92% of statements. The floor is 90% (`[tool.coverage.report]`).
  `pytest-cov` joined the `dev` extra.
- Frontend (all of `src`): 67.8% statements, 66.2% branches, 53.0% functions,
  71.4% lines. The floors are 66, 64, 51 and 69 (`vitest.config.ts`).
  `@vitest/coverage-v8@4.1.11` was added, with an `npm run test:coverage`
  script.

CI changes:
- a new `supply-chain` job (pip-audit, npm audit);
- a Trivy step in `deployment`;
- coverage in `quality-gates` and `frontend`;
- `.github/dependabot.yml` (uv, npm, docker, docker-compose, actions).

Commands (local):
- `pytest --cov` (with PostgreSQL) — PASS, 1586 passed, 92% total
- `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports` —
  PASS
- `uvx pip-audit==2.10.1 --strict …` — PASS, no known vulnerabilities
- `npm audit --audit-level=high` — PASS, 0 vulnerabilities
- `npm run test:coverage`, `lint`, `typecheck`, `build`, `api:check` — PASS
- The `deployment` job replayed locally:
  - images built, and Trivy exited 0 for both;
  - `run --rm maintenance`, then `up -d --wait`;
  - `/api/ready` returned 200, and `frame-ancestors` was present.

### Phase 4 — 2026-09-24, branch `fix/review-remediation`
Delivered 4.1 and 4.2 (ADR-0078). The review said three authorization styles;
there were four: the `authorized_requirement_mutation` context manager, a
duplicate fence in the service, route-chosen permissions, and inline checks.

- **The service.** `RequirementAccessService` now provides:
  - `mutation`, `automatic_mutation` and `require`, each taking an explicit
    `RequirementPermission`;
  - `require_owner_of_either` and `require_answerer` for the two rules that
    need more than one permission level.
  `mutation_authorization.py`, `MutationPermission`, and
  `execute_member_mutation`/`execute_owner_mutation` are deleted.
- **Use cases.** 25 context-manager calls in 9 modules and about 15 inline
  checks in 8 modules now go through the service. Twelve use cases swapped the
  raw `access` repository for `authorization`. `AnalysisCollaboration`,
  `SuggestClarificationAnswers`, `DecideKnowledgeFinding` and `ApprovalRecorder`
  keep the repository for ownership reads only.
- **Routes.** `RequirementCommands.run` has no `permission` parameter. Every
  command gets the member baseline; `UpdateRequirement` enforces owner itself.
  The one route that passed `OWNER` no longer does.
- **Guards.** `tests/architecture/test_authorization_placement.py` now enforces
  three rules:
  - only the service checks membership (the delegating `ApprovalRecorder`
    excepted);
  - `AuthorizationDeniedError` is raised only by the service, or by five
    allow-listed rules about library documents and question assignees;
  - routes never reference `RequirementPermission`.
- **Tests.** `tests/unit/access_service.py` builds a real service over a test's
  own repositories, so hand-built use cases still exercise authorization.
- **Found.** Unified search shows only the caller's own Requirements, narrower
  than ADR-0075's workspace-wide read. It is recorded there as a deliberate,
  unchanged exception.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest --cov` (with PostgreSQL) — PASS, 1590 passed, 91.6% coverage
- `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports` —
  PASS
- `npm run api:check` — PASS (no contract change)
- `npx playwright test review-flow.spec.ts focused-breakdown.spec.ts` — PASS,
  26 passed. This covers owner and reviewer identity enforcement, private
  drafts, and the approval flows at both viewports.

### Phase 5 — 2026-09-24, branch `fix/review-remediation`
Delivered 5.1 and 5.2. Every move is mechanical: code moved verbatim, and the
move tool rewrote every importer. There are no re-export aliases and no
behaviour change.

- **5.1 `snapshot_mapper.py` (1,636 lines → removed).** Seven layered modules,
  each depending only on those listed before it:
  - `payload_fields.py` (110): typed JSON field primitives;
  - `shared_payloads.py` (354): actors, approvals, comments, generation,
    architecture, evidence and quality;
  - `document_payloads.py` (190);
  - `analysis_payloads.py` (549);
  - `backlog_payloads.py` (271);
  - `review_payloads.py` (244);
  - `identity_payloads.py` (111).

  The 29 cross-module helpers became public, named after checking for no
  collisions with any existing identifier.
- **5.1 `text_extractor.py` (1,618 → 106 lines).** `SafeDocumentTextExtractor`
  now composes five format classes over `ExtractionBase`, which holds the
  limits, bounded XML parsing, archive and image safety checks, and the
  size-capped result. The format classes live in:
  - `plain_text_extraction.py` (135);
  - `presentation_extraction.py` (226);
  - `word_extraction.py` (496);
  - `spreadsheet_extraction.py` (443);
  - `pdf_image_extraction.py` (120).

  Methods moved unchanged, because this parses untrusted input; a rewrite
  around a new context object was rejected for that reason. The extraction
  child still imports it lazily, so native thread caps are set before NumPy
  loads. All 143 document tests pass.
- **5.1 `settings.py` (819 → 558 lines).**
  - `options.py` (186) holds the providers, defaults and `ConfigurationError`,
    with 40 importers repointed.
  - `settings_validation.py` (240) holds the cross-field validation that
    `Settings.__post_init__` calls.

  Neither module reads the environment; AGENTS.md §4.5 still holds.
- **5.2 Imports.** 58 function-level imports were hoisted, in the composition
  package, `activity_projection`, `postgres_worklist`, the fake analyzer and
  one route. None was hiding a cycle, and every entry point still imports.
  The runtime-invariant guard now covers every layer and every import kind,
  with two named exceptions (the extraction child, and platform OS APIs). A
  second test fails if an exception becomes unnecessary. AGENTS.md §12 records
  the rule.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest --cov` — PASS, 1591 passed, 91.7% coverage
- `ruff check .`, `ruff format --check .` (963 files), `mypy src tests` (506
  files), `lint-imports` — PASS
- `npm run api:check` — PASS (no contract change)

### Phase 6 — 2026-09-24, branch `fix/review-remediation`
Delivered 6.1.

- **Where.** Token usage is read at the one seam every provider call already
  passes through: the metered `httpx` and `httpx2` transports (ADR-0074, now
  amended). No adapter changed.
- **What is read.** Each 2xx JSON response's `usage` is parsed in both
  spellings: `prompt_tokens`/`completion_tokens` for chat and embeddings, and
  `input_tokens`/`output_tokens` for the Responses API. The body's `model` is
  kept, truncated to 100 characters, or `unknown` if absent.
- **What is exported.** `smb_provider_tokens_total{provider, model,
  direction}`.
- **Safety.** A body that isn't JSON, has no usage, or exceeds 16 MiB records
  nothing, and never fails the call. Every provider call is non-streaming
  (`"stream": False`), so the transport reads the body and the client reuses
  it.
- **Latency change.** Provider latency is now measured to the end of the
  response body, not the headers. The deployment guide says so, and adds a
  token-budget alert.

Tests added (`tests/unit/test_observability.py`):
- usage parsing for chat, embeddings and Responses API bodies, a missing
  model, invalid counts (bool, negative), non-object and non-JSON bodies;
- a real local HTTP server called through both transports: tokens are counted
  and the client still reads the full body;
- no tokens counted for a failed (429) response.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest --cov` — PASS, 1601 passed, 91.7% coverage
- `ruff check .`, `ruff format --check .` (963 files), `mypy src tests` (506
  files), `lint-imports` — PASS
- `npm run api:check` — PASS; `npm run test:coverage` — PASS, 287 tests

All six phases of this remediation are delivered locally. CI evidence for the
pushed commits waits on the pull request's first run (finding 3.5).

### CI follow-up — 2026-09-25, PR smoke failure
The first PR run failed `smoke` on `review-flow.spec.ts` ("owner assigns a
reviewer who drafts and resolves", responsive-chromium). The error was
`Your answer` "not visible", and the retry failed too.

- **Cause (backend).** `ScreenRequirementKnowledge`'s commit-time check raised
  `KnowledgeGenerationError` (PROVIDER, 502) when the corpus changed during
  screening. The smoke suite creates Requirements continuously on one server,
  so automatic screens failed outright instead of retrying. That produced
  failure notifications and re-renders on the Clarify page.
- **Fix (backend).**
  - The check now raises `KnowledgeIndexPendingError` for a pending index, or
    `KnowledgeScreenConflictError` (CONFLICT, 409) for a changed fingerprint
    or stale citations. That error was already catalogued, but nothing raised
    it.
  - `ExecuteAiJob` defers both for `requires_current_index` operations,
    without consuming the attempt.
  - This is safe: a rerun whose fingerprint no longer matches returns the
    current review without a write.
- **Fix (harness).**
  - `openTriage` now retries until the row is open. The row is an
    uncontrolled `<details>`, and a refetch that lands after the click
    remounts it closed.
  - The test's post-switch fill is retried until the reviewer's view settles.
  - No UI code changed.
- **Tests.** Two tests added in `tests/unit/test_requirement_indexing.py`:
  - the conflict and pending cases raise their own errors, not 502;
  - an automatic screen that conflicts at commit is deferred with no failure
    notification, then succeeds on the next claim.

  Both fail on the previous code with the exact CI error.

Commands (local; `TEST_DATABASE_URL` pointed at a pgvector test container):
- `pytest` — PASS, 1603 passed
- `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports` —
  PASS
- `npm run build`, `npm run lint` — PASS
- `CI=1 npx playwright test` (both projects) — PASS, 89 passed, 5 skipped,
  0 flaky. The server log shows no "changed during screening" failures; the
  earlier CI-like run had one.
