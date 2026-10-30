# Enhancement — Story point estimates

## Objective

Let a team size User Stories in story points inside the portal: the AI suggests a relative size for
each of a Feature's Stories, a person accepts it, chooses another or leaves the Story unsized, and
only the confirmed sizes reach totals, review, export and Azure DevOps (ADR-0121).

## User Outcome

On a Feature's Stories, a reviewer selects **Suggest sizes**. Each Story then shows "AI suggests 5
points" with a one-sentence reason (or why it cannot be sized) and an **Accept** button, beside a
Story points select for the team's own size. The Feature heading shows "21 points · 4 of 5 sized";
Review & approve shows each Story's size and the backlog total; the export, the Business
Requirements Document and the Azure DevOps work items carry the confirmed size.

## In Scope

- Suggesting sizes for one Feature's Stories as a durable AI job, with provenance and freshness.
- Recording, changing and clearing a confirmed size, attributed and with its basis.
- Feature and backlog totals of confirmed sizes; size badges on the Story card, the Feature's Story
  list and Review & approve.
- Export schema 1.8, Excel columns, BRD schema 1.4, ADO story-points field and republish.

## Out of Scope

- Velocity, capacity or any conversion of points into time.
- A configurable scale or T-shirt sizes.

## Domain

- `breakdown/domain/story/estimate.py`: `StoryPoints` (1, 2, 3, 5, 8, 13), `EstimateBasis`,
  `StoryEstimate`, `EstimateSuggestion`, `FeatureEstimateSuggestions`, `EstimateTotal`,
  `estimate_total`.
- `UserStory.estimate` and `UserStory.sized()` — a human edit; the same size again is a no-op.
- `artifact_fingerprint` covers `story_points` only when set; `ArtifactApprovalState.story_points`.

## Application Use Cases

- `SuggestStoryEstimates`, `GetStoryEstimateSuggestions`, `SetStoryEstimate`
  (`breakdown/application/use_cases/story_estimates.py`).
- `AiJobOperation.SUGGEST_STORY_ESTIMATES`, dispatched by `ExecuteAiJob`, gated by the stories
  generation context.
- Errors: `StoryEstimationError` (502), `StoryEstimateSuggestionsNotFoundError` (404),
  `StoryEstimateSuggestionsConflictError` (409).
- Export, BRD, approval completion and publication plan carry confirmed sizes.

## Ports

- `StoryEstimatorPort`, `StoryEstimateSuggestionRepositoryPort`.

## Adapters

- `StructuredStoryEstimatorAdapter` (local, OpenAI, OpenRouter, profiles on the `review` client) with
  prompt `story-estimate-v1`, schema and `request_complete_estimates` (one retry for Stories left out
  or unexplained; unknown or duplicate labels fail); `FakeStoryEstimator` for offline mode.
- In-memory and Postgres suggestion repositories; migration
  `202610301200_feature_estimate_suggestions.sql`; Story codec writes `estimate` only when set.
- XLSX columns; BRD outline; ADO adapter `story_points_field` (`ADO_STORY_POINTS_FIELD`).

## API

- `POST /requirements/{id}/ai-jobs` with `operation: suggest_story_estimates`.
- `GET /requirements/{id}/features/{feature_id}/stories/estimate-suggestions`.
- `PUT /requirements/{id}/features/{feature_id}/stories/{story_id}/estimate`.
- `StoryResponse.estimate`, `StorySetResponse.estimate_total`, approval-workflow `story_points` and
  completion totals, publication preview `story_points`. Regenerated OpenAPI types.

## UI

- `StorySizePanel` on each Story card, after the readiness checks: the question "How big is this
  Story, compared with the others?" with what a point means; the AI suggestion on the provenance
  register (spark glyph, sunken ground) with one **Accept** and "Choose another size" behind it; a
  confirmed size collapsed to who decided it and when, with **Change size**; **Suggest sizes** from
  the Story itself when there is no current suggestion; confirmation before re-sizing an approved
  Story; focus back on the heading and the new size announced after a save.
- `SizeBadge` (upright weight glyph) in the card's meta row, the Feature's compact Story list and
  Review & approve's Story decisions, where the basis is read out and an unsized Story says "Not
  sized yet"; the Feature total under the Story count; a "Backlog size" line kept apart from the
  approval counts; **Suggest sizes** in the Story list toolbar and an out-of-date warning card with
  **Suggest sizes again**; job labels; publication copy names story points.
