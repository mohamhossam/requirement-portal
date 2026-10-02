# UX Plan — Requirement AI

**Status:** source of truth for the UI/UX redesign, per the UI Redesign Rules in [`CLAUDE.md`](../CLAUDE.md). Produced by reading the shipped frontend. No code was changed to produce it.

**Companion:** [`docs/design-system.md`](design-system.md) governs mechanics (contrast, z-index, table construction). [`DESIGN.md`](../DESIGN.md) currently records the *shipped* identity — see §0; it becomes an output of this redesign rather than an input.

---

## 0. Scope decisions

Four decisions were taken before this plan was written. They are recorded here because most of what follows depends on them.

| Decision | Choice | Consequence |
|---|---|---|
| **Identity** | Full reset, including palette, typeface and tone | `DESIGN.md` is no longer an input. Bureau Oxblood `#af101a`, Archivo Narrow and the cool-paper canvas are all open. `DESIGN.md` gets rewritten from the finished redesign. `docs/design-system.md` §2 (generator-vs-shipped reconciliation) is void and needs re-deciding. |
| **Accessibility** | **WCAG 2.2 AA** | Adds target size (2.5.8), focus not obscured (2.4.11), consistent help (3.2.6), redundant entry (3.3.7) and dragging alternatives (2.5.7) on top of 2.1 AA. `PRODUCT.md` records this as undecided and should be updated. |
| **Role model** | One or two people wear several hats | **No role-scoped navigation.** A single, complete IA that every role sees, with the existing per-Requirement owner/reviewer permissions as the only gate. Do not build role-based dashboards or role-filtered menus. |
| **Priority driver** | Daily speed for the BA and Product Owner | Worklist → Clarify → Review/Approve come first. The business owner's intake screen and the portfolio screens come later. |

Users are already documented in [`PRODUCT.md`](../PRODUCT.md) §Users and are not restated here: business owner (non-agile), business analyst / RE lead, Product Owner, solution architect / tech lead.

---

## 1. Screens and routes

Eighteen route entries resolve to nine distinct screens. Routes are declared in [`App.tsx`](../frontend/src/app/App.tsx).

### Global screens

| Route | Component | Whose screen | The user's goal here |
|---|---|---|---|
| `/` and `*` | `DashboardPage` | BA, PO (daily) | **"What needs me today, and where do I resume?"** Scan the worklist, read the attention strip, filter to a saved view, jump straight into a requirement at its current stage. |
| `/requirements/new` | `NewRequirementPage` | Business owner | **"Get my business need into the system without learning the method."** Type or attach the need, see what still blocks analysis, save and kick off analysis in one action. The draft autosaves and is resumable. |
| `/documents` | `DocumentsPage` | BA, architect | **"What evidence does this project hold?"** Browse the immutable source-document catalogue and see what is included in analysis. |
| `/documents/:documentId` | `DocumentDetailPage` | BA, architect | **"Is this file trustworthy, and should the AI see it?"** Inspect versions, checksums, extraction warnings and evidence blocks; toggle inclusion; include hidden worksheets; upload a new version. |
| `/activity` | `ActivityPage` | All, audit | **"Who did what, when, and against which evidence?"** Filter the audit projection by category, requirement, actor and date. |
| `/reports` | `ReportsPage` | PO, lead | **"Is the portfolio moving, and what is stuck?"** Weekly throughput over 4/12/26 weeks, clarification resolution rate, oldest blockers. |
| *(gate, not a route)* | `LoginPage` via `AuthGate` | All | **"Get in."** SSO, or the dev persona switcher. |

### Requirement workspace

`/requirements/:id` (`RequirementEntryRedirect`) resolves the requirement's current stage via [`stagePath.ts`](../frontend/src/app/stagePath.ts) and redirects. All stage routes render one shell, `RequirementWorkspaceShell` in [`RequirementPage.tsx`](../frontend/src/app/RequirementPage.tsx).

