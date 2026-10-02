# Production-Readiness Remediation

## Status

Implementation and local verification are complete for both architecture reviews. All CI-equivalent
backend, frontend, browser, PostgreSQL, typing, formatting, and architecture gates pass locally.
The ordered migration and maintenance commands also pass on a fresh disposable PostgreSQL database.
CI remains the authority, and a real production maintenance window, backup/restore rehearsal, and
deployment are still operational release prerequisites rather than local development checks.

## Goal

Close the production-readiness review findings without changing the modular-monolith shape,
Clean Architecture dependency direction, immutable history, browser review journey, or fake
provider path.

## Domain

- Retained Features and Stories survive source invalidation with identity, human edits, proposals,
  and approval history intact; retained artifacts become stale individually.
- Replacement means update retained IDs, insert new IDs, and delete omitted IDs only in an explicit
  replacement operation.
- Current approval is the latest decision for the current fingerprint and is effective only when
  that decision approves an artifact whose lifecycle is `approved`.
- Mutable aggregates carry positive versions. Feature and Story collections carry set versions.
- AI jobs carry versions and every execution attempt is identified independently of the job.

## Application

- `RequirementAccessService` is the shared authorization collaborator. Membership permits content
  mutations; ownership is required for source edits and governance. Provider-backed synchronous
  commands recheck membership after external work and before commit.
- Mutation commands carry displayed versions, fingerprints, or collection versions as applicable.
- Generation context tokens bind source, evidence, clarification, parent, target, and set state.
- The in-memory transaction manager coordinates all mutable stores with nested rollback semantics.
- Worklist classification remains a pure Application projector. PostgreSQL persists its output.
- Public failures use stable codes and correlation IDs; internal provider/database details remain
  in diagnostic logs.

## Ports

- Artifact repositories expose compare-and-swap replacement and collection-version reads.
- Job repositories expose Requirement-scoped leasing, attempt-token fencing, heartbeats, progress,
  cancellation, completion, and deadline fencing.
- Document storage separates immutable bytes from document metadata.
- `CurrentWorklistProjectionPort` refreshes one current Requirement within the active unit of work.
- Extraction limits and child resource enforcement sit behind infrastructure boundaries.

## Adapters

- Memory uses a container-wide reentrant transaction lock and coordinated snapshots.
- PostgreSQL exposes aggregate-specific Requirement, draft, access, analysis, Epic, Feature,
  Story, proposal, and review repositories over one connection/unit-of-work owner. Requirement
  snapshot serialization has its own compatibility-preserving codec module.
- PostgreSQL adds ordered migrations `013` through `021` for optimistic state/job fencing,
  document blobs, literal search, knowledge catch-up, activity/worklist projections, and projection
  input cursors. Unfinished v1 generation jobs are retired explicitly during maintenance.
- PostgreSQL document blobs are immutable and checksum/size verified. Revision JSON stores metadata
  only.
- Document extraction uses bounded spawned child processes: two active, four waiting, 30 seconds,
  and 512 MiB per child by default.
- OIDC uses validated discovery/JWKS payloads, a 15-minute key TTL, single-flight refresh, and a
  bounded 30-second unknown-key cache. TTL and cache limits are centrally configured.
- Provider and identity HTTP clients are constructed and closed by the composition root.

## API

- Versioned edits and decisions use typed request bodies.
- Artifact decisions include the displayed content fingerprint. Generation includes the displayed
  context token.
- Stale preconditions return `409`; missing required Pydantic fields return `422`.
- Public errors have `{code, message, correlation_id}` and an `X-Request-ID` response header.
- The application factory accepts a container factory so lifespan, middleware, dependencies,
  workers, and fixtures share one graph.

## UI

- API calls carry displayed versions, fingerprints, set versions, and context tokens.
- Access responses expose `can_manage_content` and `can_govern` for consistent action state.
- API error handling covers JSON, downloads, and empty/non-JSON responses.
- Token renewal cannot replace the unauthorized handler. Identity changes cancel outstanding
  queries, clear actor-bound cache, and reset form state.
- A `409` remains visible and preserves the current form so the user can refresh and reconcile;
  stale writes are never automatically replayed.

## Tests

Coverage is added and verified for invalidation/replacement, approval chronology, optimistic and
generation conflicts, role combinations, job lease races and fencing, atomic rollback, idempotency,
single-container wiring, safe errors/OIDC identity transitions, extraction limits, document-blob
durability/backfill, bounded worklist reads, architecture boundaries, and fake-provider startup.
CI provisions PostgreSQL with pgvector and supplies `TEST_DATABASE_URL`, so the integration suite
cannot silently skip.

## Finding-to-change ledger

