# Slice 04 — Feature Decomposition

> Status: **delivered**. Decisions taken during implementation are recorded
> below.

## Objective

Decompose an approved Epic into a reviewable set of Feature candidates, each
tracing to that Epic, each carrying the rationale for why it is a separate
Feature, and each independently editable and approvable.

## User Outcome

A Product Owner can:

1. Generate Feature candidates from an approved Epic.
2. Read each Feature's outcome, delivery drop, and splitting rationale.
3. Edit any Feature.
4. Approve Features one at a time.
5. See Features flagged stale when the Epic or requirement above them changes,
   without losing the ones already approved.

## Why this slice is different

Slice 03 introduced a lifecycle on a single aggregate. This one applies that
lifecycle to a **collection**, which is not a mechanical extension:

- **Set-level operations meet item-level state.** Regenerating "the Features"
  is one action against many items with individually differing status.
- **A three-level tree.** Requirement → Epic → Features means invalidation
  cascades rather than fans out one step.
- **Identity across regeneration matters for the first time.** A child that
  references its parent breaks if the parent's identity is not stable.

## Approved decisions

Confirmed before planning.

| Question | Decision |
|---|---|
| Port shape | **Separate `FeatureGeneratorPort`.** The evidence the Slice 03 decision waited for now exists, and it argues against unification — see below. |
| Slice scope | **Defer `SplitFeature` and `MergeFeatures`.** Generate, edit, approve satisfies the roadmap's exit criteria. |
| Regenerating a set containing human-owned Features | **409 unless `?force=true`**, which replaces the whole set. Consistent with the Epic rule. |
| Epic regenerated or gone stale | **Features go stale too.** Flag, never destroy. |

### Closing the `BacklogDecompositionPort` question

`ROADMAP.md` Slice 3 suggested extending a shared decomposition port. That was
deferred for evidence, and the evidence now points the other way:

```
EpicGeneratorPort.generate(requirement, analysis)          -> EpicCandidate
FeatureGeneratorPort.generate(requirement, analysis, epic) -> list[FeatureCandidate]
```

Different inputs, different cardinality, no shared behaviour. A combined port
would be two unrelated methods sharing a name — a grouping, not an
abstraction — and every implementer would have to satisfy both to provide
either. Record this in an ADR so the roadmap's suggestion is answered rather
than quietly ignored, and revisit only if Story generation in Slice 05 turns
out to share a real signature.

## Prerequisite fix

**`GenerateEpic` mints a fresh `EpicId` on every regeneration**
(`generate_epic.py:83`). Harmless today, because nothing references an Epic by
id. It becomes a live bug the moment a Feature stores `epic_id`: forcing a
regeneration would silently orphan every Feature under it.

Fix first, in its own commit: when replacing an existing Epic, carry its `id`
forward. One Epic per requirement means the Epic's identity belongs to the
requirement, not to a particular generation of its text. Add a test asserting
the id is stable across a forced regeneration.

## In Scope

- `Feature` aggregate and `FeatureSet` semantics, with per-Feature lifecycle.
- Shared staleness extracted to `domain/shared/` and reused by Epic and Feature.
- `GenerateFeatures`, `GetFeatures`, `EditFeature`, `ApproveFeature`.
- `FeatureGeneratorPort`, `FeatureRepositoryPort`, and their adapters.
- Cascading invalidation extended to the third level.
- Generation gated on an approved Epic.
- Four endpoints and their error mappings.
- The `EpicId` stability fix above.
- Domain, use-case, adapter, and API tests; one ADR.

## Out of Scope

- `SplitFeature` and `MergeFeatures` — deferred to a follow-up slice.
- User Stories and acceptance criteria (Slice 05).
- INVEST / SPIDR validation (Slice 06).
- System and squad tagging per Feature (Slice 07) — the source prompt asks for
  it, but it depends on the architecture-knowledge port that does not exist yet.
- Reordering Features, or numbered drops beyond MVP/Later.
- Set-level approval as a single operation, and Feature candidate history.
- Durable persistence, export, ADO, UI.

## Domain

### Shared staleness (`domain/shared/staleness.py`)

Two aggregates now need staleness, which is the second use case `AGENTS.md` §16
asks for before extracting an abstraction. Move `Staleness` and `StaleReason`
out of `domain/epic/` and add the new reason:

```
REQUIREMENT_CHANGED   -- the source requirement text changed
EPIC_CHANGED          -- the parent Epic was regenerated or edited
```

Epic keeps its behaviour unchanged; only the import moves.

### `domain/feature/`