| Route | View | Whose screen | The user's goal here |
|---|---|---|---|
| `…/capture` | `CaptureView` | Business owner, BA | **"Is this requirement ready to analyse, and if not, what is missing?"** See eligibility, manage attachments, edit the source. |
| `…/clarify` | `AnalysisView` | BA + business owner | **"Close the gaps the analysis found."** Read findings by tone, answer blocking and non-blocking questions, accept grounded suggestions, reclassify and assign questions, decide AI intent proposals, trigger re-analysis. **The highest-value screen in the product.** |
| `…/knowledge` | `KnowledgeView` | BA | **"Has this been asked before, and does it contradict anything we know?"** Review duplicate and contradiction findings; mark distinct, close as duplicate, or propose/accept a resolution. |
| `…/confirm` | `AnalysisView` (same component) | Requirement Owner | **"Sign off that the analysis is right before anything is generated from it."** Read the facts/rules/constraints summary, then confirm. |
| `…/breakdown`, `…/breakdown/epic`, `…/breakdown/features/:featureId`, `…/breakdown/features/:featureId/stories/:storyId` | `BreakdownView` → `BreakdownWorkspace` | PO, BA | **"Read and shape the generated backlog."** Navigate Epic → Feature → Story, edit, approve each level, regenerate, map architecture, check INVEST quality. |
| `…/review` | `BreakdownReviewPanel` | PO + architect | **"Is this backlog safe to approve?"** Resolve review flags, read dependencies/risks/recommendations and story-quality evidence, record decisions, submit for review, grant final approval, comment. |
| `…/revisions` | `RevisionsView` | PO, audit | **"What changed, and give me the approved export."** Compare immutable revisions; download an approved revision as JSON or XLSX. |

**Note the mismatch:** the journey model in [`journey.ts`](../frontend/src/app/requirement/journey.ts) declares **five** steps (Capture, Analyse, Knowledge, Confirm, Breakdown). `/review` and `/revisions` are real screens that the progress model does not contain. See §3.2.

---

## 2. Core flows

### Flow A — Triage: pick up the day's work
*BA / PO, several times a day. The most frequent flow in the product.*

1. Land on `/`. Header, sidebar and page title render; the worklist query and three others fire.
2. Read **Needs attention** — a collapsible strip, one line per item, highest-priority first.
3. Or scan the worklist: four columns — Requirement, Owner, Progress, Next action.
4. Optionally narrow: search, owner select, "Assigned to me", status chips (only statuses with a non-zero count are shown), sort, or apply a saved view.
5. Click a row. The whole row is one link to `stagePath(item)` — the requirement's **current stage**, not an overview.
6. Land inside the requirement workspace at that stage.

### Flow B — Intake: raw need to analysis running
*Business owner, once per requirement.*

1. `/requirements/new`. A single form; guidance and the worked example sit behind a `<details>`.
2. Type title and business need; optionally attach PDF/DOCX/XLSX/TXT via `DocumentPanel`.
3. The draft autosaves after 700 ms idle. A four-state indicator reads Saving / Saved HH:MM / Changes not saved / Draft save failed.
4. An eligibility card updates live: **Ready for analysis**, or **Missing: title, business need text or a ready attachment…**
5. Submit **Save and analyse business need** — the draft is persisted, promoted to a Requirement, and an `analyse_requirement` job starts, then redirect to `/clarify`.
   - Or **Save draft and exit**, back to `/`, resumable from the dashboard's "Resume …" link.
   - If the job fails to start, the page shows "Nothing was lost" with **Open saved requirement** and **Retry analysis**.

### Flow C — The clarification loop
*BA driving, business owner answering. Multi-session; the deep work.*

1. `/clarify`. The AI job panel reports progress if analysis is still running.
2. Findings render grouped by tone; **Needs confirmation** holds the questions, with a progress bar.
3. Per question: request grounded **answer suggestions**; accept one or type an answer; save as a draft; optionally reclassify severity and "Blocks confirmation", and assign an owner. New questions can be added by hand.
4. **Resolve** a batch of answers, or **re-analyse** with them — a new round supersedes the old, and a reconciliation line reports *retained / retired / revised / new*.
5. Navigate to `/knowledge`. Screening is auto-started by the shell for team members. Decide each finding: distinct, duplicate, or propose/accept a resolution.
6. Navigate to `/confirm` — **the same `AnalysisView` component**, plus a facts/rules/constraints summary.
7. Confirm. Gated on: Requirement Owner, knowledge review ready, no unresolved blockers. On success, auto-navigate to `/breakdown/epic`.

