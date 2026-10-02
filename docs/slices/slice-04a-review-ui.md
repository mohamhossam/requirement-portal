# Slice 4A — Review UI

> Status: **delivered**. The browser review flow, generated API contract,
> component tests, full-flow smoke test and CI jobs are implemented.

## Objective

Give the Requirement → Analysis → Epic → Features flow a review surface a
Product Owner can actually use, repaying the UI debt carried from Slices 01–04.

## Why this slice exists

`ROADMAP.md` named a UI in Slices 1, 2, 3 and 4. Each shipped without one, and
none recorded it as a decision. The result is a human-review product with no
review surface: staleness, approval revocation, forced regeneration and the
flag-don't-destroy rule were all designed for a reviewer nobody has watched
work, and every response shape was designed for screens that do not exist.

This slice adds no domain concepts and no AI capability. It makes what already
exists usable, and — just as importantly — tests whether the API is right.

## User Outcome

A Product Owner can, in a browser:

1. Submit a requirement and edit it.
2. Read its analysis, with assumptions and open questions visibly separated
   from facts and constraints.
3. Review the Epic, edit it, approve it, or regenerate it.
4. Review the Feature tree, edit and approve Features individually.
5. See at every step what is AI-generated, what a human has touched, what is
   approved, and what has gone stale — and why.

## Scope decision

The plan covers **read plus review actions**, not read-only.

A reviewer who cannot approve is not reviewing, and the roadmap's UI entries
name edit, approve and regenerate explicitly. But the implementation order
below lands the read-only tree first, so the API-shape question — the main
thing this slice is meant to answer — gets answered early and cheaply, before
any mutation UI is built on a shape that might change.

There is no automatic scope cut if the slice runs long. Any omission from the
roadmap scope must be raised with the user before implementation and recorded
under **Dropped from this slice**, per `AGENTS.md` §15.1.

## In Scope

- A `frontend/` workspace: TypeScript, React, Vite, per `WORKSPACE.md` §13.
- A typed API client generated from or checked against the live OpenAPI schema.
- Requirement form: create and edit.
- Empty-state actions that advance the pipeline: analyse, generate Epic, and
  decompose the approved Epic into Features.
- Analysis panel with the fact/assumption separation made visual and the whole
  analysis labelled as an AI-generated candidate, not approved business truth.
- Epic review card: content, provenance, status, staleness, with edit, approve
  and regenerate.
- Feature tree under the Epic: per-Feature outcome, delivery drop, splitting
  pattern and rationale, status and staleness, with edit and approve.
- An explicit confirmation step for any destructive action.
- Component tests for the review states, and one smoke test driving the full
  flow against the running API.
- CI extended to build, lint and test the frontend.

## Out of Scope

- User Stories and acceptance criteria (Slice 05) — the screens for those come
  with that slice, under the new §15.1 rule.
- Authentication, multi-user, and any notion of who approved something.
- Listing or searching requirements; the UI works from a requirement id.
- Split and merge of Features, still deferred from Slice 04.
- Feature-set regeneration after the initial decomposition. Slice 4A exposes
  the roadmap's per-Feature edit and approve actions; it does not expose the
  set-replacement operation, so the browser never sends `force=true` to the
  Feature endpoint in this slice.
- Styling beyond what makes review state legible. This is a review tool, not a
  design exercise.
- Server-side rendering, offline support, i18n.

## Backend Changes

No new endpoints, use cases or domain changes were required. Existing interface
schemas were refined without changing JSON values:

- `EpicProvenanceResponse` / `EpicStalenessResponse` became the artifact-neutral
  `ProvenanceResponse` / `StalenessResponse` components;
- review status, stale reason, Feature delivery drop and splitting pattern are
  closed OpenAPI enums rather than unrestricted strings;
- Feature edit requests use the same closed delivery/splitting choices already
  enforced by the application layer.

Two things are permitted and must be recorded if they happen:

1. **A response shape the UI proves wrong.** This is a likely and welcome
   outcome — it is why the slice is worth doing now. Each change gets a note in
   this spec and contract tests. An ADR is required only if the change is a
   structural decision under `docs/architecture/README.md`, not merely because
   an OpenAPI contract changed.
