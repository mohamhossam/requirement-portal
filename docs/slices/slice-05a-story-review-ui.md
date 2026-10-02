# Slice 5A — Story Review UI

## Objective

Give the Story layer the browser review surface the ROADMAP's Slice 5 entry
requires. Slice 5 landed its whole backend — `domain/story/`, `story_workflow`,
`StoryGeneratorPort` with fake/local/openai adapters, and a full story API
(generate, get, edit, split, merge, regenerate, change-proposals) — but shipped
**no UI and no slice spec**. This slice repays that debt for the Story layer
exactly as Slice 4A repaid it for Slices 1–4. It introduces no new domain
concept, no new use case, and no new AI capability.

## Why this slice exists

The product's entire premise is human review of AI-generated backlog content.
Every Story rule already built — sprint-sized stories, structured Given/When/Then
acceptance criteria, provenance, staleness cascade from an edited Feature,
review-before-apply split/merge proposals, forced regeneration over human-owned
content — was designed for a reviewer who currently has no screen. A Product
Owner today can drive Requirement → Analysis → Epic → Features in the browser
(Slice 4A) and then must drop to curl or the OpenAPI page the moment Stories
begin. That is the same "slice without its UI" failure the ROADMAP and AGENTS.md
§15/§18 exist to stop. This slice ends it.

## User Outcome

Under each approved Feature in the existing review page, a Product Owner can:
generate Stories, read each Story in user-story voice with its Given/When/Then
acceptance criteria, see what is AI-generated versus human-edited versus stale,
edit a Story (including its acceptance criteria), regenerate it
(with an explicit confirmation when that would discard human-owned content),
and propose a split or merge and review the AI candidates before applying them —
all without leaving the browser.

## In Scope

- A `frontend/src/features/stories/` module rendering the Story list for one
  Feature, wired into the existing Feature section of `RequirementPage`.
- Per-Story review states made visible: generated, edited, approved, stale,
  with provenance (AI vs human) and staleness reason.
- Story actions against the existing endpoints: generate set, edit,
  regenerate (per-story and whole-set), manual split/merge, and the change-proposal
  review-then-apply/discard flow.
- Destructive regeneration (over edited/approved Stories) gated behind an
  explicit `ConfirmDialog`, never a silent `?force=true`.
- Typed client + query keys + `api.*` methods for every story endpoint,
  regenerated from the current OpenAPI schema.
- A `canGenerateStories` review rule (a Feature must be approved and not stale
  before its Stories are offered), mirroring `canDecompose`.
- Component tests for the story review states and the confirm-on-force path,
  and an extension of the Playwright smoke flow through Stories with
  `LLM_PROVIDER=fake`.
- The Slice 5 spec doc gap closed: this file, plus marking the Slice 5 ROADMAP
  entry's UI status and recording the omission-then-repayment in AGENTS.md §19.

## Out of Scope

- Any new domain concept, value object, use case, port, or adapter. If the UI
  proves the story model or a response shape wrong, that is a finding to raise
  and record — not to absorb here.
- INVEST / SPIDR quality validation (Slice 6). Stories are reviewed for content
  and provenance here, not scored.
- New backend endpoints. Response-shape changes are permitted **only** where the
  UI proves a shape wrong, and each must be recorded as a decision.
- Persistence or revision changes (Slice 10 already landed those).

## Domain

None. See Out of Scope. A required domain change is a finding, not scope.

## Application Use Cases

None. The existing `story_workflow` use cases (`GenerateStories`, `GetStories`,
`EditStory`, `SplitStory`, `MergeStories`, `RegenerateStory`,
`StoryChangeProposals`) are consumed as-is through the HTTP API.

## Ports

None on the backend. The browser talks to the existing HTTP API.

## Adapters

None on the backend. The frontend is the only surface that changes.

## API

No new endpoints. The story routes already exist and are the contract:

- `POST   /requirements/{id}/features/{fid}/stories` — generate set
- `GET    /requirements/{id}/features/{fid}/stories` — get set
- `PUT    /requirements/{id}/features/{fid}/stories/{sid}` — edit
- `POST   /requirements/{id}/features/{fid}/stories/{sid}/split`
- `POST   /requirements/{id}/features/{fid}/stories/merge`
- `POST   /requirements/{id}/features/{fid}/stories/regeneration?force=` — set
- `POST   /requirements/{id}/features/{fid}/stories/{sid}/regeneration?force=`
- `POST   /requirements/{id}/features/{fid}/stories/change-proposals` — create
- `GET    /requirements/{id}/features/{fid}/stories/change-proposals` — list
- `POST   .../change-proposals/{pid}/application` — apply
- `DELETE .../change-proposals/{pid}` — discard

Story approval: the current API has no dedicated `.../approval` route for
Stories (Epic and Feature do). **Decision to settle in Step 0**: either an
`approve` action already exists in the workflow surface to bind to, or approval
is out of scope for 5A and recorded under "Dropped from this slice". Do not add
an endpoint without agreement.

## UI
<!-- Not optional. The ROADMAP Slice 5 entry names a Feature-detail Story
     surface (story tree, story voice, acceptance-criteria editor,
     regenerate/edit/split/merge). That is this slice. -->

New `frontend/src/features/stories/`:

- **`StoryList.tsx`** — renders the `StorySetResponse` for one Feature: an
  ordered list of Story cards, an empty state offering "Generate Stories" gated
  by `canGenerateStories`, and set-level actions (regenerate all, propose merge).
- **`StoryCard.tsx`** — one Story showing: `StatusBadge` (generated / edited /
  approved), the user-story voice line, a Given/When/Then acceptance-criteria
  list, `ProvenanceDetails` (AI vs human), and `StalenessNotice` when stale.
  Actions: Edit, Regenerate, and Split. (Approve is deferred to Slice 9 — see
  Step 0.) Regenerate over non-`generated` content opens a `ConfirmDialog`
  describing the loss.
- **`StoryEditForm.tsx`** — role / action / value fields plus a repeatable
  Given/When/Then acceptance-criteria editor (add/remove rows, minimum one),
  matching `FeatureEditForm` conventions.
- **`StoryProposalPanel.tsx`** — for a pending split/merge proposal, shows the
  AI candidate Stories and Apply / Discard, so the change is reviewed before it
  replaces the current Stories.

Integration: mount `StoryList` inside each approved `FeatureCard` (or directly
under the Feature in `FeatureTree`) in `RequirementPage`, following the existing
query/mutation wiring pattern (`useQuery` per Feature's stories, `useMutation`
per action, `refresh` of the story + revision query keys on success).

Client layer:

- Regenerate `frontend/src/api/schema.d.ts` from the running app's OpenAPI.
- Add `Story`, `StorySet`, `StoryInput`, `AcceptanceCriterion`,
  `StoryChangeProposal` types and the `api.*` story methods to `client.ts`,
  reusing the `request` / `optional` / `?force=true` patterns.
- Add `queryKeys.stories(requirementId, featureId)`.
- Add `canGenerateStories(feature)` and a `storyRegenerationLoss(...)` helper to
  `review/rules.ts`, mirroring `canDecompose` / `regenerationLoss`.

## Business Rules

- A Feature must be approved and not stale before its Stories are offered
  (`canGenerateStories`), consistent with `canDecompose` for the Epic→Feature
  step.
- AI-generated Stories are never silently treated as human-approved; provenance
  and status are always visible.
- Regeneration that would discard edited or approved Story content requires an
  explicit confirmation; there is no silent force in the UI.
- Split and merge go through the change-proposal review surface (create → review
  candidates → apply/discard); the UI never applies an AI split/merge without a
  human confirming the candidates.
- Editing a Feature marks its Stories stale (existing cascade); the UI surfaces
  that staleness and blocks approval of a stale Story.

## Tests

- **Component (`vitest` + Testing Library):**
  - `StoryCard` renders each review state — generated, edited, approved, stale —
    with the correct badge, provenance, and staleness notice.
  - `StoryCard` regenerate over edited/approved content opens the confirm dialog
    and only fires the mutation on confirm.
  - `StoryEditForm` enforces at least one acceptance criterion and round-trips
    Given/When/Then rows.
  - `StoryProposalPanel` shows candidates and wires Apply / Discard.
  - `StoryList` empty state respects `canGenerateStories`.
  - `review/rules.test.ts` covers `canGenerateStories` and the story
    regeneration-loss message.
