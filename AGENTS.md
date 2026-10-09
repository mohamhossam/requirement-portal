# AGENTS.md — SMB AI Requirement Breakdown Agent

## 1. Purpose

This repository builds an AI-assisted Requirement Engineering and Backlog Generation application for a Telecom SMB value stream.

The product accepts a raw business requirement, analyzes what is known and unknown, decomposes the requirement into Epic → Feature → User Story, generates Given/When/Then acceptance criteria, applies Agile quality rules, maps impacted systems/squads, exposes assumptions/open questions/dependencies/risks for human review, and later publishes only approved backlog items to Azure DevOps (ADO).

This file is the standing engineering constitution for any coding agent working in this repository, including OpenAI Codex and Google Antigravity.

The coding agent MUST optimize for:
1. Correct business behavior.
2. Clean Architecture dependency direction.
3. Small vertical slices.
4. Explicit uncertainty instead of invented requirements.
5. Testability and maintainability.
6. Human approval before external backlog publication.
7. Minimal implementation necessary for the active slice.

---

## 2. Authoritative Project Documents

Before changing code, read these files in this order:

1. `AGENTS.md` — mandatory engineering rules.
2. `ROADMAP.md` — approved slice sequence and scope.
3. `WORKSPACE.md` — workspace, commands, package boundaries, and developer workflow.
4. `docs/source/SMB_AI_Story_Breakdown_Prompt_Template_requirement_1.md` — original business decomposition reference.
5. `docs/architecture/` — accepted architecture decision records (ADRs).
6. The active slice file in `docs/slices/`, if one exists.
7. Existing tests and code in the area being changed.

### 2.1 Sibling repositories

This repository is one of three (ADR-0098):
- `requirement-portal` (this one) owns the requirements service, its UI and the platform
  deployment.
- `knowledge-portal` owns the shared library, the architecture catalogue and the squad
  catalogue, with its own database and UI.
- `platform-kernel` owns `smb_kernel`, which holds shared mechanisms with no business meaning
  (ADR-0100).

Rules:
- Reach knowledge only through the ports in ADR-0099.
- Never add a dependency on knowledge-portal code.
- A change that belongs in the kernel goes there as a release, never as a local copy.

The original `smb-ai-requirement-agent` stays maintained in parallel. Port its fixes only by the
procedure in `UPSTREAM.md`.

If documents conflict:
- `AGENTS.md` governs engineering behavior and architecture.
- An accepted ADR in `docs/architecture/` governs the specific decision it records.
- The active slice spec governs the current implementation scope.
- `ROADMAP.md` governs sequencing.
- The source prompt governs the original Agile/SMB business reference unless an approved later decision changes it.

Do not silently reinterpret a documented business rule.

---

## 3. Mandatory Task Startup Procedure

For every implementation task:

1. Read this file.
2. Identify the active roadmap slice.
3. **Read that slice's roadmap entry field by field — Domain, Application,
   Ports, Adapters, API, UI, Tests — and check your plan against every one.**
   Anything you do not intend to build must be raised with the user *before*
   implementation, with the reason. See §15.1.
4. Inspect the existing repository before proposing new abstractions.
5. State internally which domain behavior, use case, port, adapter, API/UI change, and tests are required.
6. Implement only the smallest end-to-end change required by the active slice/task.
7. Run the relevant tests and quality gates.
8. Report:
   - what changed,
   - tests executed,
   - architectural impact,
   - assumptions or unresolved issues,
   - anything intentionally deferred.

Do not implement later roadmap slices “while already here.”

---

## 4. Clean Architecture Rules

Dependency direction is inward:

`Interfaces / Infrastructure -> Application -> Domain`

### 4.0 Bounded contexts (ADR-0103)

**Status:** accepted 2026-10-07 and implemented 2026-10-08 (`docs/slices/refactor-bounded-contexts.md`,
PRs 1–16; ADR-0103 Amendment 2 records where the implementation differs). There is no layer-first
`domain/` or `application/use_cases/` package any more. New code goes in the context that
`docs/architecture/context-map.md` assigns it.

The layering above applies **inside each bounded context**. The contexts, their modules and their
relationships are in `docs/architecture/context-map.md`.