2. **A missing read.** The UI works from a requirement id because there is no
   list endpoint. If that proves unworkable in practice, raise it rather than
   quietly adding `GET /requirements`.

A domain change requested by the UI is a finding about the model, not a task
for this slice. Raise it.

## UI

### Screens

One page per requirement, with four stacked sections mirroring the pipeline:

| Section | Shows | Actions |
|---|---|---|
| Requirement | title, description, status, human-input label | create, edit |
| Analysis | facts, constraints, business rules / assumptions, open questions, ambiguities, AI-candidate label | analyse when absent, re-analyse with confirmation when present |
| Epic | name, outcome, business case, status, staleness, provenance | generate when absent; edit, approve, regenerate when present |
| Features | tree of Features under the Epic | decompose when absent; edit, approve per Feature when present |

### Ownership and review state, made visible

The whole point of the screen is to preserve the distinction between source
input, AI output, and human action:

- the Requirement is labelled **Human-provided input**;
- the Analysis is labelled **AI-generated candidate — not human-approved**;
- the Epic and Features show their review status and original AI provenance.

Every reviewable generated item — Epic and Feature — shows:

- **status** — generated / edited / approved, distinguishable without colour
  alone,
- **staleness** — when set, the reason (`requirement_changed`,
  `epic_changed`) and since when, stated in words rather than a badge alone,
- **provenance** — model and prompt version under the label **Original AI
  generation**, on demand rather than shouting. This avoids implying that the
  model produced later human edits.

`RequirementAnalysis` has no lifecycle, timestamp, model or prompt provenance
today. Slice 4A must not invent those values. The static AI-candidate label is
the truthful UI available within the roadmap's no-domain-change constraint;
the missing provenance remains the recorded pre-Slice-09 debt.

Two rules the backend already enforces must be legible *before* the user acts,
not only as a rejected request:

- a stale item cannot be approved — the approve control explains why, rather
  than failing with a 409,
- regenerating over edited or approved content destroys work — the control
  says exactly what will be lost and requires confirmation before sending
  `?force=true`.

### Fact versus assumption

`AGENTS.md` §7 makes this the product's core distinction, and it must survive
into the UI: known facts, constraints and business rules in a group labelled
**Extracted from the requirement**; assumptions, open questions, ambiguities
and potential dependencies in a visibly separate group labelled **Needs
confirmation**. The heading **Confirmed** must not be used: the current model
records no human confirmation of the analysis. The groups must be structural,
not merely differently styled lists.

## Tests

**Component** — each review state renders correctly: generated, edited,
approved, stale-with-reason; ownership labels are truthful; the approve control
is disabled and explained for a stale item; the regenerate confirmation
appears for human-owned Epic content and not for untouched content;
re-analysis requires confirmation when an analysis already exists; assumptions
render in the needs-confirmation group.

**Smoke** — one test drives the real flow against the API with
`LLM_PROVIDER=fake`: create → analyse → generate Epic → approve → decompose →
approve a Feature → edit the requirement → both Epic and Features show stale,
the approved Feature keeps its content, and re-approval is refused.

That smoke test is the slice's real acceptance criterion. It is also the first
test in the repository that exercises the backend the way a user does.

## Acceptance Criteria

- [x] The full flow is usable in a browser with no curl and no OpenAPI page.
- [x] Epic and Feature status, staleness and original AI provenance are
      visible; Analysis is explicitly labelled as AI-generated and does not
      fabricate unavailable provenance.
- [x] Requirement, Analysis, Epic and Feature sections distinguish human input,
      AI output and human review actions.
- [x] Assumptions are visually separated from facts.
- [x] A stale item's approve control explains itself before the user clicks.
- [x] Regeneration over human-owned content requires explicit confirmation.
- [x] No new backend endpoint; response-schema refinements are recorded here.
- [x] Frontend build, lint and tests run in CI.
- [x] Backend gates still green.
- [x] README and WORKSPACE document how to run the browser flow and its tests.
- [x] No Story, INVEST, or architecture-mapping functionality added.

## Implementation Order

1. `frontend/` scaffold (Vite, TypeScript, React), wired into CI as a separate
   job so a frontend failure is legible on its own.