The follow-up ledger maps every second-review finding to source changes. Its closure-status column
preserves the implementation-era review state; the completed local acceptance evidence is recorded
in the Validation Evidence section below. The first-pass ledger follows it.

| Review finding | Current follow-up work | Closure status |
|---|---|---|
| C1 PostgreSQL commit wiring | Explicit audit adapter and composed snapshot/revision sources; production-container commit regression | Added; unverified |
| H1 transaction/lease boundaries | Close the physical connection during provider work; reacquire and check commit guards; lease-before-job fencing; shared memory lock | Added; unverified |
| H2 complete generation preconditions | v2 full descendant/proposal/document context; direct-command resume guards; coherent response/token snapshots; retained Story versions | Added; unverified |
| H3 evidence cache | v2 complete semantic input identity; staged writes accepted with the generated mutation | Added; unverified |
| H4 progress attempt identity | Context-bound original worker/attempt; synchronous calls have no progress recipient | Added; unverified |
| H5 editor conflicts | Capture opening artifact/version; await successful save; preserve draft and explicitly reconcile conflicts | Added; unverified |
| H6 identity changes | Abort old credential-session requests, including response bodies; sequence actor reconciliation; reset changed-actor state and ignore late sign-out callbacks | Added; unverified |
| H7 application authorization | Actor-required content/source commands; transactional member/owner checks; automatic commands require their bound worker attempt | Added; unverified |
| M1 idempotent replay | Authenticate and compare stored command identity before applying new-context validation to a new job | Added; unverified |
| M2 transport-neutral errors | Application codes/categories; API-only HTTP status mapping | Added; unverified |
| M3 memory transaction parity | Explicit snapshot/restore participants; shared transaction/job/knowledge lock; nested suspension preserves independent progress and index work | Added; unverified |
| M4 knowledge index | Durable dirty-source versions; batches of 100; embedding CAS; targeted citations and source locks before accepting screens/suggestions | Added; unverified |
| M5 activity/reporting | Maintained events/blockers; revision and audit-input cursors; SQL filtering/paging and weekly/cohort/median aggregation; explicit rebuild | Added; unverified |
| M6 search parity | Escaped literal casefold substring, pg_trgm index, stable casefold title/id ordering | Added; unverified; backfill not run |
| M7 architecture contracts | Remove duplicate contracts; include external dependencies; prohibit application HTTP clients and route/dependency adapter selection | Added; unverified |
| M8 resource ownership | Inject root-owned provider/identity clients; ExitStack cleanup on partial construction; startup/shutdown cleanup; persistence-only maintenance graph | Added; unverified |
| M9 persistence responsibilities | SQL in aggregate/document/revision/snapshot adapters over PostgresSession; transaction-only PostgresStore; commit callback replaces deferred binding; shared activity codec | Added; unverified |
| M10 readiness/operations | `/ready`, worker heartbeat health, schema/backfill marker, diagnostic redaction, explicit OIDC deployment preflight | Added; unverified |
| Cleanup | Test-only no-op transaction stub; remove obsolete runtime filesystem storage; generated-schema aliases | Added; unverified |

The complete local test and quality matrix has now run. Migration and maintenance commands were
rehearsed only against a fresh disposable PostgreSQL database; no production service or deployment
was changed.

| Finding | Implementation evidence | Acceptance evidence | State |
|---|---|---|---|
| Invalidation deleted descendants | `invalidate_derived_artifacts.py`; replacement repository contracts | Domain/use-case invalidation cases | Implemented, not run |
| Rejection could leave approval effective | `ReviewableGeneration.current_approval`; readiness policy | approve/reject/approve chronology cases | Implemented, not run |
| Missing authorization policy | `identity_access.py`; permission response; pre/post-provider mutation fence | owner/reviewer/unrelated/unowned/draft and mid-generation revocation cases | Implemented, not run |
| Stale mutations overwrote edits | positive versions, set versions, context tokens, versioned legacy clarification, `409` mapping | before/during-generation and clarification conflict cases | Implemented, not run |
| Transactions differed by adapter | explicit PostgreSQL units; coordinated memory transaction manager and revision checkpoints | rollback matrix in both modes | Implemented, not run |
| Competing/stale workers could publish | Requirement lease plus worker/attempt/expiry fencing | claim/reclaim/cancel/fenced completion cases | Implemented, not run |
| Idempotency crossed Requirements | fingerprint format 2 includes Requirement identity | cross-Requirement key case | Implemented, not run |
| Shutdown closed live resources | claim stop, heartbeat drain, 150-second grace, deadline fencing | shutdown deadline cases | Implemented, not run |
| Fixtures bypassed production graph | `create_app(container_factory)` | single-container lifespan case | Implemented, not run |
| Raw failures leaked | error catalogue/handlers and frontend normalization | API/job safe-error cases | Implemented, not run |
| OIDC refresh/cache was unbounded | validated TTL, single flight, negative cache | malformed/rotation/renewal cases | Implemented, not run |
| Actor changes retained private state | auth/query cancellation and actor reset | actor-switch browser case | Implemented, not run |
| Extraction exhausted process resources | bounded subprocess executor and complexity limits | timeout/saturation/resource cases | Implemented, not run |
| Durable bytes used runtime filesystem | PostgreSQL blob table/storage and resumable importer | restart/checksum/historical import cases | Implemented, not run |
| Worklist hydrated the workspace | maintained projection, database filters/counts/paging, targeted hydration | parity/query-budget cases | Implemented, not run |
| Structural dead weight weakened boundaries | explicit Story dependencies, SQL-owning aggregate PostgreSQL adapters, shared codecs, and strengthened contracts | architecture import cases | Implemented, not run |
| Migration/release was unsafe | maintenance runbook and ordered migrations | rehearsal remains deferred | Documented, not run |

