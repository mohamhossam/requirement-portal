# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Four confirmed roles work in the same application, at different points of one requirement's life. **How many people those roles map to varies by organization** — in a small one, one or two people wear several hats; in a larger one the roles are separate. The product must serve both shapes without assuming either:

- **Business owner (non-agile).** Owns the raw business need and has no SAFe training. Writes or attaches the requirement, answers clarification questions in business language, and confirms the analysis. The original decomposition prompt was written for exactly this person, and the product exists so they never have to learn the method to get a usable result.
- **Business analyst / RE lead.** Owns requirement quality. Drives the answer → re-analysis loop, judges known facts, constraints, assumptions, ambiguities and open questions, and decides what is clean enough to go downstream.
- **Product Owner.** Consumes and approves the generated Epic → Feature → Story backlog, checks acceptance criteria and INVEST quality, and owns the export that loads into the backlog tool.
- **Solution architect / tech lead.** Reviews impacted systems, dependencies, risks and architecture findings against the organization's landscape before approval.

The application already models this as explicit per-Requirement access: exactly one **owner** and any number of **reviewers** (`AssignmentRole` in `src/smb_requirement_agent/identity/domain/entities.py`), with ownership transfer and an audited access history. The roles above are jobs people do, not a second permission system.

Because role concentration varies, **one complete information architecture serves every role**. There is no role-scoped navigation, no role-filtered menu and no role-based dashboard; per-Requirement owner/reviewer access is the only gate. That single IA is the safe superset for both org shapes (`docs/ux-plan.md` §0).

## Product Purpose

Turn a raw business requirement into a reviewable, traceable delivery backlog — Requirement → Analysis → Epic → Features → User Stories → Acceptance Criteria → Quality/Architecture Review → Human Approval → Export — while keeping uncertainty explicit and human approval strictly separate from AI generation.

Success is that an organization's analysts and Product Owners stop hand-writing decomposition, and that what comes out the far end loads into the backlog without rework.

## Positioning

Two commitments a neighboring "AI writes your user stories" tool could not truthfully copy:

1. **Uncertainty is a first-class artifact, not a caveat.** The product surfaces known facts, constraints, business rules, assumptions, open questions, ambiguities, dependencies and risks as reviewable items, and runs an iterative answer → re-analysis loop that ends only when a human explicitly confirms the analysis. Blocking questions actually block.
2. **Generated content is never business truth.** AI output is always a review candidate. Approval is content-bound, revisions are immutable and comparable, regeneration preserves human edits, downstream artifacts are flagged stale rather than silently overwritten, and nothing reaches an external backlog except an explicitly approved revision.

## Operating Context

- **Value stream work, not ticket writing.** The method is SAFe-aligned: Epic (portfolio, multiple PIs) → Feature (one customer-recognizable capability, fits one PI) → User Story (one sprint, passes INVEST), with SPIDR and named splitting patterns applied when something is too big.
- **Requirements arrive as raw material.** A typed business need, or attached source documents (including BRDs) that are versioned immutably, extracted, screened for knowledge, and cited back into the analysis.
- **Reviewing is a multi-session, multi-person activity.** Work is picked up from a worklist with saved views and an attention strip, resumed across days, handed between owner and reviewers, and audited — there is an activity feed and reporting over it.
- **Architecture knowledge is part of the judgement.** Features and stories are tagged with the likely owning system(s)/squad(s) so cross-system work gets split and the right squads get looped in early. The reference landscape is a Telecom SMB value stream (`docs/source/SMB_AI_Story_Breakdown_Prompt_Template_requirement_1.md`): digital channels, CRM systems, order fulfilment/COM, the Netcracker transformation platform, middleware, and shared enabling services.
- **Daily speed for the BA and the Product Owner drives priority.** Worklist → Clarify → Review/Approve is the path walked many times a day and is the one that has to be fast. The business owner's intake screen and the portfolio screens are used less often and come after it (`docs/ux-plan.md` §0).
- **The far end is an external backlog tool.** Azure DevOps publication is a later roadmap slice; today the workflow ends in deterministic JSON and Excel export of an exactly approved revision.
- **Desktop is the real usage scene.** This work happens at a desk on a wide screen. Narrow layouts must not break, but no flow is designed for a phone.

## Capabilities and Constraints

**Confirmed capabilities.** Requirement capture and editing; analysis of known facts, constraints, business rules, assumptions, open questions, ambiguities and dependencies; an iterative human answer → re-analysis loop ending in explicit Requirement Owner confirmation; knowledge screening and grounded suggestions; Epic generation, editing, regeneration and approval; decomposition into Features approved independently; User Stories with Given/When/Then acceptance criteria and quality findings; quality, architecture, dependency, risk and final-approval reviews; provenance, ownership, review status and downstream staleness; immutable revision history with in-browser comparison; source documents with immutable versions and attachments; durable, leased, resumable AI jobs with notifications; a worklist with saved views, an activity feed and reports; deterministic JSON and Excel export of an approved revision.

**The journey has five steps, one route each:** Capture → Analyse → Knowledge → Confirm → Breakdown (`frontend/src/app/requirement/journey.ts`). Analyse and Clarify are one screen. Blocked steps stay navigable; each destination explains itself.

**Durable constraints.**