2. Typed API client checked against the live OpenAPI schema.
3. **Read-only view**: requirement, analysis, Epic, Feature tree, with status
   and staleness rendered. Stop here and assess the API shape before going on.
4. Requirement create/edit and Analysis analyse/re-analyse, with replacement
   confirmation.
5. Epic generate, edit, approve and regenerate — with prerequisites and the
   confirmation flow.
6. Initial Feature decomposition plus Feature edit and approve, per item.
7. Component tests for the review states.
8. Smoke test across the full flow.
9. Update this spec with Validation Evidence and record any API change.

Step 3 is the checkpoint. If the API shape is wrong, it is far cheaper to find
out with a read-only view than after building six mutation flows on it.

## Detailed Build Plan

The section above says *what* Slice 4A delivers. This one says *how*, file by
file, so the work can be picked up without re-deriving the decisions.

### Step 0 — Decisions to settle before any code

These are cheap now and expensive after step 4.

| Question | Decision | Why |
|---|---|---|
| Cross-origin dev | Vite dev-server proxy: `/api/*` → `http://127.0.0.1:8000`. **No CORS middleware in the backend.** | Keeps the "no backend change" promise. CORS becomes a real question only when the UI is deployed on its own origin, which this slice does not do. |
| API base URL | `VITE_API_BASE` defaulting to `/api`; the proxy strips the prefix. | One switch for dev, preview and the Playwright run. |
| Client state | `@tanstack/react-query`. | The cascade *is* cache invalidation: editing the requirement invalidates analysis, Epic and Features; approving an Epic unlocks decomposition. Hand-rolling that across four resources costs more than the dependency. |
| No list endpoint | The requirement id lives in the URL (`/requirements/:id`), with the last id kept in `localStorage` purely as a convenience. A landing route offers "create new" or "open by id". | `GET /requirements` does not exist and this slice does not add it. In-memory persistence means a server restart makes a remembered id 404 — that path must render an explicit empty state, not a crash. |
| Analysis language | “Extracted from the requirement” and “Needs confirmation”; never “Confirmed”. | Analysis is AI output without a human-confirmation lifecycle. Calling it confirmed would turn classification into business truth. |
| Feature regeneration | Initial decomposition only; no set-regeneration control after Features exist. | The Slice 4A roadmap names per-Feature edit and approve, not replacement of the whole set. This keeps the browser from needing the destructive Feature `force=true` path. |
| Component tests | Vitest + React Testing Library + MSW. | Standard for the Vite/React baseline in `AGENTS.md` §11. |
| Smoke test | Playwright, Chromium only, one spec, against a real `uvicorn` with `LLM_PROVIDER=fake`. | This slice exists because "specified" was mistaken for "works" four times. A test that never opens a browser cannot retire that debt. It runs as its own CI job so its cost and its flakes stay legible. |

### Step 1 — `frontend/` scaffold and CI

Files:

```text
frontend/
├── package.json          # scripts: dev, build, preview, lint, typecheck, test, test:smoke
├── package-lock.json     # committed; required by npm ci and setup-node caching
├── tsconfig.json         # strict: true, noUncheckedIndexedAccess: true
├── vite.config.ts        # server + preview /api proxy → 127.0.0.1:8000
├── eslint.config.js
├── vitest.config.ts      # jsdom, setup file for RTL + MSW
├── playwright.config.ts  # chromium, webServer: uvicorn + vite preview
├── index.html
└── src/main.tsx          # renders <App/>, nothing else
```

Root `.gitignore` also gains `frontend/node_modules/`, `frontend/dist/`,
frontend coverage, `frontend/playwright-report/` and
`frontend/test-results/`.

CI (`.github/workflows/ci.yml`) gains two jobs beside `quality-gates`:

- **`frontend`** — `setup-node@v4` (Node 22, `cache: npm`,
  `cache-dependency-path: frontend/package-lock.json`); every npm command runs
  with `working-directory: frontend`: `npm ci`, `npm run api:check`,
  `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`.
