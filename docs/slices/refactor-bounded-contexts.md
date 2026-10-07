# Refactor — Bounded-context packages and domain events

**Status:** ADR-0103 accepted and the slice scheduled 2026-10-07. PR 1 delivered. The PR 1
findings were decided the same day (ADR-0103 Amendment 1). PRs 2–6 delivered; PR 7 (move
`identity`) is next.

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
| 11 | Move `breakdown` | |
| 12 | Move `governance` | |
| 13 | Move `reporting` | |
| 14 | Move `workflows` | |
| 15a | Move `references`. The ACL decodes knowledge-portal events into typed state, which replaces PR 2's `KnowledgeStateDecoderPort`, and takes over `HistoricPassage.from_entry` and `HistoricWorkItem.from_entry` | After Knowledge Center E2 merges, because E2 is the most active area |
| 15b | Move `knowledge` (screening) | After 15a |
| 16 | **Finish.** Delete every migration shim; enable `contexts_layered` and `published_surface` without exceptions beyond those ADR-0103 records; remove the empty `domain/` and `application/use_cases/`; retire the AGENTS.md §19 debt row | Locks the boundaries in |

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

## Tests

- **Golden characterisation tests (PR 1).** They are unchanged by every later PR.
- **Handler order.** For each event, the handlers run in the order ADR-0103 §3 lists. A handler failure rolls back the whole unit of work. `publish` outside a transaction, or inside `external_call`, raises.
- **Domain-only unit tests** for every rule moved into an aggregate or domain service in PR 6.
- **New `tests/architecture/test_context_boundaries.py`:**
  - handlers are subscribed only in `interfaces/api/composition/events.py`;
  - no shim imports from `src/`;
  - every context package has the expected layer subpackages.
- **Existing suites:** API tests, `tests/integration` against PostgreSQL (including legacy-payload loading), and the OpenAPI snapshot all pass unchanged.
- **Layout:** `tests/unit/<context>/` mirrors the contexts, with `__init__.py` in each directory so equal file names do not collide. `tests/integration` stays flat.

## Acceptance Criteria

- [x] ADR-0103 accepted by the owner (2026-10-07).
- [ ] PRs 1–16 merged, each green on `pytest`, `ruff check .`, `ruff format --check .`, `mypy src tests` and `lint-imports`.
- [ ] The golden fingerprints, golden payloads and OpenAPI snapshot from before PR 1 are byte-identical after PR 16.
- [ ] No module under `src/smb_requirement_agent/domain/` or `application/use_cases/` remains.
- [ ] No use case calls a downstream context; `lint-imports` enforces this.
- [ ] Smoke flow with `LLM_PROVIDER=fake`: create → analyse → confirm → Epic → Features → Stories → approve all → edit the Requirement. The analysis is gone; Epic, Features and Stories are stale and kept; the breakdown review needs revision.
- [ ] AGENTS.md, WORKSPACE.md (package boundaries and the boundary map) and ADR statuses updated.

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
