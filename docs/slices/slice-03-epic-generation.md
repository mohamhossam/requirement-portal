# Slice 03 — Epic Generation

> Status: **delivered**. Two decisions changed during implementation and are
> recorded under *Decisions taken during implementation* below.

## Objective

Turn an analysed requirement into a single reviewable Epic candidate that a
human can edit and approve, and that the system refuses to silently overwrite
or to approve once its source has moved on.

## User Outcome

A Product Owner can:

1. Generate an Epic candidate from a requirement and its analysis.
2. Read the Epic's name, business outcome, and business case.
3. Edit any of those fields.
4. Approve the Epic.
5. See that an Epic has gone stale because its source requirement changed, and
   regenerate it deliberately rather than by accident.

An approved Epic is a durable human decision. Nothing in this slice may destroy
it without an explicit instruction.

## Why this slice is different

Slices 01 and 02 were create-and-read. This one introduces three things the
codebase has never had, and most of its risk lives there:

- **A lifecycle.** Epic is the first aggregate with meaningful state
  transitions and rules about which are legal.
- **Human approval.** The first content whose destruction is a real loss, which
  is what `AGENTS.md` §8 exists to protect.
- **A third derived artifact.** Requirement → Analysis → Epic makes the
  ad-hoc invalidation in `UpdateRequirement` untenable and forces the debt to
  be paid (see *Debt retired* below).

## Approved product decisions

Confirmed before planning; they set the domain shape.

| Question | Decision |
|---|---|
| Epics per requirement | **Exactly one.** Addressed as `/requirements/{id}/epic`, mirroring analysis. Multi-Epic requirements are a later slice. |
| Source requirement changes under an approved Epic | **Mark stale, keep content.** The Epic keeps its text and approval record and is flagged stale with a reason. Never auto-deleted. |
| Regenerating an edited or approved Epic | **Refused with 409 unless forced.** Destroying human work must be a deliberate act. |

## In Scope

- `Epic` aggregate with lifecycle, staleness, and provenance.
- `GenerateEpic`, `GetEpic`, `EditEpic`, `ApproveEpic` use cases.
- `EpicGeneratorPort` and `EpicRepositoryPort`.
- `OpenAIEpicGenerator`, `FakeEpicGenerator`, `InMemoryEpicRepository`.
- `ClockPort` + `SystemClock` / `FixedClock`, required for provenance.
- Provenance on generated content: timestamp, model, prompt version.
- Staleness propagation when a requirement changes, replacing
  `UpdateRequirement`'s optional analysis dependency.
- Four endpoints (below) and their error mappings.
- Domain, use-case, adapter, and API tests.
- ADRs for the lifecycle and the invalidation shape.

## Out of Scope

- Feature and UserStory decomposition (Slices 04–05).
- INVEST / SPIDR validation (Slice 06).
- SMB architecture/system tagging on the Epic (Slice 07).
- Multiple Epics per requirement, and Epic candidate history or diffing.
- Un-approving as its own operation — editing an approved Epic revokes its
  approval, which is the only route back.
- Durable persistence, export, ADO, and UI.
- Regenerating the *analysis* as part of Epic regeneration.

## Domain

New package `domain/epic/`, split into `value_objects.py`, `entities.py`, and
`errors.py` — matching `domain/requirement/`, not `domain/analysis/`.

### Value objects

| Class | Rule |
|---|---|
| `EpicId` | Non-blank. Unlike `RequirementId`, validated from the start. |
| `EpicName` | Non-blank, whitespace-normalised. |
| `BusinessOutcome` | Non-blank. The measurable outcome the Epic delivers. |
| `BusinessCase` | Non-blank. One or two sentences of justification. |

### `EpicStatus`

```
GENERATED  -- AI output, untouched by a human
EDITED     -- a human has changed the content
APPROVED   -- a human has signed off on the current content
```

### `EpicProvenance`

`generated_at: datetime`, `model: str`, `prompt_version: str`.

Recorded at generation and carried unchanged through edits and approval, so a
reviewer can always tell what produced the text they are approving. This is the
`AGENTS.md` §7.14 rule applied at the first opportunity, rather than retrofitted
after approval workflows exist.

### `EpicStaleness`

`reason: StaleReason`, `since: datetime`. Absent when the Epic is current.
`StaleReason` starts with a single member, `REQUIREMENT_CHANGED`.

### `Epic` (aggregate root)

Frozen dataclass: `id`, `requirement_id`, `name`, `outcome`, `business_case`,
`status`, `provenance`, `staleness`.

Behaviour — this aggregate is deliberately not anemic, unlike
`RequirementAnalysis`:

| Method | Rule |
|---|---|
| `edit(name, outcome, business_case)` | Returns an edited copy with status `EDITED`. **Editing an approved Epic revokes its approval**, because the approval attested to content that no longer exists. Provenance is preserved. |
| `approve()` | `GENERATED`/`EDITED` → `APPROVED`. Idempotent on an already-approved Epic. **Raises `StaleEpicApprovalError` if the Epic is stale** — approving content whose source has changed is precisely the failure this slice exists to prevent. |
| `mark_stale(reason, at)` | Idempotent. Preserves status and content, including `APPROVED`. |
| `is_human_owned` | `True` for `EDITED` or `APPROVED`. The single predicate that gates forced regeneration. |

### Domain errors

| Class | Meaning |
|---|---|
| `InvalidEpicContentError` | Empty or blank Epic field |
| `EpicNotFoundError` | No Epic stored for the requirement |
| `EpicGenerationError` | Provider failed or returned unusable output |
| `StaleEpicApprovalError` | Approval attempted on a stale Epic |
| `EpicRegenerationConflictError` | Regeneration would discard human work without `force` |

Place these in `domain/epic/errors.py` for consistency with existing packages.
The register in `AGENTS.md` §19 already tracks relocating error types that are
really persistence or provider concerns; do not partially relocate here — that
is a separate, whole-codebase change.

## Application Use Cases

### `GenerateEpic`
Inputs: `RequirementId`, `force: bool = False`.

1. Load the requirement — `RequirementNotFoundError` if absent.
2. Load the analysis — `RequirementAnalysisNotFoundError` if absent. **An Epic
   may not be generated from an unanalysed requirement**; the analysis is a
   required input, not an optional enrichment.
3. Load any existing Epic. If it exists and `is_human_owned` and not `force`,
   raise `EpicRegenerationConflictError`.
4. Call `EpicGeneratorPort`.
5. Build the aggregate with provenance stamped from `ClockPort` and the
   adapter-reported model and prompt version.
6. Save and return.

### `GetEpic`
Verifies the requirement exists, then returns its Epic or raises
`EpicNotFoundError`.

### `EditEpic`
Loads, calls `Epic.edit(...)`, saves. Value objects enforce the invariants.

### `ApproveEpic`
Loads, calls `Epic.approve()`, saves. Surfaces `StaleEpicApprovalError`.

### `InvalidateDerivedArtifacts` (new collaborator)
`execute(requirement_id, at)` — deletes the analysis and marks the Epic stale.

`UpdateRequirement` takes this as a **required** constructor dependency,
replacing today's optional `analysis_repository`. The asymmetry between
deleting and flagging is deliberate and must be documented in the ADR:

- an **analysis** is disposable AI output that no human has approved, so it is
  deleted and simply regenerated;
- an **Epic** may carry a human decision, so it is flagged, never destroyed.

## Ports

### `EpicGeneratorPort`
`generate(requirement, analysis) -> EpicCandidate`, where `EpicCandidate` is a
provider-neutral `TypedDict` of `name`, `outcome`, `business_case`, plus the
`model` and `prompt_version` used.

> **Deliberate divergence from `ROADMAP.md`.** The roadmap suggests extending a
> shared `BacklogDecompositionPort`. `AGENTS.md` §16 requires evidence of a
> second use case before an abstraction, and §2 gives `AGENTS.md` precedence on
> engineering shape while the roadmap governs sequencing. A single-method
> `EpicGeneratorPort` is introduced now; whether Slice 04's Feature generation
> shares enough with it to justify unification is a decision for Slice 04,
> recorded in an ADR at that point. Raise this if you would rather commit to
> the shared port now — it is cheap today and expensive after Slice 05.

### `EpicRepositoryPort`
`save`, `get_by_requirement_id`, `delete_by_requirement_id`. Keyed by
`RequirementId` for as long as the one-Epic-per-requirement rule holds.

### `ClockPort`
`now() -> datetime` (timezone-aware, UTC).

Required because provenance and staleness both record time, and `AGENTS.md` §12
requires nondeterministic dependencies to be injected. Every timestamp
assertion in the suite depends on this being a port, not a `datetime.now()`
call buried in a use case.

## Adapters

| Adapter | Notes |
|---|---|
| `OpenAIEpicGenerator` | New prompt and structured-output schema. Reuses `response_sanitizer`; must strip blank fields and raise `EpicGenerationError` on unusable output, per `AGENTS.md` §4.3. |
| `FakeEpicGenerator` | Deterministic candidate plus a `should_fail` switch, mirroring `FakeRequirementAnalyzer`. |
| `InMemoryEpicRepository` | Dictionary keyed by requirement ID. |
| `SystemClock` | `datetime.now(tz=UTC)`. |
| `FixedClock` | Test double returning a set instant. |