| Class | Rule |
|---|---|
| `FeatureId` | Non-blank, validated. |
| `FeatureName` | Non-blank, normalised. |
| `FeatureOutcome` | Non-blank. One measurable outcome. Not user-story voice. |
| `SplittingRationale` | Non-blank. Why this is a separate Feature. |
| `SplittingPattern` | Enum: `COMPONENT_SYSTEM`, `JOURNEY_STAGE`, `MVP_VS_LATER`, `CHANNEL`, `BUSINESS_VARIANT` — the five strategies in `AGENTS.md` §6. |
| `DeliveryDrop` | Enum: `MVP`, `LATER`. Numbered drops deferred. |
| `FeatureStatus` | `GENERATED`, `EDITED`, `APPROVED`, mirroring Epic. |

### `Feature` (aggregate root)

Fields: `id`, `epic_id`, `name`, `outcome`, `delivery_drop`,
`splitting_pattern`, `splitting_rationale`, `status`, `provenance`, `staleness`.

Behaviour mirrors `Epic` exactly — `edit`, `approve`, `mark_stale`,
`is_human_owned`, `is_stale`, with the same rules: editing revokes approval and
clears staleness; a stale Feature cannot be approved.

**Reuse, do not re-derive.** These rules are already stated and tested on
`Epic`. If the two aggregates end up with copy-pasted transition logic, extract
the shared lifecycle rather than maintaining it twice — `AGENTS.md` §12 forbids
duplicating domain invariants, and the analysis value objects are already on
the debt register for exactly this.

### Set-level rules

There is no `FeatureSet` aggregate. The set is the Features sharing an
`epic_id`, and set-level questions are answered in the use case:

- `is_human_owned` for the set is true if **any** Feature is.
- Every Feature traces to exactly one Epic — enforced by construction, since
  `epic_id` is required and the repository is keyed by it.

### New domain errors

| Class | Meaning | Status |
|---|---|---|
| `InvalidFeatureContentError` | Blank or invalid Feature field | 422 |
| `FeatureNotFoundError` | No such Feature under this Epic | 404 |
| `FeaturesNotFoundError` | No Features generated yet | 404 |
| `FeatureGenerationError` | Provider failed or returned unusable output | 502 |
| `StaleFeatureApprovalError` | Approval attempted on a stale Feature | 409 |
| `FeatureRegenerationConflictError` | Regeneration would discard human work | 409 |
| `EpicNotApprovedError` | Feature generation attempted on an unapproved Epic | 409 |

`InvalidFeatureContentError` is **422, not 502** — the same reasoning that
corrected the Epic mapping in Slice 03. Features have a human-authored path
(`PUT`), and blank provider output is rejected in the adapter before it can
reach the domain.

## Application Use Cases

### `GenerateFeatures`
Inputs: `RequirementId`, `force: bool = False`.

1. Load requirement, analysis, and Epic — 404 if any is missing.
2. **Refuse unless the Epic is `APPROVED`** (`EpicNotApprovedError`). The
   roadmap decomposes an *approved* Epic; generating from a draft means
   building a backlog on text nobody has signed off.
3. Refuse if the Epic is stale, for the same reason.
4. If any existing Feature is human-owned and not `force`, raise
   `FeatureRegenerationConflictError`.
5. Generate, build the set, replace atomically within the repository call,
   stamp each with provenance from `ClockPort`.

### `GetFeatures`
Returns the Features for the requirement's Epic, ordered as generated.

### `EditFeature` / `ApproveFeature`
Address one Feature by id; verify it belongs to the requirement's Epic before
acting, so a Feature id from another Epic cannot be edited through this path.

### `InvalidateDerivedArtifacts` (extended)
Now cascades one level further:

| Trigger | Analysis | Epic | Features |
|---|---|---|---|
| Requirement text changed | deleted | stale (`REQUIREMENT_CHANGED`) | stale (`REQUIREMENT_CHANGED`) |
| Epic regenerated or edited | untouched | — | stale (`EPIC_CHANGED`) |

The second row is new: Epic changes must now invalidate downward, which means
`GenerateEpic` and `EditEpic` gain a call into invalidation. Keep the rule in
`InvalidateDerivedArtifacts`; do not scatter `mark_stale` calls across use
cases.

## Ports and Adapters

- `FeatureGeneratorPort.generate(requirement, analysis, epic) -> list[FeatureCandidate]`,
  each candidate a neutral `TypedDict` carrying `model` and `prompt_version`.
- `FeatureRepositoryPort`: `replace_for_epic`, `get_by_epic_id`, `get`, `save`,
  `delete_by_epic_id`. `replace_for_epic` exists so set replacement is one call
  rather than a delete-then-insert the caller must sequence correctly.