### Flow D — Backlog generation and approval
*PO with architect input. The second-most-frequent flow.*

1. `/breakdown/epic`. Generate the Epic from the confirmed analysis; edit; approve.
2. **Decompose into Features**; navigate the backlog tree (Epic → Feature → Story) in the left navigator, or via **Continue reviewing**, which jumps to the first unapproved or stale item.
3. Per Feature: edit, approve, optionally **Map architecture** (behind a disclosure).
4. Per Story: read Given/When/Then, edit, propose a manual change, check INVEST quality findings.
5. Go to `/review`. Generate or refresh the breakdown review.
6. Resolve flags (blocking / warning), each linking back to its source; answer open questions inline, which triggers re-analysis; record freeform decisions.
7. **Submit for review**, which locks the current fingerprint. Then per-story approve/reject with a reason. Then **Final approval**.
8. Any upstream edit marks downstream artifacts **stale**, not deleted; a global flag appears at the bottom of the shell.

### Flow E — Traceability and export
*PO / audit, at the end and on demand.*

1. `/revisions`, reached from the source rail's "View revisions" or the Breakdown header's **History**.
2. Pick two revisions, compare, read the diff.
3. Download an approved revision as JSON or XLSX. Gated on `canExportApprovedRevisions`.
4. Cross-check in `/activity`, filtered to that requirement — or arrive there from a `/reports` metric link.

---

## 3. Current UX pain points

Each is verified against the code, with the file to look at.

### 3.1 Three navigation systems disagree about what the product contains

[`AppHeader.tsx`](../frontend/src/components/AppHeader.tsx) renders all three:

- **Header `global-nav`** — 3 links: Requirements, Activity, Reports. **Source documents is missing.**
- **`app-sidebar`** — 4 links: All requirements, Source documents, Activity, Reports. **Rendered only on `variant="default"`**, so it vanishes on the Breakdown route.
- **Breakdown `<details>` "Menu"** — 5 links, duplicating the header nav and adding New requirement and Source documents.

Four destinations, three lists, no two the same. A person who learns the product on the dashboard loses half the navigation when they reach the backlog.

### 3.2 Two real screens are invisible to the progress model

The journey has five steps. `/review` and `/revisions` are not among them. They are reachable only from buttons in the Breakdown page header (**Review breakdown**, **History**) and a text link in the source rail.

Worse, [`stagePath.ts`](../frontend/src/app/stagePath.ts) routes requirements whose stage is `features` or `stories` to `/review`. So clicking a worklist row can land you on a screen the stepper says does not exist, while the stepper highlights **Breakdown**. This is a modelling inconsistency, not just a visual one — see §6.

### 3.3 Breakdown is a different application

Different shell class (`breakdown-shell`), different header variant, no sidebar, no full stepper (a `compact` variant lives in the page header instead), the source rail and people panel become drawers, plus its own backlog tree and its own breadcrumbs. Moving from Confirm to Breakdown is a product change, not a page change. ADR-0045 records this as deliberate; the redesign should supersede it.

### 3.4 Every stage route is titled four times over

On `/clarify` a user reads, top to bottom: `Requirement · a1b2c3d4` (header context) → `Requirement workspace / <title>` (eyebrow) → **Clarification Required** (`h1`) → `Analyse / Clarify / Confirm` (panel eyebrow) → **Structured understanding** (`h2`). Five labels before the first question. The requirement's own title — the thing a person with four tabs open is looking for — appears only inside an eyebrow, subordinate to the stage name.

### 3.5 Clarify and Confirm are one component split by Knowledge

`AnalysisView` serves both `/clarify` and `/confirm`; the only difference is a summary block. Between them in the journey sits Knowledge. So the sequence is: one screen, a different screen, then the same first screen again with a box added. Nobody would design this on purpose.

