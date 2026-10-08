# Refactor — Bounded-context packages and domain events

**Status:** Delivered 2026-10-08. ADR-0103 was accepted and the slice scheduled 2026-10-07, and
the PR 1 findings were decided the same day (ADR-0103 Amendment 1). PRs 1–16 and 11b complete the
migration: every context has its own package, and `lint-imports` enforces the dependency order
with no exemptions (ADR-0103 Amendment 2). Merging is the owner's step. The work left is under
*Follow-ups*.

**Related:** [context map](../architecture/context-map.md),
[ubiquitous language](../architecture/ubiquitous-language.md).

## Objective

Restructure `src/smb_requirement_agent` from layer-first packages into bounded-context packages.
Replace the direct cross-context invalidation calls with in-process domain events, move the
governance rules into the domain, and enforce context boundaries with import-linter. The behaviour
of the running application does not change.

## User Outcome

No user-visible change. The outcome is for maintainers:
- A context's model, use cases and adapters live in one package.
- A boundary violation fails `lint-imports`.
- Adding a consumer of "something changed" is one handler, not edits to every trigger.

## In Scope

- The package moves in ADR-0103 §1 and the module mapping in `context-map.md`.
- `DomainEvent`, `DomainEventPublisher`, `InProcessEventDispatcher`, `TransactionManagerPort.in_unit_of_work()`, and the handlers in ADR-0103 §3.
- Moving the governance rules into the domain (ADR-0103 §4).
- Breaking the domain package cycles, and moving payload codecs out of the domain.
- The import-linter contracts in ADR-0103 §5.
- Test reorganisation under `tests/unit/<context>/`.
- Removing the stale `smb_requirement_agent.infrastructure.architecture` package-data entry from `pyproject.toml`; that package no longer exists.

## Out of Scope

- **Any change to the REST contract, the OpenAPI snapshot, the database schema, the migrations or the persisted JSONB payloads.**
- **The frontend.** `frontend/src/review/rules.ts` is recorded debt under ADR-0073 and AGENTS.md §19, and CLAUDE.md allows only presentation changes during the redesign.
- **New business behaviour.** That includes new events without a consumer today (AGENTS.md §16).
- **Asynchronous events or an outbox inside this service.**
- **Changes in knowledge-portal or platform-kernel.**

## Domain

- **Shared kernel.** `shared_kernel/` is created from `domain/shared` plus `RequirementId`, `ActorSnapshot` (re-exported from `smb_kernel`), `SourceLineage`, `require_aware` and the `DomainEvent` base.
- **Context domains.** Each context's `domain/` is created from the current `domain/*` packages, following `context-map.md`.
- **Events.** One `events.py` per owning context.
- **New in the governance domain:**
  - a `Fingerprint` value object and the fingerprint functions, with byte-identical output;
  - `BreakdownReadiness`;
  - `ApprovalPolicy`, compared on the enum, not the string;
  - `BreakdownReviewPolicy`;
  - `ReviewEvidence` as a value object;
  - `BreakdownReview.refresh()` and a carry-forward method replacing `breakdown_review.py:543-571`.

## Application Use Cases

- **Moves.** All 72 use-case modules move to their context, following `context-map.md`. The cross-context orchestrators go to `workflows/`.
- **Dissolved.** `InvalidateDerivedArtifacts` and `InvalidateApprovalWorkflow` become handlers.
- **Publish instead of call.** The call sites listed in ADR-0103 *Context* point 2 publish events instead of calling them.

## Ports

- New: `DomainEventPublisher`, `TransactionManagerPort.in_unit_of_work()`, `ScreeningRequestPort` (owned by requirements) and `CandidateReviewPort` (owned by breakdown).
- Existing ports move with their owning context. Every other port keeps its signature.

## Adapters

- **Event infrastructure.** `InProcessEventDispatcher` is pure Python. The PostgreSQL and in-memory transaction managers implement `in_unit_of_work()`.
- **Repositories and payload codecs** move to their context's `infrastructure/`.
- **What stays.** `PostgresStore`, migrations, settings and LLM transport stay in the shared `infrastructure/`.
- **Composition.** The builders are renamed one-to-one to the contexts, and `composition/events.py` is added.

## API

None. This is a behaviour-preserving refactor, and the routes and schemas do not move. `tests/unit/test_openapi_snapshot.py` must stay unchanged in every PR.

## UI

None. This is a behaviour-preserving backend refactor: the ROADMAP entry names no UI, and the owner agreed on 2026-10-07 to an architecture-only change. See *Dropped from this slice*.

## Business Rules

The refactor must keep each of these rules exactly as it is today:
- **ADR-0004.** A Requirement revision deletes the analysis and supersedes its questions. Epic, Features and Stories are flagged stale and never destroyed.
- **ADR-0021.** Approvals bind to the fingerprint of the exact content, and any change resets the review workflow. Fingerprint output is unchanged byte for byte.
- **ADR-0070.** One unit of work and advisory lock per Requirement. Handlers run inside it and never inside `external_call`.
- **AGENTS.md §8.** Regeneration never silently destroys human edits.

## Migration Sequence

Each PR is independently mergeable and behaviour-preserving, and is green on all five quality gates.
Moves are made with `git mv`, and the import rewrite goes in a commit listed in
`.git-blame-ignore-revs`. When the moved files change only in their imports, the move and the
rewrite share one commit (from PR 3 on). Git still records the files as renames, and every commit
stays green. A move that also edits code keeps a separate move-only commit.

| PR | Content | Why at this point |
|---|---|---|
| 1 | **Characterisation tests.** Golden ADR-0021 fingerprints for representative artifacts and breakdowns; golden payload JSON for every codec in `infrastructure/persistence/*_payloads.py`; golden expected-context tokens; an invalidation-order test recording today's side-effect order for each trigger. Also adds `.git-blame-ignore-revs` and a script that reports import edges between the candidate contexts | Later PRs prove they preserve behaviour against these. The dependency report confirms the order in ADR-0103 §2 before any move |
| 2 | **Make `domain/shared` a leaf** (ADR-0103 Amendment 1). Move `RequirementId` (`domain/shared/identifiers.py`), the actor types re-exported from `smb_kernel` (`actors.py`), `PublishedReference` and `normalize_search` (`citation.py`), and `SourceLineage` and `merge_lineage` (`lineage.py`) into `domain/shared`, and rewrite every importer. Move the `to_payload`/`from_payload` of `ReferenceDocumentState` and `HistoricRequirementState` into `infrastructure/persistence/knowledge_payloads.py`, with byte-identical output, behind a `KnowledgeStateDecoderPort` for the two event-feed use cases. Rename the architecture `InvalidKnowledgeError` to `InvalidRelationshipKindError` rather than merging it: a merge would move knowledge errors onto another public error code | It is the smallest change that makes the shared kernel extractable |
| 3 | **Create the shared kernel.** Rename `domain/shared` to `shared_kernel/` and add the `shared_kernel_pure` contract | Every later move depends on it |
| 4 | **Event infrastructure.** Add the publisher, dispatcher, `in_unit_of_work()` and `composition/events.py`. `InvalidateDerivedArtifacts` and `InvalidateApprovalWorkflow` become thin facades that publish events, with handlers holding their former bodies. Add the handler-order test | The mechanism changes while the existing invalidation tests stay green unchanged |
| 5 | **Publish directly.** Call sites publish events directly; delete both invalidation classes; replace the `make_invalidation` fixture in `tests/conftest.py` with an event-publisher fixture. Add `ScreeningRequestPort` and `CandidateReviewPort` | Removes every dependency from upstream to downstream contexts |
| 6 | **Governance into the domain** (ADR-0103 §4) | The golden fingerprints from PR 1 guard it |
| 7 | Move `identity` | Leaf context |
| 8 | Move `jobs` | Leaf context |
| 9 | Move `requirements` (intake + source documents) | Upstream of everything else |
| 10 | Move `analysis` | |
| 11 | Move `breakdown`, with its own `BreakdownContextPort` (F2) | |
| 11b | The per-context LLM adapters (deferred from PR 10) | Needs both analysis and breakdown moved: the shared candidate mappers held both |
| 12 | Move `governance` | |
| 13 | Move `reporting` | |
| 14 | Move `workflows` | |
| 15a | Move `references`. The ACL decodes knowledge-portal events into typed state, which replaces PR 2's `KnowledgeStateDecoderPort`, and takes over `HistoricPassage.from_entry` and `HistoricWorkItem.from_entry`. Also splits the analysis half of `reference_currency` (`stale_analysis`, `stale_proposals`) into analysis behind a references currency port that keeps today's lock order (deferred from PR 10) | After Knowledge Center E2 merges, because E2 is the most active area |
| 15b | Move `knowledge` (screening) | After 15a |
| 16 | **Finish.** Delete every migration shim; enable `contexts_layered` and `published_surface` without exceptions beyond those ADR-0103 records; remove the empty `domain/` and `application/use_cases/`; retire the AGENTS.md §19 debt row. Done 2026-10-08; the ACL consolidation deferred from PR 15a became a follow-up | Locks the boundaries in |

`references` and `knowledge` sit in the middle of the dependency order but move last, which is safe for two reasons:
- **Their contracts follow the move.** Contracts are enabled per context as it moves, so until PRs 15a and 15b they are checked only by the existing layer contracts.
- **No moved context reaches into them.** Contexts moved earlier reach them only through their existing ports, which stay importable through shims.

Each of PRs 7–15b does four things:
1. moves the context's domain, use cases, ports and adapters;
2. moves its tests to `tests/unit/<context>/`;
3. renames its composition builder;
4. enables its `context_internal_layers` and `published_surface` entries.

## PR 1 — Characterisation baseline (2026-10-07)

### Delivered

**Golden values.** `tests/characterisation/` holds fixed sample aggregates (`samples.py`) and the
values computed from them (`cases.py`), compared byte for byte against `golden/`.

| Golden | What it pins | Where it breaks if changed |
|---|---|---|
| `golden/payloads/*.json` (20 files) | Every public codec in `infrastructure/persistence/*_payloads.py`, `requirement_snapshot.py` and `activity_codec.py`, plus the two codecs still in the domain (`ReferenceDocumentState`, `HistoricRequirementState`) | Stored JSONB rows |
| `golden/fingerprints.json` | `artifact_fingerprint` for generated, approved and stale Epics, Features and Stories; `breakdown_fingerprint`; `evidence_fingerprint` | Every recorded approval (ADR-0021) |
| `golden/context_tokens.json` | The analysis, Epic, Feature, Stories and Story expected-context tokens for a full breakdown | Tokens clients already hold |
| `golden/review_policy_build.json` | The review `BreakdownReviewPolicy` builds from the sample evidence (10 flags, 3 risks, 4 recommendations) | Review flags when PR 6 moves the policy |

**Checks on every payload.** Each golden payload must:
- decode to its sample;
- re-encode unchanged.

So a row written before the migration still loads, and a load-then-save leaves it as it was. A
further test fails if a golden file exists that nothing compares.

**Rewriting the goldens is a decision, not a fix.** It is done with
`python -m tests.characterisation.golden`, and only with a reviewed reason.

**Invalidation order.** `tests/characterisation/test_invalidation_order.py` records today's write
sequence for each trigger, using recording in-memory repositories:
- *requirement changed:* review reset → analysis deleted → open question superseded → Epic
  stale → each Feature's Stories, then the Feature;
- *Epic changed* and *Feature changed:* their cascades, in the same pattern;
- *the reset alone:* the review write only.

An already-stale artifact keeps its first reason and is still written. PR 4 and PR 5 keep these
sequences.