The Epic prompt carries an explicit `PROMPT_VERSION` constant. Changing prompt
text without bumping it makes provenance a lie.

## API

| Method | Path | Success | Errors |
|---|---|---|---|
| `POST` | `/requirements/{id}/epic` | 201 created, 200 regenerated | 404 requirement or analysis missing; 409 human-owned without `force`; 502 generation failure |
| `GET` | `/requirements/{id}/epic` | 200 | 404 |
| `PUT` | `/requirements/{id}/epic` | 200 | 404; 422 invalid content |
| `POST` | `/requirements/{id}/epic/approval` | 200 | 404; 409 stale |

`POST` accepts `?force=true` to regenerate over human-owned content.

Approval is a subresource, not a `status` field on `PUT`, so that approving
cannot be done accidentally by a client replaying an edit payload.

New entries required in `interfaces/api/error_handlers.py`:

```
EpicNotFoundError             -> 404
EpicRegenerationConflictError -> 409
StaleEpicApprovalError        -> 409
InvalidEpicContentError       -> 422   (changed during implementation, see below)
EpicGenerationError           -> 502
```

`test_every_mapped_error_is_covered` fails the build until each is also added
to `EXPECTED_STATUS_CODES`. That guard is the intended mechanism — do not work
around it.

Response schema includes `status`, `stale` (with reason and timestamp), and
`provenance`, so a UI can render the review state without a second call.

## UI

**Not delivered.** `ROADMAP.md` specifies a UI for this slice; it was not
built, and at the time that was recorded only as "None" rather than raised as a
decision. Carried into Slice 4A, and tracked in the `AGENTS.md` §19 register.
`AGENTS.md` §15.1 now forbids this route.

Originally recorded as:
> None. Deferred with the rest of the frontend. The response schema above is
> shaped for the eventual Epic review card described in `ROADMAP.md`.

## Business Rules

- An Epic is generated from a requirement **and its analysis**; an unanalysed
  requirement cannot produce one.
- An Epic describes a portfolio-level business outcome spanning multiple PIs.
  It is not written in user-story voice — see `AGENTS.md` §6.
- Exactly one Epic per requirement in this slice.
- Approval attaches to specific content. Editing approved content revokes the
  approval.
- A stale Epic cannot be approved.
- Regeneration never silently discards edited or approved content.
- Approved content is never deleted as a side effect of an upstream change.
- The generator must not invent business justification absent from the
  requirement and analysis. Missing justification is surfaced, not fabricated —
  the analysis already carries assumptions and open questions for this purpose.

## Tests

**Domain**
- Each value object rejects empty and whitespace-only input.
- `edit` on an approved Epic returns `EDITED` and clears approval.
- `approve` is idempotent; `approve` on a stale Epic raises.
- `mark_stale` preserves content and `APPROVED` status.
- `is_human_owned` across all three statuses.

**Use cases** (fakes and in-memory adapters throughout)
- Generate happy path stamps provenance from `FixedClock`.
- Generate against a requirement with no analysis raises.
- Regeneration over `GENERATED` succeeds; over `EDITED`/`APPROVED` raises
  without `force` and succeeds with it.
- Edit and approve round-trips.
- `InvalidateDerivedArtifacts` deletes the analysis and marks the Epic stale,
  preserving approved content — the regression test for the decision above.
- `UpdateRequirement` invokes it, with the dependency now required.

**Adapters**
- `OpenAIEpicGenerator` success, provider error, blank fields stripped, all-blank
  response raising, empty `choices` — matching the coverage added for the
  analyzer.
- `FixedClock` determinism.

**API**
- All four endpoints, every status code in the table.
- Full flow: create → analyse → generate → edit → approve → update requirement
  → confirm Epic is stale, still approved, content intact.

## Decisions taken during implementation

Two points the plan left underspecified, both resolved against a failing test.

### `InvalidEpicContentError` maps to 422, not 502

The plan copied the analysis precedent, where blank content can only come from
a provider. That is wrong for Epics: `PUT /requirements/{id}/epic` carries
human input, so a Business Owner submitting a blank name would have received
`502 Bad Gateway` for a typo. Blank *provider* output cannot reach the domain —
`OpenAIEpicGenerator` rejects it as `EpicGenerationError` first — so this error
arriving at the boundary is the caller's fault. Caught by
`test_blank_edit_returns_422`.

### `Epic.edit` clears staleness