### 3.6 The review screen is thirteen stacked sections, governance first

[`BreakdownReviewPanel`](../frontend/src/features/review/BreakdownReviewPanel.tsx) mounts `ApprovalWorkflowPanel` **at the top**, so the order is: approval stepper → completion counts → blocking reasons → Submit/Final approval buttons → story approve/reject → approval history → comments → *then* the review heading, staleness notice, counts, filters, flags, dependencies, risks, recommendations, story quality, decision log.

**The approve buttons render above the evidence you would approve on.**

### 3.7 Raw enum strings are shown as UI copy

`.replaceAll("_", " ")` appears in at least six places: approval stages ("under review", "needs revision"), artifact status, backlog item status, `analysis_readiness`, workflow status, and the review filter buttons — which render the literal lowercase strings `all` / `blocking` / `warning` / `resolved`. This directly violates `PRODUCT.md` Principle 3 ("a business owner should never need the method") and its brand-voice commitment.

### 3.8 Activity filters ask for UUIDs by hand

[`ActivityPage.tsx`](../frontend/src/app/ActivityPage.tsx) offers **Requirement ID** and **Actor ID** as free-text inputs with the placeholders "Any requirement" and "Any actor". Nobody can type a UUID from memory. Category is a proper select; Action has no control at all — it is only settable from a `/reports` deep link.

### 3.9 The token layer is bypassed, and three dead visual generations remain

- **365 hardcoded hex values** across the stylesheets outside `tokens.css`, spanning 40+ distinct colours.
- Three abandoned generations are still live: `#201e1d` warm near-black (44 uses), `#ec3013` orange-red (18), `#81e4d0` teal (3), plus a dead teal focus ring `rgba(17,123,114,.08)` at `01-foundation.css:131`.
- **216 selectors are declared in more than one file**, and `index.css` states in its own comment that import order is load-bearing and must not be regrouped.
- `.app-header` is defined twice — `01-foundation.css` (4.7rem, sticky, backdrop-blur) and `08-stitch-foundation.css`. `docs/design-system.md` documents it as 64px, so the docs have already drifted from the code.

This is the single largest tax on every other item in this plan.

### 3.10 The login page is a fourth visual generation

`login-story` uses a dark navy-to-teal gradient (`#0e1d36 → #132d4a → #0f4f55`) with a teal radial glow, and `login-choice` has 0.82rem radii and transform transitions. Nothing else in the product looks remotely like it.

### 3.11 Accessibility: strong bones, specific 2.2 gaps

Credit where due — `base.css` sets a global 3px `:focus-visible` outline, there is a skip link, there is one `prefers-reduced-motion` block, and `WorklistTable` / `JourneyStepper` carry unusually careful accessible-name work. Verified gaps:

| Criterion | Finding |
|---|---|
| **2.5.8 Target size (2.2 AA)** | `.text-button` has no minimum size — it is an underlined inline button used standalone for Cancel, Retry, Mark read, Clear all, Enable browser alerts. At the `.72rem`/`.75rem` sizes it appears in, it is well under 24×24 px. `.button` (41.6 px) and `.icon-button` (32 px) pass. |
| **1.4.11 Non-text contrast** | `--line #d4dbe2` is **1.40:1** on white and **1.32:1** on canvas. Where it is the only thing identifying an input or a control boundary, it fails the 3:1 requirement. |
| **1.4.3 Contrast** | The palette is otherwise healthy — `--ink-muted` 6.46:1, `--accent` 7.21:1, `--ink-blocked` 5.19:1. The one at risk is `--warning-bright #d97706` at **3.19:1**: it passes as a border but must never carry text. |
| **2.4.11 Focus not obscured (2.2 AA)** | The sticky header (`z-index: 10`, `backdrop-filter`) and the sticky `.source-rail-inner` (`top: 152px`) can cover a focused element during keyboard traversal. Not yet verified in-browser; treat as a must-test. |
| **3.2.6 Consistent help (2.2 AA)** | No consistent help affordance exists. Intake guidance lives in a `<details>`; nothing equivalent exists on any other screen. |
| **Dark mode** | Not implemented at all. No `prefers-color-scheme` anywhere in the stylesheets. |