- **Package per context.** Each context is a package under `smb_requirement_agent`, with its own
  `domain/`, `application/` and `infrastructure/`:
  - `identity`, `jobs`, `requirements`, `references`, `analysis`, `knowledge`, `breakdown` and
    `governance`;
  - `reporting` (no domain);
  - `workflows` (application only).

  `shared_kernel/` is pure domain and imports nothing else from the package.
- **Dependency order between contexts:**
  `workflows → reporting → governance → breakdown → knowledge → analysis → references → requirements → {jobs | identity} → shared_kernel`
  (ADR-0103 Amendment 1).
  A context never imports one to its left.
- **Published surface.** From another context, import only its `domain`, `application/ports`,
  `application/errors` and `application/published`. Never import its use cases or its
  infrastructure: `<ctx>_published_surface` rejects both. The one exception is `workflows`,
  the orchestration context, which may call other contexts' use cases (ADR-0103 Amendment 3).
- **No downstream calls from upstream.** When an upstream context needs a downstream effect, it
  publishes a domain event, or calls a port it owns itself that the composition root implements.
- **How domain events run.** In process and synchronously, inside the caller's unit of work and
  lock. They are never published inside `external_call()`. They carry identities, never
  aggregates.
- **What stays shared.** These are not contexts:
  - `interfaces/`: routes, schemas, dependency providers, the error map and the composition root;
  - the shared `application/`: the platform-kernel error re-exports, the event dispatcher and the
    technical ports. `shared_application_uses_no_context` keeps context code out of it;
  - the shared `infrastructure/`: settings, the persistence machinery (`PostgresStore`,
    migrations) and the LLM transports. `shared_infrastructure_uses_no_context` keeps context
    code out of it, so a context's adapters live in that context.
- **Errors.** A context's application errors are in `<ctx>/application/errors.py`. The public
  error catalogue, `workflows/application/public_errors.py`, maps every error to its public code
  and category. `interfaces/api/error_handlers.py` builds the HTTP map from it.

### 4.1 Domain

Everything in this section applies to `shared_kernel/` too (ADR-0103). It is domain code
shared by every context, and `.importlinter` checks it with the domain contracts.

The domain contains:
- business entities,
- value objects,
- domain services,
- invariants,
- domain errors,
- deterministic business rules.

The domain MUST NOT import:
- FastAPI,
- SQLAlchemy,
- HTTP clients,
- OpenAI/Anthropic/Gemini SDKs,
- Azure DevOps SDK/client code,
- UI frameworks,
- persistence implementations,
- environment/config frameworks.

The domain must be executable and testable without network, database, LLM, or web server.

### 4.2 Application

The application layer contains:
- use cases,
- commands/queries,
- application DTOs where needed,
- outbound ports,
- orchestration.

Application code MAY depend on the domain.

Application code MUST NOT depend directly on:
- concrete LLM providers,
- concrete databases,
- Azure DevOps,
- FastAPI route objects,
- React/UI code.

### 4.3 Infrastructure

Infrastructure contains adapters for external concerns, for example:
- LLM provider adapters,
- persistence adapters,
- YAML/DB architecture-knowledge adapters,
- Azure DevOps adapter,
- clock/id adapters when externalized.

Infrastructure implements application/domain ports. It does not own business rules.

**An adapter must return content the domain can accept.**

External systems return data that is well-formed but unusable: blank strings,
partial records, empty result sets. Normalising or rejecting that is the
adapter's job, at the boundary where the external system is known about.

- Never hand the domain content that will trip its own invariants. If a
  domain value object can raise on the data, clean it or fail before
  constructing that value object.
- An unusable external response is an explicit adapter-level failure
  (`RequirementAnalysisGenerationError` and its future equivalents), not an
  empty success and not a leaked `ValueError`, `KeyError`, or `IndexError`.
- Index into a provider response only after checking it is populated.
- Sanitising in the adapter is not defensive clutter. Skipping it means the
  use case builds an invalid aggregate and the failure surfaces as a 500.

### 4.4 Interfaces

Interfaces contain delivery mechanisms:
- REST API,
- CLI if introduced,
- web UI boundary/BFF if introduced.