- AI generation never auto-publishes. External publication is allowed only from an explicitly approved revision, and human approval is a separate act from generation.
- Assumptions, open questions, dependencies and quality findings must be visible before approval.
- Regeneration must not silently destroy human edits or approved history; changed upstream content flags downstream artifacts as stale rather than deleting them.
- Explicit uncertainty over invented requirements — never fabricate a fact to fill a gap, in the product or in work about the product.
- Clean Architecture dependency direction is enforced by import-linter; AI and external systems stay behind ports. Delivery is vertical-slice, and a slice's UI has the same standing as its API.
- Runtime baseline: Python 3.12 / FastAPI backend, PostgreSQL (or in-memory/fake mode), React 19 + Vite + Tailwind 4 review UI, Keycloak-brokered login with a fake-actor persona switcher in development. Deterministic offline operation through the fake LLM adapter is a supported first-class mode, as is a private local OpenAI-compatible model server.
- One information architecture serves every role. Role-scoped navigation, role-filtered menus and role-based dashboards are excluded by decision, not by omission.
- Three breakpoints, a single modal primitive, a persistent journey stepper, and Tailwind utilities confined to a named layer are accepted architecture decisions (ADRs 0045–0050), not preferences to relitigate casually.

**Settled scope.**

- **One organization.** The product is being built for a single organization; multi-org tenancy is out of scope for the foreseeable roadmap. The Telecom SMB value stream is therefore the working architecture reference, not the first entry in a configurable set, and no tenancy, per-org configuration or vocabulary-generalization work is planned. This is a scope decision, not an architectural prohibition: nothing should be hardwired in a way that would make per-org configurable knowledge expensive to add later, but no surface should be designed around a landscape the organization can manage today.
- **Accessibility standard: WCAG 2.2 AA.** Settled and binding. See below.

**Open product decisions.**

- The active production-readiness remediation is implemented for review but unverified and undeployed; migrations `013`–`015` have documented operating procedures that precede any deployment claim.

## Brand Commitments

- **Product name: Requirement AI.** This is the binding name. It is used in the in-app brand lockup and appended to every route title by `frontend/src/app/useDocumentTitle.ts`. "SMB AI Requirement Breakdown Agent" is the repository description. The retired name "SMB Requirement Review" no longer appears anywhere in the product; the static shell title in `frontend/index.html` was aligned in redesign Phase 0.
- No logo, wordmark, palette, typographic or identity assets have been committed. Nothing about the current appearance is a brand commitment.
- Voice: business language, not agile jargon, wherever a business owner reads it. The product's own writing should be able to explain a blocking question to someone who has never heard of INVEST.

## Evidence on Hand

Real, in-repository:

- The original business decomposition reference — hierarchy, splitting rules, INVEST/SPIDR, guardrails, and the Telecom SMB architecture map — at `docs/source/SMB_AI_Story_Breakdown_Prompt_Template_requirement_1.md`.
- Fifty accepted architecture decision records in `docs/architecture/`, the slice sequence in `ROADMAP.md`, the engineering constitution in `AGENTS.md`, and slice specs in `docs/slices/`.
- The redesign's governing documents, both produced by reading the shipped frontend rather than by changing it: `docs/ux-plan.md` (scope decisions, screens, routes, information architecture and flows) and `docs/design-system.md` (mechanics — contrast, z-index, table construction). Per `CLAUDE.md`, `docs/ux-plan.md` is the source of truth for the redesign; where the two disagree, the plan wins.
- A running application with deterministic offline operation, so real flows can be demonstrated without credentials or network access.

Deliberately absent — future work must not fabricate these: no customers, no logos, no testimonials, no case studies, no adoption or accuracy metrics, no pricing, no licensing, no press, no deployment claims, and no photography or illustration assets.

## Product Principles

1. **Uncertainty stays visible.** The unknown parts of a requirement are the product's most valuable output. Never let a surface bury an open question, an assumption, or a blocking item to look finished.
2. **The human decides; the AI drafts.** Generation and approval are different acts by different means, and the interface must never blur which one just happened.
3. **A business owner should never need the method.** Agile vocabulary is the product's internal machinery, not an entry requirement. If a surface only makes sense to someone SAFe-trained, it has failed one of its four users.
4. **Nothing human is silently lost.** Edits, answers, approvals and history survive regeneration, staleness and change; the product flags rather than overwrites.
5. **Traceable end to end.** Every downstream artifact can be walked back to the requirement, the revision, the source citation and the person who approved it.

## Accessibility & Inclusion

**WCAG 2.2 AA.** Settled, and binding on all frontend work. It is the bar recorded in `CLAUDE.md`'s UI Redesign Rules and in `docs/ux-plan.md` §0. Five success criteria sit on top of 2.1 AA, and this product's surfaces touch all of them:

- **2.5.8 Target size (Minimum)** — 24×24px, enforced in the primitives. The old `.text-button` failure (Cancel, Retry, Mark read, Clear all and Enable browser alerts at 0.72–0.75rem) was fixed in redesign Phase 0: every inline action is the `text` variant of `Button`, with a 24×24 floor.
- **2.4.11 Focus not obscured (Minimum)** — a focused element must not be hidden behind the fixed 56px header, the 240px sidebar, or a sticky panel. Verified at the end of Phase 0 by tabbing every stop from the skip link on the worklist, login and a requirement's clarify, backlog and review routes at 1440px and 900px.
- **3.2.6 Consistent help** — help affordances keep the same relative order across pages.
- **3.3.7 Redundant entry** — information already supplied earlier in the journey is not asked for a second time.
- **2.5.7 Dragging movements** — any drag interaction has a single-pointer alternative.

`docs/design-system.md` once proposed WCAG 2.1 AA; it now records that proposal as superseded (§0) and states 2.2 AA throughout (§13).

Beyond the standard, ordinary craft holds regardless: full keyboard operability, visible focus, readable contrast, correct semantics, and respect for `prefers-reduced-motion`.