**Other files.**
- `.git-blame-ignore-revs`: empty until the first move PR.
- `scripts/context_dependency_report.py`: classifies every domain and application module into
  its context per `context-map.md`, and lists each import that runs against the order in
  ADR-0103 §2.

### PR 1 findings: the dependency report

`python scripts/context_dependency_report.py` classifies all 185 domain and application modules.
Contexts cross in 79 pairs, and 30 of those pairs run against the order. Some were expected and
are already planned:

| Crossing | Imports | Planned in |
|---|---|---|
| `shared_kernel` → `identity`, `requirements`, `knowledge` (`approval.py` and `lineage.py` import `ActorSnapshot`, document errors and `PublishedReference`) | 4 | PR 2. `SourceLineage` carries `PublishedReference`, so that citation type moves into the shared kernel too |
| `RequirementId` and `ActorSnapshot` used from `identity`, `jobs` and `transaction_manager` | most of `identity` → `requirements` and `jobs` → `identity`/`requirements` | PR 2 (both move into the shared kernel) |
| `breakdown` → `governance` (invalidation, `approval_policy`, `approval_workflow`, review policy) | 12 | PRs 4–6 |
| `requirements` → `governance` (invalidation) | 2 | PRs 4–5 |
| `requirements` → `knowledge` (screen scheduler) | 2 | PR 5 (`ScreeningRequestPort`) |

The rest were **not covered by the accepted context map**. The owner decided all eight on
2026-10-07, as proposed below, and ADR-0103 Amendment 1 records them. Each module moves in the
PR of its target context:

| # | Crossing | Imports | Proposed resolution |
|---|---|---|---|
| F1 | `knowledge` ↔ `analysis` | 14 one way, 13 the other | Split `knowledge` in two. **`references`**, upstream of `analysis`, holds the ACL to knowledge-portal, reference grounding, the catalogue, the historic corpus and embeddings. **`knowledge`**, downstream of `analysis`, holds requirement screening, findings, answer suggestions, prior art and source impact. `analysis`'s confirmation gate on the screen becomes a port that `analysis` owns |
| F2 | `analysis`, `breakdown` and `jobs` → `workflows` (`generation_context`) | 6 | Callers depend on an `ExpectedContextPort` in the shared `application/`. `GenerationContextTokens` implements it in `workflows/`, wired in the composition root |
| F3 | `jobs` → `identity`, `requirements`, `knowledge`, `analysis`, `breakdown`, `workflows` | 23 | `ai_job_scheduling` and `ai_jobs` know every job kind and the access service, so they move to `workflows/` beside `ai_job_execution`. `jobs` keeps the `AiJob` aggregate, leasing, notifications, retention and the provider rate |
| F4 | `identity` → `requirements`, `analysis`, `jobs` (`identity_access`) | 8 | `identity` publishes a `RequirementAccessPort`. The requirement-scoped implementation (`RequirementAccessService`), which reads Requirements, drafts, question assignees and job context, moves to `workflows/`. Callers keep depending on `identity` |
| F5 | shared `application/errors.py` and `application/public_errors.py` → every context's domain errors | 20 | `public_errors` is the client-facing error catalogue, so it moves beside `interfaces/api/error_handlers.py`. Errors in `application/errors.py` that belong to one context move into that context |
| F6 | `requirements` → `analysis` (`documents`, `source_lineage`), `requirements` → `reporting` (`requirement_impact`) | 5 | `source_lineage` and `requirement_impact` assemble views across contexts, so they move to `workflows/`. The `documents` → `requirement_analyzer` port edge is reviewed in PR 2 |
| F7 | `knowledge` → `governance` (`knowledge_handoff` reads the export) | 4 | `knowledge_handoff` moves to `governance`. It publishes the approved backlog through the knowledge ACL port |
| F8 | `knowledge` → `breakdown` (`architecture_knowledge` port returns `ArchitectureImpact`) | 1 | The port returns knowledge's own catalogue-match type, and `breakdown` maps it to its impact value object. Resolved in the knowledge move |

F1, F3 and F4 change which context owns code, so they amend `context-map.md`. F2 and F5–F8 move
individual modules within the accepted design. The report now classifies every module by its
target context, so what it lists is the work still to do.

## PR 2 — `domain/shared` is a leaf (2026-10-07)

### Delivered

`domain/shared` imports nothing from another `smb_requirement_agent.domain` package. Its only
outside imports are the pure kernel modules `smb_kernel.identity.actor` and
`smb_kernel.documents.model`.

**New shared modules:**

| Module | Holds | Was in |
|---|---|---|
| `identifiers.py` | `RequirementId` | `domain/requirement/value_objects.py` |
| `actors.py` | `ActorId`, `ActorProfile`, `ActorSnapshot` (re-exported from `smb_kernel`) | re-exported by `domain/identity/entities.py` |
| `citation.py` | `PublishedReference`, `normalize_search` | `domain/document/reference.py` |
| `lineage.py` | `SourceLineage`, `merge_lineage` | `domain/document/lineage.py` (which keeps `ImpactDecision`) |

**Error behaviour.**
- A blank `RequirementId` now raises `InvalidRequirementIdError`, which lives in
  `domain/shared/errors.py`. It is not a `ValueError`, just like the error it replaces.
  - Its catalogue entry gives clients the same public error as before: code
    `invalid_requirement_context`, category invalid input, status 422, and the same message.
  - `test_blank_requirement_id_keeps_its_public_error` pins this.
- `PublishedReference` and `SourceLineage` still raise the kernel's `InvalidDocumentError`.
- The architecture `InvalidKnowledgeError` is renamed `InvalidRelationshipKindError` and keeps
  its own public code. Merging it with the knowledge error instead would have moved every
  knowledge error onto the earlier `invalid_architecture_knowledge` catalogue entry.

**Codecs.**
- The `ReferenceDocumentState` and `HistoricRequirementState` codecs moved, unchanged, to
  `infrastructure/persistence/knowledge_payloads.py`.
- `ProjectKnowledgeEvents` and `ProjectHistoricRequirements` decode through
  `KnowledgeStateDecoderPort`, which `PayloadKnowledgeStateDecoder` implements and the composition
  root wires.
- PR 15a replaces that port with typed events decoded in the ACL. It also moves
  `HistoricPassage.from_entry` and `HistoricWorkItem.from_entry`.

**Three commits.**
1. The new modules, plus temporary re-export shims at the old paths, so the commit is green on
   its own.
2. A mechanical rewrite of 325 import statements in 232 files, by a one-off AST script and
   ruff's import sorting. It also removes the shims. This commit is in `.git-blame-ignore-revs`.
3. This record.

### Dependency report

| | Before PR 2 (target mapping) | After PR 2 |
|---|---|---|
| Classified modules | 185 | 189 (the four new shared modules) |
| Crossing pairs | 90 | 88 |
| Pairs against the order | 26 | 22 |

**Gone:**
- every `shared_kernel → *` crossing;
- `identity → requirements` and `jobs → requirements`, which were `RequirementId`;
- four of the five `jobs → identity` imports, which were the actor types.

**Left:** the expected PR 4–6 crossings (breakdown and requirements into governance), and the
F1–F8 moves that happen in their contexts' PRs.

### Validation evidence (PR 2, local)

- `pytest` — exit 0 after the shared-modules commit and again after the import rewrite. The PR 1
  goldens are unchanged: no file under `tests/characterisation/golden/` is modified.
- `ruff check .` and `ruff format --check .` — clean.
- `mypy src tests` — no issues in 558 source files. Strict mode (`no_implicit_reexport`) rejects
  any import left on an old path.
- `lint-imports` — 9 contracts kept, 0 broken.
- **Old paths are gone:** `grep` finds no import of a moved name from its old module in `src/` or
  `tests/`.

## PR 3 — The `shared_kernel` package (2026-10-07)

### Delivered

- **The package.** `src/smb_requirement_agent/domain/shared` is now
  `src/smb_requirement_agent/shared_kernel`, ADR-0103's home for the shared kernel.
  - 11 modules are recorded as renames.
  - 440 import lines in 257 files point at the new package.
  - Move and rewrite are one commit, listed in `.git-blame-ignore-revs`.
  - No shim stays at `domain/shared`, because no in-flight branch imports it.
- **A new `.importlinter` contract, `shared_kernel_pure`.** The kernel imports nothing from
  `domain`, `application`, `infrastructure` or `interfaces`.
- **Existing contracts cover the kernel.** `domain_independence`,
  `domain_framework_independence` and `kernel_contracts_only_inward` now include
  `smb_requirement_agent.shared_kernel`, so the domain rules hold there too. AGENTS.md §4.1 says
  so.
- **The dependency report** classifies `shared_kernel.*` directly. Its numbers are unchanged:
  189 modules, 88 crossing pairs, 22 against the order, and none from `shared_kernel`.

### Validation evidence (PR 3, local)