Interfaces translate transport/input concerns into application commands and translate application results into transport/view models.

No business rule belongs in a route handler or UI component.

### 4.4.1 Composition root

The object graph is wired in exactly one place: the composition root, which is
`interfaces/api/container.py` plus the `interfaces/api/composition/` package
(provider and persistence selection, one builder per bounded context, projection
refresh, operational entry points — ADR-0071).

- `build_container(settings)` and the composition package are the only places a
  concrete adapter is named.
  Choosing an adapter anywhere else — in a route, a use case, or a dependency
  provider — is an architecture violation even though import-linter cannot see it.
- **Nothing in the graph may be constructed at import time.** No module-level
  repository, adapter, provider client, or use-case instance. `main.py` builds
  the container during the FastAPI lifespan so a misconfiguration fails the
  boot, not the first request that happens to need it.
- Route handlers receive use cases through `interfaces/api/dependencies.py`
  and never name a concrete adapter.
- A new adapter is reached by extending `build_container`, never by importing
  it into the layer that uses it.
- Domain-event handlers are subscribed only in
  `interfaces/api/composition/events.py` (ADR-0103). A use case publishes an
  event; it never registers or looks up a handler.

### 4.4.2 Error translation

Domain and application errors are mapped to HTTP status codes in exactly one
place: `interfaces/api/error_handlers.py`. It derives the map from the public
error catalogue, `workflows/application/public_errors.py`, which durable jobs
also use for their failure codes. A new error is added to that catalogue.

- Route handlers must not contain `try`/`except` for domain errors and must
  not raise `HTTPException` for them. A route calls a use case and returns a
  response.
- **Every new domain or application error must be added to the map in the same
  commit that introduces it, with a test asserting its status code.** An
  unmapped error reaches the client as a 500. This is not hypothetical: the
  analysis endpoint returned 500 for schema-valid provider output because one
  route knew about an error type another did not.
- Choose the status by whose fault it is: 4xx for the caller, 502 for a
  misbehaving external provider, 500 only for a genuine bug in this codebase.

### 4.5 Configuration

Configuration is an infrastructure concern.

- Environment variables are read in exactly one module:
  `infrastructure/config/settings.py`. No `os.environ` or `os.getenv` call
  belongs in a domain module, a use case, a port, a route, or an adapter.
- Adapters receive resolved values through their constructor. An adapter that
  reads its own configuration cannot be substituted or tested.
- Settings are resolved and validated once, at startup. **Never supply a
  placeholder credential to make startup succeed.** A missing required secret
  raises `ConfigurationError` and fails the boot, naming the variable and the
  fix. Degrading to a dummy key converts a clear configuration error into a
  confusing runtime failure much later.
- Every variable documented in `.env.example` must actually be read, and every
  variable read must be documented there. A documented switch that nothing
  consumes is worse than an undocumented one — it describes behaviour the
  application does not have.
- The application must stay runnable with no external provider account
  (`LLM_PROVIDER=fake`). Every future external integration adds a comparable
  offline path before it is depended upon.

---

## 5. Core Product Model

The product evolves around these concepts, introduced only when the active slice needs them:

- Requirement
- RequirementAnalysis
- KnownFact
- Constraint
- BusinessRule
- Assumption
- OpenQuestion
- Epic
- Feature
- UserStory
- AcceptanceCriterion
- Dependency
- Risk
- Recommendation
- Architecture/SystemReference
- Review/Approval
- Revision/Version
- ExternalPublicationMapping

Do not create all future entities upfront. Introduce a concept only when its slice needs real behavior.

Each concept's owning bounded context and its precise meaning are in
`docs/architecture/ubiquitous-language.md`. Use those names in code, API and UI, and update the
glossary in the same change when a term is introduced or its meaning changes.

---

## 6. Business Decomposition Rules

The original business reference defines the following hierarchy:

- **Epic**: portfolio/LPM-level business outcome or bundled offer; may span multiple PIs.
- **Feature**: one customer-recognizable capability with one measurable outcome; intended to fit roughly one PI.
- **User Story**: one small, testable slice of a Feature; intended to fit one sprint.

### Feature splitting candidates

