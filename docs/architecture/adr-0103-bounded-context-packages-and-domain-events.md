# ADR 0103 — Bounded-context packages and in-process domain events

## Status

Accepted 2026-10-07 by the repository owner. It:
- supersedes the *mechanism* of ADR-0004, while ADR-0004's delete-versus-stale semantics carry forward unchanged;
- amends ADR-0021, ADR-0070 and ADR-0071 as described under Decision;
- amends AGENTS.md §4, §5, §15 and §19.

The code reaches this layout one PR at a time. Until a context has moved, its code stays in the layer-first packages, and the rules it already follows still apply.

The migration is sequenced in `docs/slices/refactor-bounded-contexts.md`. The contexts and their relationships are in `docs/architecture/context-map.md`, and the terms are in `docs/architecture/ubiquitous-language.md`.

## Context

The backend already uses most of DDD's tactical building blocks:
- **Immutable aggregates with transition methods:** `Epic.approve`, `BreakdownReview.submit`, `AiJob.claim`, `RequirementAccess.transfer`.
- **Typed identities on almost every aggregate**, with references between aggregates by ID.
- **One shared review lifecycle**, `ReviewableGeneration` (`domain/shared/generation.py`).
- **"Can I do X?" rules in the domain**, through `ActionAvailability` (ADR-0073).
- **An anti-corruption layer** toward knowledge-portal (`infrastructure/knowledge_client.py`, ADR-0099).
- **One composition builder per bounded context** (ADR-0071).

What is missing is the *strategic* half. The bounded contexts exist only as composition builders and folder names. Four problems follow from that.

1. **No boundary between contexts is enforced.** `.importlinter` enforces layers only. Nothing stops `domain/story` importing `domain/analysis`, or one context's use case calling another's internals. The code is organised by technical layer (`domain/`, `application/use_cases/` with 72 modules, `application/ports/` with 49), so a context's code is scattered across all of them.

2. **Upstream code calls downstream code directly.** A change to a requirement, Epic, Feature or Story reaches the analysis, the backlog and the approval workflow through direct calls:
   - `InvalidateDerivedArtifacts` (`application/use_cases/invalidate_derived_artifacts.py:62-105`);
   - `InvalidateApprovalWorkflow`.

   They are called from about 20 sites in 9 modules:
   - `update_requirement.py:133`
   - `documents.py:279,314,483,556,603`
   - `edit_epic.py:97`, `generate_epic.py:159`
   - `feature_review.py:172`
   - `generate_features.py:201`
   - `story_workflow.py:299,342,398,454,577,651`
   - `story_change_proposals.py:311`
   - `architecture_mapping.py:308`

   Intake and breakdown code therefore depends on governance code, which is the wrong direction.

   ADR-0004 rejected domain events for two subscribers and set a revisit trigger: "a third consumer that is not simple invalidation". That trigger has fired. Today's consumers are:
   - discarding the analysis and superseding its questions;
   - marking the backlog stale;
   - resetting the approval workflow, which is governance, not invalidation.

   They belong to three different contexts.

3. **Governance rules live in the application layer.**
   - `approval_workflow.py` recalculates review status and decides `can_submit` and `can_approve` (`:201-230`). Its `_readiness` (`:558-592`) holds the approval invariants.
   - `approval_policy.py` defines what an approval attests to: `artifact_fingerprint` and `breakdown_fingerprint` (`:58-145`). It also counts blockers by comparing a raw string (`:159`).
   - `breakdown_review_policy.py` is a pure domain service placed in the application layer.
   - `breakdown_review.py:543-571` rebuilds `BreakdownReview` with `dataclasses.replace` and skips its transition methods.

4. **The domain packages form cycles.**
   - `domain/shared/approval.py:9` imports `ActorSnapshot` from `domain/identity`, and `domain/identity/entities.py:19` imports back from `domain/shared`.
   - `domain/shared/generation.py:25` imports `SourceLineage` from `domain/document`, and `domain/document/*` imports `domain/shared/staleness`.
   - Payload serialisation also sits in the domain: `domain/document/reference.py:138-161` and `domain/knowledge/historic.py:55-73`.

The owner decided on 2026-10-07 to restructure the code by bounded context, rather than only deepen the tactical model inside the current layout. Cross-context effects are to travel as domain events dispatched synchronously inside the existing transaction.