### 3.12 Smaller, and real

- **Dead state.** `localStorage.lastRequirementId` is written in two places and read nowhere in `src/`. The product captures "where you left off" and never offers to take you back.
- **No bulk action.** The worklist row is a single link, so a triaging BA cannot multi-select, batch-assign, or sort by clicking a column header — only a sort dropdown exists.
- **Reports are three tables.** No visualization, for data that is explicitly a weekly time series.
- **Intake guidance is hidden from the person who needs it most.** The worked example sits behind a closed `<details>`, and the non-agile business owner is the one user who cannot be assumed to know to open it.
- **The duplicate banner is buried.** On a requirement closed as a duplicate, the banner renders *below* the AI job panel and the page heading.

---

## 4. Proposed information architecture

Two levels. That is the whole model.

```
Workspace  (global — identical on every route, including Backlog)
├── Requirements        /                     ← home
├── Documents           /documents
├── Activity            /activity
└── Reports             /reports

Requirement  (local — one requirement's own space, persistent stage rail)
│
├── Journey  (sequential, each step carries a status)
│   1. Source            …/capture
│   2. Clarify           …/clarify        ← Analyse + Clarify + Confirm, one step
│   3. Knowledge         …/knowledge
│   4. Confirm           …/confirm
│   5. Backlog           …/breakdown/*    Epic → Feature → Story
│   6. Review & approve  …/review         ← promoted from orphan to step 6
│
└── Always available  (panels, not steps — same affordance on every stage)
    ├── Source document   (today: a rail on 6 routes, a drawer on 1)
    ├── People            (today: a <details> on 6 routes, a drawer on 1)
    └── History           …/revisions
```

### What this changes

**One navigation, everywhere.** A single persistent left sidebar carrying all four global destinations, collapsible to icons, present on *every* route including Backlog. It replaces the header `global-nav`, the `app-sidebar`, and the breakdown `<details>` menu. The header keeps only: brand, global search, notifications, account, primary action.

**Six journey steps, not five.** Review & approve becomes step 6 instead of a button in a page header. This is the single highest-leverage IA change: it makes the PO's screen a first-class destination and removes the §3.2 inconsistency.

**One frame for all stages.** Backlog stops being a separate application. Same shell, same stage rail, same Source and People affordances. Its internal Epic → Feature → Story tree stays — that is legitimate depth *within* a step, not a second navigation system.

**Panels, not stage-dependent shapeshifting.** Source, People and History behave identically on every stage. Today each has two different implementations depending on which route you are on.

**Requirement identity comes first.** The `h1` is the requirement's title. The stage is named by the rail, which already shows where you are. This deletes three of the five labels in §3.4.

**Business language at the boundary.** One label map, in the presentation layer, for every enum the API returns. No `.replaceAll("_", " ")` reaching a user.

### Deliberately not proposed

- **No role-based navigation, dashboards or menus** — per the §0 role decision.
- **No mobile-first layout.** `PRODUCT.md`: "Desktop is the real usage scene." Narrow widths must not break; no flow is designed for a phone.
- **No new top-level destination.** Four is right. Anything new earns its place inside one of them.

### ADRs this supersedes

The redesign contradicts accepted decisions. These need superseding ADRs, not silent breakage:

| ADR | Why |
|---|---|
| `adr-0045-focused-breakdown-workspace` | Backlog stops being a separate shell (§3.3). |
| `adr-0047-persistent-journey-stepper` | The stepper becomes a persistent rail with six steps, not a top bar with five. |
| `adr-0050-header-navigation-row` | The header navigation row is removed in favour of one sidebar. |
| `adr-0049-three-breakpoints` | Revisit only if the new layout needs it — otherwise keep. |
| `adr-0048-tailwind-utilities-in-a-named-layer` | Keep. The layer discipline survives the identity reset. |

---

## 5. Prioritized redesign order