- `pytest` — exit 0. No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .` — clean.
- `mypy src tests` — no issues in 558 source files.
- `lint-imports` — 10 contracts kept, 0 broken.
- **The new contract catches a violation:**
  - adding `from smb_requirement_agent.domain.requirement.errors import RequirementError` to
    `shared_kernel/errors.py` made `lint-imports` report `shared_kernel_pure` BROKEN (9 kept,
    1 broken);
  - reverting it brought back 10 kept, 0 broken.
- **Old path is gone:** `grep -rn "domain\.shared" src tests scripts --include=*.py` finds
  nothing.

## PR 4 — In-process domain events (2026-10-07)

### Delivered

- **Events.**
  - `shared_kernel/events.py` defines `DomainEvent`, which carries `requirement_id` and nothing
    but identities.
  - The concrete events live in the domain package that owns each one:
    - `domain/requirement/events.py`: `RequirementRevised`;
    - `domain/epic/events.py`: `EpicChanged` (`epic_id`);
    - `domain/feature/events.py`: `FeatureChanged` (`feature_id`).
  - **Dropped:** ADR-0103 §3 gave `RequirementRevised` a `cause`. No handler reads it, so it was
    left out (AGENTS.md §16) and is added if a consumer ever needs it.
- **Dispatch.**
  - `application/ports/domain_events.py` defines `DomainEventPublisher`.
  - `application/events.py` defines `InProcessEventDispatcher`. It matches the exact event type
    and runs handlers synchronously, in subscription order. An exception propagates, so the
    unit of work rolls back.
  - It raises `RuntimeError` outside a unit of work or during `external_call()`, through the
    new `TransactionManagerPort.in_unit_of_work()`. That method is implemented by `PostgresStore`,
    `InMemoryTransactionManager` and the unit-test stub.
  - Every existing call site already runs inside `transaction()`, so the check changes nothing
    at runtime.
- **Handlers.** Each holds the body it replaced, verbatim:
  - `DiscardAnalysis` (analysis): delete the analysis, then supersede its questions;
  - `MarkBacklogStale` (breakdown): the Epic, then each Feature's Stories, then the Feature;
  - `InvalidateApprovalWorkflow.on_change` (governance).
- **Subscriptions.** `interfaces/api/composition/events.py` is the only place they are made:
  - `RequirementRevised`: approval reset → discard analysis → backlog stale;
  - `EpicChanged`: approval reset → Features and Stories stale;
  - `FeatureChanged`: approval reset → Stories stale.
- **Facade.** `InvalidateDerivedArtifacts` now only publishes. Its eight call sites are
  unchanged; PR 5 has them publish directly and removes the facade.
- **Wiring.** The container builds the dispatcher on the persistence transaction manager. The
  `make_invalidation` fixture wires handlers through the same `subscribe_invalidation_handlers`.

### Tests

- `tests/characterisation/test_invalidation_order.py` now runs through the dispatcher inside an
  in-memory unit of work. Its expected write sequences have not changed since PR 1.
- New `tests/unit/test_domain_events.py`: subscription order; exact-type match; no
  subscribers; the refusal outside a unit of work and during an external call; a failing
  handler rolling back an earlier handler's write.
- New `tests/architecture/test_context_boundaries.py`: `.subscribe(` only in
  `composition/events.py`, and `InProcessEventDispatcher(` only in the composition root.
- **Probes,** each reverted:

  | Probe | Result |
  |---|---|
  | A stray `.subscribe(` in a use case | The boundary test fails |
  | Swapping the analysis and backlog handlers | The order test fails |
  | Removing the guard | The dispatcher tests fail |

### Validation evidence (PR 4, local)

- `pytest` — exit 0. No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .` — clean.
- `mypy src tests` — no issues in 569 source files.
- `lint-imports` — 10 contracts kept, 0 broken.
- **Dependency report** — 197 of 197 modules classified, 88 crossing pairs, 22 against the order,
  as before.
  - The two `requirements → governance` imports remain: they are the facade, which PR 5 removes.

## PR 5 — Use cases publish events; the invalidation classes go (2026-10-07)

### Delivered

- **New events, each published where the old direct call ran:**
  - `FeaturesReplaced` (`epic_id`), by `GenerateFeatures`;
  - `StoriesChanged` (`feature_id`), by `GenerateStories`, `EditStory`, `SplitStory`,
    `MergeStories`, `RegenerateStory` (one or all) and `StoryChangeProposals._apply`;
  - `ArchitectureImpactChanged`, by `MapBreakdownArchitecture`.

  Each is subscribed to the review reset only.
- **Existing events, now published by the use cases themselves:**
  - `UpdateRequirement` and the four document commands publish `RequirementRevised`;
  - `GenerateEpic` and `EditEpic` publish `EpicChanged`;
  - `EditFeature` publishes `FeatureChanged`.
- **Deleted:** `InvalidateDerivedArtifacts` and `InvalidateApprovalWorkflow`.
  - `ResetApprovalWorkflow.on_change` is the governance handler, with the same body.
  - `subscribe_domain_event_handlers` in `composition/events.py` subscribes all six events.
  - The builders and the container pass one `DomainEventPublisher`.
  - The `make_event_publisher` fixture replaces `make_invalidation`.
- **`ScreeningRequestPort`** (requirements, `application/ports/screening_requests.py`):
  `CreateOwnedRequirement`, `PromoteOwnedRequirementDraft` and `UpdateRequirementWithImpact` ask
  for a screen through it. Knowledge's scheduler still satisfies it.
- **`CandidateReviewPort`** (breakdown, `application/ports/candidate_review.py`):
  - `GenerationChecks` critiques unsaved Feature candidates and refreshes the saved review through
    it. It no longer imports governance's review use cases, evidence or policy.
  - `GovernanceCandidateReview`, in `breakdown_review.py`, implements it with the same policy
    call and feedback order. `tests/unit/test_candidate_review.py` pins that against the
    policy's own output.

### Unpinned ordering

Within one unit of work, the review reset runs before `GenerationChecks.save` refreshes the review.
That keeps review version numbers what they were. A probe moved `StoriesChanged` after the refresh
in `GenerateStories`, and the unit suite still passed, so no test pins this order today.

The code keeps the order, because every publish sits where the old call ran. A test for it is
left to PR 6, which moves the review refresh into the governance domain.

### Deferred

- **`analysis` → `knowledge` (two imports).** `analysis_collaboration`'s screen scheduler and the
  suggestion ports become analysis-owned ports when `analysis` moves (PR 10, Amendment 1 F1).
- **`requirements` → `knowledge` (one import).** The `source_dependencies` port uses
  `ImpactDecision` (source impact). It is placed when `source_lineage` and `source_impact` move
  (PR 14 and PR 15b).
- **`breakdown` → `governance` (two imports).** `feature_review`'s `ApproveFeature` still imports
  `approval_policy` and `approval_workflow`. It moves to governance in PR 12.

### Dependency report

| | After PR 4 | After PR 5 |
|---|---|---|
| Classified modules | 197 | 200 |
| Crossing pairs | 88 | 87 |
| Pairs against the order | 22 | 21 |

- `requirements → governance` is gone.
- `breakdown → governance` falls from 12 imports to 2.
- `requirements → knowledge` falls from 2 to 1.

### Validation evidence (PR 5, local)

- `pytest` — exit 0 after each code commit. No file under `tests/characterisation/golden/`
  changed.
- The write-order test's expected sequences are unchanged.
- `ruff check .` and `ruff format --check .` — clean.
- `mypy src tests` — no issues in 573 source files.
- `lint-imports` — 10 contracts kept, 0 broken.
- `grep -rn "InvalidateDerivedArtifacts\|InvalidateApprovalWorkflow\|make_invalidation" src tests`
  finds only the write-order test's docstring, which names the classes it replaced.

## PR 6 — Governance rules in the domain (2026-10-07)

### Delivered

**Moved verbatim into the governance domain (`domain/review/`):**

| New module | Holds | Was in |
|---|---|---|
| `fingerprints.py` | `artifact_fingerprint`, `breakdown_fingerprint` | `approval_policy.py` |
| `evidence.py` | `ReviewEvidence`, `evidence_fingerprint` | `breakdown_review_evidence.py` |
| `policy.py` | `BreakdownReviewPolicy`, `REVIEW_RULESET_VERSION`, `ApprovalPolicy` | `breakdown_review_policy.py`, `approval_policy.py` |
| `readiness.py` | `ArtifactApprovalState`, `artifact_states`, `readiness_reasons`, `approval_subject` | private helpers of `approval_workflow.py` |

- `ApprovalPolicy`'s blocker count now compares `FlagSeverity.BLOCKING` rather than the string
  `"blocking"`. The two are equivalent for the `StrEnum`.
- `readiness_reasons` gives the same reasons in the same order as before.

**Two pure dependencies moved into the breakdown domain (`domain/story/quality.py`):**
- `StoryQualityEvidence`. Its field names are unchanged, so its `asdict` (and the evidence
  fingerprint built from it) is identical.
- `spidr_recommendations`. `SuggestStorySplit.for_assessment` delegates to it, so its callers are
  untouched.

**New `BreakdownReview` behaviour.** Nothing outside the aggregate rebuilds it with `replace()`
any more:
- `effective_status(subject, evidence_fingerprint)` replaces the recalculation in
  `GetApprovalWorkflow.build`;
- `carry_forward_from(existing)` replaces `_carry_forward_decisions`;
- `with_knowledge_version(version)` replaces the two `replace(..., knowledge_version=...)` calls.

**Imports.** 43 import statements in 34 files were rewritten. The three application modules are
deleted, and the rewrite commit is in `.git-blame-ignore-revs`.

`can_submit` and `can_approve` stay in `GetApprovalWorkflow.build`: they combine these domain
answers with the actor's access.

### The ordering left unpinned in PR 5 is now pinned

`test_story_regeneration_resets_the_review_before_refreshing_it` (in
`tests/unit/test_approval_workflow_api.py`):
1. submits the review;
2. regenerates a Feature's Stories with `force`;
3. checks the stored review is `needs_revision`, at its version plus 2.

Swapping the publish and `checks.save` in `RegenerateStory._execute_all` made it fail (+1). The
swap was reverted.

### Deferred

- **The `Fingerprint` value object** named in ADR-0103 §4. Fingerprints stay `str`, because a
  value object would change every approval, route and schema type for no behavioural gain. It is
  worth doing only alongside an approval-model change that needs it.

### Validation evidence (PR 6, local)

- `pytest` — exit 0 after each code commit. No file under `tests/characterisation/golden/`
  changed, which covers the fingerprints, the review policy build and the context tokens.
- The new `tests/unit/test_review_domain_rules.py` passes 9 tests.
- `ruff check .` and `ruff format --check .` — clean.
- `mypy src tests` — no issues in 575 source files.
- `lint-imports` — 10 contracts kept, 0 broken.
- **Dependency report** — 201 of 201 modules, 87 crossing pairs, 21 against the order (unchanged).
  Moving code inside governance changes no crossing. The two `breakdown → governance` imports
  are `ApproveFeature`'s, until PR 12.

## PR 7 — The `identity` package (2026-10-07)

### Delivered

**Moved with `git mv` into `smb_requirement_agent/identity/`.** The moved files changed only in
their imports, so the move and the rewrite share one commit, which is in
`.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| `domain/identity/{entities,errors}.py` | `identity/domain/` |
| `application/ports/{access_repository,actor_directory,identity}.py` | `identity/application/ports/` |
| `infrastructure/identity/fake_identity.py` | `identity/infrastructure/` |
| `infrastructure/persistence/{identity_payloads,in_memory_identity}.py` | `identity/infrastructure/` |

- **PostgreSQL adapters.** `PostgresAccessRepository` and `PostgresActorDirectory` left
  `infrastructure/persistence/postgres_repositories.py` for the new
  `identity/infrastructure/postgres_identity.py`. Their bodies are unchanged; this is a separate
  commit because it edits an existing module.
- **No shims.** Every importer in `src/` and `tests/` was rewritten in the same commit, and
  nothing still imports the old paths.
- **Composition.** `composition/identity.py` already has its target name, so no rename was needed.

**Contracts (13 kept, up from 10).**
- The identity modules join the existing layer, framework and adapter-selection contracts.
- `shared_kernel_pure` now also forbids `smb_requirement_agent.identity`.
- Three new per-context contracts:

| Contract | Checks |
|---|---|
| `identity_internal_layers` | `infrastructure > application > domain` inside `identity` |
| `identity_depends_on_no_other_context` | `identity` imports nothing from `domain`, `application.use_cases` or `interfaces` |
| `identity_published_surface` | `domain`, `application` and `shared_kernel` never import `identity.infrastructure` |

`identity_depends_on_no_other_context` checks direct imports only (`allow_indirect_imports`).
Identity imports only the shared kernel and shared technical modules: `application.errors`, the
payload helpers, `postgres_session` and `postgres_values`. Those still reach unmoved context code,
for example `application.errors` imports context errors until F5. The exemption is removed in PR
16, once those modules have been split.

### Not moved, and why

- **`identity_access`** is the access service that use cases call. It moves to `workflows` in PR
  14 (F4), and `tests/unit/test_identity_access.py` moves with it.
- **`RequirementAccessPort`**, which F4 has `identity` publish, is added with that move in PR 14.
  Until then, nothing would implement or consume it.
- **No `tests/unit/identity/` yet.** No test module covers only the identity package. The identity
  adapters are exercised through the API and persistence tests.

### Dependency report

`scripts/context_dependency_report.py` gained `CONTEXT_PACKAGES`. A moved context's `domain` and
`application` layers are classified whole, and its infrastructure is out of scope, like all other
infrastructure. The per-module `domain.identity` and identity `PORTS` entries are gone.

### Validation evidence (PR 7, local)

- `pytest`: 1789 passed, 75 skipped (PostgreSQL integration tests without a database), exit 0. No
  file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 579 source files.
- `lint-imports`: 13 contracts kept, 0 broken.
- **Dependency report:** 203 of 203 modules classified (the two extra are the new package
  `__init__`s), 87 crossing pairs, 21 against the order (unchanged). One of the 21 is
  `jobs → identity`: `leased_jobs` imports the identity port. That pair was counted before the
  move too, because `jobs` and `identity` are unordered siblings. It is reviewed with PR 8.

## PR 8 — The `jobs` package (2026-10-07)

### Delivered

**Moved with `git mv` into `smb_requirement_agent/jobs/`.** The moved files changed only in their
imports, so the move and the rewrite share one commit, which is in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| `domain/jobs/{entities,errors}.py` | `jobs/domain/` |
| `application/ports/{ai_jobs,notifications}.py` | `jobs/application/ports/` |
| `application/use_cases/{job_execution_context,provider_call_rate,retention}.py` | `jobs/application/use_cases/` |
| `infrastructure/persistence/{in_memory_ai_jobs,postgres_ai_jobs}.py` | `jobs/infrastructure/` |
| `tests/unit/{test_ai_jobs,test_notification_retention,test_provider_call_rate}.py` | `tests/unit/jobs/` |

- **No shims.** Every importer was rewritten in the same commit.
- **Composition.** `composition/jobs.py` already has its target name.

### Placement corrections

The context map put `leased_jobs` and all of `infrastructure/jobs/` in `jobs`. Each of them
imports a context ranked above `jobs`, so they could not live in the most upstream context without
breaking ADR-0103 §2. They are reassigned by what they depend on:

| Module | Depends on | Now belongs to | Moves in |
|---|---|---|---|
| `application/use_cases/leased_jobs.py` | breakdown's `architecture_jobs` port; its only subclass is `ArchitectureMappingJobs` | `breakdown` | PR 11 |
| `infrastructure/jobs/architecture_job_worker.py` | `LeasedJobs`, `ArchitectureJob` | `breakdown` | PR 11 |
| `infrastructure/jobs/polling_worker.py` | `ExecuteAiJob` | `workflows` | PR 14 |
| `infrastructure/jobs/prior_art_gate.py` | `PriorArtBudgetPort` | `knowledge` | PR 15b |
| `infrastructure/jobs/requirement_index_worker.py` | the `requirement_indexing` use case | `knowledge` | PR 15b |

The reassignment only changes where these files go later. They stay at their current paths until
then. `tests/unit/test_polling_worker.py` and `test_worker_process.py` stay with them.

### Contracts (16 kept, up from 13)

- Jobs joins the layer, framework and adapter-selection contracts, and `shared_kernel_pure` now
  also forbids it.
- `jobs_internal_layers`, `jobs_depends_on_no_other_context` and `jobs_published_surface` match
  identity's. The second one checks direct imports only, for the same reason as identity's.
- **Tightened.** ADR-0103 §2 has `identity` and `jobs` as unordered siblings, so each "depends on
  no other context" contract now forbids the sibling. Both contracts now also forbid
  `application.ports`, not only `application.use_cases`. Both contexts already satisfied this.
- **Probe.** An identity import added to `retention` broke `jobs_depends_on_no_other_context`. An
  adapter import added to `ai_jobs` (a use case) broke `jobs_published_surface` and
  `application_independence`. Both probes were reverted.

### Dependency report

206 of 206 modules classified, 84 crossing pairs (87 before), 19 against the order (21 before).
`jobs` now crosses into nothing.

| Pair | Change |
|---|---|
| `jobs → breakdown`, `jobs → identity`, `jobs → interfaces` | gone: they were `leased_jobs`' imports |
| `breakdown → jobs` | gone: `architecture_mapping_jobs → leased_jobs` is now inside breakdown |
| `breakdown → interfaces` | new: `leased_jobs → application.public_errors`, which leaves `application/` with F5 |

### Validation evidence (PR 8, local)

- `pytest`: 1789 passed, 75 skipped (PostgreSQL integration tests without a database), exit 0. No
  file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 585 source files.
- `lint-imports`: 16 contracts kept, 0 broken.

## PR 9 — The `requirements` package (2026-10-07)

### Delivered

**Moved with `git mv` into `smb_requirement_agent/requirements/`.** The move and the import
rewrite share one commit, which is in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| `domain/requirement/*` | `requirements/domain/requirement/` |
| `domain/document/{attachment,entities,errors,ingestion,value_objects}.py` | `requirements/domain/document/` |
| `application/ports/{attachment_ingestions,document_repository,requirement_draft_repository,requirement_repository,screening_requests}.py` | `requirements/application/ports/` |
| `application/use_cases/{create_requirement,update_requirement,get_requirement,requirement_drafts,owned_requirements,requirement_sources,documents,attachment_ingestion}.py` | `requirements/application/use_cases/` |
| `application/document_upload_validation.py` | `requirements/application/` |
| `infrastructure/documents/attachment_worker.py` | `requirements/infrastructure/` |
| `infrastructure/persistence/{attachment_ingestions,document_payloads,in_memory_document_repository,in_memory_requirement_draft_repository,in_memory_requirement_repository,postgres_document_metadata,postgres_document_repository,requirement_snapshot}.py` | `requirements/infrastructure/` |
| 12 requirements-only unit test modules | `tests/unit/requirements/` |

Three changes that are not just moves each have their own commit. Each was checked against the
original text with `diff`.

| Change | Commit |
|---|---|
| `AssembleAnalysisDocuments` and `AnalysisDocumentSelection` move verbatim from `documents.py` to analysis's new `application/use_cases/analysis_documents.py` | before the move |
| `PostgresRequirementRepository` and `PostgresRequirementDraftRepository` move verbatim to `requirements/infrastructure/postgres_requirements.py` | after the move |
| `composition/documents.py` is merged into `composition/requirements.py` | after the move |

- **No shims.** Every importer was rewritten.
- **`domain/document/`** keeps only `lineage.py` (knowledge) and `reference.py` (references) until
  those contexts move.

### Placement corrections

| Module | Context map said | Now | Why |
|---|---|---|---|
| `AssembleAnalysisDocuments` (in `documents.py`) | requirements | analysis | It builds analysis's input types (`AnalysisDocumentContext`, `AnalysisDocumentReference`), and only analysis calls it. These were the two `requirements → analysis` imports |
| `application/ports/source_dependencies.py` and its adapter | requirements | knowledge, moving in PR 15b | It is the reverse evidence index and its `ImpactDecision`s. No requirements code uses it: its users are `source_impact` (knowledge), `dependency_projection` (reporting) and `internal_reads` (workflows). This was the `requirements → knowledge` import |
| `infrastructure/documents/ingestion_loop.py` | requirements | stays shared | It is a generic polling loop that the requirements, references and knowledge workers all run |
| `infrastructure/persistence/backfill_document_blobs.py` | requirements | stays | Operators run it by its module path (`docs/operations/production-readiness-maintenance.md`), so moving it would change their command |

### Contracts (19 kept, up from 16)

- Requirements joins the layer, framework and adapter-selection contracts.
- `requirements_internal_layers` and `requirements_published_surface` match the other contexts'.
- **`requirements_depends_only_upstream`** forbids every unmoved context (`domain`,
  `application.use_cases`, `application.ports`) and `interfaces`. It reports 11 ignored imports:
  - the shared technical ports: `domain_events` (2) and `transaction_manager` (5);
  - **debt:** 4 imports of `application.use_cases.identity_access`, the access service. It stays
    in workflows until PR 14 gives identity `RequirementAccessPort` (F4).
- `identity` and `jobs` now also forbid `requirements`, and their published-surface contracts
  treat requirements as a consumer.
- **Probes**, all reverted:
  - an analysis domain import added to `get_requirement` broke `requirements_depends_only_upstream`;
  - a requirements adapter import added to `analyze_requirement` broke
    `requirements_published_surface` and `application_independence`;
  - a requirements import added to jobs' `retention` broke `jobs_depends_on_no_other_context`.

### Dependency report

211 of 211 modules classified, 82 crossing pairs (84 before), 17 against the order (19 before).

| Pair | Change |
|---|---|
| `requirements → analysis` | gone: `AssembleAnalysisDocuments` is analysis's |
| `requirements → knowledge` | gone: `source_dependencies` is knowledge's |
| `requirements → workflows` | 4 imports remain: `identity_access`, until PR 14 |

### PostgreSQL integration tests now run locally

Earlier PRs skipped the 75 PostgreSQL integration tests: the session had no database. From PR 9
they run against a local PostgreSQL 16 with `pgvector`, through `TEST_DATABASE_URL`. That covers
the adapters PRs 7–9 moved: identity's, the AI job stores, and the requirement and document
repositories.

### Validation evidence (PR 9, local)

- `pytest` with `TEST_DATABASE_URL` set: 1864 passed, 0 skipped, exit 0, after each code commit
  from the PostgreSQL extraction on. Earlier commits ran without the database: 1789 passed, 75
  skipped. No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 594 source files.
- `lint-imports`: 19 contracts kept, 0 broken.

## PR 10 — The `analysis` package (2026-10-07)

### Delivered

Seven commits. The first three remove analysis's wrong-way imports before anything moves.

**1. Analysis owns its screening ports (Amendment 1, F1).**
- **New ports.** `application/ports/knowledge_screening.py`, now
  `analysis/application/ports/knowledge_screening.py`, holds three ports:
  - `AnswerSuggestionRequestPort`;
  - `KnowledgeGatePort`;
  - `SuggestionProvenancePort`.
- **Screening requests.** Analysis asks for a screen through requirements' `ScreeningRequestPort`,
  which is upstream and published. Owning an identical copy would add nothing.
- **Composition.** The composition root passes the same screening objects as before; they satisfy
  the new ports structurally, and mypy checks that.
- **Provenance.** `SuggestionProvenancePort` returns the lineage an answer taken from a suggestion
  records, so analysis no longer handles knowledge's `AnswerSuggestion` or `RelationshipEvidence`.
  The lineage expression moved verbatim from `AnalysisCollaboration` to
  `SuggestClarificationAnswers.suggestion_provenance`. A new test,
  `tests/unit/test_suggestion_provenance.py`, pins both kinds of evidence. Until now only the
  reference-citation half was tested.
- **Deleted.** Analysis was the only user of knowledge's `AnswerSuggestionValidatorPort`, so it is
  gone. Two test doubles renamed their method to match.

**2. Analysis stops importing workflows (F2 and a correction to F6).**
- **`source_lineage` is analysis domain code.** It is pure functions over `RequirementAnalysis`,
  and its importers are analysis or downstream of it. It moved with `git mv` to
  `domain/analysis/lineage.py`, now `analysis/domain/lineage.py`. F6 had sent it to workflows.
- **`ExpectedContextPort`** (`application/ports/expected_context.py`, shared technical) replaces
  the concrete `GenerationContextTokens` in `AnalysisCollaboration`. It has the two methods
  analysis uses; breakdown adds its own in PR 11.

**3. The analysis half of the reference-grounding ports.** These moved verbatim to
`reference_analysis.py`:
- `ReferenceProposerPort` and `ReferenceAnalysisPort`;
- `ReferenceProposalCandidate` and `ReferenceProposalResult`.

**4. The move.** One commit, in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| `domain/analysis/*` (with `lineage.py`) | `analysis/domain/` |
| 12 use cases: `analyze_requirement`, `get_requirement_analysis`, `clarify_requirement_analysis`, `confirm_requirement_analysis`, `analysis_collaboration`, `analysis_mapping`, `analysis_reconciliation`, `evidence_analysis`, `generation_effects`, `reference_grounding`, `discard_analysis`, `analysis_documents` | `analysis/application/use_cases/` |
| 6 ports: `analysis_audit_repository`, `requirement_analysis_repository`, `requirement_analyzer`, `requirement_evidence_analyzer`, `knowledge_screening`, `reference_analysis` | `analysis/application/ports/` |
| `infrastructure/persistence/{analysis_payloads,in_memory_analysis_audit_repository,in_memory_analysis_repository,in_memory_evidence_fragment_cache,postgres_evidence_fragment_cache}.py` | `analysis/infrastructure/` |
| 9 analysis-only unit test modules | `tests/unit/analysis/` |

**5–7. Adapters, composition and contracts.**
- `PostgresAnalysisRepository` and `PostgresAnalysisAuditRepository` moved verbatim to
  `analysis/infrastructure/postgres_analysis.py`, checked with `diff`.
- `composition/analysis_workflow.py` was merged into `composition/analysis.py`.
- The contracts and the dependency report were updated.

No shims.

### Deferred, and why

| Item | Deferred to | Why |
|---|---|---|
| The staleness half of `reference_currency` (`stale_analysis`, `stale_proposals`) and `ReferenceEvidencePort`'s analysis-typed methods | PR 15a | The implementations lock references' publication state and read it inside one transaction. Splitting them needs a references currency port and must keep today's lock order (origins' documents, then proposals'). That belongs with the references move. These are the 5 remaining `references → analysis` imports |
| Per-context LLM adapters (`fake_requirement_analyzer`, `local_requirement_analyzer`, `reference_proposals`, the analysis prompt and schema) | A step after PR 11 | `candidate_mappers.py` and the OpenAI and OpenRouter adapter modules mix analysis and breakdown, so moving one context's half now would leave cross-imports in both directions |
| `identity_access` (2 imports) | PR 14 (F4) | As for requirements |

### Contracts (22 kept, up from 19)

- **New contracts.** `analysis_internal_layers`, `analysis_depends_only_upstream` and
  `analysis_published_surface`.
- **Ignored imports.** The upstream contract reports 10:
  - the shared technical ports `expected_context` (1) and `transaction_manager` (2);
  - references' unmoved ports `embedding` (1) and `reference_grounding` (4), which go in PR 15a;
  - `identity_access` (2), which goes in PR 14.
- **Upstream contexts.** `identity`, `jobs` and `requirements` now forbid `analysis` and treat it
  as a consumer of their published surface.
- **Probes**, all reverted:
  - a knowledge port import added to `get_requirement_analysis` broke
    `analysis_depends_only_upstream`;
  - an analysis adapter import added to `generate_epic` broke `analysis_published_surface` and
    `application_independence`;
  - an analysis import added to `get_requirement` broke `requirements_depends_only_upstream`.

### Dependency report

217 of 217 modules classified, 78 crossing pairs (82 before), 14 against the order (17 before).

| Pair | Change |
|---|---|
| `analysis → knowledge` | gone: F1 |
| `analysis → workflows` | 4 → 2: `generation_context` and `source_lineage` gone; `identity_access` remains |
| `breakdown → workflows` | 15 → 12: `source_lineage` is analysis domain code |
| `knowledge → workflows` | 7 → 6, for the same reason |
| `references → workflows`, `reporting → workflows` | gone, for the same reason |
| `references → analysis` | 5 remain, deferred to PR 15a |

### Validation evidence (PR 10, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1865 passed, 0 skipped, exit 0, after each code commit.
  No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 604 source files.
- `lint-imports`: 22 contracts kept, 0 broken.

## PR 11 — The `breakdown` package (2026-10-07)

### Delivered

Seven commits. The first two remove breakdown's wrong-way imports before anything moves.

**1. `ApproveFeature` is governance's (Amendment 1).**
- It records an approval through `ApprovalRecorder` against the artifact fingerprint. It moved
  verbatim from `feature_review.py` to `application/use_cases/approve_feature.py`, beside
  `approve_epic.py`, checked with `diff`.
- Its lookup base `_FeatureLookup` became the public `FeatureLookup`, which `GetFeatures` and
  `EditFeature` already share.
- This removed breakdown's two governance imports.

**2. Per-context ports for the generation context tokens (F2, refined).**
- Breakdown's token methods take `FeatureId`. The shared `expected_context.py` may import only the
  shared kernel, so it cannot declare them. The design:

| Port | Holds |
|---|---|
| `ExpectedContextPort` (shared) | only the context-agnostic `guard`, now with its `references_for` and `reference_targets` keywords |
| `AnalysisContextPort` (`analysis/application/ports/analysis_context.py`) | extends it with `analysis` |
| `BreakdownContextPort` (now `breakdown/application/ports/breakdown_context.py`) | extends it with `epic`, `features`, `stories` and `input_artifact_ids` |

- `GenerationContextTokens` satisfies both structurally.
- `GenerateEpic`, `GenerateFeatures`, the Story change proposals and the Story workflow now depend
  on `BreakdownContextPort`. This removed breakdown's four `generation_context` imports.

**3. The move.** One commit, in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| `domain/{epic,feature,story}/` | `breakdown/domain/{epic,feature,story}/` |
| `domain/architecture/{__init__,entities,errors,events}.py` (impact) | `breakdown/domain/architecture/` |
| 13 use cases: `generate_epic`, `edit_epic`, `get_epic`, `generate_features`, `feature_review`, `story_workflow`, `story_change_proposals`, `story_quality`, `generation_checks`, `architecture_mapping`, `architecture_mapping_jobs`, `mark_backlog_stale`, `leased_jobs` | `breakdown/application/use_cases/` |
| 13 ports: `architecture_jobs`, `architecture_mapping_stats`, `candidate_review`, `epic_generator`, `epic_repository`, `feature_generator`, `feature_repository`, `generation_guidance`, `story_generator`, `story_quality_evaluator`, `story_quality_repository`, `story_repository`, `breakdown_context` | `breakdown/application/ports/` |
| `infrastructure/persistence/{backlog_payloads,in_memory_epic_repository,in_memory_feature_repository,in_memory_story_repository,in_memory_architecture_jobs,postgres_architecture_jobs,architecture_mapping_stats,story_quality_repository}.py`, `infrastructure/jobs/architecture_job_worker.py` | `breakdown/infrastructure/` |
| 15 breakdown-only unit test modules | `tests/unit/breakdown/` |

- `domain/architecture/` keeps `knowledge.py` (the catalogue, references) until PR 15a.
- **Test fix.** `tests/architecture/test_provider_rate_limit.py` resolved annotations from the old
  `application` package only, and failed when breakdown's use cases left it. It now walks every
  module under an `application` package. That covers the old layer and each moved context's, so
  it checks at least what it did before.

**4–7. Adapters, composition and contracts.**
- `PostgresEpicRepository`, `PostgresFeatureRepository`, `PostgresStoryRepository` and
  `PostgresStoryChangeProposalRepository` moved verbatim to
  `breakdown/infrastructure/postgres_backlog.py`, checked with `diff`.
  `postgres_repositories.py` keeps only governance's `PostgresBreakdownReviewRepository`.
- `composition/architecture.py`, which held only the mapping-job wiring, was merged into
  `composition/breakdown.py`. Catalogue retrieval was already in `knowledge_service.py`.
- The contracts and the report were updated.

No shims.

### Deferred, and why

| Item | Deferred to | Why |
|---|---|---|
| `identity_access` (8 imports) | PR 14 (F4) | As for requirements and analysis |
| `leased_jobs → application.public_errors` | F5 | The public error catalogue is used by application code too (this and `ai_job_execution` record a failure's public code), so moving it beside `error_handlers.py` needs a decision on where failure codes are described. It is not under a forbidden module, so only the report shows it |
| References' unmoved catalogue (`application.ports.architecture_knowledge`, 4 imports; `domain.architecture.knowledge`, 3) | PR 15a | As for analysis's references imports |
| `references → breakdown`: `architecture_knowledge` returns breakdown's impact types | PR 15a (F8) | The port should return its own match type |
| Per-context LLM adapters | The next step | `candidate_mappers.py` and the OpenAI and OpenRouter adapter modules mix analysis and breakdown; both have now moved |

### Contracts (25 kept, up from 22)

- **New contracts.** `breakdown_internal_layers`, `breakdown_depends_only_upstream` and
  `breakdown_published_surface`.
- **Ignored imports.** The upstream contract reports 31:
  - the shared technical ports `domain_events` (7), `expected_context` (1) and
    `transaction_manager` (8);
  - references' `architecture_knowledge` port (4) and `domain.architecture.knowledge` (3), which
    go in PR 15a;
  - `identity_access` (8), which goes in PR 14.
- **Upstream contexts.** Identity, jobs, requirements and analysis now forbid breakdown, and treat
  it as a consumer of their published surface.
- **Probes**, all reverted:
  - a governance import added to `get_epic` broke `breakdown_depends_only_upstream`;
  - a breakdown adapter import added to `export_breakdown` broke `breakdown_published_surface` and
    `application_independence`;
  - a breakdown import added to analysis's `get_requirement_analysis` broke
    `analysis_depends_only_upstream`.

### Dependency report

224 of 224 modules classified, 77 crossing pairs (78 before), 13 against the order (14 before).

| Pair | Change |
|---|---|
| `breakdown → governance` | gone: `ApproveFeature` |
| `breakdown → workflows` | 12 → 8: `generation_context` gone; `identity_access` remains |
| `governance → breakdown` | 35 → 40: `ApproveFeature` now imports breakdown, an allowed direction |

### Validation evidence (PR 11, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1865 passed, 0 skipped, exit 0, after each code commit.
  No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 615 source files.
- `lint-imports`: 25 contracts kept, 0 broken.

## PR 11b — Per-context LLM adapters (2026-10-08)

### Delivered

**1. The candidate mappers split by context.**
- `infrastructure/llm/candidate_mappers.py` held analysis's mappers (lines 68–695) and breakdown's
  Epic, Feature and Story mappers (696–792). No private helper was shared between the halves.
- They split verbatim into `analysis_mappers.py` and `backlog_mappers.py`, checked with `diff`.
  Each keeps only the imports it uses.
- Seven importers were repointed: four local adapters and three test modules.

**2. The move.** One commit, in `.git-blame-ignore-revs`. The layout mirrors the shared one
(`llm/`, `llm/prompts/`, `llm/schemas/`).

| Context | Moved to `<context>/infrastructure/llm/` |
|---|---|
| analysis | `fake_requirement_analyzer`, `local_requirement_analyzer`, `reference_proposals`, `analysis_mappers`, `prompts/analysis_prompt`, `schemas/analysis_schema` |
| breakdown | `fake_` and `local_` `{epic_generator,feature_generator,story_generator,story_quality_evaluator}`, `story_quality_mapping`, `backlog_mappers`, `prompts/{epic,feature,story,story_quality}_prompt`, `prompts/generation_guidance`, `schemas/{epic,feature,story,story_quality}_schema` |

The rewrite covered the dotted `@patch` targets in `test_local_llm_adapters.py`.

**Stays in the shared `infrastructure/llm/`:**

| Module | Why |
|---|---|
| `openai_adapters.py`, `openrouter_adapters.py` | Provider selection and transport: they build every context's adapters |
| `response_sanitizer.py` | Generic text helpers both mapper halves use |
| `requirement_knowledge_adapters.py`, `fake_requirement_knowledge.py`, the knowledge and prior-art prompts and schemas | Knowledge's; they move with it in PR 15b |

**Tests stay in `tests/unit/`.** `test_local_llm_adapters`, `test_openai_*`, `test_story_adapters`
and `test_debug_trace` exercise the adapters through the shared provider modules, and several
cover both contexts in one file.

### Contracts

Still 25 kept. The adapter contracts already named `{analysis,breakdown}.infrastructure`. Two
moved adapters reach references' unmoved ports through existing ignores, so the ignored counts
rose:

| Contract | Ignored imports | New import |
|---|---|---|
| `analysis_depends_only_upstream` | 10 → 11 | `reference_proposals → application.ports.reference_grounding` |
| `breakdown_depends_only_upstream` | 31 → 32 | `prompts/generation_guidance → application.ports.architecture_knowledge` |

The dependency report does not cover infrastructure, so it is unchanged: 224 of 224 modules,
77 pairs, 13 against the order.

### Validation evidence (PR 11b, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1865 passed, 0 skipped, exit 0, after each code commit.
  No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 622 source files.
- `lint-imports`: 25 contracts kept, 0 broken.

## PR 12 — The `governance` package (2026-10-08)

### Delivered

Governance needed no inversion before the move. Its only wrong-way imports are the three
`identity_access` imports owed to PR 14. Everything else points upstream.

**1. The move.** One commit, in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| `domain/review/*`, `domain/revision/*` | `governance/domain/{review,revision}/` |
| 8 use cases: `breakdown_review`, `approval_workflow`, `approve_epic`, `approve_feature`, `revision_history`, `export_breakdown`, `knowledge_handoff` (F7), `reset_approval_workflow` | `governance/application/use_cases/` |
| 3 ports: `backlog_export`, `breakdown_repository`, `breakdown_review_repository` | `governance/application/ports/` |
| `application/exports.py` | `governance/application/exports.py` |
| `infrastructure/persistence/{review_payloads,in_memory_breakdown_review_repository,in_memory_revision_repository,postgres_revisions,revision_tracking}.py` | `governance/infrastructure/` |
| `infrastructure/persistence/postgres_repositories.py`, which by now held only `PostgresBreakdownReviewRepository` | `governance/infrastructure/postgres_breakdown_review.py` |
| `infrastructure/exports/` (the JSON and XLSX exporters) | `governance/infrastructure/exports/` |
| 7 governance-only unit test modules | `tests/unit/governance/` |

- One line changed besides the rewrite. `revision_tracking.py` imported the shared
  `in_memory_transaction` relatively (`from .in_memory_transaction import …`), which broke once
  the file moved. It is now an absolute import.
- No shims.

**2. Composition.** `composition/review.py` became `composition/governance.py`. `build_review` and
`ReviewWiring` keep their names.

**3. Contracts and report.** See below.

### Stays where it is

| Module | Why |
|---|---|
| `application/ports/knowledge_handoff.py`, `infrastructure/persistence/backlog_handoffs.py` | The approved-backlog outbox and inbox are references' ports, moving in PR 15a. Governance writes to them through the port |
| `infrastructure/persistence/postgres_snapshots.py` | Worklist snapshots, reporting (PR 13) |
| `test_review_actions{,_api}` | They test the shared kernel's `actions` across contexts |

### Observation, not fixed here

`breakdown_review` holds analysis's `AnalysisCollaboration` (`breakdown_review.py:516`) and
breakdown's `ValidateStory` and `story_set_fingerprint`. These are upstream use cases, not ports.
The direction is legal and the published-surface contracts forbid only adapters. It is a
candidate for ports when PR 16 tightens the published surfaces.

### Contracts (28 kept, up from 25)

- **New contracts.** `governance_internal_layers`, `governance_depends_only_upstream` and
  `governance_published_surface`.
- **Ignored imports.** The upstream contract reports 11:
  - `transaction_manager` (4);
  - references' `architecture_knowledge` (1), `knowledge_handoff` (2) and `reference_grounding`
    (1), which go in PR 15a;
  - `identity_access` (3), which goes in PR 14.
- **Upstream contexts.** Every earlier context's "depends only upstream" contract now forbids
  `governance`.
- **Published surfaces, refined.** A context's sources are now its `domain` and `application`
  layers, not the whole package.
  - Why: adding governance as a consumer broke four of them. `postgres_revisions` snapshots the
    whole Requirement tree into a revision, so it reuses the identity, requirements, analysis and
    breakdown payload codecs.
  - The contracts exist to stop domain and application code from reaching adapters.
    Infrastructure reusing another context's codecs is allowed and now recorded in the contract
    comments.
  - A probe confirmed the narrowed contracts still catch governance *application* code importing
    analysis's adapters.
- **Probes**, all reverted:
  - a reporting use case (`requirement_worklist`) imported from `revision_history` broke
    `governance_depends_only_upstream` and `governance_internal_layers`;
  - a governance adapter imported from an unmoved use case broke `governance_published_surface`
    and `application_independence`;
  - a governance import in breakdown's `get_epic` broke `breakdown_depends_only_upstream`;
  - an analysis adapter imported from `revision_history` broke `analysis_published_surface`.

### Dependency report

228 of 228 modules classified, 77 crossing pairs, 13 against the order. Unchanged: moving
governance changes no context pair.

### Validation evidence (PR 12, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1865 passed, 0 skipped, exit 0, after each code commit.
  No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 629 source files.
- `lint-imports`: 28 contracts kept, 0 broken.

## PR 13 — The `reporting` package (2026-10-08)

### Delivered

Reporting is the read side: the Requirement worklist, activity, saved views and the dependency
pages. It is downstream of every context but workflows, so it had no wrong-way imports to remove.

**1. The move.** One commit, in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| 4 use cases: `requirement_worklist`, `activity_reporting`, `saved_views`, `dependency_projection` | `reporting/application/use_cases/` |
| 3 ports: `activity`, `requirement_worklist`, `saved_views` | `reporting/application/ports/` |
| `infrastructure/persistence/{activity_projection,activity_codec,postgres_activity,postgres_activity_reader,postgres_activity_sources,postgres_worklist,in_memory_worklist,postgres_snapshots,in_memory_saved_views,postgres_saved_views}.py` | `reporting/infrastructure/` |
| 5 reporting-only unit test modules | `tests/unit/reporting/` |

No code changes and no shims.
- **No domain layer.** Reporting reads projections that other contexts' changes maintain. Its
  internal-layers contract therefore has two layers.
- **No composition builder.** The context map gives reporting none. Its use cases are built in
  `container.py` and the technical builders (`persistence.py`, `projections.py`, `operations.py`).
  A `reporting.py` builder would only move those lines, so it is left for PR 16.

**2. Contracts and report.** See below.

### Contracts (31 kept, up from 28)

- **New contracts.**
  - `reporting_internal_layers`: infrastructure > application.
  - `reporting_depends_only_upstream`: 6 ignored imports, all knowledge's unmoved modules, which
    go in PR 15b. They are `application.ports.requirement_knowledge` (3),
    `application.ports.source_dependencies` (1) and `domain.knowledge.entities` (2).
  - `reporting_published_surface`.
- **Upstream contexts.** Every earlier context now forbids `reporting`, and lists reporting's
  application layer as a consumer of its published surface.
- **Probes**, all reverted:
  - a workflows use case imported from `saved_views` broke `reporting_depends_only_upstream`;
  - a reporting adapter imported from a workflows use case broke `reporting_published_surface` and
    `application_independence`;
  - a reporting port imported from governance's `revision_history` broke
    `governance_depends_only_upstream`.

### Dependency report

231 of 231 modules classified, 77 crossing pairs, 13 against the order. No pair changed.

### Validation evidence (PR 13, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1865 passed, 0 skipped, exit 0. No file under
  `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 635 source files.
- `lint-imports`: 31 contracts kept, 0 broken.

## PR 14 — The `workflows` package and the identity access port (2026-10-08)

### Delivered

This PR paid off the access-service debt that every earlier context carried (F4). Two commits came
before the move.

**1. The command fingerprint is jobs'.**
- `command_fingerprint` and `COMMAND_FINGERPRINT_VERSION` are a pure function over the jobs
  vocabulary.
- They moved verbatim, checked with `diff`, from workflows' `ai_jobs` to
  `jobs/application/use_cases/command_fingerprint.py`.
- This removed knowledge's `prior_art → ai_jobs` import.

**2. Contexts authorize through `RequirementAccessPort` (F4).**
- **Identity's port.** Identity publishes `RequirementAccessPort` and `RequirementPermission` in
  `identity/application/ports/requirement_access.py`.
  - The port holds the ten methods other contexts call: `require`,
    `require_requirement_member`, `require_answerer`, `require_owner_of_either`, `mutation`,
    `execute_mutation`, `create_requirement_owner`, `create_draft_owner`, `require_draft_owner`
    and `can_access_draft`.
  - `RequirementPermission` moved verbatim. Its 22 importers were repointed.
- **Knowledge's port.** Knowledge's automatic work also calls `automatic_mutation`, which takes
  jobs' `AiJobOperation`. Identity cannot import jobs, its sibling, so knowledge owns
  `KnowledgeAccessPort` (`application/ports/knowledge_access.py`), extending the port with it.
  This is the same per-context extension pattern as the PR 11 context-token ports.
- **Implementation.** Workflows' `RequirementAccessService` satisfies both ports structurally, and
  mypy checks it at every wiring site.
- **Consumers.** Requirements, analysis, breakdown, governance and knowledge now type their access
  collaborator with a port. That removed all 22 `identity_access` imports outside workflows, and
  the four F4 ignores from the contracts:

| Contract | Ignored imports |
|---|---|
| requirements | 11 → 7 |
| analysis | 11 → 9 |
| breakdown | 32 → 24 |
| governance | 11 → 8 |

**3. The move.** One commit, in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| 8 use cases: `requirement_commands`, `ai_job_execution`, `ai_job_scheduling`, `ai_jobs`, `identity_access`, `generation_context`, `requirement_impact`, `internal_reads` | `workflows/application/use_cases/` |
| `infrastructure/jobs/polling_worker.py` (PR 8 reassignment) | `workflows/infrastructure/` |
| 7 workflows-only unit test modules | `tests/unit/workflows/` |

- **No domain layer.** Workflows orchestrates the other contexts.
- **One test path.** `test_requirement_internal_contract` finds the committed OpenAPI contract
  from its own path, so it now looks one directory further up.

**4. Contracts and report.** See below.

### Contracts (33 kept, up from 31)

- **New contracts.**
  - `workflows_internal_layers`: infrastructure > application.
  - **`nothing_imports_workflows`.** Workflows is downstream of every context, so instead of a
    published surface it has one rule: nothing in `domain`, `application`, `infrastructure`, the
    shared kernel or any context may import it. That includes indirect imports, so it needs no
    exemption. Only delivery and composition use workflows.
- **Probes**, all reverted:
  - an `ai_jobs` import in knowledge's `prior_art` and an `identity_access` import in analysis
    both broke `nothing_imports_workflows`;
  - an `interfaces` import in `internal_reads` broke `application_independence` and the framework
    contracts.

### Dependency report

236 of 236 modules classified, 72 crossing pairs (77 before), 8 against the order (13 before).
- **Gone:** `requirements`, `analysis`, `breakdown`, `governance` and `knowledge → workflows`, the
  last of them its `ai_jobs` import as well.
- **Remaining 8:**
  - `references → analysis`, `references → breakdown`, `references → knowledge`: PR 15a;
  - `technical → analysis`, `technical → breakdown`, `technical → requirements`: context errors
    in `application/errors.py`, F5;
  - `breakdown → interfaces` and `workflows → interfaces`: `public_errors`, F5.

### Validation evidence (PR 14, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1865 passed, 0 skipped, exit 0, after each code commit.
  No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 643 source files.
- `lint-imports`: 33 contracts kept, 0 broken.

## PR 15a — The `references` package (2026-10-08)

### Delivered

Knowledge Center E2 (the historic corpus and prior art) had already merged as #47, the commit
this branch started from, so no merge was needed.

References had three wrong-way pairs. Four commits removed them before the move.

**1. The catalogue content is references' (F8).**
- `SystemReference`, `SystemCapability`, `ArchitectureDependency`, `ArchitectureCitation`,
  `DomainSuggestion`, `ProductContext`, `OfferingDuty`, `JourneyStep`, `JourneyNeighbour` and
  `OrganisationReference` describe the knowledge service's catalogue. Breakdown's
  `ArchitectureImpact` records them as they were at mapping time.
- They moved verbatim, checked with `diff`, to `references/domain/architecture/catalogue.py`.
  `ArchitectureError`, `InvalidArchitectureContentError` and their `_text` helper moved with them.
- Breakdown's architecture `errors.py` is gone. `ArchitectureImpact` keeps its own four-line
  `_text`.
- **The plan changed.** The plan was for the catalogue port to return "its own match type",
  translated in breakdown. Moving the types instead needs no mapping code: breakdown conforms to
  references' published language. The port now returns references' own types.

**2. The screening errors leave the shared knowledge errors.**
- `domain/knowledge/errors.py` keeps `KnowledgeError` and `InvalidKnowledgeError`, which the
  historic corpus and knowledge share. It is now `references/domain/errors.py`.
- The four screening errors moved verbatim to knowledge's `domain/knowledge/screening_errors.py`.
  They still subclass `KnowledgeError`, so the class hierarchy and public codes are unchanged.

**3. `bounded_knowledge_text` is references'** (ADR-0103 Amendment 1). It moved verbatim to
`references/domain/bounded_text.py`. That removed `historic_corpus → requirement_knowledge`.

**4. The reference staleness checks are analysis's.**
- `stale_analysis` and `stale_proposals` moved verbatim from references' `ReferenceCurrency` to
  analysis's `AnalysisReferenceCurrency` (`analysis/application/use_cases/reference_staleness.py`).
  The diff shows two substitutions: they now lock and check through references' new
  `PublicationCurrencyPort` (`lock_documents`, `is_current`), which `ReferenceCurrency` already
  did privately.
- **Lock order.** They still run in one transaction and lock in the same order: an analysis's
  origins, then its proposals'.
- **Ports.** `ReferenceEvidencePort` and `require_analysis_references` moved to analysis's
  `reference_analysis` ports. References keeps `CitationCurrencyPort` (`require_current`), which
  `ReferenceSearchPort` and `CurrentReferences` use.
- **Wiring.** The composition root gives `SourceImpactReview` an `AnalysisReferenceCurrency` over
  the same `ReferenceCurrency`. The release-recovery check now asks source impact.

**5. The move.** One commit, in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| `domain/document/reference.py`, `domain/knowledge/{historic,errors,bounded_text}.py` | `references/domain/` |
| `domain/architecture/{knowledge,catalogue}.py` | `references/domain/architecture/` (the old `domain/architecture/` package is gone) |
| 8 ports: `architecture_knowledge`, `embedding`, `historic_corpus`, `knowledge_events`, `knowledge_handoff`, `knowledge_views`, `reference_grounding`, `reference_publications` | `references/application/ports/` |
| 5 use cases: `historic_corpus`, `knowledge_event_cursor`, `knowledge_views`, `qualify_chunk_tokens`, `reference_currency` | `references/application/use_cases/` |
| `application/{grounding,retrieval}_evaluation.py` | `references/application/` |
| `infrastructure/persistence/{historic_corpus,reference_publications,knowledge_payloads,backlog_handoffs,architecture_release_state}.py`, `infrastructure/knowledge_client.py` (the ACL) | `references/infrastructure/` |
| 6 references-only unit test modules | `tests/unit/references/` |

- **Test fixes.** Two moved tests find committed contract files from their own path, so they now
  look one directory further up. One architecture test imported `historic_corpus` from the ports
  package.
- **Ignores removed.** The contracts' "until PR 15a" ignores for references' modules no longer
  applied, and are gone.
- No shims.

**6. Composition.** `composition/knowledge_service.py` became `composition/references.py`.

### Deferred to PR 16

**The ACL consolidation.**
- **What it is.** Folding references' event decoding (`KnowledgeStateDecoderPort` and
  `PayloadKnowledgeStateDecoder`) and `HistoricPassage.from_entry` / `HistoricWorkItem.from_entry`
  into `knowledge_client`.
- **Why it waits.** With references in one package, the port, its adapter and the client are all
  inside references. So consolidating them changes the event-feed port's shape without improving
  any boundary.

### Contracts (36 kept, up from 33)

- **New contracts.**
  - `references_internal_layers`.
  - `references_depends_only_upstream`: it forbids every unmoved context module, `analysis`,
    `breakdown`, `governance` and `reporting`. It has 2 ignored imports, both of
    `transaction_manager`.
  - `references_published_surface`.
- **Other contracts.** `nothing_imports_workflows` now lists references. Identity, jobs and
  requirements forbid references.
- **Ignored imports fell.** References' modules are no longer under the forbidden packages:

| Contract | Ignored imports |
|---|---|
| analysis | 9 → 4 |
| breakdown | 24 → 16 |
| governance | 8 → 4 |

- **Probes**, all reverted:
  - an analysis import in references' `knowledge_views`, and a knowledge use case imported from
    references' `knowledge_event_cursor`, broke `references_depends_only_upstream`;
  - a references adapter imported from knowledge's `prior_art` broke
    `references_published_surface` and `application_independence`;
  - a references import in requirements' `get_requirement` broke
    `requirements_depends_only_upstream`.

### Dependency report

244 of 244 modules classified, 69 crossing pairs (72 before), 5 against the order (8 before).
- **Gone:** `references → analysis`, `references → breakdown` and `references → knowledge`.
- **Remaining 5:** all F5. Three are context errors in `application/errors.py`
  (`technical → analysis`, `technical → breakdown`, `technical → requirements`). Two are
  `breakdown → interfaces` and `workflows → interfaces`, the public error catalogue.

### Validation evidence (PR 15a, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1865 passed, 0 skipped, exit 0, after each code commit.
  No file under `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 653 source files.
- `lint-imports`: 36 contracts kept, 0 broken.

## PR 15b — The `knowledge` package (2026-10-08)

### Delivered

Knowledge (requirement screening) had no wrong-way imports. It imports only analysis, references,
requirements, identity, jobs, the shared kernel and technical modules. So it needed no inversion,
only the move and its contracts.

**1. The move.** One commit, in `.git-blame-ignore-revs`.

| Was | Now |
|---|---|
| `domain/knowledge/{entities,membership,prior_art,screening_errors}.py`, `domain/document/lineage.py` (`ImpactDecision`) | `knowledge/domain/` |
| 9 use cases: `requirement_knowledge`, `requirement_indexing`, `rebuild_knowledge_index`, `knowledge_portfolio`, `corpus_actions`, `unified_knowledge_search`, `prior_art`, `source_impact`, `answer_suggestions` | `knowledge/application/use_cases/` |
| 9 ports: `knowledge_access`, `source_dependencies`, `corpus_membership`, `corpus_summary`, `knowledge_index_generations`, `knowledge_portfolio`, `prior_art`, `requirement_indexing`, `requirement_knowledge` | `knowledge/application/ports/` |
| `application/prior_art_evaluation.py` | `knowledge/application/` |
| 10 persistence adapters, and `infrastructure/jobs/{prior_art_gate,requirement_index_worker}.py` (PR 8 reassignment) | `knowledge/infrastructure/` |
| `infrastructure/llm/{requirement_knowledge_adapters,fake_requirement_knowledge}.py` and the knowledge and prior-art prompts and schemas | `knowledge/infrastructure/llm/`, mirroring PR 11b |
| 9 knowledge-only unit test modules | `tests/unit/knowledge/` |

- **Gone.** The emptied `domain/knowledge/`, `domain/document/`, `infrastructure/jobs/` and shared
  `infrastructure/llm/{prompts,schemas}/` packages.
- **Hand fixes.**
  - Three package-level imports were repointed by hand: `composition/persistence.py` and two
    tests.
  - `test_prior_art` reads its evaluation fixture from one directory further up.
  - The contracts lost reporting's three "until PR 15b" ignores and the vanished
    `infrastructure.jobs` entry.
- No code changes and no shims.

**2. Contracts and report.** See below.

### What is left outside the contexts

- `domain/__init__.py` and `application/use_cases/__init__.py`: empty packages. The contracts
  still name them, and PR 16 removes both.
- **Shared technical modules:**
  - `application/{errors,events,public_errors}.py`;
  - the four technical ports (`domain_events`, `expected_context`, `external_work`,
    `transaction_manager`);
  - `infrastructure/persistence`'s session, store, migrations and payload helpers;
  - `infrastructure/llm`'s provider selection and sanitizer;
  - `infrastructure/{config,documents/ingestion_loop,text}`.
- **Stays here, as decided earlier:** `moved_knowledge_tables.py`, the operator's drop command,
  and `backfill_document_blobs.py`.

### Contracts (39 kept, up from 36)

- **New contracts.**
  - `knowledge_internal_layers`.
  - `knowledge_depends_only_upstream`: it forbids every unmoved context module, `breakdown`,
    `governance` and `reporting`. It has 6 ignored imports, all of `transaction_manager`.
  - `knowledge_published_surface`.
- **Other contracts.** Identity, jobs, requirements, references and analysis forbid knowledge.
  `nothing_imports_workflows` lists it.
- **Ignored imports.** The only exemptions left in any "depends only upstream" contract are the
  shared technical ports.
- **Probes**, all reverted:
  - a breakdown import in `corpus_actions` broke `knowledge_depends_only_upstream`;
  - a workflows import in `prior_art` broke `nothing_imports_workflows`;
  - a knowledge adapter imported from workflows' `internal_reads` broke
    `knowledge_published_surface` and the application contracts;
  - a knowledge import in analysis broke `analysis_depends_only_upstream`.

### Dependency report

247 of 247 modules classified, 69 crossing pairs, 5 against the order. No pair changed.
- **Report simplified.** Every context is now a package, so the report no longer needs its
  per-module tables for domain, use cases and context ports.
- **The remaining 5 are F5,** for PR 16:
  - context errors in `application/errors.py`: `technical → analysis`, `technical → breakdown` and
    `technical → requirements`;
  - the public error catalogue: `breakdown → interfaces` and `workflows → interfaces`.

### Validation evidence (PR 15b, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1865 passed, 0 skipped, exit 0. No file under
  `tests/characterisation/golden/` changed.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 660 source files.
- `lint-imports`: 39 contracts kept, 0 broken.

## PR 16 — Finish (2026-10-08)

### Delivered

1. **Context errors moved into their contexts (F5).**
   - 51 errors moved verbatim from `application/errors.py` into a new `application/errors.py` in
     each of the nine contexts. The placement rule: an error goes with its base's family, or else
     with the most upstream context that raises it.
   - The shared module keeps the platform-kernel re-exports and `ArtifactVersionConflictError`, and
     imports no context.
2. **References raises its own citation error.**
   - `ReferenceCurrency.require_current` raised analysis's `RequirementAnalysisConflictError`,
     which ran against the dependency order. It now raises `CitationNotCurrentError` with the same
     message.
   - The catalogue maps the new error to `requirement_analysis_conflict` / CONFLICT, so HTTP
     responses and job failure codes are unchanged. A new `test_error_handlers` case pins this.
   - Analysis's `AnalysisReferenceCurrency` translates it back, so analysis's callers still see
     `RequirementAnalysisConflictError`.
   - Knowledge's search and answer suggestions catch it where they caught the analysis error.
   - Five tests that reach references without going through analysis now expect the new error.
3. **The public error catalogue moved into `workflows` (F5, refined).**
   - `application/public_errors.py` → `workflows/application/public_errors.py`; this is a
     move-only commit.
   - Breakdown's `LeasedJobs` takes an injected `FailureCode` instead of importing the catalogue.
     The composition root passes `describe_public_error(exc).code`.
4. **The shared persistence helpers lost their context code.** All moves are verbatim.
   - `shared_payloads`:
     - the Story-quality and architecture-impact codecs moved to
       `breakdown/infrastructure/backlog_codecs.py`;
     - `evidence_payload` moved to `analysis/infrastructure/analysis_payloads.py`.
   - `postgres_values`: the Epic and Feature lookups moved to
     `breakdown/infrastructure/postgres_backlog.py`.
   - `payload_fields`: its three `RequirementContext` helpers had no callers and were deleted.
   - `in_memory_transaction`: `checkpoint()` is typed with a local protocol.
5. **The empty packages and the contract exemptions are gone.**
   - `domain/` and `application/use_cases/` are removed.
   - The context contracts lose every `ignore_imports` and `allow_indirect_imports`.
   - `contexts_layered` and `shared_application_uses_no_context` are added.
6. **A vacuous test was fixed.**
   - **What was wrong.** `test_authorization_placement` scanned only `application/use_cases/`.
     From PR 7 on it checked a shrinking set, and since PR 15b none at all, so its two use-case
     checks passed vacuously.
   - **The fix.** It now scans every context's use cases, and asserts that the access service is
     among them.
7. **The layout checks the spec promised.** `test_context_boundaries` now also checks three
   things:
   - each context has exactly its layer packages;
   - the layer-first packages stay gone;
   - no migration shim exists.

### Contracts (41 kept, up from 39)

- **New:**
  - `contexts_layered`: ADR-0103 §2 as one `layers` contract, with `jobs | identity` as
    independent siblings;
  - `shared_application_uses_no_context`.
- **Exemptions.** No context contract has `ignore_imports` or `allow_indirect_imports`. The three
  that keep `allow_indirect_imports` are the route and dependency-provider contracts, which reach
  adapters through the composition root by design.
- **Probes**, all reverted:
  - an analysis → breakdown import broke `contexts_layered`, `analysis_depends_only_upstream` and
    `knowledge_depends_only_upstream`;
  - a breakdown import in `payload_fields`, which identity uses, broke 7 contracts, including
    `identity_depends_on_no_other_context` (indirect imports are now checked);
  - a context import in `application/errors.py` broke `shared_application_uses_no_context`,
    `contexts_layered` and the identity and jobs contracts;
  - recreating `domain/` failed `test_the_layer_first_packages_stay_gone`.

### Dependency report

256 of 256 modules classified, 53 crossing pairs, **0 against the order** (5 before). Compared
with PR 15b:
- **Gone:**
  - every pair through the old `interfaces` classification of the catalogue;
  - `technical → {analysis, breakdown, requirements}`;
  - `jobs → technical` and `reporting → technical`, which were context errors.
- **New:** `workflows → references`, because the catalogue maps references' errors.

### Smoke flow (acceptance)

With `LLM_PROVIDER=fake`, through the API test client:
1. create the Requirement, analyse and confirm;
2. generate and approve the Epic, the Features and the Stories, then submit and approve the
   breakdown;
3. edit the Requirement, acknowledging the impact.

Results:
- the analysis is gone (404);
- the Epic, both Features and the Stories are kept, each stale with `requirement_changed`;
- the breakdown review is `needs_revision`, and the worklist shows `stale`.

The same script's output is identical on `84e5cfc`, the commit before PR 1. Two outcomes are
unchanged from that commit:
- `GET /approval-workflow` answers 404 `requirement_analysis_not_found` once the analysis is gone;
- the breakdown review still answers 200.

### Validation evidence (PR 16, local, with PostgreSQL)

- `pytest` with `TEST_DATABASE_URL` set: 1870 passed, 0 skipped, exit 0. Three are new.
- **Unchanged files:**
  - `tests/characterisation/golden/` has not changed since PR 1 recorded it (`a0fa37e`);
  - `frontend/openapi.json`, `contracts/` and the migrations have not changed since `84e5cfc`.
- `ruff check .` and `ruff format --check .`: clean.
- `mypy src tests`: no issues in 668 source files.
- `lint-imports`: 41 contracts kept, 0 broken.
- **Verbatim moves.** The 52 classes and 36 functions were compared by AST span against their
  old text, and all match.

## Follow-ups

These were agreed on 2026-10-08 as out of PR 16's scope. Each is a separate change, scheduled
through ROADMAP.md when a slice next touches the area.

- **ACL consolidation** (deferred from PR 15a). This means folding references' event decoding
  (`KnowledgeStateDecoderPort`, `PayloadKnowledgeStateDecoder`) and
  `HistoricPassage.from_entry` / `HistoricWorkItem.from_entry` into `knowledge_client`. It
  improves no boundary, because all of it is already inside `references`.
- **Published surfaces for use cases.** ADR-0103 §2 says no context imports another's use cases,
  and no context has a `published.py`. 25 import statements still reach another context's
  `application/use_cases`, all of them upstream, so `contexts_layered` accepts them:
  - 20 are in `workflows`;
  - 5 are elsewhere:
    - governance → `AnalysisCollaboration`;
    - governance → `FeatureLookup` (`feature_review`) and `ValidateStory` (`story_quality`);
    - analysis → `requirement_sources`;
    - knowledge → `command_fingerprint`.

  The fix gives governance ports for the upstream use cases it calls, and decides whether
  `workflows` may call use cases directly. After that, the `<ctx>_published_surface` contracts
  can forbid `application.use_cases` too.
- **A reporting builder.** Reporting is still wired in `composition/persistence.py`,
  `projections.py` and `operations.py`, not in its own `composition/reporting.py`.
- **Shared infrastructure that imports contexts.** No contract checks shared infrastructure yet.
  The modules involved:
  - `infrastructure/llm/{openai,openrouter}_adapters.py`, which select a provider for every
    context's adapters;
  - `response_sanitizer.py`, which raises an analysis error;
  - `postgres_store.py` and `backfill_document_blobs.py`, which raise requirements errors.

  Moving those raises behind ports, and the provider selection into composition, would allow a
  `shared_infrastructure_uses_no_context` contract.

## Shims

When a module moves, a re-export module stays at the old path:

```python
# MIGRATION SHIM: remove in PR 16 (docs/slices/refactor-bounded-contexts.md)
from smb_requirement_agent.breakdown.domain.epic import *  # noqa: F401,F403
```

The shim needs explicit `__all__` where mypy requires it.

**Rules:**
- Production code and tests switch to the new paths in the same PR, so shims exist only for branches still in flight.
- `tests/architecture/test_context_boundaries.py` counts imports of shim modules from `src/` and `tests/`, and fails if the count is above zero in `src/`, or rises in `tests/`.
- The shims are recorded as debt in AGENTS.md §19 until PR 16.

**Outcome:** none was needed. Every PR switched production code and tests to the new paths in the
same commit. `test_no_migration_shims_remain` keeps it that way.

## Tests

- **Golden characterisation tests (PR 1).** They are unchanged by every later PR.
- **Handler order.** For each event, the handlers run in the order ADR-0103 §3 lists. A handler failure rolls back the whole unit of work. `publish` outside a transaction, or inside `external_call`, raises.
- **Domain-only unit tests** for every rule moved into an aggregate or domain service in PR 6.
- **New `tests/architecture/test_context_boundaries.py`:**
  - handlers are subscribed only in `interfaces/api/composition/events.py`;
  - the dispatcher is built only by the composition root;
  - no shim exists in `src/` or `tests/` (PR 16);
  - every context package has exactly its layer subpackages, and `domain/` and
    `application/use_cases/` stay gone (PR 16).
- **Existing suites:** API tests, `tests/integration` against PostgreSQL (including legacy-payload loading), and the OpenAPI snapshot all pass unchanged.
- **Layout:** `tests/unit/<context>/` mirrors the contexts, with `__init__.py` in each directory so equal file names do not collide. `tests/integration` stays flat.

## Acceptance Criteria

- [x] ADR-0103 accepted by the owner (2026-10-07).
- [ ] PRs 1–16 merged, each green on `pytest`, `ruff check .`, `ruff format --check .`, `mypy src tests` and `lint-imports`.
  - Every PR was green locally on all five gates, as recorded in its *Validation evidence*.
  - All are pushed on `claude/lucid-wright-ba5v7x`. Merging is the owner's step.
- [x] The golden fingerprints, golden payloads and OpenAPI snapshot from before PR 1 are byte-identical after PR 16. Evidence: `git diff a0fa37e -- tests/characterisation/golden/` and `git diff 84e5cfc -- frontend/openapi.json` are both empty.
- [x] No module under `src/smb_requirement_agent/domain/` or `application/use_cases/` remains. Both packages are removed, and `test_the_layer_first_packages_stay_gone` checks it.
- [x] No use case calls a downstream context; `lint-imports` enforces this with `contexts_layered` and the per-context contracts, with no exemptions. Calls to *upstream* use cases remain; see *Follow-ups*.
- [x] Smoke flow with `LLM_PROVIDER=fake`: create → analyse → confirm → Epic → Features → Stories → approve all → edit the Requirement. The analysis is gone; Epic, Features and Stories are stale and kept; the breakdown review needs revision. Evidence: PR 16, *Smoke flow*.
- [x] AGENTS.md, WORKSPACE.md (package boundaries and the boundary map) and ADR statuses updated (PR 16).

## Validation Evidence

PR 1, local, 2026-10-07:

- `pytest` — exit 0, no failures. The 68 new characterisation tests pass. The PostgreSQL
  integration tests skip without a database, as they do locally on `main`.
- **Drift detection** — a hand-corrupted `golden/fingerprints.json` fails
  `test_value_matches_golden[fingerprints]`, and restoring it passes again.
- `ruff check .` — all checks passed.
- `ruff format --check .` — 1110 files already formatted.
- `mypy src tests` — no issues in 553 source files.
- `lint-imports` — 9 contracts kept, 0 broken.

CI evidence is recorded when the PR runs.

## Risks

| Risk | Mitigation |
|---|---|
| A moved class changes stored JSONB | Codecs write explicit dicts and store no module paths. PR 1's golden payloads must not change |
| A fingerprint changes and every existing approval silently stops being current | The golden fingerprints from PR 1, unchanged through PR 16 |
| Handler order differs from today's call order | The order test from PR 1, kept through PR 5 |
| A handler runs outside the transaction or the lock | `in_unit_of_work()` guard and its test |
| Merge conflicts with feature work in flight | The knowledge move is last, after E2. Shims keep old imports working, move PRs stay small and short-lived, and the touched paths are announced before each move |
| A cycle between contexts that the order in ADR-0103 §2 does not allow | PR 1's dependency report runs before any move. A cycle is resolved with an event, a port the caller owns, or a recorded merge of contexts, and is added to this spec |
| A future import-linter downgrade below the sibling-layer syntax | The pin `>=2.1,<3` already resolves to 2.15, which supports independent sibling layers. If a downgrade is ever forced, replace them with explicit `forbidden` contracts |
| `git blame` loses history | Move-only commits, `.git-blame-ignore-revs`, `git log --follow` |

## Dropped from this slice

- **UI and API surface.** None is needed: this is a behaviour-preserving architecture refactor, agreed with the owner on 2026-10-07. Nothing is carried forward.

## Deferred

- Moving the remaining primitive types to value objects (`version: int`, document, attachment and architecture IDs). Do it per context after its move, when that context is next changed for a slice.
- Entity equality by identity instead of by all fields. `!=` is used today to detect change (for example `invalidate_derived_artifacts.py:67`), so it needs its own decision.
- Removing the legacy unattributed `approve(None)` path (`domain/epic/entities.py:84-89`, `domain/feature/entities.py:102-107`). It keeps old snapshots readable; its removal is a data decision, not a refactor.
- `frontend/src/review/rules.ts` (AGENTS.md §19).