Use the documented strategies when they are relevant:
- component/system boundary,
- customer journey stage,
- MVP vs later drop,
- channel,
- business variant.

A Feature must trace to exactly one Epic.

### Story rules

Stories use:
`As a [role], I want [action], so that [value].`

Acceptance criteria are represented structurally as:
- Given
- When
- Then

Stories should be evaluated using INVEST:
- Independent
- Negotiable
- Valuable
- Estimable
- Small
- Testable

When a story is still too large/complex, use the documented SPIDR/splitting approaches:
- Spike,
- Paths,
- Interfaces,
- Data,
- Rules,
- Workflow Steps,
- Business Rules,
- CRUD,
- Data Variations,
- Interface/Channel Variations,
- Happy Path vs Edge Cases,
- performance/NFR sequencing where appropriate.

Security/compliance must not be silently dropped or indefinitely deferred.

---

## 7. AI / LLM Rules

The LLM is an external reasoning adapter, not the domain.

### Mandatory rules

1. Never embed provider SDK objects in domain/application models.
2. Call LLMs through explicit ports.
3. Validate LLM output into typed structures before using it.
4. Preserve provenance/state distinction between:
   - source requirement facts,
   - AI inference,
   - AI assumption,
   - human-confirmed decision.
5. Never silently convert an assumption into a confirmed business rule.
6. Never invent missing telecom/business behavior merely to produce a complete backlog.
7. Missing information must become one of:
   - OpenQuestion,
   - explicit Assumption,
   - Spike recommendation,
   - blocked/needs-review state.
8. Prompts are replaceable adapter/configuration artifacts. Do not treat prompt text as the canonical domain model.
9. Deterministic validations belong in code where possible; semantic judgments may use AI behind a port.
10. LLM failure, invalid structured output, timeout, and partial response must produce explicit application-level failure handling.
11. **A structured-output schema constrains shape, not content.** `list[str]`
    permits `[""]`; a required field permits `"   "`. The schema being satisfied
    is not evidence the response is usable. Every provider field that reaches a
    domain value object must be stripped and checked in the adapter first.
12. A response left with no usable content after cleaning is a failed
    generation, not an empty result. Persisting an empty analysis hides the
    failure from the reviewer who needs to see it.
13. Provider failures surface as 502. A 500 from an LLM path is a bug in this
    codebase, not a provider problem.
14. Record provenance with generated content: which model, which prompt
    version, and when. A reviewer approving AI output must be able to tell what
    produced it. Add this to any new generated aggregate at the point it is
    introduced — retrofitting it after approval workflows exist is far harder.

Prefer several focused LLM operations over one giant prompt when decomposition quality and recoverability improve.

---

## 8. Human-in-the-Loop Rules

Generated content is a candidate, not automatically approved business truth.

Keep distinct workflow concepts such as:
- generated,
- under review,
- needs revision,
- approved.

The exact statuses may evolve by slice, but these constraints are permanent:

- AI generation MUST NOT automatically publish work items to ADO.
- ADO publication is allowed only from an explicitly approved backlog/revision.
- Users must be able to see assumptions, open questions, dependencies, and quality findings before approval.
- Regeneration must not silently destroy human edits or approved history.

---

## 9. Azure DevOps Boundary

ADO is an external system.

The core domain must not contain:
- organization URLs,
- project names,
- area paths,
- iteration paths,
- ADO field names,
- ADO work item IDs as native Epic/Feature/Story attributes.

Use an outbound publication port and an infrastructure adapter.

External IDs belong in a separate publication/mapping model.

Do not implement ADO integration before its roadmap slice unless the user explicitly changes the roadmap.

---

## 10. SMB Architecture Knowledge

The source reference currently contains SMB systems and flow knowledge such as:
- B2B digital channels,
- BCRM/CIM/DCRM,
- CBCM/CRMGW,
- RTF/CWOM,
- Netcracker,
- TIBCO,
- IBM BPM,
- Felix,
- CNS,
- GIS,
- EDMS/OCR/EIDA/ADFS,
- ServiceNow/HPSM/Remedy,
- BSCS,
- WFM,
- inventories,
- activation systems.