Ordered for **daily speed for the BA and Product Owner**. Every phase ends with `cd frontend && npm run build` green, per `CLAUDE.md`.

### Phase 0 — Foundation *(blocks everything; ships no screen)*

Because the identity is being fully reset, doing this second would mean redesigning every screen twice.

1. **New identity and token set.** `tokens.css` becomes the only source of colour, type and space. Every one of the 365 hardcoded hex values is either tokenised or deleted with its dead generation.
2. **Collapse the 15 stylesheets.** Resolve the 216 duplicate selectors so import order stops being load-bearing.
3. **The shell:** one sidebar, one header, one requirement frame with its stage rail.
4. **Primitives:** button, field, badge, card, table, panel, drawer, modal, empty state, skeleton, toast — each built to 2.2 AA at the primitive, so no screen has to remember.
5. **Fix the §3.11 gaps at the token and primitive level:** `.text-button` to a 24 px minimum target, a `--line` value clearing 3:1 where it identifies a control, `--warning-bright` restricted to non-text use.
6. **Login page** — cheap once tokens exist, and currently a whole generation adrift.

### Phase 1 — Worklist and shell `/`

The screen the BA and PO open every morning, and the proof the new shell works. Column-header sorting, multi-select and bulk action, the "resume where you left off" affordance the dead `lastRequirementId` was already collecting, and the attention strip reworked as the primary entry point.

### Phase 2 — Clarify `/clarify` + `/confirm`

The highest-value screen in the product and the deepest daily work. Merge Clarify and Confirm into one coherent step (§3.5), put the question list first, make the suggestion → answer → resolve → re-analyse loop fast, and make the reconciliation summary legible.

### Phase 3 — Review and approve `/review`

The PO's screen, and the worst-structured one. Invert §3.6 so evidence precedes approval; turn thirteen stacked sections into a structured screen; promote it to journey step 6; replace the raw enum copy.

### Phase 4 — Backlog `/breakdown/*`

Fold it into the shared frame (§3.3). Keep the Epic → Feature → Story tree; drop the second header, the second nav, and the drawer-only Source and People.

### Phase 5 — Knowledge `/knowledge` and Source `/capture`

Lower frequency, and both get most of their improvement free from the Phase 0 shell.

### Phase 6 — Intake `/requirements/new`

The business owner's screen. Later only because of the §0 priority choice — it is the product's first impression for one of its four users, so it should not slip further than this. Bring the worked example out of the closed `<details>` for the person who most needs it.

### Phase 7 — Documents `/documents`, `/documents/:id`

Catalogue and detail. Detail is dense and information-rich, and mostly needs the new primitives rather than a rethink.

### Phase 8 — Activity and Reports

Replace the UUID text inputs with real pickers (§3.8), expose the Action filter, and give the weekly time series a visualization alongside the table.

### Phase 9 — History `/revisions`

Lowest frequency, highest tolerance for density. Comparison and export.

---

## 6. Open decisions — needs a product answer, not a design call

1. **`stagePath` sends `features` and `stories` to `/review`.** Should a requirement mid-decomposition open on the Review screen, or on the Backlog? This changes behaviour, so it is not a redesign call. Flagged from §3.2.
2. **URL changes.** This plan keeps every existing URL. If Review becoming step 6 should also change its path, that is a separate, explicit decision — links are shared between people over days.
3. **`PRODUCT.md` accessibility section** — *closed.* It records WCAG 2.2 AA as settled and binding, per §0.
4. **`DESIGN.md` and `docs/design-system.md` §2** — *closed at the end of Phase 0.* `DESIGN.md` was rewritten from the shipped code ("The Working Paper"), with its `.impeccable/design.json` sidecar. `docs/design-system.md` §2 records what the generator proposed and what was taken, not the retired identity, so it stands.
5. **Dark mode** — *closed.* Specified in `docs/design-system.md` §4.3 before the token structure was fixed, and shipped in Phase 0: the Paper and Slate themes in `tokens.css`, `prefers-color-scheme` with an explicit-choice override, and a blocking script in `index.html` so the wrong theme never flashes.
