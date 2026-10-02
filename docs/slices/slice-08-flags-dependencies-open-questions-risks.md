# Slice 8 — Flags, Dependencies, Open Questions, Risks

> Status: **complete locally; CI pending push**. Every Slice 8 roadmap field is
> implemented and validated below.

## Objective

Give the Product Owner and Business Owner one durable, severity-aware review
surface that assembles the current analysis uncertainty, architecture impact,
and Story quality findings without turning derived warnings into confirmed
business facts.

## User Outcome

A reviewer can refresh one current breakdown review, understand what blocks or
threatens the work, answer an open question through the existing clarification
loop, record an explicit decision, and resolve an eligible flag while retaining
an audit trail.

## In Scope

- A refreshable `BreakdownReview` for each Requirement.
- Stable, source-linked flags covering:
  - open questions, assumptions, ambiguities, and potential dependencies,
  - architecture dependencies and cross-system warnings,
  - stale generated content,
  - failed INVEST findings and existing SPIDR recommendations.
- Explicit severity, resolution eligibility, blocker count, review freshness,
  and source links for every displayed concern.
- Durable decisions and flag resolutions in memory and PostgreSQL modes.
- A focused open-question resolution path that reuses the current analysis
  clarification and re-analysis behavior.
- Immutable revision snapshots containing review and decision state.
- A browser route and panel usable without curl or the OpenAPI page.

## Out of Scope

- Authentication, actor identity, owner-only actions, roles, assignments, or
  “Assigned to me” behavior (Slice 8A).
- Stateful question identities, partial collaborative answers, immutable
  analysis rounds, answer attribution, and question assignment (Slice 8B).
- Background jobs, retry/cancel orchestration, polling, or notifications
  (Slice 8C).
- Story approval, full-breakdown approval, review comments, rejection states,
  or approval gating (Slice 9).
- New semantic risk discovery, a general review LLM prompt, or a new AI port.
- ADO publication or neutral export.
- Architecture catalogue administration or invented squad ownership.

## Planning Decisions

| Question | Planned decision | Reason |
|---|---|---|
| Is the review live-computed on every GET? | No. `POST` explicitly generates or refreshes a durable snapshot; `GET` reads it. | Story quality can call the configured semantic evaluator. A GET must not create cost or new generated state. |
| Does Slice 8 add another review LLM? | No. Reuse `ValidateStory`, deterministic analysis/architecture mappings, and current SPIDR advice. | Existing evidence is sufficient for the roadmap outcome and avoids a second, potentially contradictory source of truth. |
| Can a failed refresh destroy the last review? | No. Build and validate the complete candidate before one atomic save. | Provider failure must remain explicit while the last successful review stays available. |
| How are stale resolutions prevented? | Each review stores a canonical fingerprint of the analysis and backlog evidence it evaluated. Mutations make the saved review visibly stale, and resolution commands require the current fingerprint. | A decision against old wording must not silently resolve a changed concern. |
| How are flag IDs kept stable? | Derive them from source kind, source entity identity, rule code, and the relevant evidence fingerprint. | Unchanged concerns retain decisions; materially changed concerns receive new IDs. |
| Can all flags be manually dismissed? | No. Each flag declares whether it is decision-resolvable or requires a source action. Open questions use `ResolveOpenQuestion`; stale content requires reconciliation. | A generic “resolve” button must not bypass existing domain invariants. |
| Does blocker count gate current approvals? | No. Slice 8 computes and displays blockers only. | Full approval policy belongs to Slice 9. Existing Epic/Feature invariants remain unchanged. |
| Who recorded a decision? | Slice 8 records what and when, but does not invent an actor. The UI must not label the action as owner-authored. | Provider-neutral identity and truthful attribution begin in Slice 8A. |

## Domain

- Introduce a focused `domain/review` package containing:
  - `Dependency` with a stable ID, description, impacted source, and explicit
    evidence kind (`potential` analysis evidence or `catalogued` architecture
    evidence).
  - `Risk` with stable ID, severity, description, and source reference.
  - `Flag` with stable ID, category, severity, title/detail, source reference,
    resolution policy, and open/resolved state.
  - `Recommendation` with stable ID, action text, rationale, and source
    reference.
  - `Decision` with stable ID, optional target flag, decision and rationale,
    timestamp, and no actor until Slice 8A.
  - `BreakdownReview` as the Requirement-scoped aggregate containing generation
    time, ruleset version, evidence fingerprint, dependencies, risks, flags,
    recommendations, and append-only decisions.