- **Smoke (`playwright`, `LLM_PROVIDER=fake`):** extend `review-flow.spec.ts` so
  that after approving a Feature the PO generates Stories, sees the voice line
  and acceptance criteria, edits a Story, and — after editing the requirement —
  sees the Stories go "Out of date", proving the cascade reaches the new surface.

## Acceptance Criteria

- [x] Every approved Feature shows its Stories in the browser with voice and
      Given/When/Then acceptance criteria; no step needs curl or the OpenAPI page.
- [x] Generated / edited / stale states are visually distinct and show
      provenance. Story approval is deferred to Slice 9.
- [x] Regenerating over human-owned Story content requires an explicit dialog.
- [x] Split and merge present AI candidates for review before they replace the
      current Stories.
- [x] Editing the requirement (or a Feature) marks the affected Stories stale in
      the UI and blocks Story mutation controls.
- [x] The typed client matches the real OpenAPI schema (schema regenerated, no
      hand-drift).
- [x] Component tests and the extended smoke flow pass.
- [x] All five backend quality gates stay green; frontend lint/typecheck/tests
      green.
- [x] The Slice 5 ROADMAP UI status is updated and the debt is recorded in
      AGENTS.md §19.

## Step 0 decisions (settled before code)

- **Story approval is out of scope for 5A.** The Slice 5 ROADMAP UI entry lists
  "regenerate/edit/split/merge" and no approve action, and no story-approval use
  case or endpoint exists (unlike Epic and Feature). Approval of Stories belongs
  to Slice 9 (Review and Approval Workflow: `ApproveStory` / `RejectStory`).
  The UI therefore shows Story status (generated / edited / stale) and provenance
  but offers no Approve button. Agreed with the roadmap owner before
  implementation. Recorded in AGENTS.md §19.
- **Split and merge expose both ownership paths.** Manual split/merge submits
  reviewer-authored replacements directly, while AI split/merge creates durable
  candidates that must be applied or discarded. The two flows are labelled
  separately so a reviewer can tell who authored the result.
- **A required backend change surfaced and was handled separately.** The merged
  Slice 5/10 commit was not actually green — the API could not start
  (`EditFeature.__init__` misplaced), and lint/type/test gates and the committed
  OpenAPI snapshot were stale. Per §15, that is a finding, not something 5A
  absorbs silently: it was fixed in its own commit ("repair red baseline") ahead
  of the UI work, and the story endpoints were added to `frontend/openapi.json`
  and `schema.d.ts` there.

## Validation Evidence
- `pytest` — 289 passed, 3 skipped (Postgres integration tests, no live DB).
- `ruff check .` — All checks passed.
- `ruff format --check .` — 184 files already formatted.
- `mypy src tests` — Success: no issues found in 153 source files.
- `lint-imports` — Contracts: 2 kept, 0 broken.
- `npm --prefix frontend run lint` — clean.
- `npm --prefix frontend run typecheck` — clean.
- `npm --prefix frontend run api:check` — `schema.d.ts` matches `openapi.json`.
- `npm --prefix frontend test` — 9 files, 35 tests passed (adds
  `StoryCard`, `StoryList`, story rules; updates `FeatureTree`).
- `npx playwright test` (`LLM_PROVIDER=fake`, `PERSISTENCE_PROVIDER=memory`) —
  1 passed: the full Requirement → Analysis → Epic → Features → **Stories** flow,
  including generating Stories, reading voice + Given/When/Then, editing a
  Story's acceptance criteria, and the confirm-before-regenerate guard.

## Dropped from this slice

- **Story approval action** — not in the Slice 5 ROADMAP UI entry; deferred to
  Slice 9. See Step 0. Recorded in AGENTS.md §19.

## Deferred

- INVEST / SPIDR quality scoring and split suggestions (Slice 6).
- Story approval / rejection lifecycle (Slice 9).
- Any story-model or response-shape change the UI reveals (raise as a finding;
  do not absorb).