## Decision

### 1. One package per bounded context

```
smb_requirement_agent/
  shared_kernel/      pure domain; imports nothing else from smb_requirement_agent
  identity/           {domain, application, infrastructure}      generic
  jobs/               {domain, application, infrastructure}      generic
  requirements/       {domain, application, infrastructure}      core: intake + source documents
  knowledge/          {domain, application, infrastructure}      supporting; holds the ACL
  analysis/           {domain, application, infrastructure}      core
  breakdown/          {domain, application, infrastructure}      core: Epic, Feature, Story
  governance/         {domain, application, infrastructure}      core: review, approval, revision, export
  reporting/          {application, infrastructure}              read models only
  workflows/          {application}                              orchestration across contexts
  application/        shared technical layer: transaction port, external work, event dispatch
  infrastructure/     shared technical layer: config/settings.py, persistence (PostgresStore,
                      migrations), LLM transport, text
  interfaces/         unchanged location: api/{routes, schemas, dependencies.py,
                      error_handlers.py, container.py, composition/}, worker, cli
```

**Layout inside each context:**
- `domain/` holds entities, value objects, domain services, errors and `events.py`.
- `application/` holds `use_cases/`, `ports/`, `published.py` (the surface other contexts may call) and `errors.py`.
- `infrastructure/` holds repositories and payload codecs.

**What moves where:**
- The top-level `domain/` package disappears. Its contents go to `shared_kernel/` and to each context's `domain/`.
- `shared_kernel/` holds:
  - today's `domain/shared` (`ReviewableGeneration`, `Approval`, `Staleness`, `Provenance`, `ActionAvailability`);
  - `RequirementId`, `ActorSnapshot` (re-exported from `smb_kernel`), `SourceLineage` and `require_aware`;
  - the `DomainEvent` base.

**Ambiguous modules:**
- Source documents merge into `requirements`, because intake and documents depend on each other. Intake uses `DocumentRepositoryPort`, and `documents.py` needs the Requirement aggregate.
- Library reference documents (`domain/document/reference.py`) go to `knowledge`.
- Architecture *impact* is backlog content that the approval attests to, so it goes to `breakdown`. The architecture *catalogue* model is published by knowledge-portal, so it goes to `knowledge`.
- `revision`, `export_breakdown` and `approve_epic` go to `governance`.
- `breakdown_review_policy` becomes a governance domain service, because it builds `BreakdownReview` content. `generation_checks` (breakdown) reaches it only through a `CandidateReviewPort` that breakdown owns and the composition root implements.
- `requirement_commands`, `ai_job_execution`, `generation_context` and `internal_reads` compose several contexts, so they go to `workflows`.

`docs/architecture/context-map.md` maps every module.

**What does not move:**
- Routes, schemas, `dependencies.py` and `error_handlers.py` stay in `interfaces/api/`. The REST surface is one adapter over all contexts, AGENTS.md §4.4.2 keeps its single error map, and the OpenAPI snapshot must not change.
- `config/settings.py` (§4.5), the SQL migrations and their package-data path, and the `persistence.migrate` entry point used by the deployment images also stay.

### 2. Dependency order between contexts

```
workflows → reporting → governance → breakdown → analysis → knowledge → requirements → {jobs | identity} → shared_kernel
```

- A context may import only contexts to its right.
- From another context it may import only:
  - `<ctx>.domain`;
  - `<ctx>.application.ports`;
  - `<ctx>.application.published`.
- It never imports another context's use cases or infrastructure.
- An upstream context learns nothing about its consumers. Where it needs a downstream effect, it publishes a domain event, or it calls a port it owns itself, which the composition root implements with the downstream context. An example is `requirements` asking for a knowledge screen; see `context-map.md`.

### 3. Domain events, in process and inside the same transaction

- **Base type.** `shared_kernel/events.py` defines a frozen `DomainEvent` base. Concrete events live in `<ctx>/domain/events.py`, are immutable, and carry identities and a cause only, never aggregates.
- **Publisher and dispatcher.**
  - `application/events.py` defines the `DomainEventPublisher` port, with `publish(event)`.
  - It also defines `InProcessEventDispatcher`, a pure-Python registry from event type to an ordered list of handlers.
