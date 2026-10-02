# Slice 6 — INVEST / SPIDR Quality Validation

## Objective

Make Story quality visible and actionable through a complete INVEST assessment
and explicit SPIDR recommendations without accepting provider output as domain
truth.

## User Outcome

A reviewer can see all six INVEST criteria for every Story, understand each
pass or failure, distinguish deterministic from semantic findings, and see
concrete split patterns when the Story fails two or more checks.

## Domain

- `InvestCriterion` defines Independent, Negotiable, Valuable, Estimable,
  Small, and Testable.
- `ValidationFinding` records criterion, outcome, explanation, and source.
- `InvestAssessment` requires exactly one finding per criterion and computes
  `passes`, `needs_attention`, or `split_recommended`.
- Two or more failures require a split recommendation, matching the source
  business rule.
- `SpidrRecommendation` and `SpidrPattern` represent Spike, Paths, Interfaces,
  Data, and Rules recommendations.

## Application

- `ValidateStory` combines semantic findings with deterministic acceptance-
  criteria validation.
- `ValidateFeatureStories` assesses every Story in a Feature.
- `SuggestStorySplit` maps failed criteria to stable, reviewable SPIDR advice.

## Ports and Adapters

- `StoryQualityEvaluatorPort` isolates semantic quality judgment.
- Deterministic fake, local OpenAI-compatible, and OpenAI adapters follow the
  existing provider selection and expose model/prompt/time provenance.
- Infrastructure mapping strips and validates every provider field and raises
  a mapped `StoryQualityEvaluationError` for unusable output.
- When a schema-valid response omits requested criteria, adapters retain only
  valid findings and make one bounded, criterion-specific request for each
  omission. A missing, blank, duplicate, or unexpected focused result remains
  an explicit provider failure rather than an incomplete assessment.

## API

- Feature-level and Story-level quality endpoints return all findings, status,
  failure count, recommendations, and provenance.
- A dedicated split-recommendation endpoint supports focused consumers.
- Semantic provider failures are centrally translated to HTTP 502.
- The committed OpenAPI document and generated TypeScript schema include all
  new contracts.

## UI

- Story cards contain an accessible INVEST region with all six criteria,
  pass/fail state, source, and explanation.
- Poor Stories display failure counts and SPIDR recommendations; passing
  Stories explicitly show that all checks pass.
- Quality is refreshed after Story mutations and reflows on the responsive
  review journey.

## Tests

- Domain tests prove exact criterion coverage and the two-failure threshold.
- Application tests prove deterministic/semantic composition and SPIDR mapping.
- Adapter tests reject blank, duplicate, incomplete, and provider-failed
  responses and prove omitted criteria are recovered with focused requests.
- API/error tests prove endpoints, provider selection, and 502 translation.
- UI and Playwright tests prove failures and split advice are visible at both
  supported viewports.

## Acceptance Criteria

- [x] Every assessment contains exactly the six INVEST criteria.
- [x] Deterministic and semantic validation are separated.
- [x] Two or more failures produce `split_recommended`.
- [x] SPIDR advice maps to the failed quality concerns.
- [x] Quality output records model, prompt version, and generation time.
- [x] Poor-quality Stories are visible and actionable in the review UI.

## Validation Evidence

- `.venv\Scripts\python.exe -m pytest -ra` — PASS, 400 passed / 5 live
  PostgreSQL tests skipped because `TEST_DATABASE_URL` is absent.
- `.venv\Scripts\python.exe -m ruff check .` — PASS, all checks passed.
- `.venv\Scripts\python.exe -m ruff format --check .` — PASS, 238 files
  formatted.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS, no issues in 196
  source files.
- `.venv\Scripts\lint-imports.exe` — PASS, 2 contracts kept / 0 broken.
- `npm.cmd run api:check` — PASS; committed TypeScript matches OpenAPI.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS, 14 files / 59 tests.
- `npm.cmd run build` — PASS, Vite emitted local Archivo assets.
- `npm.cmd run test:smoke` — PASS, 4 journeys across Chromium 1440×1000
  and responsive Chromium 740×1000.
- Live local-provider check against an existing Story — PASS, HTTP 200 with
  all six criteria and `story-quality-v2` provenance after API restart.
- CI — not independently verifiable from this workspace because the GitHub
  repository is private and no authenticated GitHub CLI/session is available.

## Scope Check

Every Domain, Validation, Application, UI, and Tests field in the Slice 6
roadmap entry is delivered. No Slice 7 behavior was introduced.