- Introduce only the supporting value objects/enums needed for invariants, such
  as `FlagSeverity`, `FlagStatus`, `FlagCategory`, `ResolutionPolicy`, and
  source/item references.
- The aggregate calculates unresolved blocker count from open blocking flags;
  callers do not duplicate this rule.
- Resolution is idempotent only for the same decision payload. Conflicting
  second resolutions fail explicitly.
- Decisions and resolutions require timezone-aware timestamps and non-blank
  content.
- An assumption, ambiguity, or potential dependency remains explicitly
  uncertain. Review mapping never promotes it to a fact, rule, or confirmed
  dependency.

## Application Use Cases

- `GenerateBreakdownReview`
  - Load the Requirement, current analysis, Epic, Features, and Stories.
  - Permit a partial journey after an analysis exists, so unresolved questions
    can appear before analysis confirmation and backlog generation.
  - Evaluate each current Story once through the existing `ValidateStory`
    behavior and derive its current SPIDR recommendations.
  - Map analysis uncertainty, architecture impact, staleness, and Story quality
    into a complete review candidate using deterministic application policy.
  - Carry forward decisions only for unchanged stable flag IDs.
  - Save once inside the existing transaction boundary.
- `GetBreakdownReview`
  - Return the last successful review plus a freshness result computed against
    the current evidence fingerprint.
  - Return not-found when no review has yet been generated; do not generate on
    read.
- `ResolveOpenQuestion`
  - Require a current open-question flag and expected review fingerprint.
  - Delegate the answer to `ClarifyRequirementAnalysis` using its current
    `ClarificationKind.OPEN_QUESTION` and subject contract.
  - Record the answer as a review decision and leave the review stale until an
    explicit refresh reflects the new analysis.
  - Do not introduce question status, assignment, partial answers, or round
    history ahead of Slice 8B.
- `RecordDecision`
  - Append a standalone or flag-linked decision with timestamp and rationale.
  - Reject unknown targets and stale review versions.
- `ResolveFlag`
  - Resolve only flags whose resolution policy permits a decision.
  - Append the resolution decision atomically with the state change.
  - Reject source-action-only, missing, already-conflicting, or stale flags.
- Keep concern mapping in a named application policy/module rather than route
  handlers, React components, persistence adapters, or domain keyword rules.

## Flag and Severity Policy

The first Slice 8 ruleset is deterministic, versioned, and covered by tests:

| Evidence | Review representation | Severity / resolution |
|---|---|---|
| Open question, assumption, or ambiguity | Flag with the original uncertainty category | Blocking; open questions resolve only through the clarification loop. Other uncertainty links back to Clarify. |
| Potential dependency from analysis | Potential `Dependency` plus flag | Blocking until clarified; never presented as confirmed. |
| Catalogue architecture dependency | Catalogued `Dependency` plus flag | Warning; decision-resolvable. |
| Cross-system Feature | Coordination `Risk`, flag, and component-split recommendation | Warning; decision-resolvable. |
| Missing architecture mapping on an existing Feature/Story | Coverage flag and “Map architecture” recommendation | Warning; source action required. A completed mapping with zero matches is not mislabeled as “not mapped.” |
| Stale Epic, Feature, or Story | Staleness risk and flag | Blocking; source action required. |
| One failed INVEST criterion | Quality risk and flag | Warning; decision-resolvable. |
| Two or more failed INVEST criteria | Quality risk, blocking flag, and existing SPIDR recommendations | Blocking; decision-resolvable for Slice 8 display, but it does not override current or future approval invariants. |
| Passing INVEST assessment | No risk/flag | The review summary records that the Story was evaluated. |

No severity is inferred from free-text keywords. A policy change increments the
review ruleset version and is handled as a deliberate business-rule change.

## Ports

- Add `BreakdownReviewRepositoryPort` with Requirement-scoped `get` and `save`
  operations.
- Reuse the existing Requirement/analysis/Epic/Feature/Story repository ports,
  `ClockPort`, `TransactionManagerPort`, `ValidateStory`, and
  `StoryQualityEvaluatorPort` boundary.
- Do not add a generic review-generator port or expose provider-specific quality
  payloads.

## Adapters