Not specified in the plan, and the two options are not symmetric. If editing
preserved staleness, a stale Epic could never be approved: the only route would
be regeneration, which discards the human's correction. Treating a deliberate
edit as an assertion that the content reflects the current requirement keeps
the lifecycle traversable. The edge — a one-word edit clearing the flag without
the editor re-reading the requirement — is recorded in ADR-0003 and in the
`AGENTS.md` §19 register for Slice 09 to revisit.

## Acceptance Criteria

- [x] An analysed requirement can produce an Epic candidate.
- [x] The Epic can be edited and approved through the API.
- [x] Editing approved content revokes approval.
- [x] A stale Epic cannot be approved.
- [x] Regeneration over human-owned content requires `force`.
- [x] Updating a requirement marks its Epic stale without deleting it or
      losing the approval record.
- [x] Provenance is recorded and returned.
- [x] `UpdateRequirement` no longer has an optional collaborator.
- [x] Every new error is in the status map with a test.
- [x] Domain and application layers import no `openai`, Pydantic, or FastAPI.
- [x] All five quality gates green.
- [x] ADRs recorded for the lifecycle (ADR-0003) and the invalidation shape
      (ADR-0004).
- [x] No Feature, Story, INVEST, or architecture-mapping functionality added.

## Implementation Order

Each step leaves the suite green.

1. `ClockPort`, `SystemClock`, `FixedClock`. Smallest independent piece.
2. `domain/epic/` — value objects, `Epic`, transitions, errors, with full
   domain tests. No I/O yet.
3. `EpicRepositoryPort` + `InMemoryEpicRepository`.
4. `EpicGeneratorPort` + `FakeEpicGenerator`.
5. `GenerateEpic`, `GetEpic`, `EditEpic`, `ApproveEpic` against the fakes.
6. `InvalidateDerivedArtifacts`; make `UpdateRequirement`'s dependency
   required and update its tests. **Do this before the API work** — it changes
   an existing contract, and doing it last invites a rushed job.
7. `OpenAIEpicGenerator` with prompt, schema, `PROMPT_VERSION`, sanitisation.
8. Routes, response schemas, error-map entries, API tests.
9. Wire into `build_container`; extend `Settings` only if the Epic model is to
   be configured separately from the analysis model.
10. ADRs, this spec's Validation Evidence, and the `AGENTS.md` §19 register.

## Debt Retired

Two entries from the `AGENTS.md` §19 register come due here and should be
struck from it as part of this slice:

- **`UpdateRequirement`'s optional `analysis_repository`.** A third derived
  artifact makes the optional-collaborator shape untenable;
  `InvalidateDerivedArtifacts` replaces it with a required dependency.
- **Missing provenance on generated aggregates.** Epic carries provenance from
  its first commit. Backfilling it onto `RequirementAnalysis` is a candidate
  follow-up once the shape has proven itself here.

Still open after this slice, unchanged: domain error relocation, re-analysis
semantics, `RequirementId` validation, and the analysis value-object
duplication.

## Risks

- **Scope creep into Slice 04.** Feature decomposition is the natural next
  thought while modelling Epics. It is out of scope; resist it.
- **Lifecycle sprawl.** Three statuses and one staleness reason are enough.
  Adding `DISCARDED`, `SUPERSEDED`, or a candidate history belongs to a slice
  that has a user need for them.
- **Port shape.** See the divergence note under `EpicGeneratorPort`. The cost
  of choosing wrong rises sharply after Slice 05.
- **Atomicity.** `InvalidateDerivedArtifacts` performs two writes with no
  transaction, as the in-memory adapters have none. Acceptable while
  persistence is in-memory; it becomes a real concern in Slice 10 and should be
  named in that slice's spec.

## Validation Evidence

Environment: Python 3.12 on Linux, `.venv` created per `WORKSPACE.md` §4.

```
pytest
```
PASS — 149 passed in 0.71s (80 before this slice)

```
ruff check .
```
PASS — All checks passed!

```
ruff format --check .
```
PASS — 103 files already formatted

```
mypy src tests
```
PASS — Success: no issues found in 86 source files

```
lint-imports
```
PASS — Analyzed 62 files, 165 dependencies. Contracts: 2 kept, 0 broken.

End-to-end against the running application with `LLM_PROVIDER=fake` and no
credentials: create → analyse → generate (201) → approve (200) → regenerate
(409) → update requirement → Epic still `approved`, flagged
`requirement_changed`, re-approval refused (409).

## Deferred

- Multiple Epics per requirement.
- Epic candidate history, diffing, and explicit un-approval.
- Unifying `EpicGeneratorPort` into a shared `BacklogDecompositionPort`.
- Staleness for analyses, and re-analysis triggered by Epic regeneration.
- Backfilling provenance onto `RequirementAnalysis`.
- Transactional invalidation.