- `OpenAIFeatureGenerator` with its own versioned prompt, carrying the five
  splitting strategies and the guardrails from `AGENTS.md` §6: every Feature
  traces to one Epic and one measurable outcome; Features are never written in
  user-story voice; variant offers and channels stay separate Features;
  security and compliance are sequenced, never dropped.
- The adapter must reject a response with **zero** Features as a generation
  failure, and strip blank fields per `AGENTS.md` §4.3.
- `FakeFeatureGenerator` returning a deterministic two-Feature set — enough to
  exercise per-item state without making assertions unwieldy.

## API

| Method | Path | Success | Errors |
|---|---|---|---|
| `POST` | `/requirements/{id}/features` | 201 first, 200 replaced | 404; 409 Epic not approved or stale; 409 human-owned without `force`; 502 |
| `GET` | `/requirements/{id}/features` | 200 (list) | 404 |
| `PUT` | `/requirements/{id}/features/{feature_id}` | 200 | 404; 422 |
| `POST` | `/requirements/{id}/features/{feature_id}/approval` | 200 | 404; 409 stale |

Each Feature response carries `status`, `stale`, and `provenance`, as Epic
does, so the eventual Epic → Feature tree renders from one call.

## UI

**Not delivered.** `ROADMAP.md` specifies a UI for this slice; it was not
built, and at the time that was recorded only as "None" rather than raised as a
decision. Carried into Slice 4A, and tracked in the `AGENTS.md` §19 register.
`AGENTS.md` §15.1 now forbids this route.

Originally recorded as:
> None. The response shape anticipates the tree described in `ROADMAP.md`.

## Business Rules

- Features are generated only from an **approved, non-stale** Epic.
- Every Feature traces to exactly one Epic.
- One Feature = one measurable outcome intended to fit a single PI.
- Features describe capability and benefit, never in user-story voice.
- Each Feature records why it was split out, using one of the five patterns.
- Variant offers and channels are separate Features, not variants of one.
- Security and compliance Features are sequenced explicitly, never dropped.
- Approved Features survive upstream change, flagged rather than deleted.
- A stale Feature cannot be approved.
- The generator must not invent capabilities absent from the requirement,
  analysis, and Epic.

## Tests

**Domain** — Feature value objects and every transition, mirroring the Epic
suite; shared staleness after extraction, with the Epic tests still passing
unchanged as the proof the move was behaviour-preserving.

**Use cases**
- Generation refused when the Epic is missing, unapproved, or stale.
- Regeneration allowed over an untouched set; refused when any Feature is
  edited or approved; allowed with `force`.
- Editing and approving one Feature leaves its siblings untouched — the test
  that collection state is really per-item.
- A Feature id belonging to another Epic is rejected.
- Cascade: requirement change marks Epic and all Features stale, preserving
  approved content; Epic regeneration marks Features `EPIC_CHANGED`.
- `EpicId` stable across forced regeneration (the prerequisite fix).

**Adapters** — success, provider error, blank fields stripped, empty Feature
list rejected, empty `choices`; the prompt labels unconfirmed analysis items,
as asserted for the Epic generator.

**API** — every row of the table, plus the full flow: create → analyse →
generate Epic → approve Epic → generate Features → edit one → approve it →
change the requirement → all stale, approved Feature intact, re-approval 409.

## Decisions taken during implementation

### The whole review lifecycle was extracted, not just staleness

The plan flagged duplicated transitions between Epic and Feature as the main
design risk and said to extract if duplication appeared. It appeared
immediately — the two aggregates have identical rules for editing, approval and
staleness — so `domain/shared/generation.py` now holds
`ReviewableGeneration`, plus the shared `GenerationStatus` and `Provenance`.
`Epic` and `Feature` inherit the mechanics and keep their own content fields,
signatures and error types, so callers still catch a Feature error for a
Feature. `EpicStatus`, `FeatureStatus`, `EpicProvenance` and
`FeatureProvenance` are aliases rather than parallel definitions.

That last point was not cosmetic: defining `FeatureStatus` as its own enum
first made `FeatureStatus.APPROVED != GenerationStatus.APPROVED`, and the
lifecycle silently stopped working. Aliasing is what makes the sharing real.

### Sharing `Provenance` changed one error type

`Provenance` validation now raises the shared `InvalidGeneratedContentError`
rather than `InvalidEpicContentError`, so two Epic tests changed. Everything
else in the Epic suite passed untouched, which is the evidence the extraction
preserved behaviour. The shared error is mapped explicitly to 500: provenance
and staleness are built from the clock and the adapter, never from client
input, so reaching it really is a bug.