## Migration and rollout

Use `docs/operations/production-readiness-maintenance.md`. Migrations and backfills are explicit
commands and never run during API startup. Legacy document files remain until separately approved.

## Changed-file guide

- Authorization, concurrency, jobs, and accepted cache effects: `application/use_cases/`,
  `application/ports/external_work.py`, and `application/public_errors.py`.
- SQL ownership, transactions, projection cursors, and search: `infrastructure/persistence/`,
  including migrations `013`–`021` and the new `postgres_session.py`, `postgres_revisions.py`,
  `postgres_activity_sources.py`, and `activity_codec.py` boundaries.
- Resource ownership and operational entry points: `interfaces/api/container.py`,
  `interfaces/api/main.py`, `interfaces/maintenance.py`, and `interfaces/deployment_preflight.py`.
- Browser edits and sessions: `frontend/src/features/{epic,features,stories}/`,
  `frontend/src/components/EditorConflictNotice.tsx`, `frontend/src/auth/AuthProvider.tsx`,
  and `frontend/src/api/client.ts`.
- Written regression coverage: `tests/unit/`, `tests/integration/test_postgres_persistence.py`,
  and frontend component/client tests. Existing dirty workspace changes were preserved.
- Structural decisions: ADRs `0034`–`0039`; rollout: the maintenance runbook.

## Validation Evidence

- `TEST_DATABASE_URL=... pytest --tb=short` — **PASS — 753 passed in 90.56s; PostgreSQL tests included**
- `ruff check .` — **PASS — all checks passed**
- `ruff format --check .` — **PASS — 425 files already formatted**
- `mypy src tests` — **PASS — 338 source files checked**
- `lint-imports` — **PASS — 6 contracts kept, 0 broken**
- `npm ci` — **PASS — 317 packages installed, 0 vulnerabilities**
- `npm run api:check` — **PASS — generated OpenAPI types match the committed schema**
- `npm run lint` — **PASS**
- `npm run typecheck` — **PASS**
- `npm run test` — **PASS — 24 files, 120 tests**
- `npm run build` — **PASS — production bundle built; Vite emitted a non-failing chunk-size advisory**
- `npm run test:smoke` — **PASS — 16 desktop/responsive Chromium journeys in 1.9m**
- PostgreSQL focused integration run — **PASS — 21 tests**
- Fresh-database migration command — **PASS — 21 ordered migrations recorded**
- Legacy document-blob backfill rehearsal — **PASS — empty rehearsal manifest imported 0 blobs**
- Activity/worklist maintenance rehearsal, including idempotent rerun — **PASS — 0 of 0 Requirements rebuilt**
- `.\start.ps1 -CheckOnly` — **PASS — fake provider and persistence prerequisites valid**
- `python -m pip check` — **PASS — no broken requirements**
- `git diff --check` — **PASS — no whitespace errors; Git reported only line-ending notices**
- High-confidence credential-pattern scan — **PASS — no matches**
- GitHub Actions CI — **NOT RUN LOCALLY — requires a pushed branch/pull request**
- Production backup/restore and coordinated deployment rehearsal — **NOT RUN — requires the target environment and an approved maintenance window**

## Deferred / Open

CI confirmation remains open until these changes are pushed. Production backup/restore timing,
non-empty legacy-document reconciliation, intended OIDC deployment preflight, and the coordinated
release rehearsal require the real target environment and an approved maintenance window.

No production service was started, no production migration or backfill was applied, and no
deployment or commit was made by this verification task. Tenant isolation, ADO publication, and
destructive legacy-file cleanup remain outside the approved remediation scope.
