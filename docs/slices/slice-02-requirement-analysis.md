# Slice 02 — Requirement Analysis

## Objective

Introduce the first AI capability: a structured analysis of a raw business
requirement that makes explicit what is known, what is assumed, and what is
still unresolved — without decomposing the requirement into backlog items.

## User Outcome

A Business Analyst can:

1. Trigger an AI analysis of an existing requirement.
2. Retrieve the stored analysis for that requirement.
3. See facts, constraints, and business rules kept strictly separate from
   assumptions, open questions, and ambiguities.

The analysis is an aid to human review. It produces no Epics, Features, or
User Stories, and it is not approved or published anywhere.

## In Scope

- `RequirementAnalysis` domain aggregate with `KnownFact`, `Constraint`,
  `BusinessRule`, `Assumption`, `OpenQuestion`, `Ambiguity`,
  `PotentialDependency`.
- Domain validation: every analysis entry must be non-empty and non-blank.
- `AnalyzeRequirement` and `GetRequirementAnalysis` use cases.
- `RequirementAnalyzerPort` (AI generation) and
  `RequirementAnalysisRepositoryPort` (persistence) outbound ports.
- `OpenAIRequirementAnalyzer` adapter using OpenAI structured outputs.
- `FakeRequirementAnalyzer` adapter for deterministic tests.
- `InMemoryRequirementAnalysisRepository` adapter.
- Analysis invalidation: updating a requirement deletes its stale analysis.
- `POST /requirements/{id}/analysis`, `GET /requirements/{id}/analysis`.
- Domain, use-case, adapter, and API tests.

## Out of Scope

- Epic, Feature, UserStory, AcceptanceCriterion (Slices 03–06).
- SMB architecture mapping (Slice 07).
- Review / Approval workflow (Slice 09).
- Versioning / revision history (Slice 10).
- Export and Azure DevOps integration (Slices 11–13).
- Database / PostgreSQL persistence.
- Frontend / React UI.
- Analysis timestamps and model/prompt provenance.
- Re-analysis conflict handling — `POST` currently overwrites.
- Streaming, batching, or cost controls on LLM calls.

## Domain

### Analysis value objects
Frozen dataclasses, each rejecting empty or whitespace-only content with
`InvalidAnalysisContentError`:

| Class | Fields |
|---|---|
| `KnownFact` | `statement` |
| `Constraint` | `statement` |
| `BusinessRule` | `statement` |
| `Assumption` | `statement` |
| `OpenQuestion` | `question`, `rationale` |
| `Ambiguity` | `statement`, `reason` |
| `PotentialDependency` | `statement` |

### `RequirementAnalysis`
- Frozen dataclass (aggregate root).
- Holds `requirement_id` plus one immutable tuple per category above.
- Carries no identity of its own; it is addressed by its `RequirementId`.

### Domain Errors
| Class | When raised |
|---|---|
| `InvalidAnalysisContentError` | Empty or blank analysis entry |
| `RequirementAnalysisNotFoundError` | No analysis stored for the requirement |
| `RequirementAnalysisGenerationError` | Provider failed or returned unusable output |

## Application Use Cases

### `AnalyzeRequirement`
Loads the requirement, calls `RequirementAnalyzerPort`, maps the neutral
candidate into the domain aggregate, and persists it. Raises
`RequirementNotFoundError` for an unknown ID.

### `GetRequirementAnalysis`
Verifies the requirement exists, then returns its stored analysis or raises
`RequirementAnalysisNotFoundError`.

### `UpdateRequirement` (extended)
Deletes the stored analysis after a successful update, so a changed
requirement never carries an analysis of its previous text.

## Ports

### `RequirementAnalyzerPort`
`analyze(requirement) -> RequirementAnalysisCandidate`. The candidate is a
provider-neutral `TypedDict` of plain lists — no Pydantic, no SDK types — so
the application layer never sees provider representations.

### `RequirementAnalysisRepositoryPort`
`save`, `get_by_requirement_id`, `delete_by_requirement_id`.

## Adapters

- `OpenAIRequirementAnalyzer` — OpenAI structured outputs against
  `RequirementAnalysisSchema`, 60s timeout. Maps provider failures to
  `RequirementAnalysisGenerationError`.
- `FakeRequirementAnalyzer` — canned deterministic candidate, with a
  `should_fail` switch to exercise the failure path.