Treat this knowledge as changeable reference data.

Do not hardcode keyword-to-system rules in domain code.

Access architecture knowledge through an abstraction once the architecture-mapping slice is reached.

---

## 11. Technology Baseline

Unless an approved architecture decision changes it:

### Backend
- Python 3.12+
- FastAPI for HTTP interface
- Pydantic for boundary/schema validation
- pytest for tests
- ruff for lint/format checks
- mypy strict for static typing
- import-linter for architecture dependency contracts
- python-dotenv for local `.env` loading (read only by the settings module)

### Frontend
Introduce the frontend when a UI slice requires it.
Preferred default:
- TypeScript
- React
- Vite

Do not couple frontend state directly to LLM provider payloads. Consume stable application/API schemas.

### Persistence
Start with in-memory adapters where sufficient.
Introduce production persistence only when the roadmap requires durable state/versioning.

---

## 12. Coding Standards

- Use explicit types.
- Prefer immutable value objects where practical.
- Avoid global mutable state. Concretely: no module-level instantiation of
  repositories, adapters, provider clients, or use cases. Anything holding
  state is created by the composition root and passed in.
- **No optional constructor dependency that silently changes behaviour.** A
  parameter defaulting to `None` creates two configurations, only one of which
  is tested, and the untested one usually ships. If collaborating with a
  dependency is part of the behaviour, require it. If it is genuinely optional,
  the two paths each need a test.
- Inject nondeterministic dependencies such as clocks when behavior/tests depend on them.
- Prefer meaningful domain names over technical names.
- Avoid generic `utils.py` dumping grounds.
- Import at module level. A function-level import hides a dependency and usually
  papers over a cycle; the two process- and platform-specific exceptions are
  listed, with reasons, in `tests/architecture/test_runtime_invariants.py`.
- Avoid “manager”, “helper”, or “service” classes unless their responsibility is precise.
- Keep functions/classes focused.
- Do not duplicate domain invariants across adapters. Adapters clean external
  data so it satisfies invariants; they do not re-implement or re-decide them.
- Do not swallow exceptions.
- Map infrastructure exceptions into explicit application/domain errors at boundaries.
- Do not use broad `except Exception` unless translating at a top-level boundary and preserving context.
- No dead code or speculative abstractions.
- No TODOs that hide required behavior for the active slice.

---

## 13. Testing Strategy

Every slice must add the cheapest tests that prove its behavior.

Preferred test pyramid:

1. Domain unit tests.
2. Application/use-case tests with fakes/in-memory adapters.
3. Adapter contract/integration tests.
4. API tests.
5. UI tests when UI behavior exists.
6. End-to-end tests only for critical cross-boundary flows.

LLM unit tests MUST use deterministic fakes/fixtures, not live provider calls.

Live-provider tests, if ever added, must be isolated and opt-in.

Architecture dependency tests are mandatory and should fail if inward dependency rules are violated.

### Test isolation rules

- Each API test builds its own container (see the `client` fixture in
  `tests/conftest.py`). Tests must never share a process-wide object graph:
  order-dependent state is a defect the suite is supposed to catch, not create.
- **A test must not import a private module member** (a leading-underscore
  name) to reach application state. Needing to is a signal that the production
  wiring lacks a seam — fix the wiring, not the test.
- Every error in the `interfaces/api/error_handlers.py` map needs a test
  asserting its status code.
- Adapter tests must cover the malformed-but-schema-valid response: blank
  entries, missing halves of a pair, an empty result set, a provider exception.
  A happy-path adapter test proves almost nothing about production behaviour.

---

## 14. Quality Gates

Five gates, all mandatory, all run by CI (`.github/workflows/ci.yml`) on every
push and pull request:

```bash
pytest
ruff check .
ruff format --check .
mypy src tests
lint-imports
```

Run all five locally before declaring a task complete. CI also enforces the
gates in ADR-0077: coverage floors, `pip-audit` and `npm audit`, a Trivy scan
of both images, and digest-pinned images. A red supply-chain gate is fixed by
upgrading, not by lowering a floor or ignoring an advisory. Also required:
- no known architecture violation,
- no secret/API key committed.