- `StorySizeCell` on each row of the Feature's Story list: the confirmed size, or the AI's
  suggestion with "Why?" and **Accept** — points are relative, so the list, with every sibling in
  view, is where most sizes are decided. While a size is open on a Story's own page, the other
  Stories are listed with their sizes; an overridden suggestion becomes a one-line footnote;
  choosing the AI's own number records it as accepted; a Story the AI could not size offers
  **Suggest a split**; the picker takes focus on open and returns it on Cancel; gated controls keep
  their tab stop. The out-of-date notice is amber only while a Story is unsized. Review & approve
  shows who decided each size and links an unsized Story to its size section.
- A row's Accept says its own outcome: an inline error when the save fails, an announcement when
  it succeeds, and focus on the new size. Who decided is worded one way everywhere ("AI suggestion
  accepted by …" / "Set by …"; the approval workflow carries the name). The AI's reasoning stays
  beside the picker; the comparison is the Feature's Stories smallest first, with this Story placed
  on it; an unsized Story says so in its header; the confirmation names the act (set, change,
  clear). Review & approve advises "size it before approving" and links to the Story with a way
  back that lands on the size question.
- Revised after three `/impeccable critique` runs (25 → 28 → 26/40; `.impeccable/critique/`). The
  Story still reads "Edited" after a size change, by decision: a size is approved content, and the
  size section says so where the act happens. Six size buttons and "accept all" were considered
  and declined.

## Business Rules

- Only a person confirms a size; the AI's is a suggestion until accepted.
- Accepting must match the current suggestion for that Story's current content.
- A size is part of what approval attests to; changing one reopens the Story's approval.
- Totals count confirmed sizes and say how many Stories are sized.

## Tests

- `tests/unit/breakdown/test_story_estimates.py`: scale, suggestion invariants, totals, approval
  revocation and replay, fingerprint stability, codec round trip, mapper (order, retry, unknown,
  duplicate, empty), API flow (suggest, accept, total, clear), accept-must-match, freshness after an
  edit, error status codes, failed job as `story_estimation`.
- Export, BRD and ADO publisher tests; error map; OpenAPI snapshot; characterisation goldens
  unchanged for unsized Stories.
- Vitest: `StorySizePanel.test.tsx`; StoryCard, StoryList, review panel fixtures.

## Acceptance Criteria

- [x] A reviewer can request size suggestions for a Feature's Stories and see each with its reason.
- [x] A reviewer can accept a suggestion, enter another size, or clear a size.
- [x] Totals show confirmed points and how many Stories are sized.
- [x] Export, BRD and Azure DevOps carry confirmed sizes only.
- [x] Existing approvals, fingerprints and context tokens are unchanged for unsized Stories.

## Validation Evidence

Run locally on `feat/story-point-estimates`, 2026-10-30 (Windows; CI is the authority):

- `pytest` with `TEST_DATABASE_URL` set (throwaway pgvector/pg17) — PASS except
  `test_database_session_limits_postgres.py::test_a_transaction_left_idle_too_long_loses_its_session`,
  which fails identically on the base commit `a55ddb9` (Windows surfaces the server's idle-session
  disconnect as a connection abort); unrelated to this change.
- `ruff check .` — PASS. `ruff format --check .` — PASS (1372 files).
- `mypy src tests` — PASS (776 source files). `lint-imports` — PASS (43 contracts kept).
- `npm run api:check` — PASS. `npm run lint` — PASS. `npm run build` — PASS.
- `npx vitest run` — PASS (69 files, 609 tests).
- `npx playwright test` — 47 passed, 5 skipped, 2 failed on the pinned export `schema_version`
  "1.7"; after updating the pin to "1.8", `-g "submitted Story rejection"` — PASS in both
  projects. The desktop journey is extended with suggest, accept and the Feature total.
- Manual check in the browser against the fake API: suggestion, accept, badge, Feature total and the
  Review & approve total render in the dark theme.

## Dropped from this slice

Agreed with the requester before implementation (AGENTS.md §15.1):

- Totals in the side-rail backlog tree and on the Epic page's Feature rows.
- A "Story points" fact in revision comparison (a size change still shows as a changed Story).
- Suggesting sizes automatically during Story generation.
- Readiness warnings for unsized Stories.

## Deferred

The four items above, to be scheduled if teams ask for them.