- **Where events are published.** Use cases publish events through the publisher at the point where they call an invalidation collaborator today.
  - Events are **not** recorded as a field on the aggregate. A field would be carried by `dataclasses.replace` and would leak into the canonical JSON that ADR-0021 fingerprints are computed from.
  - Aggregate methods do **not** return `(aggregate, events)` tuples either. That would change every transition's signature without changing behaviour.
- **Dispatch rules.**
  - Dispatch is synchronous and immediate, and handlers run in registration order. This is equivalent to today's direct calls, including the order of side effects within one use case.
  - `publish` refuses to run outside a transaction, or inside `TransactionManagerPort.external_call()`. This needs a new `TransactionManagerPort.in_unit_of_work()`, implemented by the PostgreSQL and in-memory transaction managers.
  - Handlers therefore run under the advisory lock the caller already holds (ADR-0070). They write only within the event's Requirement, and a handler that raises rolls back the whole unit of work.
- **What does not change.** No outbox is added and nothing is persisted. The commit-time projection refresh (dirty-Requirement set, ADR-0037/0038) is unchanged.
- **Where handlers are subscribed.** Only in the composition root, in a new `interfaces/api/composition/events.py`.

**Initial catalogue** (only events with a consumer today, per AGENTS.md §16):

| Event (owning context) | Published by | Handlers, in this order |
|---|---|---|
| `RequirementRevised(requirement_id, cause)` (requirements) | `UpdateRequirement`; `UploadDocument`, `SetDocumentInclusion`, `SetHiddenWorksheetInclusion`, `RemoveDocument` | governance: reset approval workflow → analysis: discard analysis and supersede its questions → breakdown: mark Epic, Features and Stories stale (`REQUIREMENT_CHANGED`) |
| `EpicChanged(requirement_id, epic_id)` (breakdown) | `GenerateEpic`, `EditEpic` | governance: reset → breakdown: mark Features and their Stories stale (`EPIC_CHANGED`) |
| `FeatureChanged(requirement_id, feature_id)` (breakdown) | `EditFeature` | governance: reset → breakdown: mark its Stories stale (`FEATURE_CHANGED`) |
| `FeaturesReplaced(requirement_id, epic_id)` (breakdown) | `GenerateFeatures` | governance: reset |
| `StoriesChanged(requirement_id, feature_id)` (breakdown) | `GenerateStories`, `EditStory`, `SplitStory`, `MergeStories`, `RegenerateStory`; applying a `StoryChangeProposals` proposal | governance: reset → governance: refresh the saved breakdown review where `generation_checks.py:231` does so today |
| `ArchitectureImpactChanged(requirement_id)` (breakdown) | architecture mapping (`architecture_mapping.py:308`) | governance: reset |

- The handler order reproduces today's call order in `InvalidateDerivedArtifacts`, and a unit test pins it.
- ADR-0004's asymmetry is unchanged: the analysis is disposable and deleted, while an Epic, Feature or Story may carry human work and is only marked stale.

### 4. Governance rules belong to the domain

These move from `application/use_cases/` into the governance domain:
- **Fingerprints.** `artifact_fingerprint` and `breakdown_fingerprint` become a `Fingerprint` value object and domain functions. Their output must stay byte-identical.
- **Readiness.** `_readiness` becomes a `BreakdownReadiness` domain service.
- **Blocker policy.** `ApprovalPolicy` moves, and compares `FlagSeverity.BLOCKING`, not a string.
- **Review policy.** `BreakdownReviewPolicy` moves, so flags, risks and recommendations are built by domain code.
- **Status recalculation.** It becomes `BreakdownReview.refresh(subject, evidence_fingerprint)`.
- **Carry-forward.** It becomes a `BreakdownReview` method, so `replace` is no longer called on the aggregate from outside.

`ReviewEvidence` becomes a governance domain value object.

### 5. Enforcement

When the migration completes, `.importlinter` gains:
- **`contexts_layered`** (`layers`), listing the order in §2. Sibling generic contexts are independent, written `jobs | identity`. The installed import-linter (2.15, pinned `>=2.1,<3`) supports independent sibling layers and wildcard module expressions.
- **`context_internal_layers`** (`layers` with `containers` = every context): `infrastructure > application > domain`.
- **Wildcard forms of today's framework contracts:**
  - `smb_requirement_agent.*.domain` must not import fastapi, pydantic, psycopg, openai, httpx or sqlalchemy;
  - `*.application` must not import fastapi, psycopg, openai, sqlalchemy or httpx;
  - the kernel-adapter contract is unchanged.