### Enum lookup is shared; the error it raises is not

Provider output and client input both arrive as strings that must become
`DeliveryDrop` or `SplittingPattern`. `domain/shared/enums.py` holds the
lookup, but an unrecognised value from a provider raises
`FeatureGenerationError` (502) while the same value from a caller raises
`InvalidFeatureContentError` (422). Coercing an unknown splitting pattern to a
default would fabricate the rationale a reviewer relies on.

### A changed requirement asks for re-analysis before it complains about the Epic

`GenerateFeatures` checks the analysis before the Epic, so after a requirement
edit the caller gets a 404 telling them to re-analyse rather than a 409 about
Epic staleness. Both are true; the 404 is the more actionable first step. Found
by a test whose premise was wrong, and kept deliberately — with a second test
pinning the ordering so it cannot change by accident.

## Acceptance Criteria

- [x] An approved Epic decomposes into reviewable Feature candidates.
- [x] Generation is refused for an unapproved or stale Epic.
- [x] Each Feature records delivery drop, splitting pattern, and rationale.
- [x] Features can be edited and approved individually.
- [x] Regeneration over human-owned Features requires `force`.
- [x] Requirement and Epic changes mark Features stale without deleting them.
- [x] `EpicId` is stable across regeneration.
- [x] Staleness is shared between Epic and Feature, not duplicated — along with
      the rest of the review lifecycle.
- [x] Every new error is in the status map with a test.
- [x] Domain and application import no `openai`, Pydantic, or FastAPI.
- [x] All five quality gates green.
- [x] ADR-0005 recorded, closing the shared-decomposition-port question.
- [x] No Story, INVEST, or architecture-mapping functionality added.

## Implementation Order

1. **Prerequisite**: stabilise `EpicId` across regeneration, with a test.
2. Extract shared staleness to `domain/shared/`; Epic tests must pass unchanged.
3. `domain/feature/` — value objects, aggregate, transitions, errors, tests.
   Watch for duplicated transition logic and extract if it appears.
4. `FeatureRepositoryPort` + `InMemoryFeatureRepository`.
5. `FeatureGeneratorPort` + `FakeFeatureGenerator`.
6. The four use cases against fakes, including the approved-Epic gate.
7. Extend `InvalidateDerivedArtifacts` and wire Epic changes into it.
8. `OpenAIFeatureGenerator` with prompt, schema, `PROMPT_VERSION`.
9. Routes, schemas, error-map entries, API tests.
10. Container wiring, ADR, Validation Evidence, `AGENTS.md` §19 register.

## Risks

- **The biggest slice so far.** Deferring split and merge was the main control;
  if it still runs long, `EditFeature` and `ApproveFeature` could ship ahead of
  the OpenAI adapter, since the fake generator makes the flow demonstrable.
- **Duplicated lifecycle.** Feature's transitions are Epic's. Copy-paste here
  doubles the maintenance cost of every future lifecycle rule.
- **Cascade correctness.** Three levels with two staleness reasons is where an
  off-by-one in the invalidation rule hides. The cascade tests are the ones to
  write first and trust least.
- **Set replacement without a transaction.** Already on the debt register for
  Slice 10; replacing a Feature set makes the window wider.
- **Prompt quality.** Feature splitting is the first genuinely hard generation
  task, and a fake generator proves nothing about it. Plan on manual review
  against the source prompt's worked example before calling it done.

## Validation Evidence

Environment: Python 3.12 on Linux, `.venv` created per `WORKSPACE.md` §4.

```
pytest
```
PASS — 229 passed in 1.06s (149 before this slice)

```
ruff check .
```
PASS — All checks passed!

```
ruff format --check .
```
PASS — 128 files already formatted

```
mypy src tests
```
PASS — Success: no issues found in 110 source files

```
lint-imports
```
PASS — Analyzed 80 files, 249 dependencies. Contracts: 2 kept, 0 broken.

End-to-end against the running application with `LLM_PROVIDER=fake` and no
credentials: create → analyse → Epic → approve → decompose (201, two Features
with distinct drops and splitting patterns) → approve one (200) → regenerate
(409) → change the requirement → both Features stale with
`requirement_changed`, the approved one still `approved`, re-approval refused
(409).

## Deferred

- `SplitFeature` and `MergeFeatures`.
- Feature reordering, numbered delivery drops, set-level approval.
- System/squad tagging per Feature (Slice 07).
- Feature candidate history and diffing.
- Backfilling provenance onto `RequirementAnalysis`.
- Transactional set replacement.