- **`smoke`** — needs `frontend`, but does not assume another job's filesystem
  or build output is shared. It checks out the repository, installs Python and
  `-e ".[dev]"`, installs Node, runs `npm ci` and `npm run build` in
  `frontend/`, installs Chromium with Playwright, and then runs
  `npm run test:smoke`. The Uvicorn web server receives
  `LLM_PROVIDER=fake` explicitly through Playwright's `webServer.env` or the CI
  step environment.

Separate jobs, not extra steps, so a frontend failure never reads as a backend
failure. If the smoke test uses `vite preview`, `preview.proxy` must carry the
same `/api` rewrite as `server.proxy`; otherwise `/api/*` never reaches Uvicorn.

**Verifiable on its own:** a page rendering the result of `GET /health` through
the proxy. Nothing else. If that is red, nothing after it is worth debugging.

### Step 2 — The typed client, checked against the real schema

```text
frontend/openapi.json          # snapshot, committed
frontend/src/api/schema.d.ts   # generated by openapi-typescript, committed
frontend/src/api/client.ts     # thin typed functions over fetch
frontend/src/api/errors.ts     # ApiError with normalised string/array/network detail
scripts/dump_openapi.py        # writes frontend/openapi.json from the app
tests/unit/test_openapi_snapshot.py
```

The snapshot check lives in **pytest**, not npm: `app.openapi()` must equal
`frontend/openapi.json`, and the failure message says to re-run
`python scripts/dump_openapi.py`. A second check, `npm run api:check`, generates
TypeScript from the committed snapshot into a temporary file and compares it
with `src/api/schema.d.ts`. The two checks form the full chain:

```text
running FastAPI schema == openapi.json == generated schema.d.ts
```

Checking only the first equality does not prove the committed TypeScript is
current.

Client surface, one function per existing endpoint and no more:

```ts
createRequirement, getRequirement, updateRequirement
analyzeRequirement, getAnalysis
generateEpic(force?), getEpic, editEpic, approveEpic
generateFeatures, getFeatures, editFeature, approveFeature
```

`generateFeatures` deliberately exposes no `force` argument in Slice 4A. The
same endpoint performs initial decomposition and set replacement, but this UI
supports only the first operation; omitting the parameter makes that scope
decision executable rather than relying on every caller to remember it.

Rule: a `404` from `getAnalysis` / `getEpic` / `getFeatures` resolves to
`null` ("not generated yet"), because that is the *normal* state of a fresh
requirement. Every other non-2xx becomes an `ApiError` carrying the server's
normalised `detail`, which is what the UI shows. FastAPI may return a string
for mapped domain errors or an array for request-validation errors, so error
normalisation must handle both plus network failures. Nothing else interprets
status codes.

The current OpenAPI response schemas declare review values as unrestricted
`str`, so generated TypeScript would reduce `status`, stale `reason`,
`delivery_drop` and `splitting_pattern` to `string`. At the read-only
checkpoint, refine those response schemas to enums/Literals (or add an equally
strict runtime refinement) so the UI rules operate on closed unions. The
preferred backend refinement is JSON-identical and remains an interface-layer
change; record it under API findings and cover the OpenAPI contract in tests.

### Step 3 — Read-only view. **This is the checkpoint.**

```text
src/app/App.tsx, src/app/routes.tsx
src/features/requirement/RequirementPanel.tsx
src/features/analysis/AnalysisPanel.tsx
src/features/epic/EpicCard.tsx
src/features/features/FeatureTree.tsx, FeatureCard.tsx
src/components/{Section,StatusBadge,StalenessNotice,ProvenanceDetails,EmptyState,ErrorNotice}.tsx
```

One page, four stacked sections in pipeline order. Epic and Feature show:

- **status** — `StatusBadge` renders the word (`Generated` / `Edited` /
  `Approved`) plus a shape, never colour alone;
- **staleness** — `StalenessNotice` turns `{reason, since}` into a sentence:
  "Out of date since 14:02 — the requirement changed after this was
  generated." The enum stays the contract; the sentence lives in the UI;
- **provenance** — `ProvenanceDetails` is a collapsed `<details>` labelled
  “Original AI generation” and showing model and prompt version. Available,
  not shouting and not presented as the source of later human edits.