- **`published_surface`** (`forbidden`, one per context): no other context imports `<ctx>.application.use_cases` or `<ctx>.infrastructure`. Any exception is listed in `ignore_imports` with a reason.
- **`shared_kernel_pure`:** `shared_kernel` imports nothing from `smb_requirement_agent`.

The route, dependency-provider and infrastructure-to-interfaces contracts are kept.

### 6. Amendments to earlier decisions, effective on acceptance

| ADR | What changes | What stays |
|---|---|---|
| ADR-0004 | *Mechanism* superseded: `InvalidateDerivedArtifacts` is replaced by event handlers | Its semantics (delete versus flag stale) |
| ADR-0021 | Approval invalidation is a governance event handler, and the fingerprints are governance domain code | Fingerprint output and the approvals stored on the artifacts |
| ADR-0070 | `RequirementCommands` moves to `workflows/`, and event handlers run inside its unit of work | The step order: snapshot, lock, authorize, execute, reauthorize, present |
| ADR-0071 | Composition builders are renamed one-to-one to contexts, and `composition/events.py` is added | The composition root is still the only place a concrete adapter is named |

## Consequences

**Easier:**
- A context's whole model, use cases and adapters can be read in one package.
- Boundaries between contexts are checked by tooling, not by review.
- Adding a consumer of a change is one handler registered in the composition root, not edits to every use case that triggers it. Upstream contexts stop importing governance.
- Governance rules can be unit-tested as pure domain code.

**Harder or costlier:**
- **Import churn.** Almost every module, and most of the 113 unit-test files, change their imports, about 368 domain import lines in tests alone.
- **Shims while the move is in flight.** Temporary re-export modules exist at the old paths during migration; they are recorded debt in AGENTS.md §19 until the final PR removes them.
- **Merge conflicts.** Feature branches in flight, Knowledge Center E2 first, will conflict with move PRs. The slice spec sequences the knowledge move last and keeps each move PR small.
- **Less direct reading.** Dispatching events adds a layer: following "what happens when a requirement is edited" means reading the handler registry in `composition/events.py`, not one class.
- **History.** `git blame` crosses the moves. Move-only commits and `.git-blame-ignore-revs` reduce this but do not remove it.

**Ruled out:**
- Asynchronous or eventually consistent propagation between contexts inside this service.
- A per-context API package.
- Events stored on aggregates.

**Unchanged:**
- The REST contract and the OpenAPI snapshot.
- The database schema and migrations, and every persisted JSONB payload. Codecs write explicit dictionaries and no module paths, so moving a class does not change stored data.
- The single unit of work and lock per Requirement.
- `LLM_PROVIDER=fake` offline operation.

## Alternatives Considered

- **Keep the layer-first layout and only deepen tactical DDD** (events, governance into the domain, value objects, import-linter rules between `domain/*` subpackages). This is cheaper and lower risk, and was the recommended option. The owner rejected it because the contexts would stay implicit and scattered across layer folders. Most of its steps remain the early PRs of this migration.
- **Record events on the aggregate** (a `compare=False` field and `pull_events()`). Rejected: `replace()` carries the field forward and `asdict` serialises it into the ADR-0021 fingerprint input.
- **Aggregate methods return `(aggregate, events)`.** Rejected: every transition signature and caller changes, for no behavioural gain over publishing at the use-case seam.
- **A transactional outbox with asynchronous handlers.** Rejected: staleness and approval reset would become eventually consistent. A reviewer could approve a breakdown in the window before its stale flags land, which is the failure ADR-0021 exists to prevent. The outboxes that already exist for knowledge-portal (ADR-0099) are integration events between services and remain as they are.
- **An `api/` package per context.** Rejected: it would split the single error map (§4.4.2) and the dependency providers, and put the OpenAPI snapshot at risk, for no domain benefit.
- **Keep Source Documents as its own context.** Rejected for now: it and intake import each other. Separating them needs a published-port design that is only worth doing when there is a reason to deploy or own them separately.