- Add `InMemoryBreakdownReviewRepository` and wire it only in
  `interfaces/api/container.py`.
- Add a PostgreSQL `breakdown_reviews` JSONB table and repository adapter through
  a forward-only migration. The table belongs to a Requirement and is included
  in request-local atomic transactions.
- Extend snapshot mapping for review aggregates with strict type/content checks
  and backward-compatible reads of historical breakdown revisions that predate
  Slice 8.
- Extend in-memory revision tracking and PostgreSQL checkpoint capture so review
  decisions appear in immutable `BreakdownRevision` history.
- Keep persistence adapters free of severity, blocker, and resolution policy.

## API

- `POST /requirements/{requirement_id}/breakdown-review`
  - Generate or refresh the complete review; return `201` for the first snapshot
    and `200` for refresh.
- `GET /requirements/{requirement_id}/breakdown-review`
  - Return the saved snapshot, counts, freshness, generation time, ruleset
    version, evidence, decisions, and source links.
- `POST /requirements/{requirement_id}/breakdown-review/open-questions/{flag_id}/resolution`
  - Accept `answer` and `expected_fingerprint`; return the updated analysis and
    stale review metadata.
- `POST /requirements/{requirement_id}/breakdown-review/decisions`
  - Accept decision text, rationale, optional flag ID, and
    `expected_fingerprint`.
- `POST /requirements/{requirement_id}/breakdown-review/flags/{flag_id}/resolution`
  - Accept decision text, rationale, and `expected_fingerprint`; return the
    updated review.
- Add explicit application/domain errors for missing review, stale review,
  missing flag, disallowed resolution, and conflicting resolution. Map them
  centrally to `404`, `409`, or `422` according to fault, with status tests.
- Update the committed OpenAPI snapshot and generated TypeScript contract.

The final route names may change only if existing API conventions prove a
clearer resource shape during implementation; any change must be recorded here.

## UI

- Add a deep-linkable `/requirements/:id/review` route and an obvious Review
  entry from the Breakdown workspace.
- Add a `BreakdownReviewPanel` that shows:
  - total and unresolved blocker/warning counts,
  - last refresh time, ruleset version, and stale/current state,
  - blocking questions and other analysis uncertainty,
  - potential and catalogued dependencies with visibly different evidence,
  - architecture warnings and cross-system risks,
  - Story quality findings and SPIDR recommendations,
  - recorded decisions and flag resolution state.
- Group by severity and category, and support severity/status filtering without
  hiding counts.
- Link each concern to its analysis, Feature, or Story source.
- Allow open-question answers from the review surface through the focused
  endpoint. Other uncertainty routes the reviewer to the existing Clarify
  experience.
- Allow eligible flag resolution and standalone decision recording with an
  explicit confirmation and rationale.
- Preserve the last successful review when refresh or resolution fails and show
  an accessible error/live-region state.
- A stale review remains readable but disables mutation actions until refresh.
- Do not add Approve Breakdown, user attribution, assignment, notification, or
  background-job controls.
- Maintain ordinary responsive reflow and keyboard/screen-reader semantics at
  the existing desktop and responsive test viewports.

## Business Rules

- Generated review content is candidate governance metadata, not approved
  business truth.
- Evidence provenance remains visible: analysis uncertainty, catalogue-derived
  architecture, deterministic rule, or semantic INVEST assessment.
- A potential dependency is never rendered as a catalogued/confirmed
  dependency.
- Resolving a flag does not modify the Requirement, analysis facts, Epic,
  Feature, Story, architecture mapping, or quality finding that produced it.
- Answering an open question does modify analysis only through the existing
  clarification/re-analysis use case and therefore stales the prior review.
- Review regeneration does not silently discard decisions. It retains decisions
  tied to unchanged flag IDs and preserves superseded decisions in immutable
  revisions.
- A current review is defined by its evidence fingerprint, not by its age.
- Blocker calculation is informative in Slice 8 and is not an approval guard.
- No route or UI component owns severity or blocker policy.

## Tests

- Domain tests:
  - non-blank IDs/content and aware timestamps,
  - dependency evidence distinction,
  - valid/invalid flag transitions,
  - source-action-only resolution rejection,
  - idempotent versus conflicting resolution,
  - unresolved blocker calculation,
  - append-only decision behavior.