`AnalysisPanel` splits into two *structurally separate* groups with their own
headings — **Extracted from the requirement** (known facts, constraints,
business rules) and **Needs confirmation** (assumptions, open questions,
ambiguities, potential dependencies). A banner identifies the entire analysis
as AI-generated and not human-approved. Per `AGENTS.md` §7 this must be
structure, not styling: a stylesheet failure must not merge them.

The requirement query is the parent query. Analysis, Epic and Feature queries
are enabled only after the Requirement resolves successfully. This matters
because each child endpoint can return the same 404 both when its own artifact
is absent and when the Requirement is absent; firing them for a missing parent
would mislabel “requirement not found” as three normal empty states.

**Checkpoint findings, confirmed during implementation:**

1. **Four requests and three expected 404s** render a fresh Requirement page. A single
   `GET /requirements/{id}/review` would be one call and one state. That is a
   new endpoint and therefore *out of scope* — record it, do not build it.
2. **`FeatureResponse` carried `EpicProvenanceResponse` and
   `EpicStalenessResponse`.** Harmless in JSON, ugly in generated TypeScript,
   where a Feature has a field typed `EpicStalenessResponse`. Renaming them to
   `ProvenanceResponse` / `StalenessResponse` is a shape the UI proves wrong,
   is JSON-identical and was applied as the permitted response-contract
   refinement.
3. **Review values are open strings in OpenAPI.** `status`, stale `reason`,
   `delivery_drop` and `splitting_pattern` need closed response types for the
   generated client and `rules.ts` to be meaningfully typed. Prefer
   JSON-identical enum refinements were applied and are asserted in the backend
   OpenAPI snapshot test.
4. **The analysis has no provenance and no timestamp**, so the analysis panel
   cannot answer "what produced this?" while every other panel can. This
   confirms an existing §19 debt entry. It remains scheduled before Slice 09;
   Slice 4A uses a truthful static AI-candidate label and does not claim
   unavailable provenance.
5. **`POST /analysis` overwrites silently** (also §19 debt). The delivered UI
   confirms before re-analysing. This is a UI-side guard; the backend
   regeneration-semantics debt remains open.

### Step 4 — Requirement and Analysis actions

`RequirementForm` (create and edit share it). Blank title or description is
blocked client-side *and* a 422 from the server still renders — client
validation is a courtesy, never the authority.

Creating a Requirement navigates to `/requirements/:id`. When Analysis is
absent, its empty state offers **Analyse requirement**. When Analysis exists,
the action becomes **Re-analyse** and opens a confirmation explaining that the
existing AI output will be replaced; the browser never treats the current
overwrite behaviour as harmless merely because the backend lacks `force`.

On a successful edit, invalidate analysis, Epic and Feature queries: the
backend has just deleted the analysis and marked the Epic and its Features
stale, and a stale screen would be lying about the very thing this slice
exists to show.

### Step 5 — The review rules module

```text
src/review/rules.ts   # pure, no React, no fetch
```

The heart of the slice, and the most-tested file in it:

```ts
canApprove(item): { ok: true } | { ok: false, reason: string }
canGenerateEpic(analysis, epic): ...        // no analysis → explain, don't 404
canDecompose(analysis, epic): ...           // analysis + approved/current Epic
regenerationLoss(epic, features): LossReport | null   // drives confirm + force
```

**Standing rule for this module: it may only ever *explain and disable*, never
*permit*.** The server stays the authority; every 409 path must still render.
A component test asserts exactly that — a server 409 on an approve the UI
thought was fine shows the server's `detail`, it does not crash and does not
swallow.

React Query invalidation is a written matrix, not ad hoc calls hidden in
components:

| Mutation | Queries invalidated or updated |
|---|---|
| create Requirement | navigate to the returned id; seed/invalidate Requirement |
| edit Requirement | Requirement, Analysis, Epic, Features |
| analyse / re-analyse | Analysis |
| generate / edit Epic | Epic, Features |
| approve Epic | Epic |
| initial Feature decomposition | Features |
| edit / approve Feature | Features |

The Epic row includes Features because both Epic editing and regeneration mark
existing Features stale in the backend. Missing that invalidation would show
the exact stale state this slice exists to expose.

