# Refactor — Bounded-context packages and domain events

**Status:** Specified 2026-10-07. Waiting on acceptance of
[ADR-0103](../architecture/adr-0103-bounded-context-packages-and-domain-events.md). Not started.

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
Moves are made with `git mv` in a move-only commit. The import rewrite goes in a separate commit,
which is listed in `.git-blame-ignore-revs`.

| PR | Content | Why at this point |
|---|---|---|
| 1 | **Characterisation tests.** Golden ADR-0021 fingerprints for representative artifacts and breakdowns; golden payload JSON for every codec in `infrastructure/persistence/*_payloads.py`; golden expected-context tokens; an invalidation-order test recording today's side-effect order for each trigger. Also adds `.git-blame-ignore-revs` and a script that reports import edges between the candidate contexts | Later PRs prove they preserve behaviour against these. The dependency report confirms the order in ADR-0103 §2 before any move |
| 2 | **Break the domain cycles.** Move `ActorSnapshot`, `SourceLineage` and `require_aware` so `domain/shared` imports no other domain package. Move the `to_payload`/`from_payload` of `ReferenceDocumentState` and `HistoricRequirementState` into infrastructure codecs, with byte-identical output. Merge the duplicate `InvalidKnowledgeError` | It is the smallest change that makes the shared kernel extractable |
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
| 15 | Move `knowledge` | Last, after Knowledge Center E2 merges, because E2 is the most active area |
| 16 | **Finish.** Delete every migration shim; enable `contexts_layered` and `published_surface` without exceptions beyond those ADR-0103 records; remove the empty `domain/` and `application/use_cases/`; retire the AGENTS.md §19 debt row | Locks the boundaries in |

`knowledge` sits in the middle of the dependency order but moves last, which is safe for two reasons:
- **Its contracts follow the move.** Contracts are enabled per context as it moves, so until PR 15 knowledge is checked only by the existing layer contracts.
- **No moved context reaches into it.** Contexts moved earlier reach knowledge only through its existing ports, which stay importable through shims.

Each of PRs 7–15 does four things:
1. moves the context's domain, use cases, ports and adapters;
2. moves its tests to `tests/unit/<context>/`;
3. renames its composition builder;
4. enables its `context_internal_layers` and `published_surface` entries.

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

- [ ] ADR-0103 accepted by the owner.
- [ ] PRs 1–16 merged, each green on `pytest`, `ruff check .`, `ruff format --check .`, `mypy src tests` and `lint-imports`.
- [ ] The golden fingerprints, golden payloads and OpenAPI snapshot from before PR 1 are byte-identical after PR 16.
- [ ] No module under `src/smb_requirement_agent/domain/` or `application/use_cases/` remains.
- [ ] No use case calls a downstream context; `lint-imports` enforces this.
- [ ] Smoke flow with `LLM_PROVIDER=fake`: create → analyse → confirm → Epic → Features → Stories → approve all → edit the Requirement. The analysis is gone; Epic, Features and Stories are stale and kept; the breakdown review needs revision.
- [ ] AGENTS.md, WORKSPACE.md (package boundaries and the boundary map) and ADR statuses updated.

## Validation Evidence

- `pytest` —
- `ruff check .` —
- `ruff format --check .` —
- `mypy src tests` —
- `lint-imports` —

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