**CI is the authority, not a local run.** A slice is not done while any gate is
red, and a red gate is never someone else's problem to clean up later. Slice 02
was completed and documented with `ruff check` and `ruff format --check`
failing, which is what made CI necessary.

`ruff` respects `.gitignore`; do not add hardcoded `exclude` paths to work
around a local directory, because the list will silently miss the next one.

If a gate cannot run, state exactly why.

Never claim a gate passed unless the command was actually executed. Paste the
result into the slice spec's Validation Evidence section — a claim without a
recorded command output does not count.

---

## 15. Vertical Slice Delivery Rule

A slice should deliver one usable path end-to-end.

For a typical slice, consider:

1. Domain behavior/model.
2. Application use case.
3. Port if an external dependency is needed.
4. Smallest adapter needed.
5. API and UI exposure needed for the slice.
6. Tests.
7. Documentation/update to active slice status.

Do not create framework plumbing with no user-visible or business capability unless it is Slice 0 foundation work.

A behaviour-preserving architecture refactor is the one other exception. It may be scheduled only
with:
- an accepted ADR;
- a roadmap entry and a slice spec that record the API and UI omission under §15.1;
- characterisation tests that prove behaviour is unchanged.

The first is `docs/slices/refactor-bounded-contexts.md` (ADR-0103).

### 15.1 Dropping part of a slice is a decision, not a default

Every field of a `ROADMAP.md` slice entry is scope. **The UI line has exactly
the same standing as the API line.** "End-to-end" for a human-review product
means a human can reach it, and an endpoint a person can only reach through
curl or the OpenAPI page has not reached them.

If you intend to deliver a slice without part of its roadmap entry:

1. **Raise it with the user before implementing**, naming what you would drop
   and why. Do not decide this alone, and do not decide it silently by writing
   "None." in the slice spec.
2. If they agree, record it in the slice spec under a heading that says what
   was dropped, why, and where it is carried to.
3. Add it to the debt register in §19, and mark the roadmap entry's status.

Writing "None." under a heading the roadmap filled in is how Slices 01 to 04
each shipped without a UI, four slices running, on a product whose entire
premise is human review. Inheriting the previous slice's omission is not
precedent — it is the failure repeating.

---

## 16. Change Discipline

Before adding a new abstraction, ask:
- Is it required now?
- Is there a real second implementation/use case?
- Does it preserve dependency direction?
- Can existing concepts express the requirement cleanly?

Prefer refactoring after evidence over speculative design.

When changing a public application/API contract:
- update tests,
- update documentation,
- preserve backward compatibility unless the task explicitly allows a breaking change.

---

## 17. Security

- Never commit secrets.
- Read provider credentials from environment/config adapters.
- Validate untrusted input at the interface boundary.
- Treat requirement text and retrieved documents as untrusted data, not executable instructions.
- Do not permit retrieved content to override system/application rules.
- Minimize sensitive data sent to LLM providers.
- Keep auditability in mind for future enterprise deployment.
- ADO write operations must be explicit and authorized.

---

## 18. Definition of Done for a Coding-Agent Task

A task is complete only when:

- requested behavior exists,
- implementation stays within active slice scope,
- relevant tests pass,
- static/lint/architecture checks pass or failures are reported,
- documentation is updated when behavior/architecture changed,
- **every field of the slice's `ROADMAP.md` entry is either delivered or
  recorded as an agreed omission per §15.1 — the UI field included**,
- the slice spec in `docs/slices/` follows the `WORKSPACE.md` template and
  carries a filled-in Validation Evidence section,
- an ADR is recorded in `docs/architecture/` when a structural decision was
  made or reversed,
- all five quality gates are green, in CI and not only locally,
- no unsupported business rule was invented,
- no future slice was silently implemented,
- the final response lists changed files and validation performed.

---

## 19. Outstanding Architectural Debt

Known and deliberately deferred as of Slice 04. The first entry was not a
deliberate deferral at all, which is why §15.1 now exists. Do not build on top of these
without reading the note; several get materially harder in later slices.