### Step 6 — Epic edit, approve, regenerate

An absent Epic renders **Generate Epic**, disabled with an explanation until an
Analysis exists. A present Epic renders `EpicEditForm` plus three controls on
`EpicCard`:

- **Approve** — disabled when `canApprove` says no, with the reason rendered
  *next to the control*, not in a tooltip and not after a failed request.
- **Edit** — inline form; on save the card shows `Edited` and staleness clears,
  because the backend clears it (ADR-0003). The UI reflects that; it does not
  argue with it.
- **Regenerate** — if `regenerationLoss` returns null (untouched, generated
  content) it just regenerates. Otherwise a `ConfirmDialog` names what is
  destroyed — "This Epic has been approved. Regenerating replaces its content
  and its approval, and marks its 3 Features out of date." — and only then does
  the request go out with `force=true`. `force=true` is never sent without a
  confirmation the user read.

### Step 7 — Feature decomposition and per-item review

`FeatureCard` shows name, outcome, delivery drop, splitting pattern, splitting
rationale, status, staleness and provenance, with per-Feature edit and approve.
Editing one Feature must visibly leave its siblings alone — that is the
invariant Slice 04 built and nobody has watched.

When no Features exist, the empty state offers **Decompose into Features**.
Decomposition is gated by `canDecompose(analysis, epic)`: missing Analysis or
an unapproved/stale Epic explains itself instead of producing a 404/409. Once
Features exist, Slice 4A shows no Feature-set regeneration action; the user can
edit and approve items individually, and the browser never sends Feature
`force=true`.

### Step 8 — Tests

**Component** (`frontend/src/**/*.test.tsx`):

- `StatusBadge` renders the status word for each of the three states.
- Requirement and Analysis show “Human-provided input” and “AI-generated
  candidate — not human-approved” respectively.
- `AnalysisPanel` places assumptions, open questions, ambiguities and potential
  dependencies under "Needs confirmation" and facts, constraints and rules
  under "Extracted from the requirement" — asserted by heading and structure,
  never by CSS class. The word "Confirmed" is absent.
- Empty Analysis, Epic and Feature sections expose Analyse, Generate Epic and
  Decompose actions respectively, with prerequisite explanations.
- Re-analysis over an existing Analysis opens confirmation before the POST.
- `EpicCard` stale → approve disabled, reason names the cause and the time.
- `EpicCard` generated + untouched → regenerate sends no confirm and
  `force` unset.
- `EpicCard` approved → regenerate opens the confirm, names the loss, and
  sends `force=true` only after confirmation.
- `EpicCard` server 409 on approve → the server's detail is rendered.
- `FeatureCard` renders all six review fields; approve disabled when stale.
- `FeatureTree` edit on one Feature leaves the other cards unchanged.
- A present Feature set exposes no set-regeneration/force control.
- `RequirementForm` blocks blank input, and renders a server 422.
- `ApiError` renders both a mapped string detail and FastAPI's array-shaped
  request-validation detail without crashing.
- `ProvenanceDetails` starts collapsed, is labelled “Original AI generation”,
  and reveals model and prompt version.
- Query tests assert child reads wait for a successful Requirement read and the
  invalidation matrix refreshes Features after Epic edit/regeneration.
- `rules.ts` unit tests for every branch, no DOM.

**Smoke** (`frontend/tests/smoke.spec.ts`, Playwright, `LLM_PROVIDER=fake`) —
one spec, the whole flow, and the slice's real acceptance criterion:

1. create a requirement → 2. analyse → 3. generate the Epic → 4. approve it →
5. decompose into Features → 6. edit one Feature and approve it →
7. edit the requirement → assert the Epic and **every** Feature show stale with
`requirement_changed`; the edited-and-approved Feature still shows the human
text; its approve control is disabled with an explanation; the analysis panel
shows its empty state (the backend deleted it); Epic generation is disabled
with a re-analysis explanation → 8. re-analyse → 9. request Epic regeneration
and assert confirmation appears before `force=true` is sent and the replacement
succeeds.

### Step 9 — Close out

Fill in Validation Evidence with all five backend gates plus
`npm run lint / typecheck / test / build / test:smoke`, record every API change
made under step 3, and add any new debt to `AGENTS.md` §19.