- `InMemoryRequirementAnalysisRepository` — dictionary keyed by requirement ID.

## API

| Method | Path | Success | Errors |
|---|---|---|---|
| `POST` | `/requirements/{id}/analysis` | 200 | 404 unknown requirement, 502 generation failure |
| `GET` | `/requirements/{id}/analysis` | 200 | 404 unknown requirement or missing analysis |

## UI

**Not delivered.** `ROADMAP.md` specifies a UI for this slice; it was not
built, and at the time that was recorded only as "None" rather than raised as a
decision. Carried into Slice 4A, and tracked in the `AGENTS.md` §19 register.
`AGENTS.md` §15.1 now forbids this route.

Originally recorded as:
> None. Frontend work is deferred until the roadmap reaches a UI slice.

## Business Rules

- `ASSUMPTION != FACT`. Facts, constraints, and business rules must be
  supported by the requirement text; anything inferred is an assumption.
- Missing or unclear information is surfaced as an open question or an
  ambiguity, never silently resolved.
- The analyzer must not produce Epics, Features, or User Stories.
- Requirement text is untrusted input; the system prompt instructs the model
  to ignore instructions embedded in it.
- An analysis must never outlive the requirement text it describes.

## Tests

- Analysis domain invariants for every value object.
- `AnalyzeRequirement` / `GetRequirementAnalysis` happy and error paths using
  the fake analyzer and in-memory repositories.
- Analysis invalidation on requirement update.
- `OpenAIRequirementAnalyzer` success and provider-error mapping, with the
  SDK client patched — no network access in the unit suite.
- API transport and status-code mapping for both endpoints.

## Acceptance Criteria

- [x] A requirement can be analysed and the analysis retrieved.
- [x] Facts and assumptions are modelled as distinct domain types.
- [x] Application and domain layers are free of `openai` and Pydantic imports.
- [x] Updating a requirement invalidates its analysis.
- [x] Provider failures surface as 502, not 500.
- [x] Full quality gates executed — see Validation Evidence.
- [x] No Epic/Feature/Story, database, or ADO functionality introduced.

## Validation Evidence

Environment: Python 3.12 on Linux, `.venv` created per `WORKSPACE.md §4`.

```
pytest
```
PASS — 80 passed in 0.44s

```
ruff check .
```
PASS — All checks passed!

```
ruff format --check .
```
PASS — 74 files already formatted

```
mypy src tests
```
PASS — Success: no issues found in 60 source files

```
lint-imports
```
PASS — Contracts: 2 kept, 0 broken.
- Domain must not depend on outer layers — KEPT
- Application must not depend on infrastructure or interfaces — KEPT

## Post-Slice Corrections

Applied after the slice review, on top of the scope above:

- **Quality gates enforced in CI.** `.github/workflows/ci.yml` runs all five
  gates on every push and pull request. `ruff check` and `ruff format --check`
  were red on this slice's files and have been fixed.
- **Schema-valid provider output no longer 500s.** `RequirementAnalysisSchema`
  permits empty strings, which the analysis value objects reject; the escaping
  `InvalidAnalysisContentError` surfaced as a 500. Blank entries are now
  stripped in the adapter, an all-blank response is a
  `RequirementAnalysisGenerationError`, and an empty `choices` list is handled
  explicitly instead of raising `IndexError`.
- **Central error mapping.** `interfaces/api/error_handlers.py` replaces the
  per-route `try/except` blocks, so a newly raised error cannot be handled in
  one route and escape as a 500 from another.
- **Composition root replaces import-time singletons.**
  `interfaces/api/container.py` wires the graph from
  `infrastructure/config/settings.py`; `main.py` builds it during startup and
  tests build one per test. `LLM_PROVIDER` now actually selects the analyzer,
  `.env` is loaded, and a missing `OPENAI_API_KEY` fails the boot instead of
  silently degrading to a `"dummy"` key and a 502 on first use.

## Deferred

- Analysis provenance (`created_at`, model and prompt version) — needed before
  the human-approval slice so reviewers know what produced an analysis.
- Re-analysis semantics: `POST` overwrites silently and costs a provider call
  on every request. Revisit with 201/409 or an explicit force flag.
- Relocating persistence- and provider-shaped errors out of the domain layer
  into the application layer.
- `UpdateRequirement`'s optional `analysis_repository` dependency, which makes
  invalidation silently skippable. A domain event is the better shape.
