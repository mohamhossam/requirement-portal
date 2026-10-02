# Slice 5 — User Stories and Acceptance Criteria

## Objective

Decompose each approved, current Feature into ordered, reviewable User Stories
with structured Given/When/Then acceptance criteria. Preserve human work,
traceability, durable AI previews, and immutable breakdown history through all
Story changes.

## Domain

`UserStory` traces to exactly one `FeatureId` and carries `StoryId`, `UserRole`,
`DesiredAction`, `BusinessValue`, one or more ordered `AcceptanceCriterion`
values, generation status, provenance, and optional staleness. Role, action,
value, and every Given/When/Then part are nonblank. The canonical voice is
derived as `As a [role], I want [action], so that [value].`

Story edits preserve identity and become `edited`. Manual split preserves the
source ID for the first replacement; manual merge preserves the earliest
source ID. AI-applied results are `generated`. Requirement, Epic, and Feature
changes mark descendant Stories stale without deleting them.

## Application

- `GenerateStories` performs initial Feature-by-Feature generation and rejects
  an existing collection.
- `GetStories` keeps stale Stories readable even when upstream analysis has
  been invalidated.
- `EditStory`, `SplitStory`, and `MergeStories` apply human-authored drafts.
- `RegenerateStory` replaces one Story with the same ID or the complete set
  with new IDs; human-owned content requires `force=true`.
- `StoryChangeProposals` creates, lists, applies, and discards durable AI
  split/merge previews. Application rejects a changed source fingerprint.
- Every mutation requires an approved, current parent Feature and runs with its
  revision checkpoint inside one transaction.

## Ports and Adapters

`StoryGeneratorPort`, `StoryRepositoryPort`, and
`StoryChangeProposalRepositoryPort` have deterministic fake, local/Ollama,
OpenAI, in-memory, and PostgreSQL implementations as applicable. Provider
mapping rejects the complete response if any Story field or criterion is
unusable. Focused prompts include the current requirement context, analysis,
approved Epic/Feature, and only operation-specific source Stories; the local
adapter rejects context overflow before calling the provider. If a local model
returns fewer than two split candidates, the adapter retries once with an
explicit corrective prompt and still fails safely if the retry is unusable.

PostgreSQL migration `002` stores ordered Stories and durable proposals.
Snapshots serialize Stories and revision comparison reports Story additions,
removals, and content changes.

## API

- `POST/GET /requirements/{id}/features/{feature_id}/stories`
- `PUT .../stories/{story_id}`
- `POST .../stories/{story_id}/regeneration?force=false`
- `POST .../stories/regeneration?force=false`
- `POST .../stories/{story_id}/split`
- `POST .../stories/merge`
- `POST/GET .../stories/change-proposals`
- `POST .../change-proposals/{proposal_id}/application`
- `DELETE .../change-proposals/{proposal_id}`

Missing resources map to 404, lifecycle conflicts to 409, invalid human input
to 422, and unusable provider output to 502 through the central error map.

## UI

Feature detail renders ordered Story cards with canonical voice, structured
criteria, provenance, status, and staleness. Reviewers can edit criteria,
perform manual split/merge, preview and apply/discard AI split/merge, regenerate
one Story, or regenerate the set. Edited set regeneration requires an explicit
loss confirmation before `force=true`. All mutation controls are disabled with
an explanation while the Feature is unapproved or stale; existing Stories stay
visible.

Story approval remains deferred to Slice 9 by agreement.

## Tests

Coverage includes domain invariants; API/use-case lifecycle, identity, force,
proposal conflict, and staleness behavior; strict adapter mapping; in-memory and
PostgreSQL ordering/durability/revision history; revision comparison; frontend
manual/AI changes, guarded regeneration, disabled controls; and a Chromium
review flow through proposal application and upstream staleness.

## Validation Evidence

- `TEST_DATABASE_URL=... pytest` — 341 passed, including 4 live PostgreSQL
  migration/durability/immutability tests.
- `ruff check .` — all checks passed.
- `ruff format --check .` — 191 files formatted.
- `mypy src tests` — no issues in 157 source files.
- `lint-imports` — 2 contracts kept, 0 broken.
- `npm --prefix frontend run api:check` — generated TypeScript matches OpenAPI.
- `npm --prefix frontend run lint` — passed.
- `npm --prefix frontend run typecheck` — passed.
- `npm --prefix frontend test -- --run` — 10 files, 44 tests passed.
- `npm --prefix frontend run build` — production build passed.
- `npm --prefix frontend run test:smoke` — Chromium flow passed through Story
  generation/editing, AI split preview/application, guarded regeneration, and
  upstream Story staleness.

## Deferred

- Story approval/rejection — Slice 9.
- INVEST/SPIDR quality assessment — Slice 6.
- System/squad mapping and ADO publication — later roadmap slices.

## Defect Correction — 2026-09-10

- Story generation context now binds exactly the Requirement, current analysis, Epic, target
  Feature, and target Feature's Story set supplied to the focused operation. Approval or editing
  of an unrelated sibling Feature no longer rejects a valid in-flight Story result.
- Target Feature approval/editing and every actual source or target mutation remain
  content-bound. Domain, ports, adapters, API, and UI contracts are unchanged, and no roadmap
  field is dropped.
- `pytest tests/unit/test_story_api.py tests/unit/test_ai_jobs.py -q` — PASS, 23 tests.
- `pytest -q` — PASS; PostgreSQL-dependent tests skipped because `TEST_DATABASE_URL` was not set.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 429 files formatted.
- `mypy src tests` — PASS, 339 source files.
- `lint-imports` — PASS, 6 contracts kept and 0 broken.