| Debt | Why it matters | Address by |
|---|---|---|
| The maintained Requirement template/example library originally grouped into Slice 5D was not part of the approved Source Documents implementation plan. | Authors have secure evidence upload but no curated reusable starting-point catalogue. | Slice 5D.1 after explicit roadmap scheduling. |
| Existing DOCX extraction revisions can contain copied table headers or merged-anchor wording. | ADR-0056 fixes new extractions; immutable legacy rows can still retain wording from a separately excluded row. Rebuilding old extracted text does not repair it. | Affected owners inspect/withdraw and upload, review and publish a new version before relying on row exclusions; see the document-knowledge runbook. |
| Existing TXT/Markdown extraction revisions can retain heading wording in descendant section paths. | ADR-0059 fixes new uploads; excluding/correcting an old heading does not remove its original wording from metadata. Rebuilding old text retains those paths. | Owners inspect/withdraw affected publications and upload/review/publish a new version; see the document-knowledge runbook. |
| Existing Word prose extraction can retain original paragraph/list labels and copied heading paths. | ADR-0060 fixes new uploads; old correction/exclusion decisions do not remove this wording from stored metadata. | Owners inspect/withdraw affected publications and upload/review/publish a new version; see the document-knowledge runbook. |
| Existing XLSX revisions can retain worksheet names in row labels, paths and warnings after heading exclusion/correction. | ADR-0061 fixes new uploads; stored extraction rebuilds retain old metadata. | Owners inspect/withdraw affected publications and upload/review/publish a new version; see the document-knowledge runbook. |
| Legacy Docling OCR revisions can retain original heading wording in descendant metadata. | ADR-0065 introduces neutral heading positions for new OCR results; rebuilding old stored extraction retains the original paths. | Owners inspect/withdraw affected publications and upload/review/publish a new version before relying on heading exclusions. |
| Requirement index embedding follows every knowledge-corpus edit, including edits through routes that are not rate-limited (saving a draft answer, assigning a question). | Those edits spend embedding calls outside the per-actor limit. The spend is bounded to the changed chunks and by the input limits (ADR-0074, amended by the third review remediation). | Charge index work to the editing actor if embedding spend becomes material. |
| `ai_jobs` rows are kept forever, because they are the activity feed's record of AI work (ADR-0079). | The table grows with use, though reads are bounded and polling cost does not grow. | Archive finished jobs past a horizon into a cold table the activity projection can still read, if the table's size starts to matter. |
| Frontend review-remediation items that need frontend logic changes, deferred on 2026-09-24 because CLAUDE.md limits frontend changes to presentation during the UI redesign. (a) `frontend/src/review/rules.ts` still restates the review rules instead of reading the API's `actions` fields (ADR-0073). (b) The knowledge API types in `frontend/src/api/knowledge.ts` are hand-written, not generated from OpenAPI. | (a) The rules now exist on the server, but the browser can still drift from them until it switches over. (b) Hand-written types can silently disagree with the contract; since the third review remediation `src/api/contract.test.ts` checks every client call's method and path against `openapi.json`, but not the payload types. | The UI redesign (`docs/ux-plan.md`), which rebuilds these screens: read `actions`, delete `rules.ts`, and use generated knowledge types. Either may instead be taken earlier as a recorded frontend logic exception (ADR-0109), once the owner approves it. Retired: the 1,790-line `AnalysisPanel.tsx`, split presentationally into seven files (third review remediation, Phase 6.2); identity-dependent queries on the Architecture knowledge page running before identity loaded (fourth review remediation, Phase 5.1); the Clarify panel showing "No analysis yet" after its job finished, because invalidation joined a still-loading read (PR #41: `invalidateWorkspaceKeys` cancels in-flight reads first). These are Phase 6.1 (frontend half), 6.2 and 6.3 of `docs/slices/enhancement-review-remediation.md`. |


Legacy CSV/TSV extraction can retain first-record wording copied into later rows. ADR-0057 fixes
new uploads only; owners must inspect affected publications, withdraw unintended text, and upload/
review a new version. Rebuilding an old extraction cannot apply the fix. Track owner cleanup before
production qualification; immutable publication history must not be silently rewritten.

Retired by Slice 03: `UpdateRequirement`'s optional collaborator, replaced by
the required `InvalidateDerivedArtifacts` (ADR-0004), and missing provenance on
generated aggregates, now carried by `Epic`.

Retired by Slice 04: duplicated lifecycle logic between generated aggregates,
now shared via `ReviewableGeneration` (see the slice spec), and the unstable
`EpicId` that would have orphaned Features on regeneration.

Retired by Slice 4A: the missing human-review UI. Requirement intake, analysis,
Epic review and Feature review are now usable in a browser, with ownership,
provenance and staleness made explicit and guarded regeneration covered by a
full-flow browser test.

Retired by the bounded-context restructure (ADR-0103, `docs/slices/refactor-bounded-contexts.md`):
the layer-first package layout, the context errors in `application/errors.py`, the public error
catalogue's placement, every contract exemption (PR 16), and the four follow-ups: use-case imports
between contexts outside `workflows`, shared infrastructure importing contexts, reporting's
inline wiring, and domain parsing of knowledge-portal content (Amendment 3).

Retired by the analysis clarification enhancement: duplicated analysis value-object
validation and the inconsistent `entities.py` placement. Analysis values now share one
non-empty validator in `domain/analysis/value_objects.py`.

Retired by Slice 5A: the missing Story review UI. The Story backend shipped in
the Slice 5/10 merge with no browser surface — the same "slice without its UI"
omission §15.1 exists to prevent, repeated one level down from Slices 1–4. Every
approved Feature's Stories are now reviewable and editable in the browser
(voice, Given/When/Then, guarded regeneration, split/merge via AI change
proposals). That merge had also left the tree red — the API could not start
(`EditFeature.__init__` misplaced), several gates failed, and the committed
OpenAPI snapshot omitted the Story endpoints; all repaired in the "repair red
baseline" commit before the UI work. Story approval remains open (row above,
Slice 9).

