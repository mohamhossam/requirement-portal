# ROADMAP.md — SMB AI Requirement Breakdown Agent

## Delivery status — verified 2026-09-28; platform rows 2026-10-05

This is the current status ledger. Slice specifications keep their dated implementation and
validation history; older statements such as "CI pending push" in those records do not override
the merge evidence below. "Implemented" describes delivered scope, "merged" describes Git history,
"specified" means a slice specification with recorded decisions exists but no implementation has
started, and production qualification remains a separate release gate. No scope is dropped by
this ledger.

| Scope | Current status | Remaining |
|---|---|---|
| Slices 0–11, including 4A, 5A–5D, 8A–8C and 10A | Implemented; merged into `main` | Release qualification; maintained templates are separately deferred to 5D.1 |
| Enhancements 5C.1, 5D.2, 8B.1–8B.3, 11A–11B.1 and business-need attachments | Implemented; merged into `main` | Representative live-provider acceptance where applicable |
| Generation quality and configured model integration | Implemented; merged into `main` | Live semantic quality and provider-capacity acceptance |
| Reviewed document library, ingestion, indexing, unified search, governance and source lineage | Functional implementation merged into `main` | Human-labelled evaluation, representative formats and production operations/capacity qualification |
| Production-readiness remediation | Implemented; merged into `main` | Target-environment release qualification |
| Four whole-workspace review remediations (`docs/slices/enhancement-review-remediation*.md`) | Implemented; merged into `main` ([#18](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/18), [#35](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/35), [#37](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/37), [#38](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/38)) | A human review of the merged changes |
| Repeatable recovery and search-load qualification tools | Implemented; merged into `main` ([#39](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/39), rebuilt from [#15](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/15)). CI runs the nonempty backup/restore rehearsal on every push | Synthetic results do not qualify production |
| Architecture knowledge administration (14) | Implemented; merged into `main` | Deployment-specific local-model qualification |
| UI/UX redesign, Phases 0–10 (`docs/ux-plan.md`) | Implemented; merged into `main` ([#46](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/46)–[#52](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/52), [#54](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/54), [#56](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/56)–[#60](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/60)) | Two open product decisions and the raised follow-ups under *UI/UX Redesign* below |
| Docker run-everything path, monitoring add-on and OpenRouter demo | Implemented; merged into `main` ([#53](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/53), [#62](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/62)–[#65](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/65)) | Live OpenRouter acceptance; free-model quota and availability are external |
| Human-answer citation salvage (`0d42039`, `docs/slices/fix-human-answer-analysis-citations.md`) | Implemented; merged in `smb-ai-requirement-agent` as [#67](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/67) before the `d5cfb57` snapshot, so it is part of this repository | — |
| Maintained template/example library (5D.1) | Deferred; requires explicit scheduling | Implementation |
| Enhancement 8A.2 — AD login with Keycloak-managed roles | Specified 2026-09-26; not scheduled | Sequencing, AD-team prerequisites, implementation and staging acceptance |
| Centralized logging in Graylog | Specified 2026-09-26; not scheduled | Sequencing and implementation |
| Administration portal, sub-slices A–F | Specified 2026-09-26 (F on 2026-09-28); not scheduled | Sequencing, an ADR amending `AGENTS.md` §4.5, and implementation |
| Squad catalogue and architecture catalogue from documents (`docs/slices/enhancement-squad-and-architecture-catalogues.md`, ADR-0080/0081) | Implemented; merged in `smb-ai-requirement-agent` as [#73](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/73) before the `d5cfb57` snapshot. Both catalogues now live in [knowledge-portal](https://github.com/mohamhossam/knowledge-portal). Pulls Knowledge Center F forward | Live vision-model acceptance, in knowledge-portal |
| Connected systems in impact mapping (`docs/slices/enhancement-architecture-impact-neighbours.md`, ADR-0087) | Implemented; merged in `smb-ai-requirement-agent` as [#77](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/77) before the `d5cfb57` snapshot. Slice A of three. The impact view is here; the catalogue's connections are matched in [knowledge-portal](https://github.com/mohamhossam/knowledge-portal) | — |
| Typed system relationships (`docs/slices/enhancement-typed-system-relationships.md`, ADR-0088) | Implemented; merged in `smb-ai-requirement-agent` as [#78](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/78) before the `d5cfb57` snapshot. Slice B of three; the catalogue now lives in [knowledge-portal](https://github.com/mohamhossam/knowledge-portal) | — |
| Capability domains (`docs/slices/enhancement-capability-domains.md`, ADR-0089) | Implemented; merged in `smb-ai-requirement-agent` as [#79](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/79) before the `d5cfb57` snapshot. Slice C of three; the catalogue now lives in [knowledge-portal](https://github.com/mohamhossam/knowledge-portal) | — |
| Structured architecture documents, slices 1a–3e (`docs/slices/enhancement-catalogue-output-aware-reading.md`, `docs/slices/enhancement-markdown-structured-passages.md`, `docs/slices/enhancement-catalogue-table-reading-rules.md`, `docs/slices/enhancement-catalogue-table-reader.md`, `docs/slices/enhancement-system-landscape-domains.md`, `docs/slices/enhancement-catalogue-landscape-suggestions.md`, `docs/slices/enhancement-product-offerings.md`, `docs/slices/enhancement-catalogue-offering-suggestions.md`, `docs/slices/enhancement-journeys.md`, `docs/slices/enhancement-catalogue-journey-suggestions.md`, `docs/slices/enhancement-impact-product-context.md`, ADR-0091, ADR-0093, ADR-0094, ADR-0095, ADR-0096 and its amendment, ADR-0097, ADR-0090/0085/0088 amendments) | Implemented; 1a–3e merged in `smb-ai-requirement-agent`, 1a as [#83](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/83) and 3e as [#100](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/100), which is the `d5cfb57` snapshot itself. Document reading and the catalogue now live in [knowledge-portal](https://github.com/mohamhossam/knowledge-portal); 3e's product and journey context on impacts is shown here | A live-model replay of the reported file, in knowledge-portal |
| System components (`docs/slices/enhancement-system-components.md`, ADR-0092) | Implemented; merged in `smb-ai-requirement-agent` as [#84](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/84) before the `d5cfb57` snapshot. Now lives in [knowledge-portal](https://github.com/mohamhossam/knowledge-portal) | Live-model extraction check, in knowledge-portal |
| Three-repository platform split (ADR-0098, ADR-0099, ADR-0100; plan `docs/slices/enhancement-platform-split.md`) | **Done 2026-10-05.** Stages 0–5: `platform-kernel` v1.0.2, the untangling and seams here, knowledge-portal v0.1.0, the cutover, and the guarded drop of the moved tables ([#31](https://github.com/mohamhossam/requirement-portal/pull/31)) with the run guides ([#32](https://github.com/mohamhossam/requirement-portal/pull/32)). No data is moved while the platform is in development. The acceptance criteria are checked in the plan, with their evidence: CI proves a withdrawal reaching requirement work, and runs the platform in a browser, on the combined stack | Branch protection on `main` (an owner setting) |
| The Product Architecture Explorer on the knowledge catalogue (ADR-0101, with Amendments 1 and 2) | **Done 2026-10-05.** Built in [knowledge-portal](https://github.com/mohamhossam/knowledge-portal) (its #22–#36). Here: the ADR, and step 7's handoff of approved backlogs to the catalogue's change-request inbox ([#35](https://github.com/mohamhossam/requirement-portal/pull/35), `docs/slices/enhancement-change-requests-from-requirement-ai.md`) | A handoff status on the approval screen (deferred by decision) |
| Knowledge Center (`docs/slices/enhancement-knowledge-center.md`, ADR-0099 Amendment 1, ADR-0102) | **Re-planned 2026-10-06 for the three repositories.** A is mostly delivered by the split, and F early. B1, A′, B2, B3, C and D are delivered (each built where its data lives). **E is scheduled 2026-10-06** (ADR-0102): E1, knowledge-portal's read-only ADO import and lineage, is in progress | E1, then E2 (historic corpus and prior art here); the ADO edition, for the REST adapter |
| ADO publication and safe republish (12–13) | Planned; not implemented | Implementation |
| Advanced workflow optimization (15) | Planned; evidence-gated | Demonstrate a need and measurable benefit before implementation |

### Merge and CI evidence

- Verified `main`: `ca0dacf` (the [#65](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/65) merge), 2026-09-28.
- Merged since the previous ledger (2026-09-25, `3669344`):
  - [#40](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/40): the previous delivery ledger;
  - [#41](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/41), [#44](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/44), [#45](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/45): refetch of workspace reads invalidated while loading, one query for
    each AI job's command, and the shared graph lock for in-memory stores written outside a
    transaction;
  - [#42](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/42): the reviewer smoke test waits for the persona switch; [#43](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/43): the stale Clarify
    panel retired from the debt register;
  - [#46](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/46)–[#52](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/52): redesign Phases 0–6;
  - [#53](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/53): the run-everything-in-Docker path, the optional Prometheus/Grafana add-on, and the
    8A.2, Graylog, administration portal and Knowledge Center specifications;
  - [#54](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/54), [#56](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/56), [#58](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/58), [#59](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/59), [#60](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/60): redesign Phases 7–10 and their critique passes;
  - [#55](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/55): CSP admits `blob:` frames so the PDF original preview renders; [#57](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/57): the `sm`
    breakpoint declared in px;
  - [#61](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/61): administration portal sub-slice F (system prompts) specified;
  - [#62](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/62), [#63](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/63), [#64](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/64): Docker as a first-class start-guide path, read-only model-profile and
    tokenizer mounts, and the Docker demo on OpenRouter and PostgreSQL;
  - [#65](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/65): citations discarded when no evidence was supplied, and the web proxy re-resolves
    the API host.
- Merged in the ledger before that (2026-09-23 `57ee26a` to 2026-09-25 `3669344`): [#18](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/18), [#19](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/19),
  [#35](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/35), [#37](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/37)–[#39](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/39), and Dependabot [#20](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/20), [#27](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/27), [#30](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/30), [#33](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/33), [#34](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/34) and
  [#36](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/36).
- Closed without merging:
  - [#15](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/15), replaced by #39;
  - Dependabot [#22](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/22) (Python 3.14 image) and [#25](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/25) (non-LTS Node 25), held
    by `.github/dependabot.yml`;
  - [#28](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/28), [#29](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/29), [#31](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/31), [#32](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/32): vitest and TypeScript are now
    grouped or held, and jsdom 30 breaks a test double;
  - #21, #23, #24 and #26, superseded by the grouped #36.
- Each PR's hosted run is on its page; verify a revision's own run rather than inferring from
  an earlier one. CI has eight jobs: quality gates, PostgreSQL architecture, frontend, supply
  chain, deployment, recovery, smoke, and PostgreSQL lineage browser.
- Unmerged remote branches:
  - `claude/fix-analysis-citations-and-proxy`: one commit (`0d42039`) beyond #65, the
    human-answer citation salvage above;
  - `single-master-docker-compose` (local-environment compose files). It is not a product
    slice, and it overlaps the `deploy/` manifests added since.

### Release work still open

- Target-environment migrations, maintenance, nonempty backup/restore, worker crash and
  provider-outage recovery, plus deployment acceptance. The CI rehearsal is synthetic; it does
  not replace a restore in the target environment.
- Human-labelled retrieval/grounding evaluation: 200 queries, including 50 cross-language
  cases, and actual-model semantic support/conflict and generation-quality acceptance.
- One million chunks with 25 users: database p95 below 1 second, end-to-end p95 below
  3 seconds, separate embedding timing and no ingestion starvation.
- Real scanner, English/Arabic OCR and Office-renderer deployment checks; representative
  customer documents; operational quotas, metrics and alerts.
- Keycloak/Entra and SMTP staging acceptance; affected legacy publications require owner
  inspection and new upload/review where old extraction metadata retained excluded wording.
  If Enhancement 8A.2 is scheduled, AD staging acceptance replaces the Entra part.
- Live-provider acceptance for the configured providers, including the OpenRouter Docker demo,
  and the full live retry recorded as incomplete in
  `docs/slices/enhancement-local-structured-analysis-recovery.md`.
- A human review of the four merged whole-workspace review remediations.

## Roadmap Principles

This roadmap is intentionally vertical-slice driven.

Each slice must:
- deliver a coherent user/business capability,
- preserve Clean Architecture,
- leave the repository runnable/testable,
- avoid implementing future capabilities early,
- introduce domain concepts only when required,
- keep AI and external systems behind ports,
- keep human review separate from AI generation.

The source business prompt remains the initial Agile/SMB reference. As product decisions are approved, record them in slice specs or architecture decision records rather than silently editing behavior.

## Every field of a slice is a deliverable

A slice entry below lists Domain, Application, Ports, Adapters, API, UI and
Tests. **Each of those is scope, not a suggestion**, and the UI line has exactly
the same standing as the API line.

A slice may still be delivered without part of its entry — but only as an
explicit, recorded decision:

1. Raise the omission **before implementing**, with the reason.
2. Get it agreed by the person who owns the roadmap.
3. Record it in the slice spec under a heading that names what was dropped and
   why, and add it to the debt register in `AGENTS.md` §19.

Writing "None." under a heading the roadmap filled in is not a decision. It is
how Slices 01 through 04 each shipped without the UI this roadmap asked for,
four times in a row, until someone noticed there was no user interface at all.
Slice 4A exists to repay that.

---

# Release 0 — Foundation

## Slice 0 — Clean Architecture Workspace

**Status: Implemented; merged into `main`.**

### Goal
Create the minimum project skeleton and quality gates needed for safe incremental delivery.

### Deliverables
- Python package structure.
- Domain/Application/Infrastructure/Interface boundaries.
- Health endpoint.
- In-memory-friendly test setup.
- ruff, mypy, pytest, import-linter configuration.
- Architecture dependency tests/contracts.
- Root `AGENTS.md`, `ROADMAP.md`, `WORKSPACE.md`.

### Domain
Only foundational IDs/status concepts if actually needed by the skeleton. Avoid speculative entities.

### Application
No business use case required yet.

### Infrastructure
No external providers.

### Interface
`GET /health`.

### Tests
- health endpoint,
- dependency-boundary checks,
- importability/startup.

### Exit Criteria
- application starts,
- tests pass,
- lint/type/import rules pass,
- no outward dependency from domain/application.

---

# Release 1 — Requirement Intake and Understanding

## Slice 1 — Requirement Intake

**Status: Implemented; merged into `main`.**

### User Outcome
A Business Owner can create, edit, and retrieve a requirement draft.

### Domain
Introduce only:
- Requirement,
- RequirementId,
- RequirementTitle,
- RequirementDescription,
- RequirementStatus.

### Application Use Cases
- CreateRequirement
- GetRequirement
- UpdateRequirement

### Port
- RequirementRepositoryPort

### Adapter
- InMemoryRequirementRepository

### API
- `POST /requirements`
- `GET /requirements/{id}`
- `PUT /requirements/{id}`

### UI
Simple requirement form:
- title,
- requirement text,
- optional context,
- save/update.

### Tests
- domain validation,
- use-case tests,
- repository contract test,
- API tests.

### Exit Criteria
Requirement draft workflow works end-to-end without AI.

### UI Status
**Delivered by Slice 4A; merged into `main`.** The original omission is resolved.

---

## Slice 2 — Requirement Analysis

**Status: Implemented; merged into `main`.**

### User Outcome
The user can analyze a raw requirement and see what is known, missing, assumed, constrained, or ambiguous before backlog generation.

### Domain
Introduce:
- RequirementAnalysis,
- KnownFact,
- Constraint,
- BusinessRule,
- Assumption,
- OpenQuestion.

### Permanent Rule
An assumption is never equivalent to a confirmed fact/business rule.

### Application Use Cases
- AnalyzeRequirement
- GetRequirementAnalysis

### Port
- RequirementAnalyzerPort

### Adapters
- deterministic fake analyzer for tests,
- first real LLM analyzer adapter.

### LLM Behavior
Return structured data only.
Never invent missing business behavior.
Classify uncertainty explicitly.

### API
- `POST /requirements/{id}/analysis`
- `GET /requirements/{id}/analysis`

### UI
Analysis review:
- Known Facts
- Constraints
- Business Rules
- Assumptions
- Open Questions
- Ambiguities

### Tests
- invalid LLM response,
- missing fields,
- assumption/fact separation,
- provider failure mapping.

### Exit Criteria
Requirement analysis is reviewable and no inferred assumption is silently treated as source truth.

### UI Status
**Delivered by Slice 4A; merged into `main`.** The original API-only review omission is resolved.

---

## Slice 3 — Epic Generation

**Status: Implemented; merged into `main`.**

### User Outcome
The user can generate, edit, regenerate, and approve an Epic candidate from the requirement and its analysis.

### Domain
Introduce:
- Epic,
- EpicId,
- EpicCandidate or equivalent generation state,
- BusinessOutcome,
- BusinessCase.

### Application Use Cases
- GenerateEpic
- EditEpic
- ApproveEpic

### Port Evolution
Extend a domain-oriented decomposition port, e.g. `BacklogDecompositionPort`, rather than exposing provider-specific operations.

### LLM Input
- requirement,
- analysis,
- Epic rules.

### UI
Epic review card with:
- name,
- outcome,
- business case,
- regenerate,
- edit,
- approve.

### Tests
- structured generation,
- approval transition,
- regeneration does not silently overwrite approved content.

### Exit Criteria
An approved Epic exists independently of Features.

### UI Status
**Delivered by Slice 4A; merged into `main`.** The original omission is resolved.

---

# Release 2 — Backlog Decomposition MVP

## Slice 4 — Feature Decomposition

**Status: Implemented; merged into `main`.**

### User Outcome
An approved Epic can be decomposed into reviewable Feature candidates.

### Domain
Introduce:
- Feature,
- FeatureId,
- FeatureOutcome,
- DeliveryDrop,
- SplittingRationale,
- SplittingPattern.

### Rules
Feature splitting may use:
- component/system,
- journey stage,
- MVP/later drop,
- channel,
- business variant.

Every Feature traces to exactly one Epic.

### Application Use Cases
- GenerateFeatures
- EditFeature
- SplitFeature
- MergeFeatures
- ApproveFeature

### LLM Input
- requirement,
- analysis,
- approved Epic,
- Feature-splitting rules.

### UI
Epic → Feature tree.
Each Feature shows:
- outcome,
- MVP/drop,
- splitting rationale,
- actions.

### Tests
- parent Epic invariant,
- split/merge behavior,
- generated candidate vs approved state.

### Exit Criteria
PO can approve the Feature structure before Story generation.

### UI Status
**Delivered by Slice 4A; merged into `main`.** The original omission is resolved.

---

## Slice 4A — Review UI

### Status
Implemented; merged into `main`. The browser flow, typed OpenAPI client, component tests and
fake-provider full-flow smoke test are implemented.

### Why this slice exists

Slices 1 to 4 each specified a UI and each shipped without one. The product is
a human-review tool whose review surface has never existed, so every rule built
so far — staleness, approval revocation, forced regeneration, flag-don't-destroy
— has been designed for a reviewer nobody has watched work.

This slice repays that debt for everything built to date. It introduces no new
domain concepts and no new AI capability.

### User Outcome
A Product Owner can run the whole flow in a browser: submit a requirement, read
its analysis, review and approve the Epic, and review and approve each Feature,
seeing at every step what is AI-generated, what a human has touched, and what
has gone stale.

### Domain
None. If this slice needs a domain change, that is a finding about the existing
model and should be raised, not absorbed.

### Application
None. Existing use cases only.

### Ports and Adapters
None on the backend. The browser talks to the existing HTTP API.

### API
No new endpoints. Changes to existing response shapes are permitted **only**
where the UI proves a shape wrong, and each one must be recorded.

### UI
The whole point of the slice:
- requirement form (create, edit),
- analysis panel: known facts, constraints, business rules, assumptions,
  open questions, ambiguities, with assumptions visibly separated from facts,
- Epic review card: name, outcome, business case, provenance, status,
  staleness, with edit / approve / regenerate,
- Epic → Feature tree: each Feature showing outcome, MVP or later drop,
  splitting pattern and rationale, status and staleness, with edit / approve,
- destructive actions (regenerate over human-owned content) must require an
  explicit confirmation, never a silent force.

### Tests
- component tests for the review states: generated, edited, approved, stale,
- a smoke test driving the full flow against the running API with
  `LLM_PROVIDER=fake`.

### Exit Criteria
The Requirement → Analysis → Epic → Features flow is fully usable and
reviewable in a browser, with no step requiring curl or the OpenAPI page.

---

## Slice 5 — User Story and Acceptance Criteria Generation

**Status: Implemented; merged into `main`.**

### User Outcome
A Feature can be decomposed into small reviewable User Stories with structured acceptance criteria.

### Domain
Introduce:
- UserStory,
- StoryId,
- UserRole,
- DesiredAction,
- BusinessValue,
- AcceptanceCriterion.

AcceptanceCriterion is structured:
- given,
- when,
- then.

### Application Use Cases
- GenerateStories
- EditStory
- SplitStory
- MergeStories
- RegenerateStory

### Generation Strategy
Generate Feature-by-Feature, not the full Epic backlog in one giant LLM call.

### UI
Feature detail:
- Story list/tree,
- story voice,
- acceptance criteria editor,
- regenerate/edit/split/merge.

### Tests
- story structure,
- acceptance-criteria validation,
- parent Feature invariant,
- partial-generation error handling.

### Exit Criteria
Every approved Feature can have reviewable Story candidates.

### UI Status
**Delivered end-to-end.** The original backend-only omission was repaid by
Slice 5A and completed by the Slice 5 closure: Feature detail now supports the
Story list, voice, Given/When/Then editing, guarded individual/set regeneration,
manual split/merge, and durable AI split/merge previews. Stale Stories remain
visible with disabled controls, and revisions compare Story changes. Story
approval is delivered by Slice 9. See `docs/slices/slice-05-user-stories.md`.

---

## Slice 5B — Desktop Worklist and Journey Refactor

**Status: Implemented; merged into `main`.**

### User Outcome
A reviewer can use a truthful desktop worklist, guided intake, and explicit
clarification/confirmation journey to reach the existing backlog review flow.

### Domain
No change. Worklist state is not added to the Requirement aggregate.

### Application
An application-owned cross-aggregate worklist query classifies workflow state,
next action, counts, latest activity, and ranked attention items. Epic generation
requires a human-confirmed analysis.

### Ports and Adapters
`RequirementWorklistSnapshotPort`, with in-memory and PostgreSQL adapters wired
only in the composition root. See ADR-0012.

### API
Extend `GET /requirements` additively with `q`, repeated `workflow_status`,
`sort`, `offset`, `limit`, enriched items, pagination, facets, and attention.
Unconfirmed Epic generation returns 409 through central error translation.

### UI
Modernist desktop worklist, one-page intake, five-step analysis journey, sticky
source/facts rail, explicit loading/error/validation/stale/destructive states,
and a visual refactor of existing Epic/Feature/Story/revision flows. Ordinary
responsive reflow remains; no dedicated mobile journey is introduced.

### Tests
Worklist policy/API/adapter tests, UI controls and failure-preservation tests,
existing review regression tests, and 1440px Playwright smoke coverage.

### Exit Criteria
The desktop route from worklist through confirmed analysis and reviewed backlog
is usable without fake dashboard controls or bypassing human confirmation.

---

## Slice 5C — Structured Intake and Resumable Drafts

**Status: Implemented; merged into `main`.**

### User Outcome
Authors can save and resume incomplete structured Requirements without losing
work or starting analysis before the minimum source is eligible.

### Domain / Application
Add optional customer, channel, system, rule, and constraint context plus a
required desired outcome and explicit analysis-eligibility validation. Existing
Requirements migrate with optional new fields. Add create/update/resume draft
use cases without changing confirmed historical content.

### Ports and Adapters
Extend persistence contracts and both adapters for partial drafts and draft
timestamps; retain offline in-memory behavior.

### API / UI
Draft-safe create/update endpoints and optimistic concurrency as required. The
intake page gains structured fields, debounced autosave, resume, and accessible
saved/failed live-region states.

### Tests / Exit Criteria
Migration, partial-draft, eligibility, concurrency, autosave, retry, and resume
coverage. A draft can be resumed safely and analysis starts only when eligible.

### Enhancement 5C.1 — Source Change Impact Preview

**Status: Implemented; merged into `main`.**

Before an existing source Requirement is changed, preview the persisted
analysis, Epic, Feature, and Story records that will be deleted or marked stale.
The final update supplies the expected Requirement version, explicitly
acknowledges non-empty impact, and recomputes that impact in the transaction so
a stale preview cannot authorize a later state silently.

---

## Slice 5D — Supporting Context

**Status: Implemented and merged into `main` — Source Documents. Maintained templates/examples are
carried to separately scheduled enhancement 5D.1 per the approved phased plan.**

### User Outcome
Authors can attach validated supporting material and choose maintained examples
or templates while keeping storage and provider concerns outside core logic.

### Domain / Application
Introduce attachment metadata and template references only to the degree needed
for validation, retrieval, and analysis context assembly.

### Ports and Adapters
Secure attachment-storage port with offline adapter and a file-backed
Requirement template/example library. Provider-specific storage remains in
Infrastructure.

### API / UI
Upload/list/remove endpoints with type/size validation and explicit counts;
intake surfaces attachments and selectable templates with accessible errors.

### Tests / Exit Criteria
Boundary, malicious-file-name, type/size, storage failure, context assembly, and
UI tests. Supporting context is durable, auditable, and never silently trusted.

---

## Enhancement 5D.2 — Structured Multimodal BRD Analysis

**Status: Implemented; merged into `main`.**

### User Outcome
Authors can upload large DOCX and XLSX business requirements and receive a reviewable,
source-linked analysis without one oversized prompt or loss of table and image context.

### Domain
Introduce immutable evidence blocks, extraction warnings/readiness, document assets,
analysis evidence references, stage provenance, and explicit hidden-worksheet selection.

### Application
Add `AssembleRequirementEvidence`, `PlanEvidencePackets`, `AnalyzeEvidencePacket`,
`ConsolidateEvidenceAnalysis`, and `ValidateAnalysisCitations`. Packet execution is
budgeted, cached, failure-atomic, and reports durable job progress.

### Ports
Add a focused `RequirementEvidenceAnalyzerPort`, fragment-cache port, and analysis-progress
port. Text and image inputs remain provider neutral.

### Adapters
DOCX and XLSX structured extractors preserve order, headings, lists, tables, worksheets,
formulas, charts and safe raster assets. Fake, OpenAI and local adapters accept bounded
evidence packets; PostgreSQL migration 011 persists fragment cache and progress.

### API
Add XLSX upload compatibility, readiness summaries, warnings, blocks, protected thumbnails,
hidden-sheet selection, item citations, stage provenance, and job progress fields. Changes are
additive and legacy plain-text versions remain readable.

### UI
Show document readiness and evidence counts, a structured outline/preview, thumbnails,
warnings, hidden-sheet opt-in, provider disclosure, live analysis progress, and citation links
from analysis items to exact blocks.

### Tests / Exit Criteria
Synthetic DOCX/XLSX safety, structure, packet budgeting, citation validation, cache
invalidation, persistence compatibility, progress, API/UI, OpenAPI and browser tests. No
confidential BRD fixture is committed and no generated finding is automatically confirmed.

---

## Slice 6 — INVEST / SPIDR Quality Validation

**Status: Implemented; all roadmap fields delivered and merged into `main`.**

### User Outcome
The user can see why a Story is good/bad and receive explicit splitting recommendations.

### Domain
Introduce:
- InvestAssessment,
- InvestCriterion,
- ValidationFinding,
- StoryQualityStatus.

### Validation
Separate:
- deterministic validations in code,
- semantic validations via AI port when needed.

### Application Use Cases
- ValidateStory
- ValidateFeatureStories
- SuggestStorySplit

### UI
INVEST panel:
- Independent
- Negotiable
- Valuable
- Estimable
- Small
- Testable

Show warnings/failures and suggested split patterns.

### Tests
- deterministic rule tests,
- fake semantic evaluator,
- split suggestion mapping.

### Exit Criteria
Poor-quality stories are visible and actionable, not silently accepted.

---

# Release 3 — SMB Architecture Intelligence

## Slice 7 — Architecture Impact Mapping

**Status: Implemented; all roadmap fields delivered and merged into `main`.**

### User Outcome
The user can see likely systems/squads and cross-system impact for each Feature/Story.

### Domain
Introduce:
- SystemReference,
- SystemCapability,
- SquadReference,
- ArchitectureDependency.

### Application Use Cases
- MapFeatureArchitecture
- MapStoryArchitecture
- DetectCrossSystemFeature

### Port
- ArchitectureKnowledgePort

### Initial Adapter
- YAML/file-backed architecture knowledge derived from the source reference.

### Future Adapters
- database,
- enterprise architecture repository,
- RAG/document retrieval.

### Permanent Rule
Do not hardcode keyword → system mapping in domain code.

### UI
Show:
- systems,
- squads,
- dependencies,
- cross-system warning.

### Tests
- architecture knowledge adapter,
- mapping behavior with fakes,
- cross-system Feature flag.

### Exit Criteria
Backlog items contain reviewable architecture impact.

---

## Slice 8 — Flags, Dependencies, Open Questions, Risks

**Status: Implemented; all roadmap fields delivered and merged into `main`.**

### User Outcome
PO/Business Owner gets one review surface for unresolved or risky work.

### Domain
Introduce:
- Dependency,
- Risk,
- Flag,
- Recommendation,
- Decision.

### Application Use Cases
- GenerateBreakdownReview
- ResolveOpenQuestion
- RecordDecision
- ResolveFlag

### UI
Severity-aware review panel:
- blocking questions,
- assumptions,
- dependencies,
- architecture warnings,
- quality findings,
- recommendations.

### Tests
- resolution/audit behavior,
- blocker calculation,
- decision recording.

### Exit Criteria
AI uncertainty and cross-system concerns are explicit before approval.

---

## Slice 8A — Identity, Ownership, and Reviewer Assignment

**Status: Implemented; all roadmap fields delivered and merged into `main`.**

### User Outcome
Authenticated users can see ownership, their assignments, and actions they are
authorized to take.

### Domain / Application
Introduce provider-neutral actor identity, Requirement ownership, reviewer
roles, assignments, and authorization policy. Confirmation becomes owner-only.

### Ports and Adapters
OIDC-compatible identity port with a deterministic fake offline adapter;
persistence adapters store ownership and assignments without OIDC SDK types.

### API / UI
Authenticated actor/assignment endpoints and authorization errors. Add owner
display/filter, Assigned to me, reviewer assignment, and truthful attribution.

### Tests / Exit Criteria
Fake identity, role/ownership authorization, filter, denial, and UI tests. No
owner-labelled action is available without a real actor and permission check.

Enhancement 8A.1 adds the branded `/login` route, Keycloak-managed local
password/recovery flows, explicitly linked Microsoft Entra brokering, and safe
deep-link restoration. See `docs/slices/enhancement-08a1-keycloak-login.md`.

---

## Slice 8B — Collaborative Clarification and Analysis Audit

**Status: Implemented; all roadmap fields delivered and merged into `main`.**

### User Outcome
Teams can assign, partially answer, and audit clarification questions across
immutable analysis rounds.

### Domain / Application
Introduce stateful question identity/status, blocker designation, assignee,
answer attribution, analysis identity/provenance, and immutable round history.
Use cases cover assign, ask, save partial answer, resolve, and inspect rounds.

### Ports and Adapters
Extend analysis/audit persistence ports and both adapters; provider output is
still normalized before entering domain models.

### API / UI
Question/assignment/round endpoints. Clarification UI gains severity, assignee,
Ask someone, per-answer actor/time, partial saving, and round history.

### Tests / Exit Criteria
State transition, authorization, provenance, attribution, immutable history,
partial save, malformed provider, and collaborative UI coverage.

---

## Enhancement 8B.1 — Business Need–Driven Intent Analysis

**Status: Implemented; all roadmap fields delivered and merged into `main`.**

### User Outcome
Authors can begin analysis with a title and business need. Requirement Owners
review AI-proposed outcomes, rules, and constraints before those proposals can
become confirmed context for backlog generation.

### Domain / Application
Make desired outcome optional for analysis eligibility. Add stable, versioned
intent proposals with append-only owner decisions, effective confirmed intent,
owner-only authorization, optimistic concurrency, confirmation gates, same-source
decision carry-forward, and source-change invalidation.

### Ports and Adapters
Extend the provider-neutral analysis candidate and focused analyzer adapters.
Use `analysis-v3` to distinguish evidence from suggestions, reject blank,
duplicate, malformed, or invented numeric content, and pass prior owner
decisions back into re-analysis. Store intent and history in existing versioned
analysis JSON; no relational migration.

### API / UI
Expose `business_intent` and a proposal-decision PATCH endpoint with central
403/404/409/422 translation. Intake marks desired outcome optional and starts
from the business need. Analysis shows provenance, pending decisions, effective
intent, owner Accept/Edit/Reject controls, and explicit confirmation blockers.

### Tests / Exit Criteria
Domain, use-case, adapter, API/OpenAPI, PostgreSQL JSON, activity/revision, UI,
and browser-flow coverage. Epic/Feature/Story prompts receive only source-backed
and owner-accepted/edited intent; no pending or rejected proposal crosses the
generation boundary.

---

## Enhancement 8B.2 — Batch Clarification Resolution

**Status: Implemented; all roadmap fields delivered and merged into `main`.**

### User Outcome
Owners and assigned reviewers can answer several active clarification questions
and submit every completed answer through one durable re-analysis job instead
of invoking the model once per question.

### Domain / Application
Keep the existing stable question, optimistic version, authorization, blocker,
and immutable-round rules. Add atomic stable-ID batch orchestration that
validates every answer before one analyzer invocation, rechecks all versions
after generation, and commits every resolution with one new analysis round.

### Ports and Adapters
Reuse the existing analyzer, audit, transaction, job, activity, notification,
and persistence ports/adapters. Store the batch in existing job-command JSON;
no relational migration or provider change is required.

### API / UI
Add a stable-ID batch resolution endpoint and durable
`resolve_clarification_questions` job operation while retaining single-question
and legacy compatibility routes. Replace per-card model actions with one
section-level action that submits all nonblank visible answers and reports the
durable batch size; Save draft remains provider-free. Group extracted evidence
as Known facts, Business rules, and Constraints, and group confirmation items
as Assumptions, Open questions, Ambiguities, and Potential dependencies.

### Tests / Exit Criteria
Application, authorization, concurrency, rollback, API/OpenAPI, job persistence,
activity/reporting, UI, and browser coverage prove multiple answers produce one
job, one analyzer cycle, one audited round, and no partial commit on failure.
UI coverage also proves evidence and questions render under their categories.

---

## Enhancement 8B.3 — Re-analysis Question Reconciliation

**Status: Implemented; all roadmap fields delivered and merged into `main`.**

### User Outcome
After a clarification batch is re-analysed, reviewers see only questions that
remain relevant. Obsolete wording is retired, changed gaps are presented as
linked revisions, genuinely new gaps are added, and all prior work remains
auditable.

### Domain / Application
Add immutable `AnalysisQuestionChange` records with retained, retired,
replaced, and created actions. Replacement questions have new application-owned
IDs linked through `replaces_question_id`, inherit classification and assignment,
and leave any draft archived on the superseded question. Reconciliation protects
human questions and atomically rechecks the complete active-question snapshot.

### Ports and Adapters
Extend the provider-neutral analyzer boundary with active-question context,
complete review candidates, and genuinely new uncertainties. `analysis-v4`
requires exactly one consistent review per active AI question and rejects
missing, duplicate, unknown, human, blank, or malformed decisions. Existing
JSON persistence gains optional question-change and replacement-link fields;
legacy snapshots default them empty and no relational migration is required.

### API / UI
Existing analysis, round, and batch-resolution endpoints return
`question_changes`; question responses add `replaces_question_id`. The active
workspace hides superseded questions, shows a compact reconciliation summary,
and labels revisions. Round history shows retired wording, decision reasons,
replacement links, and archived drafts.

### Tests / Exit Criteria
Domain, application, adapter, atomicity, API/OpenAPI, PostgreSQL JSON, activity,
UI, and browser coverage prove complete reconciliation, protected human
questions, linked provenance, current-blocker confirmation, and rollback on
provider or concurrent-state failure.

---

## Slice 8C — Async AI Jobs and Notifications

> Status: **implemented; merged into `main`**. Every roadmap field is
> implemented; no scope was dropped.

### User Outcome
Long-running analysis and generation continue safely after navigation and expose
durable retry/cancel/failure state.

### Domain / Application
Introduce durable AI job identity/status and orchestration use cases, including
retry/cancel rules. Existing synchronous operations remain during migration.

### Ports and Adapters
Job queue/repository and notification ports with fake offline adapters and
production-capable durable implementations.

### API / UI
Start/status/retry/cancel endpoints. UI reads persisted `reanalysing` and other
job states, can leave safely, and offers opt-in completion/failure notification.

### Tests / Exit Criteria
Idempotency, retry/cancel, restart durability, notification opt-in, status
polling, and migration coverage. The worklist `reanalysing` status becomes live.

---

# Release 4 — Human Governance and Traceability

## Slice 9 — Review and Approval Workflow

**Status: Implemented; merged into `main`. No roadmap field was dropped.**
See `docs/slices/slice-09-review-and-approval-workflow.md`.

### User Outcome
Generated content can move through a controlled human review lifecycle.

### Domain
Introduce:
- BreakdownStatus,
- Approval,
- ApprovalDecision,
- ReviewComment.

Candidate states may include:
- GENERATED,
- UNDER_REVIEW,
- NEEDS_REVISION,
- APPROVED.

### Application Use Cases
- SubmitForReview
- ApproveEpic
- ApproveFeature
- ApproveStory
- RejectStory
- ApproveBreakdown

### Rules
- generated != approved,
- ADO publication requires approved state,
- blocking open questions may prevent final approval according to configured business policy.

### UI
Review dashboard with completion and blockers.

### Tests
- valid/invalid transitions,
- approval guards,
- rejection/revision paths.

### Exit Criteria
A full human-approved backlog can exist without ADO.

---

## Slice 10 — Persistence and Versioning

### Status
Implemented; merged into `main`. PostgreSQL persistence, immutable revision history, API/UI
comparison, and live restart validation are delivered. Production recovery qualification remains open.

### User Outcome
Requirements and approved/generated revisions are durable and traceable over time.

### Domain
Introduce:
- RequirementRevision,
- BreakdownRevision.

### Ports
- RequirementRepositoryPort evolves for persistence,
- BreakdownRepositoryPort,
- ApprovalRepositoryPort if separate storage is justified.

### Infrastructure
Introduce production persistence, preferably PostgreSQL, behind adapters.
Use migrations.

### Application Use Cases
- CreateRequirementRevision
- GetRevisionHistory
- CompareBreakdownVersions

### UI
Revision history and change summary.

### Rules
Do not overwrite approved historical revisions.

### Tests
- persistence integration tests,
- revision immutability/history,
- migration tests where practical.

### Exit Criteria
Full revision traceability exists.

---

## Slice 10A — Activity, Saved Views, and Reporting

**Status: Implemented; merged into `main`.**

### User Outcome
Reviewers can inspect an audit-derived activity feed, reuse worklist views, and
understand delivery/clarification trends.

### Domain / Application
Define saved-view criteria and reporting queries over existing immutable audit
events; do not duplicate source events into dashboard-only domain state.

### Ports and Adapters
Activity/reporting read ports with in-memory and PostgreSQL implementations;
saved-view persistence is actor-scoped through the identity boundary.

### API / UI
Activity, saved-search, and aggregate-report endpoints. Add last-updated
attribution, saved filters, weekly counts, clarification-loop metrics, oldest
blockers, and functional Reports navigation.

### Tests / Exit Criteria
Audit projection, actor isolation, aggregation/time-boundary, saved-view, and UI
tests. Every metric and activity item traces to persisted events.

---

# Release 5 — Portable Backlog

## Slice 11 — Neutral Export

**Status: Implemented; merged into `main`. No roadmap field was dropped.**

### User Outcome
An approved backlog can be exported without requiring ADO.

### Application
- ExportBreakdown

### Port
- BacklogExportPort

### Adapters
- Deterministic UTF-8 JSON package (`schema_version: "1.0"`).
- Lossless, formula-safe XLSX workbook using `openpyxl`.

### Rules
- Export only the exact requested immutable revision when it carries a matching,
  content-bound final approval.
- Authorize the current Requirement Owner or an assigned reviewer.
- Do not regenerate or persist content during export.

### API
- `GET /requirements/{requirement_id}/revisions/{revision_number}/export?format=json|xlsx`

### UI
- Export the selected eligible revision with approval attribution and format choice.

### Tests
- stable JSON schema and deterministic ordering,
- hierarchy and acceptance-criteria preservation,
- XLSX structure, relationships, formula safety, and format limits,
- authorization, lifecycle, historical revision, API, UI, persistence, and browser
  download behavior.

### Exit Criteria
Approved backlog is portable and integration-ready.

---

## Enhancement 11A — Requirement Knowledge Screening

**Status: Implemented; merged into `main`. No roadmap field was dropped.**

### User Outcome
Owners see possible duplicate and contradictory Requirements before confirming a new analysis.

### Domain
Trusted knowledge chunks, immutable screens, versioned findings and decisions,
duplicate Requirement state/linkage, and bilateral contradiction resolution.

### Application
Build the trusted Requirement-derived corpus, schedule fingerprinted durable screens,
classify retrieved candidates, enforce confirmation and duplicate-state gates, and keep
all findings advisory until explicit owner decisions.

### Ports
Provider-neutral embedding, hybrid knowledge index/search, relationship classifier,
knowledge review repository, and automatic screen scheduler ports.

### Adapters
Deterministic fake, OpenAI, and local OpenAI-compatible AI adapters; in-memory and
PostgreSQL/pgvector repositories using full-text/vector retrieval and reciprocal-rank fusion.

### API
Knowledge-review read and version-checked decision endpoints; additive AI-job origin,
knowledge operations, duplicate linkage, and worklist status fields.

### UI
A Requirement Knowledge journey panel with running/current/stale state, linked evidence,
provenance, decision history, and authorized distinct/duplicate/bilateral-resolution actions.

### Tests / Exit Criteria
Corpus boundaries, retrieval, citations, provider failures, scheduling, staleness,
confirmation gates, duplicate closure, two-owner resolution, notifications, persistence,
activity, API, component, and worklist behavior are covered.

---

## Enhancement 11A.1 — Lazy Knowledge Screening and Restart-Storm Prevention

**Status: Implemented; merged into `main`. No roadmap field was dropped.**

### User Outcome
Restarting the service never creates portfolio-wide screening work. Owners and assigned reviewers
receive one lazy, idempotent knowledge screen when they enter Knowledge or Confirm, and terminal
attempts remain stopped until a person explicitly retries them.

### Domain
Existing immutable job status, origin, Requirement version, and evidence-fingerprint concepts
govern retry eligibility; no provider or persistence concern enters the Domain.

### Application
Remove startup backfill, retain genuine change-driven screening, ensure a current screen lazily for
one authorized Requirement, suppress terminal automatic retries for the same fingerprint, and
carry related-change identity/version into idempotency.

### Ports
Extend the knowledge-screen scheduling boundary with explicit ensure outcomes and the durable job
repository with an atomic automatic-attempt reservation.

### Adapters
In-memory and PostgreSQL queues atomically reserve one automatic attempt. PostgreSQL migration
`012` cancels only queued automatic knowledge-screen jobs while preserving all other history and
work.

### API
Team-member-only `POST /requirements/{requirement_id}/knowledge-screen/ensure` returns `current`,
`scheduled`, `already_scheduled`, or `manual_retry_required` with the applicable job ID.

### UI
Knowledge and Confirm lazily ensure stale/required screening once per evidence fingerprint, show
queued/running/current/manual-retry states, and retain confirmation gating until review is current.

### Tests / Exit Criteria
Startup recovery without backfill, every change trigger, terminal suppression, manual retry and
priority, linked changes, atomic concurrency, migration selection/idempotency, authorization,
API/client, component, and browser behavior are covered.

---

## Enhancement 11B — Grounded Clarification-Answer Suggestions

**Status: Implemented; merged into `main`. No roadmap field was dropped.**

### User Outcome
An owner or assigned reviewer can request up to three concise answers grounded in trusted
Requirement evidence, select one into the existing answer draft, edit it, and deliberately
resolve/re-analyse through the existing human action.

### Domain
Immutable suggestion sets and cited evidence fingerprints; human clarifications retain an
optional originating suggestion ID without changing their human-confirmed status.

### Application
Search only current trusted knowledge for an active question, validate every citation,
persist zero-to-three suggestions with provenance, and hide stale results.

### Ports
Provider-neutral clarification suggester and suggestion-validation boundaries reuse the
embedding and hybrid-search ports from Enhancement 11A.

### Adapters
Fake, OpenAI, and local OpenAI-compatible suggestion adapters plus in-memory and PostgreSQL
suggestion persistence.

### API
Durable suggestion job operation, current-suggestion read endpoint, and additive
`source_suggestion_id` on clarification resolution.

### UI
Each active question exposes Suggest answers, rationale and linked evidence while retaining
free text; selection fills rather than submits the draft.

### Tests / Exit Criteria
Grounding, zero-result success, malformed citations, staleness, draft preservation,
selection/edit/manual answer behavior, provenance, API, component, and persistence are covered.

---

## Enhancement 11B.1 — Automatic Dual-Source Clarification Suggestions

**Status: Implemented; merged into `main`. No roadmap field was dropped.**

### User Outcome
Every active clarification question begins generating up to three supported answers as soon as
analysis completes, using clearly labeled current-analysis evidence, trusted cross-Requirement
knowledge, or both. Reviewers can refresh, select, edit, and deliberately submit an answer.

### Domain
Derived suggestion-source classification (`current_analysis`, `trusted_knowledge`, or `combined`)
and an explicit unconfirmed current-analysis evidence kind. Provider labels never establish trust.

### Application
Transactionally and idempotently queue one asynchronous suggestion job per active question after
analysis/re-analysis and after a human question is added. Keep suggestion failure independent from
analysis review, validate both evidence sets, cap the ranked result at three, and invalidate it when
the question or any cited evidence changes.

### Ports
Add an automatic suggestion scheduling port and extend the focused clarification suggester port
with separate current-analysis and trusted-knowledge evidence inputs.

### Adapters
Fake, OpenAI, and local OpenAI-compatible adapters use a versioned dual-source prompt. Existing
memory and PostgreSQL suggestion persistence remains compatible without a relational migration.

### API
Add the derived `source` field to `AnswerSuggestionResponse`; retain existing suggestion GET and
AI-job contracts and the `suggest_clarification_answers` operation.

### UI
Show automatic loading and progressive results directly on each question card, source badges,
supported-empty and unavailable/retry states, and a **Refresh suggestions** action. Selection fills
editable text and never submits it.

### Tests / Exit Criteria
Automatic scheduling/retry/idempotency, dual-source boundaries, provider/citation failures,
source derivation, compatibility and staleness, authorization, rollback, API/client generation,
component states, and browser review flow are covered.

---

# Release 6 — Azure DevOps

## Slice 12 — ADO Publication

**Status: Planned; not implemented.**

### User Outcome
An approved backlog can be previewed and explicitly published into Azure DevOps.

### Core Boundary
Application depends on a publication port, never on ADO client code.

### Port
- WorkItemPublisherPort or BacklogPublisherPort

### Infrastructure
- AzureDevOpsWorkItemAdapter
- ADO authentication/configuration adapter

### Mapping
- Domain Epic → configured ADO Epic work item type
- Domain Feature → configured ADO Feature type
- Domain UserStory → configured ADO User Story type
- preserve parent/child links

### ADO Configuration
Keep outside domain:
- organization,
- project,
- area path,
- iteration,
- field mappings,
- process/work-item type names.

### UI
Publication preview:
- target project,
- item counts,
- hierarchy,
- publish confirmation.

### Rules
Only approved revision is publishable.
No automatic publish after AI generation.

### Tests
- fake publisher,
- ADO adapter contract tests,
- partial publication failure handling,
- link creation behavior.

### Exit Criteria
Approved backlog can be safely published to ADO.

---

## Slice 13 — External ID Mapping and Safe Republish

**Status: Planned; not implemented.**

### User Outcome
The system knows which local items already exist in ADO and avoids duplicates.

### Domain/Application Model
Introduce separate:
- ExternalWorkItemMapping
- PublicationResult
- PublicationStatus

Do not add `ado_id` fields to Epic/Feature/Story domain entities.

### Application Use Cases
- GetPublicationStatus
- DetectAlreadyPublished
- UpdatePublishedBacklog
- RetryFailedPublication where safe

### Tests
- idempotency,
- duplicate prevention,
- partial recovery,
- mapping persistence.

### Exit Criteria
Republish/update behavior is controlled and traceable.

---

# Release 7 — Maintainable Knowledge Platform

## Slice 14 — Architecture Knowledge Management

**Status: Implemented; merged into `main`.** Deployment-specific local-model qualification pending.

**Specification:** `docs/slices/slice-14-architecture-knowledge-administration-and-local-rag.md`

### User Outcome
Authorized maintainers can update SMB architecture/system ownership without editing the AI system prompt.

### Domain
Introduce/evolve:
- ArchitectureKnowledge,
- SystemDefinition,
- SystemRelationship,
- Ownership.

### Port
- ArchitectureKnowledgeRepositoryPort

### Adapters
- file/YAML,
- database,
- later connector/RAG source if approved.

### UI
Admin screens for systems, capabilities, ownership, known constraints, relationships.

### Rules
Knowledge changes are versioned/auditable where required.

### Exit Criteria
Architecture knowledge is maintainable independently of code/prompt release.

The implemented slice adds versioned releases, audited publication, maintained
ownership, cited local hybrid retrieval, durable build/mapping jobs, and a
browser administration workspace while preserving the deterministic fake path.

---

# Release 8 — Advanced Agent Orchestration

## Slice 15 — Agent Workflow Optimization

**Status: Planned; not implemented.**

### Goal
Improve quality/cost/recoverability only after the single orchestrated workflow is stable.

### Initial Architecture
Keep one application-level Requirement Breakdown workflow that performs:
1. Analyze
2. Generate Epic
3. Generate Features
4. Generate Stories
5. Map Architecture
6. Validate
7. Produce Review

### Consider Multi-Agent Split Only When Evidence Exists
Potential future specialists:
- Requirement Analysis Agent
- Backlog Decomposition Agent
- Architecture Analysis Agent
- Quality Review Agent

### Do Not Split Merely for Naming
Require a real reason:
- different model/provider,
- distinct scaling,
- distinct permissions,
- independent lifecycle,
- measurable quality gain.

### Exit Criteria
Any multi-agent change has tests, observable benefits, and preserves application/domain boundaries.

---

# Release 9 — Enterprise Identity, Administration and Operations

**Status: Specified; not scheduled.** Each enhancement below has a slice specification with
recorded decisions (2026-09-26; administration portal sub-slice F on 2026-09-28). Each
specification says implementation must not begin until it is scheduled here. Listing an
enhancement in this release records its scope; it does **not** schedule it. The roadmap owner
assigns each one (or its first sub-slice) a position in the *Recommended Delivery Order* before
work starts. The fields below summarize the specifications, which remain authoritative.

## Enhancement 8A.2 — Active Directory Login with Keycloak-Managed Roles

**Status: Specified; not scheduled.**
**Specification:** `docs/slices/enhancement-08a2-ldap-login-keycloak-roles.md`

### User Outcome
People sign in with their existing Active Directory credentials through Keycloak LDAP
federation. Only people granted the Keycloak `app_user` role can use the application; nobody
has a separate password for it.

### Domain
No change. `ActorProfile.roles` already carries provider-neutral global roles.

### Application
`ResolveCurrentActor` gains the required-role precondition, as defense in depth behind the
Keycloak gate. No other use case changes.

### Ports
No change.

### Adapters
The OIDC adapter is unchanged; the fake identity adapter adds `app_user` to its personas.
Keycloak realm and deployment gain LDAP federation, roles as groups carrying client roles, and
a lockout threshold below AD's. Microsoft Entra brokering and local Keycloak accounts are
removed.

### API
Protected routes return 403 for an OIDC actor without `OIDC_REQUIRED_ROLE`;
`GET /identity/config` returns the configurable password-login label.

### UI
No frontend code change. The Keycloak login theme gains AD wording and an access-denied
explanation.

### Tests
Required-role precondition, fake personas, OpenAPI check, and the staging acceptance list in
the specification against the real AD.

### Prerequisites
From the AD team: LDAPS host and CA certificate, a read-only service account, the users' base
DN, the domain lockout policy, and the sign-in attribute.

## Enhancement — Centralized Logging in Graylog

**Status: Specified; not scheduled.**
**Specification:** `docs/slices/enhancement-centralized-logging-graylog.md`

### User Outcome
An operator retrieves every log line related to one Requirement by its ID, follows one request
from the edge to the API, and watches a security stream of failed sign-ins, lockouts, 401s and
403s, in development and production.

### Domain
No change.

### Application
Draft promotion writes a `requirement.draft_promoted` log line with both IDs. No behaviour,
port or return value changes.

### Ports
No change. Log context is an infrastructure/interface concern.

### Adapters
Structured log context and formatter fields in `infrastructure/observability`; the background
workers set a correlation scope per unit of work. Fluent Bit reads every container's Docker
logs and forwards GELF to a project-shipped Graylog stack. Retention is 30 days operational and
365 days security, both configurable.

### API
No contract change. Request log lines gain `requirement_id`, `draft_id`, `job_id` and the
opaque `actor_id`; new `SERVICE_NAME` and optional `RELEASE` settings.

### UI
No change.

### Tests
Log-context propagation, field presence, no names, emails, bodies or provider payloads in
logs, and the Graylog stack acceptance in the specification.

## Enhancement — Administration Portal

**Status: Specified; not scheduled.** Six independently shippable sub-slices.
**Specification:** `docs/slices/enhancement-admin-portal.md`

### User Outcome
Configuration administrators change live settings, AI model profiles and system prompts with
validation, history and rollback, applied on every process within seconds. Access
administrators grant access and roles from the directory, sign people out, and hand a leaving
owner's Requirements to someone else with a recorded reason.

### Sub-slices
- **A — Foundation (read-only):** admin roles, `/admin` overview, effective configuration and
  admin audit.
- **B — Live settings (Tier 1):** versioned runtime settings with history, refreshed on every
  process.
- **C — Users and access:** directory search, group membership and sign-out through Keycloak;
  depends on 8A.2.
- **D — AI model management (Tier 2):** model profiles move to a versioned store, with
  validation, smoke test, activation, embedding rebuild and rollback.
- **E — Requirement ownership administration:** administrative transfer and reviewer changes
  with a mandatory reason.
- **F — System prompts:** versioned prompt per AI operation, with built-in defaults, a locked
  guard, validation, smoke test, activation, reset and rollback; needs A and B.

### Domain
Administrative variants of transfer and reviewer changes in `RequirementAccess` with
`ADMIN_REASSIGNED`; value objects for admin audit entries, runtime-setting versions and
system-prompt versions.

### Application
Overview, configuration, audit, runtime-setting, directory, model-profile, ownership and
system-prompt use cases. Every mutation authorizes `config_admin` or `access_admin` in the
application layer and writes an audit entry in the same transaction.

### Ports
`RuntimeSettingsPort`, `AdminAuditPort`, `ProcessRegistryPort`, `AccessDirectoryPort`,
`ModelProfileStorePort`, `SystemPromptPort` and `SystemPromptStorePort`.

### Adapters
PostgreSQL and in-memory/fake adapters and migrations; a Keycloak admin REST adapter; the
settings refresh loop and process heartbeat. The OpenAI, local and OpenRouter adapters take
their prompts from `SystemPromptPort`.

### API
Authenticated `/admin/...` routes for overview, configuration, settings, models, prompts,
users, groups, ownership and audit; smoke tests and rebuilds use the provider rate limit.

### UI
An admin-only **Administration** area (`/admin`, `/admin/settings`, `/admin/models`,
`/admin/prompts`, `/admin/users`, `/admin/ownership`, `/admin/audit`), governed by
`docs/ux-plan.md`, `docs/design-system.md` and WCAG 2.2 AA. This is feature work (new client
code, hooks and state), outside the redesign's presentation-only rule.

### Tests
As listed in the specification, per sub-slice.

### Dependencies and order
8A.2 for the Keycloak side of A and C; Graylog optional. A new ADR amending `AGENTS.md` §4.5.
Suggested order: A, B, F, E, C (after 8A.2), D.

## Enhancement — Knowledge Center

**Status: re-planned 2026-10-06 for the three repositories (ADR-0099 Amendment 1). B1, A′,
B2, B3, C and D are delivered. E is scheduled 2026-10-06 (ADR-0102): E1, then E2.**
**Specification:** `docs/slices/enhancement-knowledge-center.md`

### User Outcome
A knowledge administrator manages architecture knowledge, the Requirement knowledge base and
the shared library from knowledge-portal. A Requirement supplied as a document is screened from
its content. Obsolete Requirements are retired from duplicate screening, and owners re-confirm
knowledge on a review cycle. Later, historic BRDs come in with their delivered Azure DevOps
breakdown as cited prior art.

### Sub-slices (each built where its data lives)
- **B1 — Attachments in the requirement corpus** (requirement-portal), **next.** An
  `attachment` source kind: analysis-included attachment passages are indexed and screened,
  and re-indexed when an attachment's version or inclusion changes.
- **A′ — Knowledge Center front page** (knowledge-portal). Freshness per body, catalogue
  failures, and Requirement-corpus health read over a new internal route. The rest of A was
  delivered by the split: the portal itself, `knowledge_admin`, and the redirects here.
- **B2 — Corpus and portfolio findings.** The queries and internal reads are here; the screens
  and owner nudges are in knowledge-portal.
- **B3 — Retire, reinstate and bulk reindex.** The rules and audit are here, behind internal
  write routes; the actions are in knowledge-portal.
- **C — Library and catalogue curation** (knowledge-portal): admin reassign and withdraw,
  bulk retry, multi-file upload into a draft, comparing any two versions, the `.doc` message,
  and citation counts.
- **D — Review cycles** (knowledge-portal): review-due dates (180 days by default),
  confirmation, the portal's own reminders, and "not reviewed since" in citations.
- **E — Historic Requirements** (split; ADR-0102). **Scheduled 2026-10-06 by this explicit
  roadmap change**: a *read-only* Azure DevOps import ahead of Slices 12–13, which `AGENTS.md`
  §9 otherwise forbids. Writes to ADO stay in Slices 12–13. The open questions are answered
  except the ADO edition, so the connector is built against a fake first.
  - **E1** (knowledge-portal): BRD import, the read-only ADO connector, preview, publish,
    refresh with a diff, and the lineage viewer. Published historic Requirements become
    `historic_requirement_changed` events on the outbox this service already polls.
  - **E2** (here): the historic corpus (`historic_brd`, `historic_backlog`, reference trust),
    prior art by search then the AI judge, informational on the Knowledge step.
- **F — AI-assisted catalogue extraction:** **delivered**
  (`docs/slices/enhancement-squad-and-architecture-catalogues.md`, ADR-0081, then
  knowledge-portal).

### Where the work goes
- **Requirement-portal:**
  - **B1, B2 and B3:** domain, use cases, migrations and the new service-token routes
    (`/internal/knowledge/...`, `/internal/references/citation-counts`);
  - **D:** the "not reviewed since" label;
  - **E:** prior art.
- **knowledge-portal:** the screens for A′, B2, B3, C, D and E, and the review state.
- **Requirement data never moves to the knowledge database.**

### Dependencies and order
ADR-0099 Amendment 1 (written with the re-plan). 8A.2 for the real `knowledge_admin` role in
production; administration portal C to manage the `knowledge-admins` group. Review reminders
are knowledge-portal's own, so they need no 8C change. A new ADR is needed before E. Order: B1,
then A′, B2, B3, C, D, then E.

---

# Cross-Cutting Workstreams

# Production-Readiness Remediation — Implementation delivered; release qualification open

**Status:** Implementation merged into `main`. Current hosted CI is tracked in the delivery ledger above; target-environment production release prerequisites remain outstanding.

The release-validation checkpoint is `docs/slices/production-readiness-qualification.md`. It
records the synthetic nonempty recovery rehearsal (now a CI job) and the HTTP load measurements,
merged through PR #39.
Production-environment and representative-corpus qualification remain separate release gates.

The remediation specification records completed local validation. The user has explicitly
authorized the generation-quality enhancement below; production maintenance, backup/restore
rehearsal and deployment remain separate operational release prerequisites.

### Domain
- Preserve retained descendant identities and immutable approval history during invalidation.
- Resolve effective approval from the latest decision for the current content fingerprint.
- Add positive optimistic versions to mutable persisted state and collection versions.
- Fence durable job attempts with Requirement-scoped leases and attempt tokens.

### Application
- Centralize Requirement membership/ownership authorization.
- Require mutation preconditions and content-bound generation context tokens.
- Use short atomic units of work and keep provider/extraction work outside write transactions.
- Keep worklist classification and attention precedence in the pure Application projector.

### Ports
- Version-aware repositories and set replacement contracts.
- Transaction, job lease/fencing, document blob, generation context, extraction-resource,
  and current-worklist projection boundaries.

### Adapters
- Coordinated reentrant in-memory transactions.
- PostgreSQL optimistic writes, job leases, immutable blobs, and maintained worklist rows.
- Bounded subprocess extraction and hardened OIDC/provider clients.

### API
- Typed mutation bodies, required versions/fingerprints/context tokens, safe correlated errors,
  and `409` stale-precondition behavior.

### UI
- Carry all preconditions, expose effective permissions, preserve forms after conflicts,
  and clear actor-bound state when identity changes.

### Tests
- Maintain the acceptance matrix in the remediation specification and require PostgreSQL/pgvector
  in CI. Local validation is recorded in that specification; verify CI for each delivered change.

### Specification
- `docs/slices/production-readiness-remediation.md`

# UI/UX Redesign — Phases 0–10 delivered; follow-ups open

**Status:** Phases 0–10 implemented and merged into `main`. Governed by `docs/ux-plan.md`,
`docs/design-system.md` and `DESIGN.md` ("The Working Paper"), under the presentation-only
rule in `CLAUDE.md`: no hook, service, state, data-fetching or API change. Each phase ran an
impeccable critique on its live screen before its PR (`.impeccable/critique/`).

| Phase | Scope | Specification | PR |
|---|---|---|---|
| 0 | Foundation: tokens, one stylesheet rule per selector, shell, primitives, login, keyboard pass | `docs/slices/redesign-phase-0-foundation.md` | [#46](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/46) |
| 1 | Worklist and shell `/` | `docs/slices/redesign-phase-1-worklist-shell.md` | [#47](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/47) |
| 2 | Clarify and Confirm, one screen in two modes | `docs/slices/redesign-phase-2-clarify-confirm.md` | [#48](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/48) |
| 3 | Review and approve `/review`, evidence before sign-off | `docs/slices/redesign-phase-3-review-approve.md` | [#49](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/49) |
| 4 | Backlog `/breakdown/*` | `docs/slices/redesign-phase-4-backlog.md` | [#50](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/50) |
| 5 | Knowledge `/knowledge` and Source `/capture` | `docs/slices/redesign-phase-5-knowledge-source.md` | [#51](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/51) |
| 6 | Intake `/requirements/new` | `docs/slices/redesign-phase-6-intake.md` | [#52](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/52) |
| 7 | Documents `/documents`, `/documents/:id` | `docs/slices/redesign-phase-7-documents.md` | [#54](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/54) |
| 8 | Activity and Reports | Commit record | [#56](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/56), [#58](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/58) |
| 9 | History `/revisions` | Commit record | [#59](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/59) |
| 10 | Legacy style layer retired onto the primitives | Commit record | [#60](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/60) |

### Open product decisions (`docs/ux-plan.md` §6)
- Whether a Requirement mid-decomposition (`features`, `stories`) opens on Review or on Backlog.
  `journey.ts` deliberately stops at Backlog until this is decided, so the rail's Next block
  still points at Backlog from Review and says "Review the generated backlog" on Backlog.
- Whether Review becoming journey step 6 should also change its URL. The plan keeps every URL.

### Follow-ups raised by the phases, outside the presentation-only rule
Each needs its own decision before it is made; none is scheduled.
- **Product decisions:** undo for one-click Story approval (Phase 3); what Enter submits on
  Intake (Phase 6); a shareable comparison URL, running a comparison on arrival, and a friendlier
  export filename (Phase 9); filters that survive navigation on the worklist and catalogue
  (Phase 7).
- **Data or API changes:** Story counts for collapsed Features on the Epic page and banner
  (Phase 4); the linked Requirement's title and both sides of a contradiction on knowledge
  findings, and a reason for closing as duplicate (Phase 5); naming the blocking file in the
  Source verdict (Phase 5); hidden sheets' own names from the API (Phase 7).
- **Page logic:** the Intake URL follows the draft after the first autosave (Phase 6); including
  or excluding a draft's file from its document detail page (Phase 7); the Next block deferring
  to a stage's own verdict (Phase 5); the live region announcing save completion (Phase 3).
- **Presentation leftovers:** the assignee slot truncating at 1280px (Phase 2); the breadcrumb's
  last crumb and dead `focused={false}` branches (Phase 4); a gated "Save and analyse" click with
  no visible response and the Source drawer's unpinned actions (Phase 6); a verification critique
  of the finished Backlog (Phase 4).
- **Carried by another slice:** the library and architecture knowledge pages keep their legacy
  styles until the Knowledge Center moves them (Phase 10).

---

These are not independent releases; implement them only as the relevant slice introduces the need.

## Security
- secret handling,
- prompt injection resistance for requirement/source content,
- provider data minimization,
- explicit ADO write authorization,
- auditability.

## Observability
- request correlation,
- LLM call metrics,
- error categorization,
- publication audit,
- no sensitive payload logging by default.

## Cost Control
- focused LLM calls,
- regeneration at Feature/Story granularity,
- caching only when behavior is understood and safe,
- token/model configuration outside domain.

## UI/UX
- show generation state,
- show AI vs human-owned content,
- preserve edits,
- explicit blockers,
- accessible forms and review views.

---

# Recommended Delivery Order

The foundation through Slice 11, Slice 14, their delivered enhancements, document-knowledge
implementation, production-readiness remediation and the UI/UX redesign (Phases 0–10) are
already merged. They are not a new implementation queue. The remaining order preserves the
approved future-slice sequence:

0. **Three-repository platform split** (ADR-0098): explicitly scheduled 2026-10-02 ahead of the items below. It
   moves the library and catalogues to `knowledge-portal`. Done 2026-10-05.
0a. **Knowledge Center B1 — attachments in the requirement corpus**, scheduled 2026-10-06
   (`docs/slices/enhancement-knowledge-center.md`, ADR-0099 Amendment 1). Then A′, B2, B3, C
   and D, all delivered.
0b. **Knowledge Center E — historic Requirements and ADO lineage**, scheduled 2026-10-06
   (ADR-0102): E1 in knowledge-portal, then E2 here. Its ADO access is read-only; publication
   stays Slices 12–13 below.
1. Merge the pending human-answer citation salvage (`0d42039`) from
   `claude/fix-analysis-citations-and-proxy`.
2. Close production release qualification: complete the environment, quality and capacity
   gates listed in the delivery ledger above. The qualification tools are merged (PR #39).
3. Slice 12 — ADO Publication.
4. Slice 13 — External ID Mapping and Safe Republish.
5. Slice 15 — Agent Workflow Optimization, only when justified by evidence.

### Specified, awaiting a position in this order

These have specifications with recorded decisions but are not yet sequenced. Scheduling one
means inserting it above; until then, implementation must not begin.

- **Enhancement 8A.2** — AD login with Keycloak-managed roles. It unblocks the Keycloak side of
  administration portal A and C and the Knowledge Center's real `knowledge_admin` role, so it
  naturally precedes them. Needs the AD team's prerequisites.
- **Centralized logging in Graylog** — independent of the others; supports the operational
  release gates.
- **Administration portal** — sub-slices in the order A, B, F, E, C (after 8A.2), D.
- **Knowledge Center** — B1, A′, B2, B3, C and D are delivered, and F before them. **E is
  scheduled 2026-10-06** (E1, then E2; ADR-0102), as the explicit roadmap change for its
  read-only ADO import ahead of Slices 12–13.
- **Enhancement 5D.1** — maintained templates/examples. Its recorded debt stays in `AGENTS.md`
  §19 until it is scheduled.
- **UI/UX redesign follow-ups** — the two §6 product decisions and the raised items under
  *UI/UX Redesign* above.

Do not reorder just because an external integration is exciting. The ADO adapter becomes straightforward only after the internal backlog model and approval lifecycle are stable.

---

# Milestone View

| Milestone | Slices | Result | Implementation status |
|---|---|---|---|
| R0 Foundation | 0 | Clean, testable workspace | Merged into `main` |
| R1 Requirement MVP | 1–3 | Requirement → Analysis → Epic | Merged into `main` |
| R2 Breakdown MVP | 4, 4A, 5, 5A–5D, 6 | Desktop review + structured context + Stories + quality | Merged into `main`; templates remain deferred to 5D.1 |
| R3 SMB Intelligence | 7, 8, 8A–8C | Architecture + flags + identity + collaborative/async analysis | Merged into `main` |
| R4 Governance | 9, 10, 10A | Approval + revisions + activity/reporting | Merged into `main` |
| R5 Portability | 11 | Neutral export | Merged into `main` |
| R5A Requirement Knowledge | 11A–11B.1 | Duplicate/conflict screening + lazy restart-safe screening + automatic dual-source clarification suggestions | Merged into `main` |
| R6 ADO | 12–13 | Safe ADO publication/update | Planned |
| R7 Knowledge | 14 | Maintainable architecture knowledge | Merged into `main`; deployment-specific local-model qualification open |
| R8 Advanced AI | 15 | Evidence-driven orchestration optimization | Planned; evidence-gated |
| R9 Enterprise identity, administration and operations | 8A.2, Graylog, administration portal, Knowledge Center | AD sign-in, centralized logs, admin portal, one home for knowledge | Specified; not scheduled |
| UI/UX redesign (cross-cutting) | Phases 0–10 | Working Paper design system across every screen | Merged into `main`; follow-ups open |

These are implementation milestones, not production release approvals. Document-knowledge and
operational qualification status is tracked in the delivery ledger at the top of this roadmap.

---

# Exported Wireframe Coverage

This matrix is the scope ledger for `RE Wireframes.dc.html`. “Implemented” means
the capability is merged into `main` and must not be reimplemented; release gates remain separate. “Planned” names
the only slice authorized to add it.

| Wireframe capability | Status | Slice |
|---|---|---|
| Desktop worklist, attention, filters, search, sort, pagination | Implemented | 5B |
| One-page two-field intake with guidance and analyse/save-only actions | Implemented | 5B |
| Clarification progress, answers, confirmation gate | Implemented | 5B |
| Epic / Feature / Story review and edit actions | Implemented | 4A / 5A / 5B restyle |
| Staleness propagation after source changes | Implemented | 3–5 |
| Immutable revisions and comparison | Implemented | 10 |
| Structured intake, autosave, resume | Implemented | 5C |
| Source Documents: attachments, extraction, selection, catalogue, preview | Implemented | 5D |
| Maintained template/example library | Planned | 5D.1 (requires scheduling) |
| INVEST/SPIDR quality panel | Implemented | 6 |
| Systems, squads, dependencies, cross-system warnings | Implemented | 7 |
| Unified severity-aware flags and decisions | Implemented | 8 |
| Identity, owners, reviewer assignment, Assigned to me | Implemented | 8A |
| Stateful/assigned questions, answer attribution, analysis rounds | Implemented | 8B |
| Durable AI jobs, live `reanalysing`, notifications | Implemented | 8C |
| Story/full-backlog approval, comments, Backlog navigation | Implemented | 9 |
| Activity feed, saved views, metrics, Reports navigation | Implemented | 10A |
| Requirement duplicate/contradiction knowledge review | Implemented | 11A |
| Grounded clarification-answer suggestions | Implemented | 11B |
| Automatic dual-source clarification suggestions | Implemented | 11B.1 |
| Dedicated mobile stepped journey | Not planned | Explicitly excluded from 5B |


## Enhancement — Product and journey context on impacts

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#100](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/100) before the `d5cfb57` snapshot. See `docs/slices/enhancement-impact-product-context.md` and ADR-0097. Slice 3e, the last of the structured-architecture-document plan; includes declared frontend feature work.

### Domain
- `ProductContext` (with `OfferingDuty`) and `JourneyStep` (with `JourneyNeighbour`) on `ArchitectureImpact`; a journey step must be of a mapped system.
### Application
- `impact_product_context.py` finds offerings the item names (by name or code, or a component's), narrowed by component and order type, and each mapped system's journey steps with the activities before and after; the resolver adds both from the pinned release.
### Ports
- `ArchitectureKnowledgeMatch.product_contexts` and `.journey_steps`.
### Adapters
- Payloads write both only when present; generation guidance strips both; export contract `1.5` with Product Context and Journey Steps sheets.
### API
- `ArchitectureImpactResponse.product_contexts` and `.journey_steps`; regenerated OpenAPI types.
### UI
- Impact panel groups "Product offering named" and "Journey steps to check", with compact forms.
### Tests
- Matching, narrowing, ranking, journey neighbours, focusing and cap, end-to-end mapping, payloads, fingerprints and guidance unchanged, export, and the panel.


## Enhancement — Journeys from documents

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#99](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/99) before the `d5cfb57` snapshot. See `docs/slices/enhancement-catalogue-journey-suggestions.md` and the ADR-0096 amendment. Slice 3d of the structured-architecture-document plan; includes declared frontend feature work.

### Domain
- A journey suggestion holds one whole journey, resolves its systems, offering, order type and components at classify and accept (`needs_offering` when its offering is missing), and replaces an existing journey only one by one; journeys merge across readings; offerings and their parts are found by id, code or name.
### Application
- Journey references resolve against the draft and offerings suggested beside it; readings of one journey become one suggestion; journeys are accepted after offerings and saved on accept.
### Ports
- No change.
### Adapters
- Table reader `catalogue-tables-v4` reads journey sections (activities, detail blocks, flow rules, integration details; offering and order type from the section); prompt `catalogue-extraction-v10` proposes lean journeys from prose; a small context reads without journeys, with a warning.
### API
- Candidate content carries the journey; `needs_offering` match; regenerated OpenAPI types.
### UI
- Journey suggestion wording and group; Edit and accept reuses the journey drawer, keeping absent systems and offerings chosen.
### Tests
- Classify, apply, replace, merge, lookups, reader with details and derived flow, broken journey left to the model, model mapping, lean fallback, merged suggestions, end-to-end accept-all, and the review UI.


## Enhancement — Journeys

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#93](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/93) before the `d5cfb57` snapshot. See `docs/slices/enhancement-journeys.md` and ADR-0096. Slice 3c of the structured-architecture-document plan; includes declared frontend feature work.

### Domain
- `Journey` with numbered activities, flow rules (decision, loop, parallel with rejoin) and activity integrations on the release; the flow is derived by `journey_edges`, never stored; named systems, offerings, order types and components cannot be removed.
### Application
- Draft updates and file import carry journeys; one evidence chunk per journey walks its activities with their systems.
### Ports
- `CatalogueContent.journeys`.
### Adapters
- YAML/JSON `journeys`; Excel Journeys, Activities, FlowRules and ActivityIntegrations sheets with row-level errors.
### API
- Journey schemas with derived edges out, ignored in; optional on draft updates; regenerated OpenAPI types.
### UI
- Journeys view with ordered activities table, drawn flow, rules in words and integrations; journeys editor and drawer under Edit manually.
### Tests
- Derived flow equals the reported 21 arrows, domain rules, files, workbook errors, diff, evidence, API, browse view and editor.


## Enhancement — Product offerings from documents

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#92](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/92) before the `d5cfb57` snapshot. See `docs/slices/enhancement-catalogue-offering-suggestions.md` and the ADR-0095 amendment. Slice 3b of the structured-architecture-document plan; includes declared frontend feature work.

### Domain
- A product suggestion holds one whole offering, resolves its systems at classify and accept, and replaces an existing offering only one by one; offerings merge across readings.
### Application
- Readings of one offering become one suggestion; offerings are accepted last and saved on accept.
### Ports
- No change.
### Adapters
- Table reader `catalogue-tables-v3` reads product sections (facts, proposition, rules, order types, values, audiences, components with gaps kept, responsibilities); prompt `catalogue-extraction-v9` proposes nested offerings from prose, made valid before use; compact answer schema; Markdown sibling-heading fix.
### API
- Candidate content carries the offering.
### UI
- Offering suggestion wording and group; Edit and accept reuses the offering drawer.
### Tests
- Classify, apply, replace, merge, reader, model mapping, merged suggestions, end-to-end accept-all, small-model room, and the review UI.


## Enhancement — Product offerings

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#91](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/91) before the `d5cfb57` snapshot. See `docs/slices/enhancement-product-offerings.md` and ADR-0095. Slice 3a of the structured-architecture-document plan; includes declared frontend feature work.

### Domain
- `ProductOffering` with order types, components, component → system responsibilities (role codes, order types, source confidence), customer value and audiences on the release; a named system cannot be removed; shared invariants module.
### Application
- Draft updates and file import carry offerings; one evidence chunk per offering names the systems behind each component.
### Ports
- `CatalogueContent.products`.
### Adapters
- YAML/JSON `products`; Excel Products, OrderTypes, OfferingComponents, Responsibilities and ProductPoints sheets with row-level errors.
### API
- Offering schemas on releases and optional on draft updates; regenerated OpenAPI types.
### UI
- Product offerings view with components table and component × system role table; offerings editor and drawer under Edit manually.
### Tests
- Domain rules, files, workbook errors, diff, evidence, API, browse view, editor and removal.


## Enhancement — Landscape domains, placements and descriptions from documents

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#90](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/90) before the `d5cfb57` snapshot. See `docs/slices/enhancement-catalogue-landscape-suggestions.md` and the ADR-0094 amendment. Slice 2b of the structured-architecture-document plan; includes declared frontend feature work.

### Domain
- `landscape_domain` and `placement` suggestions and a system description: matched, classified (`needs_domain`) and applied without replacing anything; moving a placed system is decided one by one.
### Application
- Accept order domains → systems → placements; accepting saves landscape domains; domain suggestions are never matched as systems.
### Ports
- No change.
### Adapters
- Table reader `catalogue-tables-v2` reads Domains tables, placements by heading, Domain or Sub-domain cell, and Function as the description; prompt `catalogue-extraction-v8` proposes the same from prose.
### API
- Candidate content gains `landscape_domain_id` and `parent_domain_id`; new kinds and match value.
### UI
- Wording for the new kinds, landscape group, and domain, placement and description fields in the suggestion editor.
### Tests
- Domain rules, reader output, model mapping, end-to-end accept-all, and the review UI.


## Enhancement — Landscape domains and system descriptions

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#89](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/89) before the `d5cfb57` snapshot. See `docs/slices/enhancement-system-landscape-domains.md` and ADR-0094. Slice 2a of the structured-architecture-document plan; includes declared frontend feature work.

### Domain
- `LandscapeDomain` tree apart from capability domains; systems gain `description` and `landscape_domain_id`; diff reports landscape domains and placement.
### Application
- Draft updates and file import carry landscape domains; evidence text gains description and landscape lines only when present.
### Ports
- `CatalogueContent.landscape_domains`.
### Adapters
- YAML/JSON `landscape_domains`, Excel `LandscapeDomains` sheet and Systems columns; older files import unchanged.
### API
- System fields, `landscape_domains` on releases and optional on draft updates; regenerated OpenAPI types.
### UI
- Description and landscape picker in the system drawer; landscape editor and tree; dossier description and path.
### Tests
- Tree rules, placement, files, diff, evidence, API, editor, drawer, Domains view and dossier.


## Enhancement — Reading catalogue tables without a model

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#88](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/88) before the `d5cfb57` snapshot. See `docs/slices/enhancement-catalogue-table-reader.md` and ADR-0093. Slice 1d of the structured-architecture-document plan.

### Domain
- No change.
### Application
- Suggestions keep the reader's provenance as their model and prompt version; table cells pass into segments.
### Ports
- `LocatedText.cells`, `ExtractionSegment.cells` and `.read`, `ProposedChange.reader`.
### Adapters
- `CatalogueTableReader` (systems, activities and integration-details tables by header) and `TableFirstCatalogueExtractor` in front of every provider; Markdown rows carry cells; prompt `catalogue-extraction-v7` reads only capabilities and constraints from rows already read.
### API
- No change; reader suggestions have model `catalogue-table-reader`.
### UI
- "Read from table" badge on those suggestions.
### Tests
- Reader against the synthetic landscape (systems, links, joins, GAP and INFERRED, determinism), the extractor wrapper, the prompt flag, the API and the badge.


## Enhancement — Prompt rules for catalogue tables and one id per system

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#87](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/87) before the `d5cfb57` snapshot. See `docs/slices/enhancement-catalogue-table-reading-rules.md` and the ADR-0085 and ADR-0088 amendments. Slice 1c of the structured-architecture-document plan.

### Domain
- `find_system` compares names with their words run together as a last, unambiguous fallback.
### Application
- Proposals re-resolve systems against a provisional draft with the suggested systems; a link listed from both ends without a kind is suggested once, with a note.
### Ports
- No change.
### Adapters
- Prompt `catalogue-extraction-v6` reads table rows as records (plain names, IDs as aliases, Function as a capability, Integrations as stated links, GAP rows left out); pictographs stripped from returned system names.
### API
- No change.
### UI
- No change.
### Tests
- Name decoration, extractor names, run-together matching, prompt rules, canonical ids across calls, both-ways merge and typed links.


## Enhancement — Heading- and table-aware Markdown passages

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#86](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/86) before the `d5cfb57` snapshot. See `docs/slices/enhancement-markdown-structured-passages.md` and the ADR-0090 amendment. Slice 1b of the structured-architecture-document plan (1a merged; 1c–3e follow).

### Domain
- No change.
### Application
- Segments carry their heading path as a section; old line-window citations open the first overlapping passage; index spans mix line and line-range locations.
### Ports
- `ExtractionSegment.section`.
### Adapters
- A dependency-free Markdown passage reader (headings, blocks, fences, pipe-table rows with repeated headers, front matter); prompt `catalogue-extraction-v5` with sections; batches and splits follow sections.
### API
- No change.
### UI
- No change.
### Tests
- Markdown reader against a synthetic landscape fixture, extractor and plain-text windows, index packing, citation fallback, sections in prompts and batching.


## Enhancement — Output-aware catalogue reading

**Status:** Merged ([#83](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/83)). See `docs/slices/enhancement-catalogue-output-aware-reading.md` and ADR-0091. Slice 1a of the structured-architecture-document plan (1b–3e follow).

### Domain
- No change; self-dependencies stay loadable in `CandidateContent` so stored suggestions still load.
### Application
- Proposals leave out a dependency of a system on itself, with a note; up to 1,200 passages per document.
### Ports
- No new ports.
### Adapters
- Calls sized from the model's output limit; a cut-off or full answer splits its part, within a bounded call budget; transports mark truncation; profile transport failures retried and matching failures contained; answer cap 200.
### API
- No change.
### UI
- No change; new notes appear in the existing reading notes.
### Tests
- Truncation and saturation splitting, budget limits, call sizing, profile retries, matcher containment, self-dependency notes, transport truncation markers.


## Enhancement — Capability domains

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#79](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/79) before the `d5cfb57` snapshot. See `docs/slices/enhancement-capability-domains.md` and ADR-0089. Third of three slices from the ontology/taxonomy/GraphRAG review.

### Domain
- A shallow, maintained tree of capability domains on the release; capabilities placed by `domain_id`; advisory `DomainSuggestion`s on impacts with no catalogued system.
### Application
- Unicode-aware fallback over catalogue words; the resolver places capabilities from the pinned release; evidence text gains domain paths.
### Ports
- `suggested_domains` on the match; `capability_domains` on catalogue content.
### Adapters
- Eight seed domains with all 31 capabilities placed; YAML/JSON/Excel domains; export `1.3`; prompts and fingerprints unchanged.
### API
- Domain schemas on releases, draft updates, capabilities and impacts.
### UI
- Workbench "Domains" view, domains editor, capability domain picker, impact domain chips, "Matched business areas" and "Closest business areas".
### Tests
- Tree rules, seed, diff, files, fallback, resolver, payloads, fingerprints, prompts, export and UI coverage.


## Enhancement — Typed system relationships

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#78](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/78) before the `d5cfb57` snapshot. See `docs/slices/enhancement-typed-system-relationships.md` and ADR-0088. Second of three slices; capability domains (ADR-0089) follow.

### Domain
- `RelationshipKind` on relationships and dependencies, an attribute not identity; kind edits diff as `changed`; suggestions set a stated kind and never clear one.
### Application
- Proposals merge by relationship identity and settle one kind; evidence words and fingerprints change only for specified kinds.
### Ports
- No new ports.
### Adapters
- Optional `kind` in YAML/JSON/Excel; extraction prompt `catalogue-extraction-v3`; export `1.2`.
### API
- `kind` on relationship, dependency and suggestion content schemas.
### UI
- "How" pickers in the dependency and suggestion editors; kind words in the dossier, diagram, suggestions and impact panel.
### Tests
- Kinds, legacy loading, diff, suggestions, merges, files, mapping, payloads, fingerprints, extraction and UI coverage.


## Enhancement — Connected systems in architecture impact mapping

**Status:** Implemented; merged in `smb-ai-requirement-agent` as [#77](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/77) before the `d5cfb57` snapshot. See `docs/slices/enhancement-architecture-impact-neighbours.md` and ADR-0087. First of three slices: typed relationships (ADR-0088) and capability domains (ADR-0089) follow.

### Domain
- One-hop, both-direction adjacency over published relationships, capped with an omitted count; connected systems kept apart from mapped ones by impact invariants.
### Application
- The resolver adds connected systems and their ownership from the pinned release; fingerprints and generation prompts ignore them.
### Ports
- `ArchitectureKnowledgeMatch` gains defaulted connected-system fields.
### Adapters
- Optional payload keys; neutral export `1.1` with a "Connected Systems" sheet.
### API
- `ArchitectureImpactResponse` gains `adjacent_systems`, `adjacent_dependencies` and `adjacent_omitted`.
### UI
- "Connected systems to check" in the impact panel; one line on Stories.
### Tests
- Adjacency, invariants, resolver, legacy payloads, stable fingerprints, prompt exclusion, export and panel coverage.


## Enhancement — Quality and risks during generation

**Status:** Implementation merged into `main`; live local-model semantic quality remediation remains open. Hosted CI is tracked in the delivery ledger above. See `docs/slices/enhancement-generation-quality.md`.

### Domain
- Retain INVEST thresholds and explicit uncertainty; bind checked proposal evidence to its sources.
### Application
- Prepare, generate, check, optionally refine once, then atomically save content and remaining concerns.
- Reuse current assessment evidence; preserve edits, approval checkpoints and concurrency protections.
### Ports
- Extend focused generator ports with typed generation guidance and correction feedback.
- Supply separately labelled source facts, human decisions and uncertainty to semantic quality assessment.
### Adapters
- Update fake, local, OpenAI and OpenRouter generators; persist checked proposals with legacy compatibility.
- Require nonempty Story/criteria arrays; version evidence-first generation and semantic review prompts.
### API
- Preserve existing generation/job endpoints; add optional quality/architecture to proposal candidates.
### UI
- Show generation stages, immediate assessments and Remaining concerns; explicit legacy/manual reassessment.
### Tests
- Prove bounded refinement, unresolved blockers, preservation/rollback, concurrency, provider boundaries,
  PostgreSQL round trips and the complete browser flow; run all quality gates and record CI status.
- Regress ignored splits, source-aware assessment freshness and separation of failed AI drafts from source evidence.


## Enhancement — Business need attachments as prompt input

**Status:** Implemented and merged into `main`; hosted CI is tracked in the delivery ledger above.
See `docs/slices/enhancement-business-need-attachments.md` and ADR-0042.

### Domain
Permit validated attachment-backed empty descriptions and image-only evidence;
persist explicit review state for failed intended uploads.
### Application
Validate current source readiness across promotion, edits and analysis; support
owned, version-checked draft selection/removal and atomic source transfer.
### Ports
Reuse source-document metadata, storage, extraction and multimodal analysis ports.
### Adapters
Safe UTF-8 Markdown, PNG/JPEG sanitation and bounded PDF page rendering; backward
compatible document JSON and Requirement snapshots.
### API
Opt-in upload inclusion, draft selection/removal and source-aware eligibility;
updated OpenAPI/frontend types.
### UI
Inline multi-file input/drop, default ready inclusion, previews, processing/retry/
exclude/remove controls, readiness gate and serialized draft saves.
### Tests
Adapter/domain/API/UI and browser upload-save-resume-analysis scenarios; run all
required quality gates and record local evidence and CI status.


## Enhancement — Direct Gemini and configured LLM integration

**Status:** Implemented and merged into `main`. Provider-capacity and full live-workflow acceptance remain open. The later post-credit retry recorded an upstream rate limit; the earlier depleted-credit note is historical, not a verified current blocker.
See `docs/slices/enhancement-configured-llm-integration.md` and ADR-0043.

### Domain
Preserve requirements, attachments, citations, approvals and generated content.
### Application
Safe failure classification, configuration-aware evidence caches and resumable isolated search rebuilds.
### Ports
Reuse focused generation ports; add provider-neutral index generations.
### Adapters
Versioned YAML profiles, shared compatible generation/embeddings, direct Google embeddings,
PostgreSQL migration and equivalent in-memory identity/version isolation.
### API
Preserve existing endpoints and job schemas; safe distinct provider failures and correlation IDs.
### UI
Reuse existing job UI; no settings screen or client credentials.
### Tests
Profile/transport contracts, secret handling, legacy/launcher precedence, index resume/current-source
activation/rollback, backend gates, PostgreSQL, frontend contracts/build and browser smoke.
Live text/image/embedding and end-to-end Gemini results are recorded separately.

## Enhancement — Reviewed document ingestion and shared knowledge

**Status: Functional implementation merged into `main`; production qualification remains open.**
Specification: `docs/slices/enhancement-document-knowledge.md`; decision: ADR-0051.
Owner-reviewed reference applicability is documented in
`docs/slices/enhancement-reference-applicability.md` and ADR-0052. The next implemented checkpoint
adds bounded same-section retrieval context while preserving exact citations; see
`docs/slices/enhancement-reference-parent-context.md` and ADR-0053. Overall release qualification remains open.
The preceding checkpoint adds table/wide-row children and owner-scoped corpus generation
build/activation; see `docs/slices/enhancement-table-corpus-builds.md` and ADR-0054.
The PowerPoint extraction-quality checkpoint adds reviewable table rows, neutral structural
context and merge warnings; see `docs/slices/enhancement-presentation-tables.md` and ADR-0055.
The preceding checkpoint applies exclusion-safe row/grid/nested-table extraction to Word documents;
see `docs/slices/enhancement-word-tables.md` and ADR-0056.
Every Domain/Application/Ports/Adapters/API/UI/Tests field below remains in scope for the
overall enhancement; the CSV/TSV checkpoint implements independently reviewable first
records and exclusion-safe positional fields through the existing full library path. See
`docs/slices/enhancement-delimited-rows.md` and ADR-0057.
The preceding XLSX checkpoint adds row-local merge annotations, bounded merge validation and exact
row review/publication; see `docs/slices/enhancement-spreadsheet-merges.md` and ADR-0058.

The merged TXT/Markdown checkpoint removes copied heading wording from descendant metadata;
see `docs/slices/enhancement-text-sections.md` and ADR-0059. Overall release qualification remains open.
The merged Word prose checkpoint removes original wording from paragraph/list labels and heading
paths; see `docs/slices/enhancement-word-prose.md` and ADR-0060.
The merged worksheet-name checkpoint isolates XLSX worksheet names from labels/paths and keeps hidden-sheet
selection explicit; see `docs/slices/enhancement-worksheet-names.md` and ADR-0061.
The chunking/indexing checkpoint adds a dedicated resumable Requirement worker, API/browser retry,
actual embedding-model token qualification and isolated live cross-owner rollout/rollback. See
`docs/slices/enhancement-chunking-indexing.md` and ADR-0062; overall release qualification remains open.

The ownership/dependency checkpoint adds audited owner handover and an access-filtered view of
current and historical Requirement reference proposals, with publication currency and exact
citations. The user selected this scope without delegated reviewers. See
`docs/slices/enhancement-library-governance.md` and ADR-0063. Implemented and merged into `main`.

The Search and AI grounding checkpoint adds member-filtered unified Requirement/document search,
published-reference clarification suggestions with exact durable citations, stale-selection guards,
reference-conflict screening and explicit semantic-judgment evaluation. Existing document-only
search and owner applicability decisions remain compatible. See
`docs/slices/enhancement-search-ai-grounding.md` and ADR-0064; human qualification remains open.
Hosted CI is tracked in the delivery ledger above.

### Domain
Standalone owned documents, immutable uploads/extraction revisions, reviewed selections,
publication approvals, generalized citations, reference applicability decisions and lineage.
### Application
Durable ingestion, extraction review, publication/withdrawal, incremental indexing, source-balanced
retrieval and separately labelled, human-reviewed references in Requirement analysis.
### Ports
Library metadata/queue, malware scanning, format extraction/OCR, token counting, reference indexing,
embedding reuse, retrieval and reference-proposal boundaries.
### Adapters
Memory and PostgreSQL blobs/metadata/jobs/indexes, local ClamAV and Docling/Tesseract,
PDF/DOCX/XLSX/PPTX/CSV/TSV/TXT/Markdown/PNG/JPEG, existing configured embeddings/providers.
### API
Async ingestion/status/retry/cancel; library review/version/approval/withdrawal; chunk previews;
`POST /knowledge/search`; grounded reference proposals and decisions. Preserve old upload APIs.
### UI
Library upload/search, original/extraction review, correction and exclusions, version/approval/index
states, exact citation previews and owner accept/edit/reject, including mixed-direction content.
### Tests
Trust leakage, owner permissions, immutability/concurrency, worker fencing/recovery, format safety,
bilingual chunking/citations, indexing activation, retrieval diversity and grounding, browser tests,
real PostgreSQL/pgvector and migration/restore. Human-labelled evaluation and measured load targets
are separate release evidence, not unit-test assertions.

The document-ingestion completion checkpoint adds private raster source comparison, exact-block
warning resolution, asynchronous Requirement/draft attachment processing and remaining OCR/format
safeguards. See `docs/slices/enhancement-ingestion-completion.md` and ADR-0065. Implemented and merged into `main`;
OCR/scanner/Office-renderer deployment qualification remains open. Hosted CI is tracked above.

The source-lineage completion checkpoint carries exact origins through answers and backlog content,
distinguishes direct citations from indirect inputs, prevents copied corroboration, adds explicit
owner impact reconciliation and replaces history scans with a transactional dependency index.
See `docs/slices/enhancement-source-lineage.md` and ADR-0066 for all six requested outcomes and
actual validation evidence. Parent production qualification remains separate.

---

# Bounded Enhancements and Maintenance Record

Corrective and bounded work on delivered slices, recorded so every specification in
`docs/slices/` is reachable from this roadmap. None starts or partially delivers a future slice.
Each record keeps its own dated validation history; the ledger at the top governs merge status.

| Record | Scope | Status |
|---|---|---|
| `docs/slices/enhancement-requirements-dashboard.md` | Requirements list for Slices 1 and 4A; retired the "No list endpoint" debt | Merged into `main` |
| `docs/slices/provider-local-llm-adapter.md` | Local LLM adapter for Slices 2–4 | Merged into `main` |
| `docs/slices/analysis-clarification-loop.md` | Explicit completion state for the clarification loop | Merged into `main` |
| `docs/slices/enhancement-local-debug-trace.md` | Local single-file debug trace | Merged into `main` |
| `docs/slices/enhancement-local-structured-analysis-recovery.md` | Recovery of malformed local structured analysis | Merged into `main`; full live retry incomplete (release gate above) |
| `docs/slices/enhancement-openrouter-gemma-provider.md` | OpenRouter provider; now the Docker demo's default | Merged into `main`; live calls opt-in and outside CI |
| `docs/slices/fix-analysis-source-presentation.md` | Quieter citations in the clarification workspace | Merged into `main` |
| `docs/slices/fix-focused-breakdown-workspace.md` | Focused Epic → Feature → Story workspace | Merged into `main` |
| `docs/slices/fix-workspace-request-loading.md` | Scoped workspace requests and shared AI jobs | Merged into `main` |
| `docs/slices/fix-human-answer-analysis-citations.md` | Human-answer citations during question resolution | Merged into `main`; #65 added the no-evidence case, and #67 merged the salvage commit `0d42039` (all in `smb-ai-requirement-agent`, before the snapshot) |
| `docs/slices/enhancement-review-remediation*.md` | Four whole-workspace review remediations | Merged into `main`; human review open (ledger above) |