Update `README.md` and `WORKSPACE.md` with:

- the two-process local run workflow (`LLM_PROVIDER=fake` Uvicorn plus Vite),
- the browser URL and create/open-by-id routes,
- frontend install, lint, typecheck, component-test, build and smoke commands,
- the `/api` proxy and `VITE_API_BASE` behaviour,
- the in-memory restart limitation.

Remove the README's “Backend only / no user interface” status once the UI and
smoke test are delivered.

### What must not happen in this slice

- No new endpoint, no new use case, no domain change. A domain change the UI
  seems to need is a **finding**, raised here, not absorbed.
- No Story, acceptance-criteria, INVEST or architecture-mapping screens.
- No auth, no reviewer identity, no requirement list or search.
- No Feature split/merge.
- No Feature-set regeneration control. Initial decomposition and per-Feature
  edit/approve are the Slice 4A roadmap scope.
- No visual design beyond making review state legible.
- No fix for the backend rules the UI exposes as wrong. Watching the flow is
  likely to confirm that clearing staleness on any edit is too loose
  (ADR-0003). That is a Slice 09 finding. Write it down; leave it alone.

## Risks

- **This is the first frontend in the repository.** Toolchain, CI wiring and
  conventions all land at once, alongside the feature work. Step 1 being small
  and separately verifiable matters more than usual.
- **Scope creep into design.** The bar is "review state is legible", not
  "looks like a product". Resist.
- **API churn mid-slice.** Expected, and the reason for the step 3 checkpoint —
  but each change must be recorded, not absorbed.
- **A generated client can still be weakly typed.** Snapshot equality alone
  does not close string-valued review enums or prove `schema.d.ts` was
  regenerated. The enum/Literal checkpoint and two-link drift check are exit
  work, not optional polish.
- **CI jobs do not share files.** The smoke job must install and build its own
  frontend even though it depends on the frontend job; `needs` supplies status,
  not `node_modules` or `dist`.
- **The backend rules may prove wrong.** If watching the flow shows that, for
  example, clearing staleness on any edit is too loose (already flagged in
  ADR-0003), that is a finding for Slice 09, not a fix to smuggle in here.

## Validation Evidence

Local validation completed on 2026-08-31. The CI workflow contains equivalent
backend, frontend and browser-smoke jobs; a remote CI run was not observed as
part of this local implementation task.

| Command | Result |
|---|---|
| `pytest` | PASS — 231 tests passed |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS — 132 files already formatted |
| `mypy src tests` | PASS — 111 source files checked |
| `lint-imports` | PASS — 2 architecture contracts kept |
| `npm run api:check` | PASS — generated API types match committed OpenAPI contract |
| `npm run lint` | PASS |
| `npm run typecheck` | PASS |
| `npm run test` | PASS — 6 files, 16 tests |
| `npm run build` | PASS — Vite production build completed |
| `npm run test:smoke` | PASS — 1 Chromium full-flow test |

## Dropped from this slice

Nothing. Every field of the Slice 4A roadmap entry was delivered.

## Deferred

- Requirement listing and search.
- Authentication and reviewer identity.
- Story and acceptance-criteria screens (Slice 05).
- Split and merge of Features.
- Feature-set regeneration UI.
- Visual design beyond legibility.

## Repeat-approval guard refresh — 2026-09-03

Approved Epic and Feature versions now render a disabled `Approved` action.
The approval rule remains unavailable until an edit or regeneration produces
a new reviewable version. This is a UI permission correction only; the
existing idempotent domain and API approval behavior is unchanged.

| Command | Result |
|---|---|
| `pytest -ra` | PASS — 400 passed, 5 PostgreSQL tests skipped because `TEST_DATABASE_URL` is absent |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS — 238 files already formatted |
| `mypy src tests` | PASS — 196 source files checked |
| `lint-imports` | PASS — 2 architecture contracts kept |
| `npm --prefix frontend run api:check` | PASS |
| `npm --prefix frontend run lint` | PASS |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend test` | PASS — 14 files, 66 tests |
| `npm --prefix frontend run build` | PASS |