Retired by the Slice 5 closure: provider/repository-shaped failures now live in
`application/errors.py`; the composition root selects the configured LLM
provider once while retaining separate focused ports; Story mutations and
revision checkpoints share one transaction; and revision comparison/UI include
Stories. See ADR-0011.

Retired by Slice 8A: `RequirementId` now rejects blank values. Provider-neutral
actor identity, Requirement/draft ownership, reviewer assignments, owner-only
confirmation, and actor-attributed confirmation/decisions now cross the full
domain-to-browser path; legacy rows remain explicitly claimable and unattributed.

Retired by Slice 8B: every new `RequirementAnalysis` now has stable identity,
generation time, model/prompt provenance, and an immutable round. Explicit
re-analysis uses `force=true`; current content can no longer be overwritten by
an accidental repeat POST. Migration `007` labels unavailable legacy metadata
honestly and backfills deterministic round/question identities.

Retired by ADR-0050: the header's navigation collision. The global nav is a
sibling of `.header-leading` rather than a child, so below the `md` tier the
header wraps and gives it a row of its own. Nothing in the header overlaps at
any width from 360 upwards, and phones have primary navigation for the first
time.

Retired by Slice 9: Epic, Feature, and Story edits require explicit source
reconciliation before clearing staleness; Stories now have attributed approval
and rejection actions; and analysis confirmation plus immutable rounds is the
analysis review lifecycle rather than a duplicate approval concept. Durable,
content-bound artifact and final approvals are governed by ADR-0021.

Retired by the second review remediation: token-blind provider metrics, now
`smb_provider_tokens_total` (ADR-0074 amended); the several Requirement
authorization styles, now one service (ADR-0078); and invalidation's two writes, which now
always run inside the caller's unit of work (every call site runs inside
`transaction()`, directly or through `@atomic_story_change`).

Adding to this table is acceptable; silently growing the debt without recording
it is not.

---

## 20. Coding-Agent Final Response Format

Use a concise final report:

### Implemented
- ...

### Architecture
- ...

### Validation
- `command` — PASS/FAIL

### Deferred / Open
- ...

Do not provide inflated claims or hide failed checks.

Retired by ADR-0066: document dependencies now use a transactionally maintained, access-filtered
reverse index. Explicit maintenance backfills recorded history; user requests do not scan it.
Portfolio load qualification and legacy unrecorded origins remain explicit limits.