- Application tests:
  - partial-journey review generation,
  - exact mapping for every policy row above,
  - assumption/potential-dependency provenance separation,
  - stable IDs for unchanged evidence and new IDs after material changes,
  - one quality evaluation per Story,
  - preservation of the previous snapshot on evaluator failure,
  - refresh decision carry-forward,
  - stale-fingerprint conflicts,
  - open-question delegation and review staleness,
  - decision and resolution audit behavior.
- Adapter tests:
  - in-memory repository contract,
  - PostgreSQL current-state and immutable-revision round trips,
  - migration behavior,
  - backward-compatible historical payloads without review data.
- API tests:
  - all five routes and response contracts,
  - first-create versus refresh status,
  - missing/stale/conflicting errors,
  - every new error's centralized status mapping,
  - provider failure remains `502` and preserves the previous review,
  - OpenAPI snapshot coverage.
- UI tests:
  - each severity/category group,
  - potential versus catalogued dependency labels,
  - blocker counts and filters,
  - fresh/stale/empty/loading/error states,
  - open-question answer, decision, and allowed/disallowed resolution paths,
  - last-successful-data preservation on failure.
- Browser smoke test:
  - fake-provider flow from Requirement review through a generated Slice 8
    review, one decision/resolution, and persisted reload at 1440px and the
    existing responsive viewport.

## Implementation Sequence

1. Confirm this plan and record an ADR for the durable review snapshot,
   evidence-fingerprint, and decision carry-forward strategy because it adds a
   new port and extends revision persistence.
2. Implement domain review types, invariants, severity policy inputs, and unit
   tests.
3. Add snapshot mapping, memory/PostgreSQL repositories, migration, revision
   integration, and adapter tests.
4. Implement generation, freshness, open-question resolution, decision, and
   flag-resolution use cases with transactional tests.
5. Wire the composition root, dependency providers, API schemas/routes, central
   errors, OpenAPI snapshot, and API tests.
6. Add the deep-linkable review UI, typed client methods, component tests, and
   accessible state handling.
7. Run backend/frontend gates and the full fake-provider browser flow; record
   exact output in Validation Evidence, mark local completion, and leave CI
   status explicitly pending until the working tree is pushed.

## Acceptance Criteria

- [x] A reviewer can generate and later retrieve one durable breakdown review.
- [x] The review visibly separates analysis uncertainty, potential dependencies,
  catalogue dependencies, architecture warnings, quality findings, risks, and
  recommendations.
- [x] Every concern exposes severity, source, resolution policy, and stable ID.
- [x] Blocker count follows the versioned deterministic policy.
- [x] Open questions can be answered through the existing clarification loop
  from the review surface.
- [x] Eligible flags can be resolved only against a current review fingerprint.
- [x] Decisions and resolutions remain auditable in immutable revisions.
- [x] A failed refresh preserves the last successful review.
- [x] No assumption or potential dependency is promoted to confirmed truth.
- [x] The browser surface is usable at the current desktop and responsive test
  viewports.
- [x] Every Domain, Application, UI, and Tests field in the Slice 8 roadmap entry
  is delivered; the necessary Port, Adapter, and API work is also complete.

## Validation Evidence

- `.venv\Scripts\pytest.exe` — PASS: 424 passed, 5 skipped in 5.62s. The
  skipped tests are the opt-in PostgreSQL suite because
  `TEST_DATABASE_URL` is not configured.
- `.venv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv\Scripts\ruff.exe format --check .` — PASS: 261 files
  already formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 215
  source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 164 files and 732 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run api:check` — PASS: generated TypeScript matches committed
  OpenAPI.
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS: 16 files, 73 tests.
- `npm.cmd run build` — PASS: 1,912 modules transformed; production bundle
  emitted.
- `$env:SMOKE_API_PORT='8018'; $env:SMOKE_UI_PORT='4188'; npm.cmd run test:smoke`
  — PASS: 4 journeys across desktop and responsive Chromium.
- CI — NOT RUN for this working tree; pending push.

## Dropped from This Slice

Nothing. Every field in the Slice 8 roadmap entry is delivered.

## Deferred

- Actor attribution, authorization, ownership, and assignments — Slice 8A.
- Stateful question lifecycle, collaborative answers, and immutable analysis
  rounds — Slice 8B.
- Async review generation and notifications — Slice 8C.
- Approval policy and enforcement based on blockers — Slice 9.
- Catalogue maintenance and verified squad ownership — Slice 14.
